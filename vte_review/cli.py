from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import ContractError, ROLES, ROLE_NAMES, validate_case
from .demo import DEMO_CASE, DEMO_EVIDENCE, DemoModel
from .providers import ChatCompletionsModel
from .retrieval import EvidenceIndex
from .workflow import Settings, Workflow


def report(result: dict) -> str:
    lines = ["# VTE Agent Review", "", f"Status: `{result['status']}`; Reason: `{result['reason']}`.",
             f"Mode: `{result['mode']}`; Draft version: {result['version']}; D revisions: {result['revisions']}.", "",
             "Research workflow output; final clinical decisions require physician review.", ""]
    if result["draft"]:
        lines += ["## " + ("Reviewed draft" if result["final"] else "Draft requiring review"), "", result["draft"]["shared_plan"], ""]
        for role in ROLES:
            section = result["draft"]["sections"][role]
            lines += [f"### {role}: {ROLE_NAMES[role]}", "", section["text"], "", "Evidence: " + ", ".join(section["evidence_ids"]), ""]
    lines += ["## Reviews and revisions", ""]
    for event in result["events"]:
        if event["event"] == "review_round":
            lines.append(f"- v{event['version']} Review: {', '.join(event['roles'])}")
        elif event["event"] == "call_completed" and event["task"] == "review":
            lines.append(f"- {event['role']}: {event['output']['verdict']}; {event['output']['note']}")
        elif event["event"] == "draft_revised":
            lines.append(f"- D revised to v{event['version']}: {event['reason']}")
    lines += ["", "## Open issues", ""]
    for role in ROLES:
        if result["approvals"][role] is None:
            review = result["reviews"].get(role, {})
            lines.append(f"- {role} has not approved the current draft.")
            for issue in review.get("issues", []):
                lines.append(f"  - {issue['id']}: {issue['problem']}; {issue['requested_change']}")
    if all(v is not None for v in result["approvals"].values()):
        lines.append("- No open workflow issues.")
    lines += ["", "## Run metrics", "", "```json", json.dumps(result["metrics"], ensure_ascii=False, indent=2), "```", ""]
    if result.get("clinical_checks"):
        lines += ["## Clinical data checks", ""]
        lines += [f"- {i['severity']}: {i['message']} (roles: {','.join(i['roles'])})" for i in result["clinical_checks"]["issues"]]
    if result.get("memory_snapshot", {}).get("sha256"):
        lines += ["", "Memory snapshot SHA-256: " + result["memory_snapshot"]["sha256"]]
    if result.get("memory_proposals"):
        lines += ["", "## Memory proposals awaiting human confirmation", ""]
        lines += ["- " + p["topic"] + ": " + p["content"] for p in result["memory_proposals"]]
    return "\n".join(lines)


async def execute(args) -> int:
    settings = Settings(args.max_revisions, args.concurrency, args.timeout, args.top_k)
    if args.command == "demo":
        case = DEMO_CASE
        index = EvidenceIndex(DEMO_EVIDENCE)
        model = DemoModel(args.scenario)
    else:
        case = validate_case(json.loads(Path(args.case).read_text(encoding="utf-8-sig")))
        index = EvidenceIndex.from_file(args.evidence)
        if any(d["synthetic"] for d in index.documents.values()):
            raise ValueError("run requires a real evidence corpus; use demo for synthetic fixtures")
        key, name = os.environ.get("VTE_API_KEY", ""), os.environ.get("VTE_MODEL", "")
        if not key or not name:
            raise ValueError("set VTE_API_KEY and VTE_MODEL before run")
        role_models = {r: os.environ[f"VTE_MODEL_{r}"] for r in (*ROLES, "D") if os.environ.get(f"VTE_MODEL_{r}")}
        model = ChatCompletionsModel(os.environ.get("VTE_BASE_URL", "https://api.openai.com/v1"),
                                     key, name, role_models=role_models, timeout=args.timeout,
                                     api_style=os.environ.get("VTE_API_STYLE", "chat_completions"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    out = Path(args.output or Path("runs") / run_id).resolve()
    try:
        # Refuse to overwrite an earlier research record.
        out.mkdir(parents=True, exist_ok=False)
        (out / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        with (out / "events.jsonl").open("w", encoding="utf-8") as stream:
            def on_event(event):
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                stream.flush()
                if event["event"] in {"review_round", "draft_revised", "finished"}:
                    print(json.dumps({k: v for k, v in event.items() if k not in {"draft", "input", "output"}}, ensure_ascii=False))
            from .patient_memory import PatientMemory
            from .intake import SourceStore
            memory, sources = {"entries": []}, None
            if args.command == "run" and case.get("patient"):
                p = case["patient"]
                memory = PatientMemory(Path(args.workspace) / "patients.sqlite3").snapshot(
                    p["patient_id"], p["decision_at"], task_type=case.get("task_type", "generate_plan"), encounter_id=p["encounter_id"])
            if args.command == "run":
                sources = SourceStore(Path(args.workspace) / "sources")
            (out / "memory_snapshot.json").write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
            result = await Workflow(model, index, settings, on_event, memory_snapshot=memory, sources=sources).run(case)
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "report.md").write_text(report(result), encoding="utf-8")
        print(f"Output: {out}")
        return {"approved": 0, "needs_human_review": 2, "failed": 1}[result["status"]]
    finally:
        if isinstance(model, ChatCompletionsModel):
            await model.close()


def main() -> int:
    # Windows console pipes otherwise use locale-dependent encodings.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="VTE parallel expert review / targeted revision prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    gui = commands.add_parser("gui", help="launch the local physician / operator interface")
    gui.add_argument("--host", default="127.0.0.1", help="bind address; keep loopback for patient data")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--runs", default="runs", help="run-record directory")
    gui.add_argument("--no-browser", action="store_true", help="do not open a window automatically")
    gui.add_argument("--verbose", action="store_true")
    for command in ("demo", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--output", help="new output directory; existing paths are never overwritten")
        sub.add_argument("--max-revisions", type=int, default=3)
        sub.add_argument("--concurrency", type=int, default=3)
        sub.add_argument("--timeout", type=float, default=60)
        sub.add_argument("--top-k", type=int, default=4)
        if command == "demo":
            sub.add_argument("--scenario", choices=["targeted", "dependency", "shared", "limit", "missing", "stagnant"], default="targeted")
        else:
            sub.add_argument("--case", required=True)
            sub.add_argument("--evidence", required=True)
            sub.add_argument("--workspace", default="runs", help="patient/source storage directory")
    try:
        args = parser.parse_args()
        if args.command == "gui":
            from .server import serve
            return serve(args.host, args.port, args.runs, not args.no_browser, args.verbose)
        return asyncio.run(execute(args))
    except (ValueError, OSError, ContractError) as exc:
        print(f"Configuration/input error: {exc}", file=sys.stderr)
        return 1
    except ModuleNotFoundError:
        print('Install the HTTP adapter with: python -m pip install -e ".[llm]"', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
