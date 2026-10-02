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
                 on_event: Callable[[dict], None] | None = None):
        self.model = model
        self.evidence = evidence
        self.settings = settings or Settings()
        self.on_event = on_event
        self._used = False

    def emit(self, event: str, **data):
        item = {"seq": len(self.events) + 1, "elapsed_s": round(time.perf_counter() - self.started, 4), "event": event, **deepcopy(data)}
        self.events.append(item)
        if self.on_event:
            self.on_event(deepcopy(item))

    async def call(self, task: str, role: str, payload: dict, validator) -> dict:
        async with self.semaphore:
            self.emit("call_started", task=task, role=role, version=self.version, input=payload)
            started = time.perf_counter()
            try:
                reply = await asyncio.wait_for(self.model.complete(task, role, deepcopy(payload)), self.settings.call_timeout)
                result = validator(reply.data, {d["id"] for d in payload["evidence"]})
                self.emit("call_completed", task=task, role=role, version=self.version,
                          duration_s=round(time.perf_counter() - started, 4), model=reply.model,
                          usage=reply.usage, output=result)
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
        query = json.dumps(self.case, ensure_ascii=False) + " " + ROLE_NAMES[role] + " " + extra
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
            "evidence": list(self.pool.values()), "events": self.events,
            "metrics": {
                "elapsed_s": round(time.perf_counter() - self.started, 4),
                "calls": sum(e["event"] == "call_started" for e in self.events),
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
        self.started = time.perf_counter()
        self.events = []
        self.version = 0
        self.revisions = 0
        self.draft = None
        self.reviews = {}
        self.approvals = {role: None for role in ROLES}
        self.pool = {}
        self.semaphore = asyncio.Semaphore(self.settings.max_concurrency)
        self.emit("started", case_id=self.case["case_id"], settings=asdict(self.settings), prompt_version=PROMPT_VERSION)
        try:
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
                    self.reviews[role] = reply
                    self.approvals[role] = self.version if reply["verdict"] == "approve" else None
                pending = {r for r in ROLES if self.approvals[r] is None}
                if not pending:
                    # Output the exact approved draft: no unreviewed final rewrite by D.
                    return self.finish("approved", "all_required_reviews_passed")
                if any(self.reviews[r]["verdict"] == "needs_information" for r in pending):
                    return self.finish("needs_human_review", "missing_information")
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
