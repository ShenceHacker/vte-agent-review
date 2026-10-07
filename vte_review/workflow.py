"""ABC concurrent assessments/reviews; D is the only writer of versioned drafts."""
from __future__ import annotations

import asyncio
import json
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Callable

from .contracts import (
    ROLES, ROLE_NAMES, ContractError, affected_roles, dependencies,
    validate_assessment, validate_case, validate_draft, validate_review, validate_revision,
)
from .prompts import PROMPT_VERSION
from .providers import Model, ProviderError
from .retrieval import EvidenceIndex
from .clinical import clinical_check
from .clinical_tools import ClinicalTools


@dataclass(frozen=True)
class Settings:
    max_revisions: int = 3
    max_concurrency: int = 3
    call_timeout: float = 60
    top_k: int = 4

    def __post_init__(self):
        if self.max_revisions < 0 or self.max_concurrency < 1 or self.call_timeout <= 0 or self.top_k < 1:
            raise ValueError("invalid workflow limits")


class Workflow:
    def __init__(self, model: Model, evidence: EvidenceIndex, settings: Settings | None = None,
                 on_event: Callable[[dict], None] | None = None, *, memory_snapshot=None, sources=None):
        self.model = model
        self.evidence = evidence
        self.settings = settings or Settings()
        self.on_event = on_event
        self._used = False
        self.memory = deepcopy(memory_snapshot or {"entries": []})
        self.sources = sources

    def emit(self, event: str, **data):
        item = {"seq": len(self.events) + 1, "elapsed_s": round(time.perf_counter() - self.started, 4), "event": event, **deepcopy(data)}
        self.events.append(item)
        if self.on_event:
            self.on_event(deepcopy(item))

    async def call(self, task: str, role: str, payload: dict, validator) -> dict:
        async with self.semaphore:
            payload = deepcopy(payload)
            payload["clinical_checks"] = {**self.checks, "issues": [i for i in self.checks.get("issues", []) if i["severity"] != "optional" and (role == "D" or role in i["roles"])]}
            payload["memory_context"] = {k: v for k, v in self.memory.items() if k != "entries"}
            session = ClinicalTools(role, self.case, self.evidence, memory=self.memory, sources=self.sources,
                                    emit=self.emit, top_k=self.settings.top_k)
            self.emit("call_started", task=task, role=role, version=self.version, input=payload)
            started = time.perf_counter()
            try:
                invoke = getattr(self.model, "complete_with_tools", None)
                usage, requests = {}, 0
                for attempt in range(2):
                    call = invoke(task, role, deepcopy(payload), session) if invoke else self.model.complete(task, role, deepcopy(payload))
                    remaining = max(.001, self.settings.call_timeout - (time.perf_counter() - started))
                    reply = await asyncio.wait_for(call, remaining)
                    requests += reply.requests
                    for k, v in reply.usage.items():
                        if isinstance(v, (int, float)):
                            usage[k] = usage.get(k, 0) + v
                    allowed = {d["id"] for d in payload["evidence"]} | set(session.retrieved)
                    try:
                        result = validator(reply.data, allowed)
                        break
                    except ContractError as exc:
                        if attempt:
                            raise
                        self.emit("call_repair_requested", task=task, role=role, error=str(exc), output=reply.data)
                        payload["validation_repair"] = {"error": str(exc), "previous_output": reply.data,
                                                        "allowed_evidence_ids": sorted(allowed)}
                        supplied = {d["id"]: d for d in payload["evidence"]}
                        supplied.update(session.retrieved)
                        payload["evidence"] = list(supplied.values())
                self.pool.update(session.retrieved)
                if role in ROLES:
                    previous = {d["id"]: d for d in self.role_evidence[role]}
                    previous.update(session.retrieved)
                    self.role_evidence[role] = list(previous.values())
                self.proposals.extend(session.proposals)
                self.emit("call_completed", task=task, role=role, version=self.version,
                          duration_s=round(time.perf_counter() - started, 4), model=reply.model,
                          usage=usage, requests=requests, output=result)
                return result
            except Exception as exc:
                # Persist only controlled errors; third-party exceptions may contain credentials.
                message = str(exc) if isinstance(exc, (ContractError, ProviderError)) else type(exc).__name__
                self.emit("call_failed", task=task, role=role, version=self.version, error=message)
                raise

    async def parallel(self, roles: list[str], operation) -> dict:
        tasks = [asyncio.create_task(operation(role)) for role in roles]
        try:
            return dict(zip(roles, await asyncio.gather(*tasks)))
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    def retrieve(self, role: str, extra: str = "") -> list[dict]:
        query = ROLE_NAMES[role] + " VTE DVT PE " + self.case["question"] + " " + json.dumps(self.case["facts"], ensure_ascii=False)
        query += " " + " ".join(str(o["key"]) + ": " + str(o["value"]) + " " + str(o["unit"]) for o in self.case.get("observations", []) if o["status"] != "excluded")
        if role == "B":
            query += " medication history drug interactions contraindications route dose renal hepatic CYP P-gp"
        query += " " + extra
        docs = self.evidence.search(query, role, self.settings.top_k)
        self.pool.update({doc["id"]: doc for doc in docs})
        return docs

    def review_payload(self, role: str) -> dict:
        related = dependencies(self.draft, role)
        sections = {r: deepcopy(self.draft["sections"][r]) for r in ROLES if r in related}
        own = self.draft["sections"][role]
        ids = set(own["evidence_ids"])
        for section in sections.values():
            ids.update(section["evidence_ids"])
        ids.update(d["id"] for d in self.role_evidence[role])
        return {
            "case": self.case, "version": self.version, "shared_plan": self.draft["shared_plan"],
            "section": own, "dependencies": sections, "initial_assessment": self.assessments[role],
            "previous_review": self.reviews.get(role),
            "assumptions": [a for a in self.draft.get("assumptions", []) if role in a["roles"]],
            "information_requests": [a for a in self.draft.get("information_requests", []) if role in a["roles"]],
            "evidence": [self.pool[k] for k in sorted(ids)],
        }

    def finish(self, status: str, reason: str) -> dict:
        self.emit("finished", status=status, reason=reason, version=self.version)
        return deepcopy({
            "status": status, "reason": reason, "case_id": self.case["case_id"],
            "mode": "synthetic_demo" if getattr(self.model, "is_demo", False) else "llm",
            "prompt_version": PROMPT_VERSION, "settings": asdict(self.settings),
            "version": self.version, "revisions": self.revisions,
            "approvals": self.approvals, "reviews": self.reviews,
            "draft": self.draft, "final": self.draft if status == "approved" else None,
            "recommendation": self.draft,
            "review_complete": status in {"approved", "conditional"},
            "information_status": "open" if self.checks.get("conditional") or (self.draft or {}).get("information_requests") else "no_requests",
            "evidence": list(self.pool.values()), "events": self.events,
            "clinical_checks": self.checks, "memory_snapshot": self.memory, "memory_proposals": self.proposals,
            "metrics": {
                "elapsed_s": round(time.perf_counter() - self.started, 4),
                "calls": sum(e["event"] == "call_started" for e in self.events),
                "model_requests": sum(e.get("requests", 0) for e in self.events if e["event"] == "call_completed"),
                "tool_calls": sum(e["event"] == "tool_completed" for e in self.events),
                "review_calls": sum(e["event"] == "call_started" and e["task"] == "review" for e in self.events),
                "reported_total_tokens": sum(e.get("usage", {}).get("total_tokens", 0) for e in self.events),
                "usage_reported_calls": sum(bool(e.get("usage")) for e in self.events if e["event"] == "call_completed"),
            },
        })

    async def run(self, case: dict) -> dict:
        if self._used:
            raise RuntimeError("create a fresh Workflow for each case")
        self._used = True
        self.case = validate_case(case)
        # Excluded observations stay in case.json for auditing, never in model inputs.
        if "observations" in self.case:
            self.case["observations"] = [o for o in self.case["observations"] if o["status"] != "excluded"]
        self.started = time.perf_counter()
        self.events = []
        self.version = 0
        self.revisions = 0
        self.draft = None
        self.reviews = {}
        self.approvals = {role: None for role in ROLES}
        self.pool = {}
        self.proposals = []
        self.checks = clinical_check(self.case) if not getattr(self.model, "is_demo", False) or "patient" in self.case else {}
        self.semaphore = asyncio.Semaphore(self.settings.max_concurrency)
        self.emit("started", case_id=self.case["case_id"], settings=asdict(self.settings), prompt_version=PROMPT_VERSION)
        try:
            if self.case.get("patient"):
                from .patient_memory import instant
                patient = self.case["patient"]
                if self.memory.get("entries"):
                    if (self.memory.get("patient_id") != patient["patient_id"]
                            or instant(self.memory.get("as_of")) != instant(patient["decision_at"])
                            or self.memory.get("task_type") != self.case.get("task_type", "generate_plan")
                            or self.memory.get("encounter_id") != patient["encounter_id"]):
                        raise ContractError("Memory snapshot does not match the current patient/time/task")
                    for entry in self.memory["entries"]:
                        if entry.get("patient_id") != patient["patient_id"] or entry.get("kind") == "model_suggestion" or entry.get("status") != "confirmed" or max(instant(entry["occurred_at"]), instant(entry["available_at"])) > instant(patient["decision_at"]):
                            raise ContractError("Invalid entry in frozen patient memory")
            if self.case.get("source_ids") and not self.sources:
                raise ContractError("Attached source storage is required")
            if self.sources and self.case.get("source_ids"):
                bundle = self.sources.bundle(self.case["source_ids"])
                allowed = set(self.case["source_ids"]) | set(bundle["image_ids"])
                if any(o["source_id"] not in allowed for o in self.case.get("observations", [])):
                    raise ContractError("Observation source is not attached to this case")
                for event in self.case.get("longitudinal", {}).get("prior_events", []) + self.case.get("longitudinal", {}).get("new_information", []):
                    scoped = self.sources.get(event["source_id"])
                    scoped_allowed = {scoped["id"], *scoped["images"]}
                    if event["text"] != scoped["text"] or any(o["source_id"] not in scoped_allowed for o in event["observations"]):
                        raise ContractError("Timeline event does not match its scoped source")
            if self.checks:
                self.emit("clinical_checked", report=self.checks)
            if self.checks.get("input_blocked"):
                return self.finish("needs_human_review", "source_verification_required")
            self.role_evidence = {r: self.retrieve(r) for r in ROLES}
            missing = [r for r in ROLES if not self.role_evidence[r]]
            if missing:
                return self.finish("needs_human_review", "no_retrieved_evidence:" + ",".join(missing))

            async def assess(role):
                return await self.call("assess", role, {"case": self.case, "evidence": self.role_evidence[role]}, validate_assessment)

            self.assessments = await self.parallel(list(ROLES), assess)
            self.draft = await self.call("synthesize", "D", {
                "case": self.case, "assessments": self.assessments, "evidence": list(self.pool.values()),
            }, validate_draft)
            self.version = 1
            self.emit("draft_created", version=self.version, draft=self.draft)
            pending = set(ROLES)

            while True:
                selected = [r for r in ROLES if r in pending]
                self.emit("review_round", version=self.version, roles=selected)

                async def review(role):
                    return await self.call("review", role, self.review_payload(role), validate_review)

                replies = await self.parallel(selected, review)
                for role, reply in replies.items():
                    if reply["verdict"] == "approve_conditional" and not any(role in a["roles"] for a in self.draft.get("assumptions", [])):
                        raise ContractError("Conditional approval requires an explicit applicable draft assumption")
                    self.reviews[role] = reply
                    self.approvals[role] = self.version if reply["verdict"] in {"approve", "approve_conditional"} else None
                pending = {r for r in ROLES if self.approvals[r] is None}
                if not pending:
                    conditional = (self.checks.get("blocking") or self.checks.get("conditional")
                                   or self.draft.get("assumptions") or self.draft.get("information_requests")
                                   or any(v["verdict"] == "approve_conditional" for v in self.reviews.values()))
                    if conditional:
                        if not self.draft.get("assumptions"):
                            return self.finish("needs_human_review", "conditional_assumptions_missing")
                        return self.finish("conditional", "conditional_recommendation_ready")
                    # Output the exact approved draft: no unreviewed final rewrite by D.
                    return self.finish("approved", "all_required_reviews_passed")
                if self.revisions >= self.settings.max_revisions:
                    return self.finish("needs_human_review", "revision_limit")

                for role in sorted(pending):
                    extra = json.dumps(self.reviews[role]["issues"], ensure_ascii=False)
                    previous = {d["id"]: d for d in self.role_evidence[role]}
                    previous.update({d["id"]: d for d in self.retrieve(role, extra)})
                    self.role_evidence[role] = list(previous.values())
                revision = await self.call("revise", "D", {
                    "case": self.case, "version": self.version, "draft": self.draft,
                    "reviews": self.reviews, "pending_roles": sorted(pending),
                    "revision_policy": "Fix actionable issues now. Convert decision-dependent missing information into explicit assumptions and if-not-met branches. Do not wait for every field or invent negative findings.",
                    "evidence": list(self.pool.values()),
                }, validate_revision)
                if revision["draft"] == self.draft:
                    return self.finish("needs_human_review", "no_change_after_revision")
                affected = affected_roles(self.draft, revision["draft"], revision["affected_roles"])
                for role in pending:
                    for issue in self.reviews[role]["issues"]:
                        affected.update(issue["related_roles"])
                pending |= affected
                for role in pending:
                    self.approvals[role] = None
                self.draft = revision["draft"]
                self.version += 1
                self.revisions += 1
                self.emit("draft_revised", version=self.version, roles=sorted(pending),
                          reason=revision["reason"], draft=self.draft)
        except Exception as exc:
            error = str(exc) if isinstance(exc, (ContractError, ProviderError)) else type(exc).__name__
            return self.finish("failed", error)
