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
from vte_review.intake import validate_extraction
from vte_review.vector import VectorStore


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
        # This test exercises intake/workflow, not network model-weight downloads.
        # Vector retrieval itself has a dedicated isolated test suite.
        self.app.vectors = VectorStore(Path(self.temp.name), enabled=False)
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

    def test_structured_extraction_notes_preserve_all_fields_without_mutating_reply(self):
        note = {"field": "creatinine", "message": "Date unavailable", "source_id": self.source,
                "details": {"alternatives": ["undated", "older result"]}}
        raw = {"observations": [observation(self.source, value=65, status="confirmed")],
               "issues": ["Keep this text", note]}
        result = validate_extraction(raw, {self.source})
        self.assertEqual(result["issues"][0], "Keep this text")
        self.assertEqual(json.loads(result["issues"][1]), note)
        self.assertEqual(result["observations"][0]["status"], "unverified")
        self.assertEqual(raw["observations"][0]["status"], "confirmed")
        self.assertIsInstance(raw["issues"][1], dict)

    def test_note_container_variants_and_size_limits(self):
        for notes, expected in [(None, []), ("Note", ["Note"]), ({"message": "Note"}, ['{"message": "Note"}'])]:
            with self.subTest(notes=notes):
                self.assertEqual(validate_extraction({"observations": [], "issues": notes}, set())["issues"], expected)
        for notes in [["x"] * 101, ["x" * 16001], [float("nan")]]:
            with self.subTest(notes_type=type(notes)), self.assertRaises(ValueError):
                validate_extraction({"observations": [], "issues": notes}, set())

    def test_structured_notes_do_not_relax_observation_validation(self):
        raw = {"observations": [observation("foreign-source")], "issues": [{"message": "note"}]}
        with self.assertRaisesRegex(ValueError, "observation or source"):
            validate_extraction(raw, {self.source})
        raw["observations"] = [observation(self.source, unit={"value": "years"})]
        with self.assertRaisesRegex(ValueError, "Invalid extraction field"):
            validate_extraction(raw, {self.source})

    def test_extraction_service_keeps_raw_response_and_normalized_notes(self):
        source = self.source
        class StructuredNotesModel(IntakeTestModel):
            async def extract(self, payload, images):
                return ModelReply({"observations": [observation(source)],
                                   "issues": [{"field": "date", "message": "Not recorded"}]}, "test-provider")
        with patch("vte_review.workspace.configured_model", return_value=(StructuredNotesModel(), {"model": "test-provider"})):
            result = self.app.extract_sources({"source_ids": [self.source]})
        saved = json.loads((Path(self.temp.name) / "intakes" / (result["id"] + ".json")).read_text())
        self.assertIsInstance(saved["raw_output"]["issues"][0], dict)
        self.assertIsInstance(saved["output"]["issues"][0], str)
        self.assertEqual(saved["output"]["observations"][0]["value"], 65)

    def test_invalid_observation_response_is_retained_for_diagnosis(self):
        class BadSourceModel(IntakeTestModel):
            async def extract(self, payload, images):
                return ModelReply({"observations": [observation("foreign-source")], "issues": []}, "test-provider")
        with patch("vte_review.workspace.configured_model", return_value=(BadSourceModel(), {"model": "test-provider"})):
            with self.assertRaisesRegex(ValueError, "observation or source"):
                self.app.extract_sources({"source_ids": [self.source]})
        files = list((Path(self.temp.name) / "intakes").glob("INT-*.json"))
        saved = json.loads(files[0].read_text())
        self.assertIn("validation_error", saved)
        self.assertNotIn("output", saved)
        self.assertEqual(saved["raw_output"]["observations"][0]["source_id"], "foreign-source")

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
