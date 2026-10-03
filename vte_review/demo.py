"""Deterministic synthetic fixture, deliberately not a medical model."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from .contracts import ROLES
from .providers import ModelReply

DEMO_CASE = {
    "case_id": "SYNTHETIC-001",
    "question": "Review a synthetic VTE case with targeted specialist revision.",
    "facts": {"synthetic": True, "scenario": "Synthetic VTE case for workflow testing only"},
    "missing_information": ["Clinical prescribing data not supplied"],
}
DEMO_EVIDENCE = [{
    "id": "DEMO-PROTOCOL", "title": "VTE demonstration protocol (synthetic)",
    "source": "local:synthetic-fixture", "version": "2026-10-02",
    "text": "The VTE demonstration requires a reassessment checkpoint in the anticoagulation duration section. Medication safety and bleeding risk use placeholder text. Do not produce a prescription.",
    "roles": list(ROLES), "synthetic": True,
}]


class DemoModel:
    is_demo = True

    def __init__(self, scenario: str = "targeted", delay: float = 0.02):
        self.scenario = scenario
        self.delay = delay
        self.revision_count = 0

    async def complete(self, task: str, role: str, payload: dict) -> ModelReply:
        await asyncio.sleep(self.delay)
        evidence_ids = [payload["evidence"][0]["id"]]
        if task == "assess":
            data = {"summary": f"{role}: synthetic workflow assessment only.", "evidence_ids": evidence_ids, "uncertainties": ["Synthetic evidence"]}
        elif task == "synthesize":
            data = {
                "shared_plan": "Synthetic demonstration of the review workflow; no clinical recommendation.",
                "sections": {r: {"text": f"{r} demonstration section.", "evidence_ids": evidence_ids, "depends_on": []} for r in ROLES},
            }
            if self.scenario == "dependency":
                data["sections"]["B"]["depends_on"] = ["A"]
        elif task == "review":
            requires_fix = role == "A" and ("reassessment checkpoint" not in payload["section"]["text"] or self.scenario in {"limit", "stagnant", "missing"})
            if requires_fix:
                data = {
                    "verdict": "needs_information" if self.scenario == "missing" else "revise",
                    "issues": [{"id": "A-01", "problem": "The protocol requires a reassessment checkpoint.",
                                "requested_change": "Add the reassessment checkpoint.", "evidence_ids": evidence_ids, "related_roles": []}],
                    "note": "D should revise section A and return it to A.",
                }
            else:
                data = {"verdict": "approve", "issues": [], "note": "This specialist approves the demonstration section."}
        elif task == "revise":
            self.revision_count += 1
            draft = deepcopy(payload["draft"])
            if self.scenario != "stagnant":
                draft["sections"]["A"]["text"] += f" Added reassessment checkpoint (revision {self.revision_count})."
            if self.scenario == "shared":
                draft["shared_plan"] += " Shared assumptions updated."
            data = {"draft": draft, "reason": "Addressed issue A-01.", "affected_roles": []}
        else:
            raise ValueError("unknown task")
        return ModelReply(data, "deterministic-demo")
