"""Incremental patient intake and immutable, time-scoped recommendation series."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from uuid import uuid4

from .clinical import FIELD_SPECS
from .intake import validate_extraction
from .prompts import PROMPT_VERSION
from .workspace import configured_model

SERIES_ID = re.compile(r"^SER-[a-f0-9]{32}$")
EXTRACTION_SLOTS = threading.BoundedSemaphore(3)
PATIENT_SLOTS = threading.BoundedSemaphore(2)
STABLE_FIELDS = {"sex", "allergies", "comorbidities", "bleeding_history", "history"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def save(path, value):
    tmp = path.with_suffix("." + uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def stage_heading(text):
    """Only explicit section markers establish time; no dates are fabricated."""
    s = text.strip().strip("：:")
    s = re.sub(r"^(?:日期|时间|Date|Time)\s*[:：]\s*", "", s, flags=re.I)
    relative = re.fullmatch(r"(?:术后|治疗后|随访|after|follow.up)\s*(\d+)\s*(周|星期|月|个月|天|weeks?|months?|days?)\s*[:：]?", s, re.I)
    if relative:
        number, unit = relative.groups()
        unit = "week" if unit in {"周", "星期"} or unit.lower().startswith("week") else "month" if "月" in unit or unit.lower().startswith("month") else "day"
        anchor = "postoperative" if s.startswith("术后") else "follow-up"
        return f"{anchor}-{number}-{unit}", f"{number} {unit}{'s' if int(number)!=1 else ''} {anchor}", "relative"
    if re.match(r"^(?:出院带药|出院用药|出院(?:$|\s|[:：])|discharge\b)", s, re.I):
        return "discharge", "Discharge", "relative"
    if re.match(r"^(?:入院后?|住院初期|住院|admission|inpatient)(?:$|[:：])", s, re.I):
        return "admission", "Admission", "relative"
    date = re.fullmatch(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?(?:[\s:：]+(.*))?", s)
    if date:
        tail = (date.group(4) or "").strip()
        if tail and not re.match(r"^(?:情况|复诊|随访|入院|出院|开药|诊疗|visit\b|follow.up\b|assessment\b|admission\b|discharge\b)", tail, re.I):
            return None  # A dated test result is not automatically a new clinical visit.
        try:
            label = datetime(*map(int, date.groups()[:3])).date().isoformat()
            return label, label, "date"
        except ValueError:
            pass
    return None


def plan_sources(store, source_ids, source_defaults=None):
    """Keep original paragraph/image association and merge repeated visit headings."""
    nodes, by_key = [], {}
    def node_for(key, label, precision):
        if key not in by_key:
            by_key[key] = {"id": "N-" + digest(key)[:12], "key": key, "label": label,
                           "time_precision": precision, "chunks": []}
            nodes.append(by_key[key])
        elif by_key[key]["time_precision"] == "unknown" and precision != "unknown":
            by_key[key].update(label=label, time_precision=precision)
        return by_key[key]
    for source_id in source_ids:
        source = store.get(source_id)
        current = node_for(*(source_defaults or {}).get(source_id, ("admission", "Initial assessment", "unknown")))
        buffer, images, locations = [], [], []
        def flush():
            nonlocal buffer, images, locations
            text = "\n".join(buffer).strip()
            if text or images:
                content = {"node": current["key"], "text": text, "images": list(dict.fromkeys(images))}
                chunk_id = "CH-" + digest(content)[:24]
                if not any(c["id"] == chunk_id for c in current["chunks"]):
                    raw = json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
                    scoped = store._save("Case section", raw, "text/plain", text, content["images"])
                    current["chunks"].append({"id": chunk_id, "source_id": scoped["id"], "original_source": source_id,
                                              "text": text, "images": content["images"], "locations": list(locations), "status": "pending"})
            buffer, images, locations = [], [], []
        for block in store.ordered_blocks(source_id):
            heading = stage_heading(block["text"])
            if heading:
                flush()
                current = node_for(*heading)
            # Long paragraphs split on sentence boundaries, never in the middle of a number/unit.
            pieces = re.split(r"(?<=[。；\n])", block["text"]) if len(block["text"]) > 3000 else [block["text"]]
            # Hard limit also covers long unpunctuated OCR output.
            pieces = [p[start:start+3000] for p in pieces for start in range(0, max(1, len(p)), 3000)]
            for piece in pieces:
                if buffer and sum(map(len, buffer)) + len(piece) > 3000:
                    flush()
                if piece.strip():
                    buffer.append(piece)
                    locations.append(block["location"])
            for image_id in block["images"]:
                if len(images) >= 2:
                    flush()
                images.append(image_id)
                locations.append(block["location"])
        flush()
    nodes = [n for n in nodes if n["chunks"]]
    if not nodes:
        raise ValueError("No readable text or images were found")
    # A free-text preamble (demographics/history) is context for the first dated
    # visit, not a separate encounter. Explicit Admission headings stay separate.
    if len(nodes) > 1 and nodes[0]["key"] == "admission" and nodes[0]["time_precision"] == "unknown" and nodes[1]["time_precision"] == "date":
        nodes[1]["chunks"] = nodes[0]["chunks"] + nodes[1]["chunks"]
        nodes.pop(0)
    # File sequence is retained for mixed/relative dates. Explicit dates alone can be sorted.
    dated = [n for n in nodes if n["time_precision"] == "date"]
    if dated and len(dated) == len(nodes):
        nodes.sort(key=lambda n: n["key"])
    if sum(len(n["chunks"]) for n in nodes) > 160:
        raise ValueError("This patient exceeds 160 extraction blocks; split the upload")
    return nodes


class SeriesJob:
    def __init__(self, path):
        self.path, self.cond, self.done = path, threading.Condition(), False
        self.events = load(path / "events.json", [])

    def push(self, event):
        with self.cond:
            self.events.append({**event, "seq": len(self.events) + 1})
            save(self.path / "events.json", self.events)
            self.cond.notify_all()

    def close(self):
        with self.cond:
            self.done = True
            self.cond.notify_all()


class LongitudinalServices:
    def series_path(self, series_id):
        if not isinstance(series_id, str) or not SERIES_ID.fullmatch(series_id):
            raise ValueError("Invalid patient timeline ID")
        path = self.runs / "series" / series_id
        if not (path / "series.json").is_file():
            raise LookupError("Patient timeline not found")
        return path

    def series_detail(self, series_id):
        item = load(self.series_path(series_id) / "series.json")
        job = self.series_jobs.get(series_id)
        if item["status"] in {"queued", "extracting", "reviewing"} and (not job or job.done):
            item["status"] = "interrupted"
        return item

    def list_series(self):
        root = self.runs / "series"
        records = [self.series_detail(p.parent.name) for p in root.glob("SER-*/series.json")]
        return sorted([{k: v for k, v in item.items() if k not in {"nodes", "config"}}
                       for item in records if self.allow_debug or item.get("purpose") != "software_test"],
                      key=lambda x: x["created_at"], reverse=True)

    def start_series(self, body):
        ids = body.get("source_ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 12:
            raise ValueError("Select 1–12 sources for a single patient")
        sources = [self.sources.get(i) for i in ids]
        parent = self.series_detail(body["parent_id"]) if body.get("parent_id") else None
        if parent and parent["status"] in {"queued", "extracting", "reviewing"}:
            raise ValueError("Wait for this patient's current timeline to finish")
        if not parent and sum("wordprocessingml" in s["mime"] for s in sources) > 1:
            raise ValueError("Start one patient timeline per Word file; add follow-up files to an existing patient")
        combined = list(dict.fromkeys((parent["source_ids"] if parent else []) + ids))
        if len(combined) > 12:
            raise ValueError("At most 12 source documents per patient timeline")
        defaults = dict(parent.get("source_defaults", {})) if parent else {}
        if parent:
            for source_id in ids:
                if source_id not in parent["source_ids"]:
                    defaults[source_id] = ("followup-" + source_id, "New follow-up (date not supplied)", "unknown")
        nodes = plan_sources(self.sources, combined, defaults)
        series_id = "SER-" + uuid4().hex
        path = self.runs / "series" / series_id
        path.mkdir(parents=True)
        item = {"id": series_id, "patient_id": parent["patient_id"] if parent else "P-" + uuid4().hex[:12],
                "label": parent.get("label", parent["patient_id"]) if parent else Path(sources[0]["name"]).stem[:120],
                "parent_id": parent["id"] if parent else None, "source_ids": combined, "source_defaults": defaults, "status": "queued",
                "created_at": datetime.now(timezone.utc).isoformat(), "completed_nodes": 0,
                "node_count": len(nodes), "nodes": nodes, "prompt_version": PROMPT_VERSION}
        save(path / "series.json", item)
        self._launch_series(item, body)
        return series_id

    def retry_series(self, series_id, body):
        with self.lock:
            job = self.series_jobs.get(series_id)
            if job and not job.done:
                raise ValueError("This timeline is already running")
            item = self.series_detail(series_id)
            if item["status"] == "complete":
                raise ValueError("This timeline is complete; add a follow-up to create a new version")
            self._launch_series(item, body)
        return series_id

    def _launch_series(self, item, body):
        path = self.series_path(item["id"])
        job = SeriesJob(path)
        self.series_jobs[item["id"]] = job
        # Credentials remain only in the worker's memory, never in series.json or cache keys.
        threading.Thread(target=self._execute_series, args=(job, item, deepcopy(body)), daemon=True,
                         name="timeline-" + item["id"]).start()

    def _execute_series(self, job, item, body):
        def emit(event, **data):
            save(job.path / "series.json", item)
            job.push({"event": event, **data})
        async def work():
            item["status"] = "extracting"
            item.pop("error", None)
            emit("started", patient_id=item["patient_id"], nodes=len(item["nodes"]))
            # Instantiate briefly to validate provider options, then close on its own event loop.
            model, config = configured_model(body.get("llm") or {})
            await model.close()
            item["config"] = config
            evidence = load(job.path / "evidence.json")
            if evidence is None:
                knowledge_ids = [d["id"] for d in self.knowledge.list_documents() if not d["synthetic"]]
                if not knowledge_ids:
                    raise ValueError("The knowledge base is empty. Add guideline documents, then retry.")
                evidence = self.knowledge.snapshot(knowledge_ids)
                save(job.path / "evidence.json", evidence)
            fingerprint = digest({"config": config, "prompt": PROMPT_VERSION})
            cache = self.runs / "extraction_cache"
            cache.mkdir(exist_ok=True)
            async def extract(chunk, node):
                key = digest({"chunk": chunk["id"], "time_label": node["label"], "config": fingerprint})
                cached = load(cache / (key + ".json"))
                if cached:
                    chunk.update(status="complete", output=cached["output"], cache_hit=True)
                    emit("chunk_completed", chunk_id=chunk["id"], node_id=node["id"], cached=True)
                    return
                chunk["status"] = "reading"
                emit("chunk_started", chunk_id=chunk["id"], node_id=node["id"])
                def call():
                    with EXTRACTION_SLOTS:
                        async def once():
                            m, _ = configured_model(body.get("llm") or {})
                            try:
                                src = self.sources.get(chunk["source_id"])
                                payload = {"timeline_intake": True, "time_label": node["label"],
                                           "sources": [{k: src[k] for k in ("id", "name", "text", "images")}],
                                           "image_ids": chunk["images"],
                                           "field_specs": [{"key": f[0], "label": f[1]} for f in FIELD_SPECS]}
                                reply = await asyncio.wait_for(m.extract(payload, [self.sources.image(i) for i in chunk["images"]]), 120)
                                raw = {"raw_output": reply.data, "model": reply.model, "usage": reply.usage}
                                try:
                                    raw["output"] = validate_extraction(reply.data, {chunk["source_id"], *chunk["images"]})
                                except ValueError:
                                    save(job.path / (chunk["id"] + "-invalid.json"), raw)
                                    raise
                                save(cache / (key + ".json"), raw)
                                return raw["output"]
                            finally:
                                await m.close()
                        return asyncio.run(once())
                try:
                    output = await asyncio.to_thread(call)
                    chunk.update(status="complete", output=output, cache_hit=False)
                    chunk.pop("error", None)
                    emit("chunk_completed", chunk_id=chunk["id"], node_id=node["id"], cached=False,
                         observations=len(output["observations"]))
                except Exception as exc:
                    chunk.update(status="failed", error="Extraction timed out" if isinstance(exc, TimeoutError) else type(exc).__name__)
                    emit("chunk_failed", chunk_id=chunk["id"], node_id=node["id"], error=chunk["error"])
            tasks = {c["id"]: asyncio.create_task(extract(c, n)) for n in item["nodes"] for c in n["chunks"]}
            parent = self.series_detail(item["parent_id"]) if item.get("parent_id") else None
            prior, previous = [], None
            item["completed_nodes"] = 0
            try:
                for node in item["nodes"]:
                    await asyncio.gather(*(tasks[c["id"]] for c in node["chunks"]))
                    if any(c["status"] != "complete" for c in node["chunks"]):
                        node["status"] = "failed"
                        raise ValueError("Some blocks could not be extracted. Retry resumes completed work.")
                    events = [{"time_label": node["label"], "source_id": c["source_id"],
                               "text": c["text"], "observations": c["output"]["observations"],
                               "status": "model_extracted", "issues": c["output"]["issues"]} for c in node["chunks"]]
                    current = [o for e in events for o in e["observations"]]
                    stable = {o["key"]: o for e in prior for o in e["observations"] if o["key"] in STABLE_FIELDS}
                    old_stable = [o for key, o in stable.items() if key not in {v["key"] for v in current}]
                    allowed_sources = list(dict.fromkeys(e["source_id"] for e in prior + events))
                    if len(allowed_sources) > 120:
                        raise ValueError("Timeline source limit exceeded")
                    case = {"case_id": item["patient_id"] + "-" + node["id"],
                            "question": "Review the documented treatment at this time and recommend VTE management, medication choices, doses, monitoring and changes from the previous visit.",
                            "facts": {"decision_stage": node["label"]}, "missing_information": [], "input_mode": "automatic",
                            "source_ids": allowed_sources, "source_context": {i: {"available_at": "", "reviewer": ""} for i in allowed_sources},
                            "observations": (old_stable + current),
                            "longitudinal": {"patient_id": item["patient_id"], "node_id": node["id"], "time_label": node["label"],
                                             "time_precision": node["time_precision"], "prior_events": prior,
                                             "new_information": events, "previous_recommendation": previous}}
                    signature = digest({"case": case, "model": fingerprint, "settings": body.get("settings", {}), "evidence": evidence,
                                        "retrieval": self.vectors.status()["method"]})
                    candidates = [node] + (parent["nodes"] if parent else [])
                    reusable = next((n for n in candidates if n.get("input_hash") == signature and n.get("status") in {"complete", "review_required"} and n.get("run_id")), None)
                    item["status"] = "reviewing"
                    if reusable:
                        node.update(run_id=reusable["run_id"], input_hash=signature, status=reusable["status"], reused=True)
                        result = self.detail(node["run_id"])["result"]
                    else:
                        node["status"] = "reviewing"
                        emit("node_started", node_id=node["id"], label=node["label"])
                        run = await asyncio.to_thread(self.start, {"mode": "llm", "evidence": evidence, "case": case, "llm": body.get("llm", {}),
                                          "settings": body.get("settings", {}), "retrieval": "frozen"})
                        node.update(run_id=run, input_hash=signature)
                        emit("node_run", node_id=node["id"], run_id=run)
                        cursor = 0
                        while not self.jobs[run].done:
                            for event in self.jobs[run].events[cursor:]:
                                if event["event"] in {"call_started", "call_completed", "review_round", "draft_revised"}:
                                    job.push({"event": "agent_progress", "node_id": node["id"], **{k: v for k, v in event.items() if k in {"role", "task", "version"}}})
                            cursor = len(self.jobs[run].events)
                            await asyncio.sleep(.15)
                        result = self.detail(run)["result"]
                        if result and result.get("recommendation"):
                            node["recommendation"] = result["recommendation"]
                            node["review_status"] = result["status"]
                            node["draft_unreviewed"] = result["status"] == "failed"
                        if not result or result["status"] == "failed":
                            node["status"] = "failed"
                            raise ValueError("A recommendation failed. Retry resumes this node.")
                        if not result.get("recommendation"):
                            node["status"] = "failed"
                            raise ValueError("No recommendation was produced. Check the node report for evidence or source issues, then retry.")
                        node["status"] = "complete" if result.get("review_complete") else "review_required"
                    node["recommendation"] = result.get("recommendation")
                    node["draft_unreviewed"] = False
                    node["review_status"] = result["status"]
                    node["new_information"] = events
                    previous = {"time_label": node["label"], "run_id": node["run_id"], "status": result["status"],
                                "recommendation": result.get("recommendation"), "kind": "model_suggestion"}
                    prior += events
                    item["completed_nodes"] += 1
                    emit("node_completed", node_id=node["id"], run_id=node["run_id"], label=node["label"])
                item["status"] = "complete"
                emit("completed")
            finally:
                # Keep successfully read later blocks even if an earlier clinical node failed.
                await asyncio.gather(*tasks.values(), return_exceptions=True)
        try:
            with PATIENT_SLOTS:
                asyncio.run(work())
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            emit("failed", error=item["error"])
        finally:
            save(job.path / "series.json", item)
            job.close()
