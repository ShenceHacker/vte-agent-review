import asyncio
import base64
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from vte_review.demo import DEMO_EVIDENCE
from vte_review.intake import SourceStore
from vte_review.longitudinal import plan_sources, stage_heading
from vte_review.providers import ModelReply
from vte_review.server import App
from tests.test_automatic_intake import IntakeTestModel, observation
from tests.test_clinical_workspace import png


def encoded(value):
    return base64.b64encode(value).decode()


def document():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("word/document.xml", '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>
        <w:p><w:r><w:t>Admission</w:t></w:r></w:p><w:p><w:r><w:t>Early DVT</w:t></w:r></w:p>
        <w:p><w:r><w:t>Discharge</w:t></w:r></w:p><w:p><w:r><w:t>Later prescription</w:t><a:blip r:embed="rId1"/></w:r></w:p>
        </w:body></w:document>''')
        z.writestr("word/_rels/document.xml.rels", '<Relationships><Relationship Id="rId1" Target="media/image1.png"/></Relationships>')
        z.writestr("word/media/image1.png", png())
    return output.getvalue()


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SourceStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_ordered_docx_keeps_later_image_out_of_early_scope(self):
        source = self.store.ingest("record.docx", encoded(document()))
        nodes = plan_sources(self.store, [source["id"]])
        self.assertEqual(len(nodes), 2)
        self.assertFalse(nodes[0]["chunks"][0]["images"])
        self.assertEqual(nodes[1]["chunks"][0]["images"], source["images"])
        scope = self.store.bundle([c["source_id"] for c in nodes[0]["chunks"]])
        self.assertFalse(scope["image_ids"])
        self.assertNotIn("Later", json.dumps(scope))

    def test_block_bounds_duplicate_visits_and_explicit_dates(self):
        text = "Admission\n" + "x"*7100 + "\n术后3周\nFollow-up details\n术后3周\nFollow-up details"
        src = self.store.ingest("case.txt", encoded(text.encode()))
        nodes = plan_sources(self.store, [src["id"]])
        self.assertEqual(len(nodes), 2)
        self.assertTrue(all(len(c["text"]) <= 3000 for n in nodes for c in n["chunks"]))
        self.assertEqual(len(nodes[1]["chunks"]), 1)
        self.assertEqual(stage_heading("日期：2026-10-01"), ("2026-10-01", "2026-10-01", "date"))
        self.assertIsNone(stage_heading("Creatinine measured on 2026-10-01"))
        self.assertIsNone(stage_heading("2026/4/6：右侧下肢血管超声"))
        self.assertEqual(stage_heading("2026-10-01：随访情况"), ("2026-10-01", "2026-10-01", "date"))

    def test_archive_members_stay_in_storage(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../../one.docx", document())
        sources = self.store.ingest_archive("cases.zip", encoded(archive.getvalue()))
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["name"], "one.docx")
        with self.assertRaises(ValueError):
            self.store.ingest_archive("cases.zip", encoded(b"bad archive"))

    def test_history_preamble_is_not_an_extra_visit(self):
        src = self.store.ingest("case.txt", encoded(b"Patient history\n2026-10-01\nDVT\n2026-10-07\nFollow-up"))
        nodes = plan_sources(self.store, [src["id"]])
        self.assertEqual([n["label"] for n in nodes], ["2026-10-01", "2026-10-07"])
        self.assertIn("Patient history", " ".join(c["text"] for c in nodes[0]["chunks"]))

    def test_table_row_preserves_label_value_and_unit(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Creatinine</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>120</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>umol/L</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        src = self.store.ingest("table.docx", encoded(output.getvalue()))
        blocks = self.store.ordered_blocks(src["id"])
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["text"], "Creatinine | 120 | umol/L")


class TimelineModel(IntakeTestModel):
    extracted = []
    assessed = []
    failures = set()
    active = 0
    max_active = 0
    lock = threading.Lock()

    async def extract(self, payload, images):
        src = payload["sources"][0]
        with self.lock:
            self.extracted.append(src["text"])
            type(self).active += 1
            type(self).max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(.025 if payload["time_label"] == "Admission" else .1)
            with self.lock:
                if payload["time_label"] in self.failures:
                    self.failures.remove(payload["time_label"])
                    raise ValueError("Transient extraction error")
            rows = [observation(src["id"], "vte_type_site", "Proximal DVT")]
            if "EARLY_LAB" in src["text"]:
                rows.append(observation(src["id"], "serum_creatinine", 99, unit="umol/L"))
            return ModelReply({"observations": rows, "issues": []}, "timeline-test")
        finally:
            with self.lock:
                type(self).active -= 1

    async def complete(self, task, role, payload):
        if task == "assess":
            with self.lock:
                self.assessed.append(deepcopy(payload["case"]))
        return await super().complete(task, role, payload)


class LongitudinalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(Path(self.temp.name))
        self.app.vectors.enabled = False
        for d in DEMO_EVIDENCE:
            self.app.knowledge.add_many([{k: (False if k == "synthetic" else v) for k, v in d.items() if k != "id"}])
        TimelineModel.extracted, TimelineModel.assessed, TimelineModel.failures = [], [], set()
        TimelineModel.active = TimelineModel.max_active = 0
        self.patches = [patch("vte_review.longitudinal.configured_model", side_effect=lambda *a, **k: (TimelineModel(), {"model": "timeline-test"})),
                        patch("vte_review.providers.ChatCompletionsModel", TimelineModel)]
        for p in self.patches:
            p.start()
        self.options = {"llm": {"model": "timeline-test", "api_key": "TEST_SECRET"}, "settings": {"timeout": 5}}

    def tearDown(self):
        for job in self.app.series_jobs.values():
            with job.cond:
                job.cond.wait_for(lambda: job.done, timeout=10)
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def source(self, value):
        return self.app.sources.ingest("case.txt", encoded(value.encode()))["id"]

    def run_series(self, ids, **extra):
        series_id = self.app.start_series({**self.options, "source_ids": ids, **extra})
        return self.wait(series_id)

    def wait(self, series_id):
        job = self.app.series_jobs[series_id]
        with job.cond:
            self.assertTrue(job.cond.wait_for(lambda: job.done, timeout=15), "Timeline did not finish")
        return self.app.series_detail(series_id)

    def test_chronological_memory_no_future_leak_and_no_lab_carry_forward(self):
        item = self.run_series([self.source("Admission\nEARLY_LAB DVT\nDischarge\nLATER_SENTINEL stopped drug")])
        self.assertEqual(item["status"], "complete", item.get("error"))
        self.assertEqual(item["completed_nodes"], 2)
        early = [c for c in TimelineModel.assessed if c["longitudinal"]["time_label"] == "Admission"]
        late = [c for c in TimelineModel.assessed if c["longitudinal"]["time_label"] == "Discharge"]
        self.assertTrue(early and late)
        self.assertNotIn("LATER_SENTINEL", json.dumps(early))
        self.assertNotIn("serum_creatinine", json.dumps(late[0]["observations"]))
        self.assertIn("serum_creatinine", json.dumps(late[0]["longitudinal"]["prior_events"]))
        self.assertEqual(late[0]["longitudinal"]["previous_recommendation"]["kind"], "model_suggestion")
        self.assertFalse(self.app.memory.patients())
        saved = "".join(p.read_text(encoding="utf-8") for p in Path(self.temp.name).rglob("*.json"))
        self.assertNotIn("TEST_SECRET", saved)

    def test_failed_chunk_retry_reuses_success_and_resumes_after_restart(self):
        TimelineModel.failures = {"Discharge"}
        item = self.run_series([self.source("Admission\nDVT EARLY\nDischarge\nDVT LATE")])
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["completed_nodes"], 1)
        early_run = item["nodes"][0]["run_id"]
        self.app = App(Path(self.temp.name))
        self.app.vectors.enabled = False
        self.app.retry_series(item["id"], self.options)
        item = self.wait(item["id"])
        self.assertEqual(item["status"], "complete", item.get("error"))
        self.assertEqual(item["nodes"][0]["run_id"], early_run)
        self.assertEqual(sum("EARLY" in t for t in TimelineModel.extracted), 1)
        self.assertEqual(sum("LATE" in t for t in TimelineModel.extracted), 2)

    def test_followup_preserves_patient_reuses_old_node_without_overwriting(self):
        parent = self.run_series([self.source("Admission\nDVT ORIGINAL")])
        follow = self.run_series([self.source("NEW FOLLOWUP without a date")], parent_id=parent["id"])
        self.assertEqual(follow["status"], "complete", follow.get("error"))
        self.assertEqual(follow["patient_id"], parent["patient_id"])
        self.assertEqual(follow["node_count"], 2)
        self.assertTrue(follow["nodes"][0]["reused"])
        self.assertEqual(follow["nodes"][0]["run_id"], parent["nodes"][0]["run_id"])
        self.assertEqual(self.app.series_detail(parent["id"])["node_count"], 1)
        other = self.run_series([self.source("Admission\nDVT OTHER PATIENT")])
        self.assertNotEqual(other["patient_id"], parent["patient_id"])
        self.assertIsNone(other["nodes"][0].get("reused"))

    def test_parallel_blocks_and_progress_precede_final_result(self):
        source = self.source("\n".join([f"2026-10-0{i}\nDVT visit {i}" for i in range(1, 7)]))
        item = self.run_series([source])
        self.assertEqual(item["status"], "complete", item.get("error"))
        self.assertGreater(TimelineModel.max_active, 1)
        self.assertLessEqual(TimelineModel.max_active, 3)
        events = self.app.series_jobs[item["id"]].events
        self.assertLess(next(i for i,e in enumerate(events) if e["event"] == "chunk_completed"), next(i for i,e in enumerate(events) if e["event"] == "completed"))
        self.assertEqual([e["seq"] for e in events], list(range(1,len(events)+1)))

    def test_product_rejects_demo(self):
        with self.assertRaisesRegex(ValueError, "debug"):
            self.app.start({"mode": "demo"})
        self.assertEqual(self.app.info()["scenarios"], {})

    def test_software_qa_records_only_listed_in_debug_workspace(self):
        item = self.run_series([self.source("Admission\nDVT QA")])
        item["purpose"] = "software_test"
        path = self.app.series_path(item["id"])/"series.json"
        path.write_text(json.dumps(item), encoding="utf-8")
        run = self.app.run_dir(item["nodes"][0]["run_id"])
        meta = json.loads((run/"meta.json").read_text(encoding="utf-8"))
        meta["purpose"] = "software_test"
        (run/"meta.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertEqual(self.app.list_series(), [])
        self.assertEqual(self.app.list_runs(), [])
        self.app.allow_debug = True
        self.assertEqual(len(self.app.list_series()), 1)
        self.assertEqual(len(self.app.list_runs()), 1)

    def test_review_failure_keeps_coordinator_draft_with_incomplete_marker(self):
        class InterruptedReview(TimelineModel):
            async def complete(self, task, role, payload):
                if task == "review" and role == "C":
                    raise TimeoutError()
                return await super().complete(task, role, payload)
        with patch("vte_review.providers.ChatCompletionsModel", InterruptedReview):
            item = self.run_series([self.source("Admission\nDVT")])
        self.assertEqual(item["status"], "failed")
        self.assertTrue(item["nodes"][0]["recommendation"]["shared_plan"])
        self.assertTrue(item["nodes"][0]["draft_unreviewed"])
        self.assertEqual(item["completed_nodes"], 0)


if __name__ == "__main__":
    unittest.main()
