import asyncio
import unittest
from copy import deepcopy

from vte_review.contracts import affected_roles
from vte_review.demo import DEMO_CASE, DEMO_EVIDENCE, DemoModel
from vte_review.providers import ModelReply
from vte_review.retrieval import EvidenceIndex
from vte_review.workflow import Settings, Workflow


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, scenario="targeted", model=None, **settings):
        return await Workflow(model or DemoModel(scenario, delay=0), EvidenceIndex(DEMO_EVIDENCE), Settings(**settings)).run(DEMO_CASE)

    def rounds(self, result):
        return [e["roles"] for e in result["events"] if e["event"] == "review_round"]

    async def test_only_a_rechecked_after_a_fix(self):
        result = await self.run_case()
        self.assertEqual(result["status"], "approved")
        self.assertEqual(self.rounds(result), [["A", "B", "C"], ["A"]])
        self.assertEqual(result["approvals"], {"A": 2, "B": 1, "C": 1})
        self.assertEqual(result["metrics"]["calls"], 9)
        self.assertEqual(result["final"], result["draft"])
        self.assertEqual(result["events"][-2]["task"], "review")

    async def test_dependency_invalidates_b_approval(self):
        result = await self.run_case("dependency")
        self.assertEqual(self.rounds(result), [["A", "B", "C"], ["A", "B"]])
        self.assertEqual(result["approvals"], {"A": 2, "B": 2, "C": 1})

    async def test_shared_plan_change_invalidates_everyone(self):
        result = await self.run_case("shared")
        self.assertEqual(self.rounds(result), [["A", "B", "C"], ["A", "B", "C"]])

    async def test_revisions_stop_without_false_final(self):
        result = await self.run_case("limit", max_revisions=2)
        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(result["reason"], "revision_limit")
        self.assertEqual(result["revisions"], 2)
        self.assertEqual(len(self.rounds(result)), 3)
        self.assertIsNone(result["final"])
        self.assertIsNone(result["approvals"]["A"])

    async def test_zero_revision_budget_still_reviews_initial_draft(self):
        result = await self.run_case(max_revisions=0)
        self.assertEqual(result["reason"], "revision_limit")
        self.assertEqual(self.rounds(result), [["A", "B", "C"]])

    async def test_missing_information_does_not_loop(self):
        result = await self.run_case("missing")
        self.assertEqual(result["reason"], "missing_information")
        self.assertEqual(result["revisions"], 0)
        self.assertIsNone(result["final"])

    async def test_no_change_ends_loop(self):
        result = await self.run_case("stagnant")
        self.assertEqual(result["reason"], "no_change_after_revision")
        self.assertIsNone(result["final"])

    async def test_timeout_never_becomes_approval(self):
        class SlowModel(DemoModel):
            async def complete(self, task, role, payload):
                if task == "review" and role == "B":
                    await asyncio.sleep(1)
                return await super().complete(task, role, payload)
        result = await self.run_case(model=SlowModel(delay=0), call_timeout=0.02)
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["final"])
        self.assertIsNone(result["approvals"]["B"])
        count = len(result["events"])
        await asyncio.sleep(0.03)
        self.assertEqual(count, len(result["events"]))

    async def test_invalid_review_is_failure(self):
        class BrokenModel(DemoModel):
            async def complete(self, task, role, payload):
                if task == "review" and role == "B":
                    return ModelReply({"verdict": "approve", "issues": [{"problem": "but unsafe"}], "note": "invalid"}, "test")
                return await super().complete(task, role, payload)
        result = await self.run_case(model=BrokenModel(delay=0))
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["final"])

    async def test_fabricated_citation_rejected(self):
        class BadCitation(DemoModel):
            async def complete(self, task, role, payload):
                reply = await super().complete(task, role, payload)
                if task == "synthesize":
                    reply.data["sections"]["A"]["evidence_ids"] = ["not-retrieved"]
                return reply
        result = await self.run_case(model=BadCitation(delay=0))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.rounds(result), [])

    async def test_unrelated_section_not_sent_to_reviewer(self):
        result = await self.run_case()
        calls = [e for e in result["events"] if e["event"] == "call_started" and e["task"] == "review"]
        for event in calls:
            self.assertNotIn("draft", event["input"])
            self.assertEqual(event["input"]["dependencies"], {})
        self.assertEqual(calls[-1]["input"]["previous_review"]["issues"][0]["id"], "A-01")

    async def test_initial_assessments_and_reviews_actually_overlap(self):
        class BarrierModel(DemoModel):
            def __init__(self):
                super().__init__(delay=0)
                self.arrivals = {"assess": set(), "review": set()}
                self.barriers = {"assess": asyncio.Event(), "review": asyncio.Event()}

            async def complete(self, task, role, payload):
                if task == "assess" or (task == "review" and payload["version"] == 1):
                    self.arrivals[task].add(role)
                    if len(self.arrivals[task]) == 3:
                        self.barriers[task].set()
                    await asyncio.wait_for(self.barriers[task].wait(), 1)
                return await super().complete(task, role, payload)
        result = await self.run_case(model=BarrierModel(), call_timeout=2)
        self.assertEqual(result["status"], "approved")

    async def test_semaphore_bounds_concurrency(self):
        class TrackingModel(DemoModel):
            def __init__(self):
                super().__init__(delay=0.002)
                self.active = self.peak = 0

            async def complete(self, task, role, payload):
                self.active += 1
                self.peak = max(self.peak, self.active)
                try:
                    return await super().complete(task, role, payload)
                finally:
                    self.active -= 1
        model = TrackingModel()
        result = await self.run_case(model=model, max_concurrency=2)
        self.assertEqual(result["status"], "approved")
        self.assertEqual(model.peak, 2)

    async def test_two_objections_revised_together_then_rechecked(self):
        class TwoIssues(DemoModel):
            async def complete(self, task, role, payload):
                reply = await super().complete(task, role, payload)
                if task == "review" and role == "B" and payload["version"] == 1:
                    reply.data = {"verdict": "revise", "note": "B 需要修改", "issues": [{"id": "B-01", "problem": "缺少演示说明", "requested_change": "补充说明", "evidence_ids": [], "related_roles": []}]}
                if task == "revise":
                    reply.data["draft"]["sections"]["B"]["text"] += " 补充说明。"
                return reply
        result = await self.run_case(model=TwoIssues(delay=0))
        self.assertEqual(self.rounds(result), [["A", "B", "C"], ["A", "B"]])
        self.assertEqual(result["revisions"], 1)

    async def test_no_evidence_stops_before_model_calls(self):
        docs = deepcopy(DEMO_EVIDENCE)
        docs[0]["roles"] = ["A"]
        result = await Workflow(DemoModel(), EvidenceIndex(docs)).run(DEMO_CASE)
        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(result["metrics"]["calls"], 0)

    async def test_dependency_removal_cannot_hide_impact(self):
        result = await self.run_case("dependency")
        old = result["draft"]
        new = deepcopy(old)
        new["sections"]["A"]["text"] += " changed"
        new["sections"]["B"]["depends_on"] = []
        self.assertEqual(affected_roles(old, new, []), {"A", "B"})

    async def test_transitive_dependency_and_cycles(self):
        result = await self.run_case("dependency")
        old = result["draft"]
        old["sections"]["C"]["depends_on"] = ["B"]
        old["sections"]["A"]["depends_on"] = ["C"]
        new = deepcopy(old)
        new["sections"]["A"]["text"] += " changed"
        self.assertEqual(affected_roles(old, new, []), {"A", "B", "C"})

    async def test_d_modifying_another_section_forces_its_review(self):
        class ExtraEdit(DemoModel):
            async def complete(self, task, role, payload):
                reply = await super().complete(task, role, payload)
                if task == "revise":
                    reply.data["draft"]["sections"]["C"]["text"] += " 意外修改。"
                return reply
        result = await self.run_case(model=ExtraEdit(delay=0))
        self.assertEqual(self.rounds(result), [["A", "B", "C"], ["A", "C"]])


if __name__ == "__main__":
    unittest.main()
