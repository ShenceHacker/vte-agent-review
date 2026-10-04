"""Patient/source workspace services, separate from clinical model context."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from .clinical import FIELD_SPECS, clinical_check
from .contracts import validate_case
from .intake import validate_extraction
from .patient_memory import instant
from .providers import ChatCompletionsModel
from .information import information_table, validate_responses


def configured_model(llm: dict, timeout: float = 120):
    if not isinstance(llm, dict) or not isinstance(llm.get("role_models", {}), dict):
        raise ValueError("Model configuration and role models must be objects")
    key = str(llm.get("api_key") or os.environ.get("VTE_API_KEY", "")).strip()
    name = str(llm.get("model") or os.environ.get("VTE_MODEL", "")).strip()
    base = str(llm.get("base_url") or os.environ.get("VTE_BASE_URL") or "https://api.openai.com/v1").strip()
    roles = {r: os.environ[f"VTE_MODEL_{r}"] for r in "ABCD" if os.environ.get(f"VTE_MODEL_{r}")}
    roles.update({r: v.strip() for r, v in llm.get("role_models", {}).items() if r in "ABCD" and isinstance(v, str) and v.strip()})
    style = llm.get("api_style") or os.environ.get("VTE_API_STYLE", "chat_completions")
    effort = llm.get("reasoning_effort") or os.environ.get("VTE_REASONING_EFFORT") or None
    max_tokens = llm.get("max_output_tokens", int(os.environ.get("VTE_MAX_OUTPUT_TOKENS", "3000")))
    model = ChatCompletionsModel(base, key, name, role_models=roles, timeout=timeout, api_style=style,
                                reasoning_effort=effort, max_tokens=max_tokens)
    return model, {"base_url": base, "model": name, "role_models": roles, "api_style": style,
                   "reasoning_effort": effort, "max_output_tokens": max_tokens, "responses_streaming": style == "responses"}


def validate_labels(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Research labels must be an array of at most 100 records")
    for item in value:
        if not isinstance(item, dict) or set(item) != {"kind", "content", "source", "recorded_by", "occurred_at"}:
            raise ValueError("Labels require kind, content, source, recorded_by and occurred_at")
        if item["kind"] not in {"physician_plan", "expert_audit", "outcome"}:
            raise ValueError("Unknown label type")
        for key in ("content", "source", "recorded_by"):
            if not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 16000:
                raise ValueError("Label " + key + " is required (max 16000 characters)")
        instant(item["occurred_at"])
    return value


class WorkspaceServices:
    def information_followup(self, run_id, body=None):
        """Append confirmations without rewriting the original case/model result."""
        path = self.run_dir(run_id)
        case = json.loads((path / "case.json").read_text(encoding="utf-8"))
        file = path / "information_responses.json"
        with self.lock:
            history = json.loads(file.read_text(encoding="utf-8")) if file.exists() else []
            if body is not None:
                rows = validate_responses(body.get("responses"))
                # Verify finite JSON before saving any part of a batch.
                json.dumps(rows, allow_nan=False)
                saved_at = datetime.now(timezone.utc).isoformat()
                history += [{"id": "INFO-" + uuid4().hex, "saved_at": saved_at, "responses": rows}]
                file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        latest = {r["field"]: r for r in case.get("information_responses", [])}
        for batch in history:
            latest.update({r["field"]: r for r in batch["responses"]})
        case["information_responses"] = list(latest.values())
        case = validate_case(case)
        return {"case": case, "table": information_table(case), "history": history,
                "original_report_unchanged": True, "parent_run_id": run_id}

    def check_case(self, body):
        case = validate_case(body.get("case"))
        checks = clinical_check(case)
        return {**checks, "information_table": information_table(case, checks)}

    def memory_for(self, case):
        p = case.get("patient")
        if not p:
            return {"entries": []}
        return self.memory.snapshot(p["patient_id"], p["decision_at"],
                                    task_type=case.get("task_type", "generate_plan"), encounter_id=p["encounter_id"])

    def extract_sources(self, body):
        bundle = self.sources.bundle(body.get("source_ids"))
        # Extraction is intake only. It does not perform clinical reasoning or auto-confirm data.
        payload = {"sources": [{k: s[k] for k in ("id", "name", "text", "images")} for s in bundle["sources"]],
                   "image_ids": bundle["image_ids"], "field_specs": [{"key": f[0], "label": f[1]} for f in FIELD_SPECS]}
        images = [self.sources.image(i) for i in bundle["image_ids"]]
        model, config = configured_model(body.get("llm") or {})
        async def extract():
            try:
                return await asyncio.wait_for(model.extract(payload, images), 120)
            finally:
                await model.close()
        reply = asyncio.run(extract())
        output = validate_extraction(reply.data, {s["id"] for s in bundle["sources"]} | set(bundle["image_ids"]))
        item = {"id": "INT-" + uuid4().hex, "source_ids": body["source_ids"], "output": output,
                "created_at": datetime.now(timezone.utc).isoformat(), "model": reply.model,
                "usage": reply.usage, "config": config}
        folder = self.runs / "intakes"
        folder.mkdir(exist_ok=True)
        (folder / (item["id"] + ".json")).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        return item

    def add_labels(self, run_id, body):
        values = validate_labels(body.get("labels"))
        path = self.run_dir(run_id) / "research_labels.json"
        with self.lock:
            previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            entries = [{**v, "id": "LBL-" + uuid4().hex, "saved_at": datetime.now(timezone.utc).isoformat()} for v in values]
            path.write_text(json.dumps(previous + entries, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"labels": entries, "included_in_model_input": False}
