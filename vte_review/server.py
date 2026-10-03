"""Local desktop-style UI: stdlib HTTP server, live SSE progress, physician sign-off.

Security posture: binds to loopback by default, rejects foreign Host headers (DNS
rebinding) and non-JSON POSTs (cross-site form posts). API keys stay in memory only.
"""
from __future__ import annotations

import asyncio
import hashlib
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
from .workflow import Settings, Workflow

WEB = Path(__file__).with_name("web")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
STATIC = re.compile(r"^[A-Za-z0-9_-]+\.(?:html|css|js|svg|png|ico)$")
MAX_BODY = 8 * 1024 * 1024
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
DECISIONS = {"accept", "accept_with_changes", "reject"}
SCENARIOS = {
    "targeted": {"title": "定向返修", "desc": "A 提出异议 → D 只修改 A 部分 → 仅 A 复核后通过", "expect": "approved"},
    "dependency": {"title": "依赖传播", "desc": "B 依赖 A；A 被修改后自动触发 B 重审", "expect": "approved"},
    "shared": {"title": "共同方案变更", "desc": "修订触及 shared_plan，A/B/C 全部重审", "expect": "approved"},
    "limit": {"title": "达到修订上限", "desc": "A 持续不通过，达到最大修订次数后转人工", "expect": "needs_human_review"},
    "missing": {"title": "缺少关键信息", "desc": "A 判定需补充患者资料，直接转人工复核", "expect": "needs_human_review"},
    "stagnant": {"title": "修订无变化", "desc": "D 未产生实际修改，停止循环并转人工", "expect": "needs_human_review"},
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


class App:
    def __init__(self, runs_dir: Path):
        self.runs = Path(runs_dir).resolve()
        self.runs.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    # ---------- queries ----------
    def info(self) -> dict:
        try:
            import httpx  # noqa: F401
            has_httpx = True
        except ImportError:
            has_httpx = False
        return {
            "version": __version__, "prompt_version": PROMPT_VERSION, "runs_dir": str(self.runs),
            "roles": ROLE_NAMES, "httpx": has_httpx, "defaults": asdict(Settings()), "scenarios": SCENARIOS,
            "env": {
                "base_url": os.environ.get("VTE_BASE_URL", ""),
                "model": os.environ.get("VTE_MODEL", ""),
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
        mode = body.get("mode", "demo")
        raw = body.get("settings") or {}
        if not isinstance(raw, dict):
            raise ValueError("运行参数必须是 JSON 对象")
        defaults = Settings()
        for key, value in raw.items():
            if key in ("max_revisions", "concurrency", "timeout", "top_k"):
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    raise ValueError(f"运行参数 {key} 需要有效数值") from None
                if isinstance(value, bool) or not math.isfinite(number) or (key != "timeout" and not number.is_integer()):
                    raise ValueError(f"运行参数 {key} 需要有限有效数值")
        settings = Settings(int(raw.get("max_revisions", defaults.max_revisions)),
                            int(raw.get("concurrency", defaults.max_concurrency)),
                            float(raw.get("timeout", defaults.call_timeout)),
                            int(raw.get("top_k", defaults.top_k)))
        meta = {"source": "gui", "mode": mode, "created_at": now_iso(), "app_version": __version__}
        if mode == "demo":
            scenario = body.get("scenario", "targeted")
            if scenario not in SCENARIOS:
                raise ValueError("未知的演示场景")
            case = validate_case(body.get("case") or DEMO_CASE)
            index = EvidenceIndex(body.get("evidence") or DEMO_EVIDENCE)
            pace = float(body.get("pace", 0.8))
            if not math.isfinite(pace):
                raise ValueError("演示节奏需要有限有效数值")
            model = PacedDemoModel(scenario, min(max(pace, 0.0), 3.0))
            meta["scenario"] = scenario
        elif mode == "llm":
            case = validate_case(body.get("case"))
            if not body.get("evidence"):
                raise ValueError("真实模型模式需要先导入证据库")
            index = EvidenceIndex(body["evidence"])
            if any(d["synthetic"] for d in index.documents.values()):
                raise ValueError("真实模型模式不接受 synthetic: true 的合成证据")
            llm = body.get("llm") or {}
            if not isinstance(llm, dict) or not isinstance(llm.get("role_models", {}), dict):
                raise ValueError("模型配置与角色模型必须是 JSON 对象")
            key = str(llm.get("api_key") or os.environ.get("VTE_API_KEY", "")).strip()
            name = str(llm.get("model") or os.environ.get("VTE_MODEL", "")).strip()
            base = str(llm.get("base_url") or os.environ.get("VTE_BASE_URL") or "https://api.openai.com/v1").strip()
            if not key or not name:
                raise ValueError("请填写模型名称与 API Key（或设置环境变量 VTE_MODEL / VTE_API_KEY）")
            role_models = {r: os.environ[f"VTE_MODEL_{r}"] for r in (*ROLES, "D") if os.environ.get(f"VTE_MODEL_{r}")}
            role_models.update({r: v.strip() for r, v in (llm.get("role_models") or {}).items()
                                if r in (*ROLES, "D") and isinstance(v, str) and v.strip()})
            try:
                from .providers import ChatCompletionsModel
                model = ChatCompletionsModel(base, key, name, role_models=role_models, timeout=settings.call_timeout)
            except ModuleNotFoundError:
                raise ValueError('缺少 HTTP 适配器：请运行 python -m pip install -e ".[llm]"') from None
            meta.update(base_url=base, model=name, role_models=role_models)  # never the key
        else:
            raise ValueError("未知的运行模式")

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        out = self.runs / run_id
        out.mkdir(parents=True, exist_ok=False)
        write_json(out / "case.json", case)
        write_json(out / "meta.json", meta)
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
                    result = await Workflow(model, index, settings, on_event).run(case)
                write_json(out / "result.json", result)
                (out / "report.md").write_text(report(result), encoding="utf-8")
            finally:
                close = getattr(model, "close", None)
                if close:
                    await close()

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
            raise ValueError("该运行没有可签署的草案")
        decision = body.get("decision")
        if decision not in DECISIONS:
            raise ValueError("请选择审阅结论")
        reviewer = str(body.get("reviewer", "")).strip()[:60]
        comment = str(body.get("comment", "")).strip()[:4000]
        if not reviewer:
            raise ValueError("请填写审阅医师姓名")
        if decision != "accept" and not comment:
            raise ValueError("“修改后采纳”或“不采纳”时请填写审阅意见")
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
            match = re.match(r"^/api/runs/([^/]+)(?:/([A-Za-z._]+))?$", url.path)
            if match:
                run_id, action = match.groups()
                if action is None:
                    return self.send_json(self.app.detail(run_id))
                if action == "stream":
                    after = int(parse_qs(url.query).get("after", ["0"])[0] or 0)
                    last = self.headers.get("Last-Event-ID", "")
                    return self.stream(run_id, max(0, after, int(last) if last.isdigit() else 0))
                if action in ("report.md", "result.json"):
                    path = self.app.run_dir(run_id) / action
                    if not path.is_file():
                        raise LookupError(action)
                    ctype = "text/markdown; charset=utf-8" if action.endswith(".md") else "application/json; charset=utf-8"
                    return self.send_bytes(path.read_bytes(), ctype, extra={
                        "Content-Disposition": f'attachment; filename="{run_id}-{action}"'})
            self.send_json({"error": "not found"}, 404)
        except LookupError:
            self.send_json({"error": "未找到该运行记录"}, 404)
        except ValueError:
            self.send_json({"error": "无效的请求参数"}, 400)
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
            return self.send_json({"error": "无效的请求长度"}, 400)
        if length <= 0 or length > MAX_BODY:
            return self.send_json({"error": "请求体为空或过大"}, 413)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("请求体必须是 JSON 对象")
            path = urlparse(self.path).path
            if path == "/api/runs":
                return self.send_json({"id": self.app.start(body)}, 201)
            if path == "/api/validate":
                return self.send_json(self.app.validate(body))
            match = re.match(r"^/api/runs/([^/]+)/signoff$", path)
            if match:
                return self.send_json(self.app.signoff(match.group(1), body), 201)
            self.send_json({"error": "not found"}, 404)
        except LookupError:
            self.send_json({"error": "未找到该运行记录"}, 404)
        except (ValueError, TypeError) as exc:  # includes ContractError / JSONDecodeError
            self.send_json({"error": str(exc) or type(exc).__name__}, 400)
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
    print(f"VTE 多专家协同审核系统 v{__version__}")
    print(f"界面地址：{url}")
    print(f"运行记录：{httpd.app.runs}")  # type: ignore[attr-defined]
    if not httpd.loopback:  # type: ignore[attr-defined]
        print("警告：服务未绑定在本机回环地址，局域网内其他设备可能访问病例数据。")
    print("关闭此窗口或按 Ctrl+C 退出。")
    if open_browser:
        threading.Timer(0.4, open_window, args=(url,)).start()
    try:
        httpd.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
