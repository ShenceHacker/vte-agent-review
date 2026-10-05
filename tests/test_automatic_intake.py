"""Automatic intake: unverified sources may inform conditional recommendations."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from vte_review.clinical import clinical_check
from vte_review.contracts import ContractError, validate_case
from vte_review.demo import DemoModel
from vte_review.providers import ModelReply
from vte_review.server import App


def observation(source, key="age_years", value=65, **extra):
    return {"key": key, "value": value, "unit": "", "observed_at": "", "available_at": "",
            "source_id": source, "location": "paragraph 1", "status": "unverified", **extra}


def automatic_case(source):
    return {"case_id": "QA-AUTO", "question": "Recommend VTE anticoagulation treatment and monitoring",
            "facts": {}, "missing_information": [], "input_mode": "automatic", "source_ids": [source],
            "source_context": {source: {"available_at": "", "reviewer": ""}},
            "observations": [observation(source)]}


class IntakeTestModel:
    """Isolated test provider; never used by the application launcher."""
    def __init__(self, *args, **kwargs):
        self.inner = DemoModel(delay=0)

    async def extract(self, payload, images):
        source = payload["sources"][0]["id"]
        return ModelReply({"observations": [observation(source),
                           observation(source, "vte_type_site", "Proximal DVT")], "issues": []}, "test-provider")

    async def complete(self, task, role, payload):
        return await self.inner.complete(task, role, payload)

    async def close(self):
        pass


class AutomaticIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name))
        self.source = self.app.sources.ingest("case.txt", base64.b64encode(b"Synthetic case: age 65, proximal DVT.").decode())["id"]
        self.case = automatic_case(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_dates_and_unverified_values_are_nonblocking(self):
        original = deepcopy(self.case)
        check = clinical_check(validate_case(self.case))
        self.assertFalse(check["input_blocked"])
        self.assertEqual(check["normalized_facts"]["age_years"], 65)
        self.assertTrue(check["conditional"])
        self.assertEqual(self.case, original)
        self.assertNotIn("active_bleeding", check["normalized_facts"])

    def test_null_readings_never_become_facts(self):
        self.case["observations"][0]["value"] = None
        self.assertNotIn("age_years", clinical_check(validate_case(self.case))["normalized_facts"])

    def test_explicit_age_and_weight_units_normalize_without_losing_source(self):
        self.case["observations"][0]["unit"] = "years"
        self.case["observations"].append(observation(self.source, "weight_kg", 70, unit="kg"))
        check = clinical_check(validate_case(self.case))
        self.assertEqual(check["normalized_facts"]["age_years"], 65)
        self.assertEqual(check["normalized_facts"]["weight_kg"], 70)
        self.assertEqual(self.case["observations"][1]["unit"], "kg")
        self.assertFalse(check["blocking"])

    def test_omitted_mode_never_starts_a_demo(self):
        with self.assertRaises(ContractError):
            self.app.start({})
        self.assertFalse(self.app.jobs)

    def test_conflicting_undated_values_are_not_silently_selected(self):
        self.case["observations"].append(observation(self.source, value=72))
        check = clinical_check(validate_case(self.case))
        self.assertNotIn("age_years", check["normalized_facts"])
        self.assertFalse(check["input_blocked"])
        self.assertIn("ambiguous_extraction", [i["code"] for i in check["issues"]])

    def test_date_only_readings_remain_available_without_fabricated_timezone(self):
        self.case["observations"][0].update(observed_at="2026-01-01", available_at="unknown")
        check = clinical_check(validate_case(self.case))
        self.assertEqual(check["normalized_facts"]["age_years"], 65)
        self.assertEqual(self.case["observations"][0]["observed_at"], "2026-01-01")

    def test_explicit_historical_cutoff_still_excludes_future_data(self):
        self.case["patient"] = {"patient_id": "QA", "encounter_id": "V1", "decision_at": "2026-01-01T12:00:00+00:00"}
        self.case["observations"][0].update(observed_at="2026-01-02T12:00:00+00:00", available_at="2026-01-02T12:00:00+00:00")
        check = clinical_check(validate_case(self.case))
        self.assertTrue(check["input_blocked"])
        self.assertNotIn("age_years", check["normalized_facts"])

    def test_strict_research_input_still_requires_source_metadata(self):
        self.case.pop("input_mode")
        with self.assertRaises(ContractError):
            validate_case(self.case)

    def test_empty_library_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "knowledge base is empty"):
            self.app.start({"mode": "llm", "retrieval": "automatic", "case": self.case})

    def test_upload_extract_retrieve_and_complete_without_confirmation(self):
        document = {"title": "QA reference", "source": "Test fixture only", "version": "1", "roles": ["A", "B", "C"],
                    "synthetic": False, "text": "VTE anticoagulation treatment DVT dose duration bleeding monitoring renal function."}
        active = self.app.knowledge.add_many([document])["ids"][0]
        self.app.knowledge.add_many([{**document, "title": "Synthetic source", "synthetic": True}])
        archived = self.app.knowledge.add_many([{**document, "title": "Archived source"}])["ids"][0]
        self.app.knowledge.archive(archived, True)
        with patch("vte_review.workspace.configured_model", return_value=(IntakeTestModel(), {"model": "test-provider"})):
            intake = self.app.extract_sources({"source_ids": [self.source]})
        self.case["observations"] = intake["output"]["observations"]
        with patch("vte_review.providers.ChatCompletionsModel", IntakeTestModel):
            run = self.app.start({"mode": "llm", "retrieval": "automatic", "case": self.case,
                                  "llm": {"model": "test-provider", "api_key": "test-only"}})
            for _ in range(200):
                if self.app.jobs[run].done:
                    break
                time.sleep(.01)
            self.assertTrue(self.app.jobs[run].done)
        path = Path(self.temp.name) / run
        result = json.loads((path / "result.json").read_text())
        meta = json.loads((path / "meta.json").read_text())
        self.assertEqual(meta["knowledge_ids"], [active])
        self.assertEqual(meta["retrieval"], "SQLite FTS5 / BM25")
        self.assertTrue(result["draft"])
        self.assertTrue(any(e["event"] == "call_started" for e in result["events"]))
        self.assertEqual(result["clinical_checks"]["normalized_facts"]["age_years"], 65)
        self.assertEqual(self.case["observations"][0]["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
