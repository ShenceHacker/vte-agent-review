"""Local desktop-style UI: stdlib HTTP server, live SSE progress, physician sign-off.

Security posture: binds to loopback by default, rejects foreign Host headers (DNS
rebinding) and non-JSON POSTs (cross-site form posts). API keys stay in memory only.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from . import __version__
from .cli import report
from .contracts import ROLE_NAMES, ROLES, ContractError, validate_case
from .demo import DEMO_CASE, DEMO_EVIDENCE, DemoModel
from .prompts import PROMPT_VERSION
from .retrieval import EvidenceIndex
from .knowledge import KnowledgeStore, SQLiteEvidenceIndex, MAX_TEXT
from .workflow import Settings, Workflow
from .patient_memory import PatientMemory
from .intake import SourceStore
from .workspace import WorkspaceServices, configured_model, validate_labels
from .providers import ProviderError
from .example_case import CLINICAL_EXAMPLE
from .clinical import FIELD_SPECS
from .information import ABSENT_VALUES, ZH_LABELS

WEB = Path(__file__).with_name("web")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
STATIC = re.compile(r"^[A-Za-z0-9_-]+\.(?:html|css|js|svg|png|ico)$")
MAX_BODY = 9 * 1024 * 1024
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
DECISIONS = {"accept", "accept_with_changes", "reject"}
SCENARIOS = {
    "targeted": {"title": "Targeted revision", "desc": "A raises an issue; D revises A; only A reviews again.", "expect": "approved"},
    "dependency": {"title": "Dependency propagation", "desc": "B depends on A; changes to A trigger a new review by B.", "expect": "approved"},
    "shared": {"title": "Shared plan change", "desc": "The shared plan changes; A, B and C review again.", "expect": "approved"},
    "limit": {"title": "Revision limit", "desc": "Unresolved issues reach the revision limit.", "expect": "needs_human_review"},
    "missing": {"title": "Missing information", "desc": "A requests missing patient information.", "expect": "needs_human_review"},
    "stagnant": {"title": "No-change revision", "desc": "D makes no changes; the workflow stops for human review.", "expect": "needs_human_review"},
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def strip_inputs(events: list[dict]) -> list[dict]:
    """Model inputs are large and already summarised elsewhere; keep the UI payload small."""
    return [{k: v for k, v in e.items() if k != "input"} for e in events]


class PacedDemoModel:
    """Deterministic demo with human-visible, role-dependent latency for the live view."""
    is_demo = True
    PACE = {"A": 1.0, "B": 1.35, "C": 0.8, "D": 1.5}

    def __init__(self, scenario: str, pace: float):
        self.inner = DemoModel(scenario, delay=0)
        self.pace = pace

    async def complete(self, task, role, payload):
        await asyncio.sleep(self.pace * self.PACE.get(role, 1.0))
        return await self.inner.complete(task, role, payload)


class Job:
    def __init__(self, run_id: str):
        self.id = run_id
        self.events: list[dict] = []
        self.cond = threading.Condition()
        self.done = False

    def push(self, event: dict) -> None:
        with self.cond:
            self.events.append(event)
            self.cond.notify_all()

    def close(self) -> None:
        with self.cond:
            self.done = True
            self.cond.notify_all()


class App(WorkspaceServices):
    def __init__(self, runs_dir: Path):
        self.runs = Path(runs_dir).resolve()
        self.runs.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.knowledge = KnowledgeStore(self.runs / "knowledge.sqlite3")
        self.memory = PatientMemory(self.runs / "patients.sqlite3")
        self.sources = SourceStore(self.runs / "sources")

    # ---------- queries ----------
    def info(self) -> dict:
        try:
            import httpx  # noqa: F401
            has_httpx = True
        except ImportError:
            has_httpx = False
        return {
            "version": __version__, "prompt_version": PROMPT_VERSION, "runs_dir": str(self.runs),
            "knowledge": self.knowledge.stats(),
            "capabilities": ["patient_memory", "source_images", "docx_intake", "tool_calling", "clinical_checks", "research_labels", "conditional_recommendations", "information_followup"],
            "information_fields": [{"field": k, "label": label, "label_zh": ZH_LABELS[k], "roles": list(roles),
                                    "priority": "decision_dependent" if critical else "optional", "allow_absent": k in ABSENT_VALUES}
                                   for k, label, roles, critical in FIELD_SPECS],
            "roles": ROLE_NAMES, "httpx": has_httpx,
            "defaults": asdict(Settings(call_timeout=float(os.environ.get("VTE_CALL_TIMEOUT", "60")))), "scenarios": SCENARIOS,
            "env": {
                "base_url": os.environ.get("VTE_BASE_URL", ""),
                "model": os.environ.get("VTE_MODEL", ""),
                "api_style": os.environ.get("VTE_API_STYLE", "chat_completions"),
                "reasoning_effort": os.environ.get("VTE_REASONING_EFFORT") or None,
                "max_output_tokens": int(os.environ.get("VTE_MAX_OUTPUT_TOKENS", "3000")),
                "api_key_set": bool(os.environ.get("VTE_API_KEY")),
                "role_models": {r: os.environ.get(f"VTE_MODEL_{r}", "") for r in (*ROLES, "D")},
            },
        }

    def run_dir(self, run_id: str) -> Path:
        if not RUN_ID.match(run_id or ""):
            raise LookupError(run_id)
        path = self.runs / run_id
        if not path.is_dir():
            raise LookupError(run_id)
        return path

    @staticmethod
    def created_at(path: Path, meta: dict) -> str:
        if meta.get("created_at"):
            return meta["created_at"]
        try:
            stamp = datetime.strptime(path.name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        return stamp.astimezone().isoformat(timespec="seconds")

    def summary(self, path: Path) -> dict | None:
        case = read_json(path / "case.json")
        if not isinstance(case, dict):
            return None
        meta = read_json(path / "meta.json", {}) or {}
        result = read_json(path / "result.json")
        error = read_json(path / "error.json")
        signoffs = read_json(path / "physician_reviews.json", []) or []
        job = self.jobs.get(path.name)
        if job and not job.done:
            status = "running"
        elif isinstance(result, dict):
            status = result.get("status", "failed")
        elif error:
            status = "failed"
        else:
            status = "interrupted"
        result = result if isinstance(result, dict) else {}
        return {
            "id": path.name, "created_at": self.created_at(path, meta),
            "case_id": case.get("case_id"), "question": case.get("question"),
            "status": status, "reason": result.get("reason") or (error or {}).get("error"),
            "mode": result.get("mode") or meta.get("mode"), "scenario": meta.get("scenario"),
            "model": meta.get("model"), "version": result.get("version"), "revisions": result.get("revisions"),
            "metrics": result.get("metrics"), "signoff": signoffs[-1] if signoffs else None,
            "source": meta.get("source", "cli"),
        }

    def list_runs(self) -> list[dict]:
        items = [s for p in self.runs.iterdir() if p.is_dir() and RUN_ID.match(p.name) and (s := self.summary(p))]
        return sorted(items, key=lambda s: s["created_at"], reverse=True)

    def detail(self, run_id: str) -> dict:
        path = self.run_dir(run_id)
        summary = self.summary(path)
        if summary is None:
            raise LookupError(run_id)
        result = read_json(path / "result.json")
        if isinstance(result, dict):
            result["events"] = strip_inputs(result.get("events", []))
            events = result["events"]
        else:
            result = None
            events = []
            if summary["status"] != "running":
                try:
                    lines = (path / "events.jsonl").read_text(encoding="utf-8").splitlines()
                    events = strip_inputs([json.loads(x) for x in lines if x.strip()])
                except (OSError, ValueError):
                    pass
        return {**summary, "case": read_json(path / "case.json"), "meta": read_json(path / "meta.json", {}),
                "result": result, "events": events,
                "signoffs": read_json(path / "physician_reviews.json", []) or [],
                "research_labels": read_json(path / "research_labels.json", []) or [],
                "memory_updates": read_json(path / "memory_updates.json", []) or [],
                "information_followup": self.information_followup(run_id),
                "has_report": (path / "report.md").exists()}

    def validate(self, body: dict) -> dict:
        out = {}
        if "case" in body:
            try:
                validate_case(body["case"])
                out["case"] = {"ok": True}
            except ContractError as exc:
                out["case"] = {"ok": False, "error": str(exc)}
        if "evidence" in body:
            try:
                docs = list(EvidenceIndex(body["evidence"]).documents.values())
                out["evidence"] = {"ok": True, "count": len(docs), "synthetic": sum(d["synthetic"] for d in docs),
                                   "roles": {r: sum(r in d["roles"] for d in docs) for r in ROLES}}
            except ContractError as exc:
                out["evidence"] = {"ok": False, "error": str(exc)}
        return out

    # ---------- commands ----------
    def start(self, body: dict) -> str:
        parent_run_id = body.get("parent_run_id")
        if parent_run_id:
            self.run_dir(parent_run_id)
        labels = validate_labels(body.get("research_labels", []))
        mode = body.get("mode", "demo")
        raw = body.get("settings") or {}
        if not isinstance(raw, dict):
            raise ValueError("Settings must be a JSON object")
        defaults = Settings(call_timeout=float(os.environ.get("VTE_CALL_TIMEOUT", "60")))
        for key, value in raw.items():
            if key in ("max_revisions", "concurrency", "timeout", "top_k"):
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Setting {key} requires a valid number") from None
                if isinstance(value, bool) or not math.isfinite(number) or (key != "timeout" and not number.is_integer()):
                    raise ValueError(f"Setting {key} requires a finite valid number")
        settings = Settings(int(raw.get("max_revisions", defaults.max_revisions)),
                            int(raw.get("concurrency", defaults.max_concurrency)),
                            float(raw.get("timeout", defaults.call_timeout)),
                            int(raw.get("top_k", defaults.top_k)))
        meta = {"source": "gui", "mode": mode, "created_at": now_iso(), "app_version": __version__}
        knowledge_ids = body.get("knowledge_ids")
        frozen = self.knowledge.snapshot(knowledge_ids) if knowledge_ids is not None else None
        if parent_run_id and frozen is None:
            parent = self.run_dir(parent_run_id)
            original_evidence = read_json(parent / "evidence.json")
            if (body.get("evidence") == original_evidence and original_evidence is not None
                    and read_json(parent / "meta.json", {}).get("retrieval") == "SQLite FTS5 / BM25"):
                frozen = original_evidence
        if frozen is not None:
            body = {**body, "evidence": frozen}
            meta.update(knowledge_ids=knowledge_ids, retrieval="SQLite FTS5 / BM25", evidence_snapshot=True)
        if mode == "demo":
            scenario = body.get("scenario", "targeted")
            if scenario not in SCENARIOS:
                raise ValueError("Unknown demo scenario")
            case = validate_case(body.get("case") or DEMO_CASE)
            index = EvidenceIndex(body.get("evidence") or DEMO_EVIDENCE)
            pace = float(body.get("pace", 0.8))
            if not math.isfinite(pace):
                raise ValueError("Demo delay must be finite")
            model = PacedDemoModel(scenario, min(max(pace, 0.0), 3.0))
            meta["scenario"] = scenario
        elif mode == "llm":
            case = validate_case(body.get("case"))
            if not body.get("evidence"):
                raise ValueError("Model mode requires evidence")
            index = EvidenceIndex(body["evidence"])
            if any(d["synthetic"] for d in index.documents.values()):
                raise ValueError("Model mode does not accept synthetic evidence")
            llm = body.get("llm") or {}
            if not isinstance(llm, dict) or not isinstance(llm.get("role_models", {}), dict):
                raise ValueError("Model configuration and role models must be JSON objects")
            key = str(llm.get("api_key") or os.environ.get("VTE_API_KEY", "")).strip()
            name = str(llm.get("model") or os.environ.get("VTE_MODEL", "")).strip()
            base = str(llm.get("base_url") or os.environ.get("VTE_BASE_URL") or "https://api.openai.com/v1").strip()
            if not key or not name:
                raise ValueError("Enter a model and API key, or set VTE_MODEL and VTE_API_KEY")
            role_models = {r: os.environ[f"VTE_MODEL_{r}"] for r in (*ROLES, "D") if os.environ.get(f"VTE_MODEL_{r}")}
            role_models.update({r: v.strip() for r, v in (llm.get("role_models") or {}).items()
                                if r in (*ROLES, "D") and isinstance(v, str) and v.strip()})
            try:
                from .providers import ChatCompletionsModel
                api_style = llm.get("api_style") or os.environ.get("VTE_API_STYLE", "chat_completions")
                effort = llm.get("reasoning_effort") or os.environ.get("VTE_REASONING_EFFORT") or None
                max_tokens = llm.get("max_output_tokens", int(os.environ.get("VTE_MAX_OUTPUT_TOKENS", "3000")))
                model = ChatCompletionsModel(base, key, name, role_models=role_models, timeout=settings.call_timeout,
                                            api_style=api_style, reasoning_effort=effort, max_tokens=max_tokens)
            except ModuleNotFoundError:
                raise ValueError('Missing HTTP adapter. Run: python -m pip install -e ".[llm]"') from None
            meta.update(base_url=base, model=name, role_models=role_models, api_style=api_style,
                        reasoning_effort=effort, max_output_tokens=max_tokens,
                        responses_streaming=api_style == "responses")  # never the key
        else:
            raise ValueError("Unknown mode")

        if frozen is not None:
            index = SQLiteEvidenceIndex(frozen)

        if parent_run_id:
            meta["parent_run_id"] = parent_run_id
        memory_snapshot = self.memory_for(case)
        if case.get("source_ids"):
            self.sources.bundle(case["source_ids"])
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        out = self.runs / run_id
        out.mkdir(parents=True, exist_ok=False)
        write_json(out / "case.json", case)
        write_json(out / "meta.json", meta)
        write_json(out / "evidence.json", list(index.documents.values()))
        write_json(out / "memory_snapshot.json", memory_snapshot)
        write_json(out / "research_labels.json", labels)
        job = Job(run_id)
        with self.lock:
            self.jobs[run_id] = job
        threading.Thread(target=self._execute, args=(job, out, case, index, model, settings),
                         name=f"run-{run_id}", daemon=True).start()
        return run_id

    def _execute(self, job: Job, out: Path, case: dict, index: EvidenceIndex, model, settings: Settings) -> None:
        async def main():
            try:
                with (out / "events.jsonl").open("w", encoding="utf-8") as stream:
                    def on_event(event):
                        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                        stream.flush()
                        job.push(event)
                    result = await Workflow(model, index, settings, on_event,
                                            memory_snapshot=read_json(out / "memory_snapshot.json", {"entries": []}), sources=self.sources).run(case)
                updates = []
                if case.get("patient"):
                    p = case["patient"]
                    for proposal in result.get("memory_proposals", []):
                        updates.append(self.memory.add(p["patient_id"], {
                            "kind": "model_suggestion", "topic": proposal["topic"], "content": proposal["content"],
                            "occurred_at": p["decision_at"], "available_at": p["decision_at"],
                            "source": "run:" + job.id + " / " + ", ".join(proposal["source_ids"]),
                            "roles": proposal["roles"], "encounter_id": p["encounter_id"]}, actor="Agent D", model=True))
                write_json(out / "memory_updates.json", updates)
                write_json(out / "result.json", result)
                (out / "report.md").write_text(report(result), encoding="utf-8")
            finally:
                close = getattr(model, "close", None)
                if close:
                    await close()
                close_index = getattr(index, "close", None)
                if close_index:
                    close_index()

        try:
            asyncio.run(main())
        except Exception as exc:  # keep the server alive; never persist raw third-party messages
            write_json(out / "error.json", {"error": type(exc).__name__, "at": now_iso()})
            job.push({"seq": len(job.events) + 1, "event": "finished", "status": "failed", "reason": type(exc).__name__})
        finally:
            job.close()

    def signoff(self, run_id: str, body: dict) -> dict:
        path = self.run_dir(run_id)
        result = read_json(path / "result.json")
        if not isinstance(result, dict) or not result.get("draft"):
            raise ValueError("This run has no draft to review")
        decision = body.get("decision")
        if decision not in DECISIONS:
            raise ValueError("Select a review decision")
        reviewer = str(body.get("reviewer", "")).strip()[:60]
        comment = str(body.get("comment", "")).strip()[:4000]
        if not reviewer:
            raise ValueError("Enter a reviewer name")
        if decision != "accept" and not comment:
            raise ValueError("Add a note when accepting with changes or rejecting")
        canonical = json.dumps(result["draft"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        entry = {
            "reviewer": reviewer, "decision": decision, "comment": comment, "signed_at": now_iso(),
            "draft_version": result.get("version"), "workflow_status": result.get("status"),
            "draft_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }
        with self.lock:
            history = read_json(path / "physician_reviews.json", []) or []
            history.append(entry)
            write_json(path / "physician_reviews.json", history)
        return entry

    @staticmethod
    def extract_file(body: dict) -> dict:
        filename = str(body.get("filename", ""))
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Upload a PDF, or paste text from a TXT or Markdown document")
        try:
            raw = base64.b64decode(body.get("content_base64", ""), validate=True)
        except (binascii.Error, ValueError, TypeError):
            raise ValueError("Invalid file encoding") from None
        if not raw or len(raw) > 5 * 1024 * 1024:
            raise ValueError("PDF must be smaller than 5 MB")
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError('PDF support is not installed. Run: python -m pip install -e ".[pdf]"') from None
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise ValueError("Use a PDF without password protection")
            if len(reader.pages) > 300:
                raise ValueError("Split PDFs longer than 300 pages before importing")
            pieces = []
            size = 0
            for page in reader.pages:
                value = page.extract_text() or ""
                size += len(value)
                if size > MAX_TEXT:
                    raise ValueError("Extracted text is too long; split the document")
                pieces.append(value)
            extracted = "\n\n".join(pieces).strip()
            if not extracted:
                raise ValueError("No extractable text. Use an OCR-processed PDF or paste the source text")
            return {"text": extracted, "pages": len(reader.pages), "filename": filename}
        except ValueError:
            raise
        except Exception:
            raise ValueError("Unable to read this PDF. Try a text-based PDF or paste the source text") from None


class Handler(BaseHTTPRequestHandler):
    server_version = "VTEReview/" + __version__
    protocol_version = "HTTP/1.1"

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt, *args):  # keep the console readable; no request bodies are logged
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    # ---------- helpers ----------
    def host_ok(self) -> bool:
        if not getattr(self.server, "loopback", True):
            return True
        host = (self.headers.get("Host") or "").strip().lower()
        host = host[1:host.index("]")] if host.startswith("[") and "]" in host else host.rsplit(":", 1)[0]
        return host in LOOPBACK

    def send_bytes(self, data: bytes, ctype: str, status: int = 200, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, value, status: int = 200):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_static(self, name: str):
        path = WEB / name
        if not STATIC.match(name) or not path.is_file():
            return self.send_json({"error": "not found"}, 404)
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        csp = {"Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                          "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"}
        self.send_bytes(path.read_bytes(), ctype, extra=csp if name.endswith(".html") else None)

    # ---------- routes ----------
    def do_GET(self):
        if not self.host_ok():
            return self.send_json({"error": "forbidden host"}, 403)
        url = urlparse(self.path)
        try:
            if url.path in ("/", "/index.html"):
                return self.send_static("index.html")
            if url.path.startswith("/static/"):
                return self.send_static(url.path[len("/static/"):])
            if url.path == "/api/info":
                return self.send_json(self.app.info())
            if url.path == "/api/runs":
                return self.send_json({"runs": self.app.list_runs()})
            if url.path == "/api/demo":
                return self.send_json({"case": DEMO_CASE, "evidence": DEMO_EVIDENCE, "scenarios": SCENARIOS})
            if url.path == "/api/demo/clinical":
                return self.send_json({"case": CLINICAL_EXAMPLE})
            if url.path == "/api/patients":
                return self.send_json({"patients": self.app.memory.patients()})
            patient_match = re.fullmatch(r"/api/patients/([A-Za-z0-9][A-Za-z0-9._-]{0,79})", url.path)
            if patient_match:
                return self.send_json({"patient_id": patient_match.group(1), "entries": self.app.memory.history(patient_match.group(1))})
            source_match = re.fullmatch(r"/api/sources/(SRC-[a-f0-9]{32})(/image)?", url.path)
            if source_match:
                source = self.app.sources.get(source_match.group(1))
                if source_match.group(2):
                    if not source["mime"].startswith("image/"):
                        raise ValueError("Not an image")
                    return self.send_bytes((self.app.sources.root / source["id"] / "source.bin").read_bytes(), source["mime"])
                return self.send_json(source)
            if url.path == "/api/knowledge":
                query = parse_qs(url.query)
                return self.send_json({"documents": self.app.knowledge.list_documents(query.get("archived") == ["1"]), "stats": self.app.knowledge.stats()})
            if url.path == "/api/knowledge/search":
                query = parse_qs(url.query)
                return self.send_json({"results": self.app.knowledge.search(query.get("q", [""])[0], query.get("role", [""])[0], int(query.get("limit", ["20"])[0]))})
            knowledge_match = re.fullmatch(r"/api/knowledge/(KB-[a-f0-9]{32})", url.path)
            if knowledge_match:
                return self.send_json(self.app.knowledge.get(knowledge_match.group(1)))
            match = re.match(r"^/api/runs/([^/]+)(?:/([A-Za-z._]+))?$", url.path)
            if match:
                run_id, action = match.groups()
                if action is None:
                    return self.send_json(self.app.detail(run_id))
                if action == "stream":
                    after = int(parse_qs(url.query).get("after", ["0"])[0] or 0)
                    last = self.headers.get("Last-Event-ID", "")
                    return self.stream(run_id, max(0, after, int(last) if last.isdigit() else 0))
                if action in ("report.md", "result.json", "evidence.json"):
                    path = self.app.run_dir(run_id) / action
                    if not path.is_file():
                        raise LookupError(action)
                    ctype = "text/markdown; charset=utf-8" if action.endswith(".md") else "application/json; charset=utf-8"
                    return self.send_bytes(path.read_bytes(), ctype, extra={
                        "Content-Disposition": f'attachment; filename="{run_id}-{action}"'})
            self.send_json({"error": "not found"}, 404)
        except LookupError:
            self.send_json({"error": "Record not found"}, 404)
        except ValueError:
            self.send_json({"error": "Invalid request parameter"}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        if not self.host_ok():
            return self.send_json({"error": "forbidden host"}, 403)
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in LOOPBACK and getattr(self.server, "loopback", True):
            return self.send_json({"error": "forbidden origin"}, 403)
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return self.send_json({"error": "Content-Type must be application/json"}, 415)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.send_json({"error": "Invalid content length"}, 400)
        if length <= 0 or length > MAX_BODY:
            return self.send_json({"error": "Request body is empty or too large"}, 413)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            path = urlparse(self.path).path
            if path == "/api/runs":
                return self.send_json({"id": self.app.start(body)}, 201)
            if path == "/api/validate":
                return self.send_json(self.app.validate(body))
            if path == "/api/clinical/check":
                return self.send_json(self.app.check_case(body))
            info_match = re.fullmatch(r"/api/runs/([^/]+)/information", path)
            if info_match:
                return self.send_json(self.app.information_followup(info_match.group(1), body))
            if path == "/api/sources":
                return self.send_json(self.app.sources.ingest(body.get("filename"), body.get("content_base64")), 201)
            if path == "/api/intake/extract":
                return self.send_json(self.app.extract_sources(body))
            patient_match = re.fullmatch(r"/api/patients/([A-Za-z0-9][A-Za-z0-9._-]{0,79})/(entries|snapshot|resolve)", path)
            if patient_match:
                patient_id, action = patient_match.groups()
                if action == "entries":
                    return self.send_json(self.app.memory.add(patient_id, body.get("entry"), actor=body.get("actor")), 201)
                if action == "resolve":
                    return self.send_json(self.app.memory.resolve(patient_id, body.get("entry_id"), body))
                return self.send_json(self.app.memory.snapshot(patient_id, body.get("as_of"),
                                      task_type=body.get("task_type", "generate_plan"), encounter_id=body.get("encounter_id", "")))
            label_match = re.fullmatch(r"/api/runs/([^/]+)/labels", path)
            if label_match:
                return self.send_json(self.app.add_labels(label_match.group(1), body), 201)
            if path == "/api/knowledge":
                return self.send_json(self.app.knowledge.add_many(body.get("documents", [body])), 201)
            if path == "/api/knowledge/extract":
                return self.send_json(self.app.extract_file(body))
            if path == "/api/knowledge/snapshot":
                return self.send_json({"evidence": self.app.knowledge.snapshot(body.get("ids"))})
            knowledge_match = re.fullmatch(r"/api/knowledge/(KB-[a-f0-9]{32})/archive", path)
            if knowledge_match:
                return self.send_json(self.app.knowledge.archive(knowledge_match.group(1), body.get("archived")))
            match = re.match(r"^/api/runs/([^/]+)/signoff$", path)
            if match:
                return self.send_json(self.app.signoff(match.group(1), body), 201)
            self.send_json({"error": "not found"}, 404)
        except LookupError:
            self.send_json({"error": "Record not found"}, 404)
        except (ValueError, TypeError) as exc:  # includes ContractError / JSONDecodeError
            self.send_json({"error": str(exc) or type(exc).__name__}, 400)
        except (ProviderError, asyncio.TimeoutError) as exc:
            self.send_json({"error": str(exc) if isinstance(exc, ProviderError) else "Model extraction timed out"}, 502)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def stream(self, run_id: str, after: int):
        self.app.run_dir(run_id)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def send(chunk: str):
            self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

        job = self.app.jobs.get(run_id)
        if job is None:  # finished before this server started: replay from disk
            for event in self.app.detail(run_id)["events"][after:]:
                send(f"id: {event.get('seq', '')}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n")
            return send("event: done\ndata: {}\n\n")
        send("retry: 1500\n\n")
        index = after
        while True:
            with job.cond:
                if len(job.events) <= index and not job.done:
                    job.cond.wait(timeout=10)
                batch, done = job.events[index:], job.done
            if not batch and not done:
                send(": keep-alive\n\n")
                continue
            for event in strip_inputs(batch):
                send(f"id: {event.get('seq', '')}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n")
            index += len(batch)
            if done and index >= len(job.events):
                return send("event: done\ndata: {}\n\n")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets two servers share a port; we want a clean "port busy" signal.
    allow_reuse_address = sys.platform != "win32"


def open_window(url: str) -> None:
    """Prefer a chromeless app window (Edge/Chrome --app); fall back to the default browser."""
    candidates = []
    if sys.platform == "win32":
        for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidates += [Path(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                               Path(base, "Google", "Chrome", "Application", "chrome.exe")]
    for name in ("msedge", "google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for exe in candidates:
        if exe.is_file():
            try:
                subprocess.Popen([str(exe), f"--app={url}", "--window-size=1480,940"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
    webbrowser.open(url)


def make_server(host: str = "127.0.0.1", port: int = 8765, runs_dir: str | Path = "runs") -> Server:
    ports = [port] + [port + i for i in range(1, 20)] if port else [0]
    last_error = None
    for candidate in ports:
        try:
            httpd = Server((host, candidate), Handler)
            break
        except OSError as exc:
            last_error = exc
    else:
        raise OSError(f"no free port near {port}: {last_error}")
    httpd.app = App(Path(runs_dir))  # type: ignore[attr-defined]
    httpd.loopback = host in LOOPBACK  # type: ignore[attr-defined]
    return httpd


def serve(host: str = "127.0.0.1", port: int = 8765, runs_dir: str | Path = "runs",
          open_browser: bool = True, verbose: bool = False) -> int:
    httpd = make_server(host, port, runs_dir)
    httpd.verbose = verbose  # type: ignore[attr-defined]
    shown = "127.0.0.1" if host in ("0.0.0.0", "", "::") else host
    url = f"http://{shown}:{httpd.server_address[1]}/"
    print(f"VTE Anticoagulation Assistant v{__version__}")
    print(f"Workspace: {url}")
    print(f"Run records: {httpd.app.runs}")  # type: ignore[attr-defined]
    if not httpd.loopback:  # type: ignore[attr-defined]
        print("Warning: this service is accessible outside loopback.")
    print("Close this window or press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, open_window, args=(url,)).start()
    try:
        httpd.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
