import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from tests.test_clinical_workspace import AT, case
from vte_review.clinical import clinical_check
from vte_review.contracts import ContractError, affected_roles, validate_case
from vte_review.demo import DEMO_EVIDENCE, DemoModel
from vte_review.information import information_table
from vte_review.retrieval import EvidenceIndex
from vte_review.server import App
from vte_review.workflow import Workflow


def response(field="active_bleeding", status="absent", value=None):
    return dict(field=field, status=status, value=value, note="For this decision", clinician="Test physician", recorded_at=AT)


def assumptions():
    return [{"id": "AS-1", "condition": "Synthetic example: no active bleeding, if confirmed",
             "if_not_met": "Use a clinician-led alternative assessment", "roles": ["A", "B", "C"]}]


class ConditionalModel(DemoModel):
    async def complete(self, task, role, payload):
        reply = await super().complete(task, role, payload)
        if task == "synthesize":
            reply.data["assumptions"] = assumptions()
            reply.data["information_requests"] = [{"id": "INFO-1", "question": "Confirm bleeding status",
                                                   "impact": "Changes the conditional branch", "roles": ["C"]}]
        if task == "review":
            if payload["version"] == 1 and role in "BC":
                reply.data = {"verdict": "needs_information" if role == "C" else "revise", "note": "Needs an explicit branch or a citation fix",
                              "issues": [{"id": role+"-1", "problem": "Missing branch" if role == "C" else "Citation gap",
                                          "requested_change": "Improve the conditional draft", "evidence_ids": [], "related_roles": []}]}
            else:
                reply.data = {"verdict": "approve_conditional", "issues": [], "note": "Conditional advice is supported; data follow-up stays open"}
        if task == "revise":
            reply.data["draft"]["sections"]["B"]["text"] += " Citation fixed."
            reply.data["draft"]["assumptions"][0]["if_not_met"] += " Do not apply the dependent recommendation."
        return reply


class ConditionalWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_information_request_does_not_prevent_other_revision(self):
        c = case(); c["facts"]["active_bleeding"] = None
        r = await Workflow(ConditionalModel(delay=0), EvidenceIndex(DEMO_EVIDENCE)).run(c)
        self.assertEqual(r["status"], "conditional")
        self.assertEqual(r["revisions"], 1)
        self.assertTrue(r["review_complete"])
        self.assertEqual(r["information_status"], "open")
        self.assertIsNone(r["final"])
        self.assertEqual(r["recommendation"], r["draft"])
        self.assertIn("Citation fixed", r["draft"]["sections"]["B"]["text"])
        self.assertIsNone(c["facts"]["active_bleeding"])
        self.assertEqual([e["roles"] for e in r["events"] if e["event"] == "review_round"], [["A", "B", "C"], ["A", "B", "C"]])

    async def test_conditional_approval_requires_reviewable_assumption(self):
        class NoAssumption(ConditionalModel):
            async def complete(self, task, role, payload):
                r = await super().complete(task, role, payload)
                if task == "synthesize": r.data["assumptions"] = []
                return r
        r = await Workflow(NoAssumption(delay=0), EvidenceIndex(DEMO_EVIDENCE)).run(case())
        self.assertEqual(r["status"], "failed")
        self.assertFalse(r["review_complete"])


class InformationTests(unittest.TestCase):
    def test_unknown_not_important_and_absent_are_distinct(self):
        c = case(); c["facts"]["active_bleeding"] = None
        self.assertIsNone(clinical_check(c)["normalized_facts"]["active_bleeding"])
        for status in ["not_relevant", "unknown"]:
            c["information_responses"] = [response(status=status)]
            validate_case(c)
            self.assertIsNone(clinical_check(c)["normalized_facts"]["active_bleeding"])
            self.assertTrue(clinical_check(c)["conditional"])
        c["information_responses"] = [response()]
        self.assertIs(clinical_check(c)["normalized_facts"]["active_bleeding"], False)
        self.assertFalse(clinical_check(c)["conditional"])
        self.assertEqual(len(information_table(c)), 22)

    def test_not_relevant_cannot_erase_positive_finding(self):
        c = case(); c["facts"]["active_bleeding"] = True
        c["information_responses"] = [response(status="not_relevant")]
        self.assertIs(clinical_check(c)["normalized_facts"]["active_bleeding"], True)
        self.assertTrue(clinical_check(c)["blocking"])
        c["information_responses"] = [response()]
        self.assertTrue(clinical_check(c)["input_blocked"])

    def test_no_none_measurements_and_no_anonymous_confirmation(self):
        for row in [response(field="serum_creatinine"), {**response(), "clinician": ""},
                    response(status="provided", value=None), {**response(), "recorded_at": "yesterday"}]:
            c = case(); c["information_responses"] = [row]
            with self.assertRaises(ContractError): validate_case(c)

    def test_lab_metadata_can_be_completed_without_replacing_value(self):
        c = case(); c["facts"]["serum_creatinine"]["observed_at"] = None
        value = {**c["facts"]["serum_creatinine"], "observed_at": AT}
        c["information_responses"] = [response("serum_creatinine", "provided", value)]
        r = clinical_check(validate_case(c))
        self.assertFalse(r["input_blocked"])
        self.assertEqual(len(r["calculations"]), 1)

    def test_changed_assumptions_invalidate_all_roles(self):
        d = {"shared_plan": "same", "assumptions": assumptions(), "sections": {}}
        new = deepcopy(d); new["assumptions"][0]["condition"] = "Changed assumption"
        self.assertEqual(affected_roles(d, new, []), {"A", "B", "C"})

    def test_followup_is_append_only_and_does_not_rewrite_case_result_or_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder)); p = Path(folder)/"test-run"; p.mkdir()
            c = case(); c["facts"]["active_bleeding"] = None
            for name, value in [("case.json", c), ("result.json", {"status": "needs_human_review"}), ("research_labels.json", ["held-out"] )]:
                (p/name).write_text(json.dumps(value), encoding="utf8")
            before = {n: (p/n).read_bytes() for n in ["case.json", "result.json", "research_labels.json"]}
            first = app.information_followup("test-run", {"responses": [response()]})
            self.assertFalse(first["table"][14]["value"])
            later = app.information_followup("test-run", {"responses": [response(status="unknown")]})
            self.assertEqual(len(later["history"]), 2)
            self.assertIsNone(later["table"][14]["value"])
            self.assertNotIn("held-out", json.dumps(later["case"]))
            for name, raw in before.items(): self.assertEqual((p/name).read_bytes(), raw)
