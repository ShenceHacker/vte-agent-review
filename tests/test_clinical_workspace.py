import base64
import io
import json
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from vte_review.clinical import (calculate_crcl, clinical_check, convert_unit,
                                 treatment_days, medication_quantity, check_regimen)
from vte_review.clinical_tools import ClinicalTools
from vte_review.contracts import ContractError, validate_case
from vte_review.demo import DEMO_EVIDENCE, DemoModel
from vte_review.intake import SourceStore, validate_extraction
from vte_review.patient_memory import PatientMemory
from vte_review.retrieval import EvidenceIndex
from vte_review.workflow import Workflow

AT = "2026-06-01T09:00:00+08:00"
LATER = "2026-06-02T09:00:00+08:00"
EARLIER = "2026-05-01T09:00:00+08:00"


def case():
    return {"case_id": "SYN-TOOLS", "question": "Synthetic VTE review", "missing_information": [],
            "patient": {"patient_id": "SYN-P1", "encounter_id": "V2", "decision_at": AT},
            "task_type": "generate_plan", "facts": {
                "age_years": 60, "sex": "female", "weight_kg": 60,
                "vte_type_site": "Synthetic proximal DVT", "diagnosis_date": "2026-05-31", "treatment_stage": "initial",
                "serum_creatinine": {"value": 88.4, "unit": "umol/L", "observed_at": AT}, "renal_stable": True,
                "hemoglobin": {"value": 130, "unit": "g/L", "observed_at": AT},
                "platelets": {"value": 220, "unit": "10^9/L", "observed_at": AT},
                "active_bleeding": False, "liver_status": "No recorded abnormality in synthetic fixture",
                "current_anticoagulation": "Explicitly none", "concomitant_medications": []}}


def entry(**updates):
    return {"kind": "fact", "topic": "history", "content": "Synthetic history", "occurred_at": EARLIER,
            "available_at": EARLIER, "source": "synthetic report", "roles": ["A", "B", "C", "D"], **updates}


def png():
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(out, format="PNG")
    return out.getvalue()


class ClinicalTests(unittest.TestCase):
    def test_crcl_conversion_and_sex_coefficient(self):
        self.assertAlmostEqual(calculate_crcl(60, "female", 60, 88.4, "umol/L", True)["value"], 56.67, places=2)
        self.assertAlmostEqual(calculate_crcl(60, "male", 60, 1, "mg/dL", True)["value"], 66.67, places=2)

    def test_crcl_rejects_aki_and_bad_inputs(self):
        self.assertEqual(calculate_crcl(60, "female", 60, 1, "mg/dL", False)["status"], "not_applicable")
        for value in [0, True, float("nan"), "88"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_crcl(60, "female", 60, value, "mg/dL", True)
        with self.assertRaises(ValueError):
            calculate_crcl(60, "female", 60, 1, "mg/dL", "unknown")

    def test_unit_conversion_not_guessing_concentration(self):
        self.assertEqual(convert_unit(1, "mg/dL", "umol/L", "creatinine")["value"], 88.4)
        self.assertEqual(convert_unit(9.3, "g/dL", "g/L")["value"], 93)
        with self.assertRaises(ValueError):
            convert_unit(.4, "mL", "mg")

    def test_drug_quantity_and_frequency_are_distinct(self):
        a = medication_quantity(1, "tablet", 2, 10, "mg/tablet")
        b = medication_quantity(2, "tablet", 1, 10, "mg/tablet")
        self.assertEqual(a["daily_total_mg"], b["daily_total_mg"])
        self.assertNotEqual(a["single_dose_mg"], b["single_dose_mg"])
        self.assertEqual(medication_quantity(.4, "mL", 1)["status"], "needs_information")
        with self.assertRaises(ValueError):
            medication_quantity(4000, "IU", 1)

    def test_regimen_scope_stage_and_jurisdiction(self):
        args = dict(drug="rivaroxaban", indication="adult_dvt_pe", stage="initial_days_1_21", dose_mg=15, frequency_per_day=2, jurisdiction="US")
        self.assertEqual(check_regimen(**args)["status"], "pattern_matches")
        self.assertEqual(check_regimen(**{**args, "dose_mg": 10})["status"], "requires_review")
        self.assertEqual(check_regimen(**{**args, "jurisdiction": "CN"})["status"], "not_covered")
        self.assertEqual(check_regimen(**{**args, "indication": "AF"})["status"], "not_covered")

    def test_treatment_days(self):
        self.assertEqual(treatment_days("2026-05-31", "2026-06-01")["treatment_day_inclusive"], 2)
        with self.assertRaises(ValueError):
            treatment_days("2026-06-01", "2026-05-31")

    def test_false_and_empty_medication_list_are_known(self):
        result = clinical_check(case())
        self.assertFalse(result["blocking"])
        self.assertEqual(len(result["calculations"]), 1)

    def test_missing_noncritical_does_not_gate_all(self):
        result = clinical_check(case())
        self.assertTrue(any(i["code"] == "missing_patient_constraints" for i in result["issues"]))
        self.assertFalse(result["blocking"])

    def test_critical_missing_becomes_condition_not_stop(self):
        data = case(); del data["facts"]["serum_creatinine"]
        result = clinical_check(data)
        self.assertTrue(result["conditional"])
        self.assertFalse(result["blocking"])
        self.assertFalse(result["input_blocked"])

    def test_future_labs_and_bad_units_not_calculated(self):
        for updates in ({"observed_at": LATER}, {"unit": "unknown"}):
            data = case(); data["facts"]["serum_creatinine"].update(updates)
            result = clinical_check(data)
            self.assertTrue(result["blocking"] or result["conditional"])
            self.assertFalse(result["calculations"])

    def test_unstable_renal_and_ambiguous_bleeding_status_gate(self):
        data = case(); data["facts"]["renal_stable"] = False
        self.assertTrue(clinical_check(data)["blocking"])

    def test_late_available_lab_future_diagnosis_and_missing_decision_time(self):
        data=case();data["facts"]["serum_creatinine"]["available_at"]=LATER
        self.assertTrue(clinical_check(data)["input_blocked"])
        self.assertFalse(clinical_check(data)["calculations"])
        data=case();data["facts"]["diagnosis_date"]="2026-06-02"
        self.assertTrue(clinical_check(data)["input_blocked"])
        data=case();del data["patient"]
        self.assertTrue(clinical_check(data)["input_blocked"])
        data = case(); data["facts"]["active_bleeding"] = "probably no"
        self.assertTrue(clinical_check(data)["blocking"])

    def test_conflicts_include_units_and_same_instant(self):
        data = case(); data["observations"] = [
            {"key": "serum_creatinine", "value": 88.4, "unit": "mg/dL", "observed_at": AT,
             "available_at": AT, "source_id": "source", "location": "row 1", "status": "confirmed"}]
        self.assertTrue(clinical_check(data)["input_blocked"])
        data["observations"][0]["status"] = "unverified"
        data["observations"][0]["observed_at"] = ""
        self.assertTrue(clinical_check(data)["input_blocked"])

    def test_generation_cannot_take_target_plan_or_labels(self):
        for addition in ({"candidate_plan": "held-out plan"}, {"research_labels": []}):
            with self.assertRaises(ContractError):
                validate_case({**case(), **addition})
        validate_case({**case(), "task_type": "review_plan", "candidate_plan": "Plan being audited"})


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.store = PatientMemory(Path(self.temp.name) / "patients.db")
    def tearDown(self): self.temp.cleanup()
    def test_future_and_late_available_records_excluded(self):
        self.store.add("P1", entry(), actor="Tester")
        self.store.add("P1", entry(available_at=LATER), actor="Tester")
        self.store.add("P1", entry(occurred_at=LATER, available_at=LATER), actor="Tester")
        self.store.add("P2", entry(), actor="Tester")
        self.assertEqual(len(self.store.snapshot("P1", AT)["entries"]), 1)

    def test_correction_is_append_only_and_time_specific(self):
        old = self.store.add("P1", entry(), actor="Tester")
        new = self.store.add("P1", entry(content="Correction", occurred_at=AT, available_at=AT, supersedes=old["id"]), actor="Tester")
        self.assertEqual(self.store.snapshot("P1", EARLIER)["entries"][0]["id"], old["id"])
        self.assertEqual(self.store.snapshot("P1", AT)["entries"][0]["id"], new["id"])
        self.assertEqual(len(self.store.history("P1")), 2)
        with self.assertRaises(ValueError):
            self.store.add("P2", entry(supersedes=old["id"]), actor="Tester")

    def test_model_suggestion_cannot_become_fact_by_acceptance(self):
        proposal = self.store.add("P1", entry(kind="model_suggestion"), actor="D", model=True)
        self.assertEqual(self.store.snapshot("P1", AT)["entries"], [])
        self.store.resolve("P1", proposal["id"], {"action": "accept", "actor": "Tester"})
        self.assertEqual(self.store.snapshot("P1", AT)["entries"], [])
        with self.assertRaises(ValueError):
            self.store.add("P1", entry(), actor="D", model=True)
        with self.assertRaises(ValueError):
            self.store.resolve("P1", proposal["id"], {"action": "reject", "actor": "Tester"})

    def test_physician_plan_held_out_by_encounter(self):
        self.store.add("P1", entry(kind="clinician_decision", encounter_id="V2"), actor="Tester")
        self.store.add("P1", entry(kind="actual_treatment", encounter_id="V1"), actor="Tester")
        self.assertEqual(len(self.store.snapshot("P1", AT, encounter_id="V2")["entries"]), 1)
        self.assertEqual(len(self.store.snapshot("P1", AT, task_type="review_plan", encounter_id="V2")["entries"]), 2)

    def test_timezone_required_and_id_safe(self):
        with self.assertRaises(ValueError): self.store.add("../P1", entry(), actor="Tester")
        with self.assertRaises(ValueError): self.store.snapshot("P1", "2026-06-01")
        with self.assertRaises(ValueError): self.store.add("P1", entry(occurred_at=LATER, available_at=AT), actor="Tester")


class IntakeTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.store=SourceStore(Path(self.temp.name))
    def tearDown(self): self.temp.cleanup()
    def test_image_upload_dedup_and_read(self):
        raw=png(); enc=base64.b64encode(raw).decode()
        a=self.store.ingest("lab.png", enc); b=self.store.ingest("other.png", enc)
        self.assertEqual(a["id"], b["id"])
        self.assertTrue(self.store.image(a["id"])["data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(self.store.bundle([a["id"]])["image_ids"], [a["id"]])
    def test_docx_text_and_embedded_images(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,"w") as z:
            z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic lab</w:t></w:r></w:p></w:body></w:document>')
            z.writestr("word/media/image1.png", png())
        doc=self.store.ingest("case.docx", base64.b64encode(buffer.getvalue()).decode())
        self.assertIn("Synthetic lab", doc["text"]); self.assertEqual(len(doc["images"]),1)
    def test_invalid_payload_and_path_rejected(self):
        for name,raw in [("x.png",b"bad"),("x.docx",b"bad"),("x.png",b"\x89PNG\r\n\x1a\nBAD")]:
            with self.assertRaises(ValueError): self.store.ingest(name,base64.b64encode(raw).decode())
        with self.assertRaises(ValueError): self.store.get("../../secret")
    def test_extraction_cannot_confirm_itself(self):
        observation={"key":"hemoglobin","value":None,"unit":"","observed_at":"","available_at":"","source_id":"SRC-1","location":"clipped row","status":"confirmed"}
        result=validate_extraction({"observations":[observation],"issues":[]},{"SRC-1"})
        self.assertEqual(result["observations"][0]["status"],"unverified")
        with self.assertRaises(ValueError): validate_extraction(result,{"SRC-2"})

    def test_long_text_never_silently_truncated(self):
        with self.assertRaises(ValueError):
            self.store.ingest("long.txt", base64.b64encode(b"a"*200001).decode())


class ToolTests(unittest.TestCase):
    def session(self,role): return ClinicalTools(role,case(),EvidenceIndex(DEMO_EVIDENCE))
    def test_role_permissions_and_unknown_tools(self):
        self.assertEqual(self.session("A").execute("calculate_crcl",{},"1")["status"],"error")
        self.assertEqual(self.session("B").execute("calculate_crcl",{},"1")["status"],"calculated")
        self.assertEqual(self.session("D").execute("shell",{"command":"bad"},"1")["status"],"error")
    def test_tool_arguments_and_traces(self):
        session=self.session("B")
        self.assertEqual(session.execute("calculate_crcl",{"creatinine":999},"1")["status"],"error")
        self.assertEqual(session.execute("convert_units",{"value":float("nan"),"from_unit":"mg","to_unit":"g","analyte":""},"2")["status"],"error")
        self.assertEqual(len(session.trace),2)
    def test_sourced_memory_proposal_permission(self):
        args={"topic":"follow-up","content":"Synthetic note","source_ids":["SYN-TOOLS"],"roles":["C"]}
        self.assertEqual(self.session("D").execute("propose_memory_update",args,"1")["status"],"pending_human_review")
        self.assertEqual(self.session("A").execute("propose_memory_update",args,"1")["status"],"error")
        self.assertEqual(self.session("D").execute("propose_memory_update",{**args,"source_ids":["other-patient"]},"1")["status"],"error")

    def test_image_tool_cannot_open_unattached_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SourceStore(Path(tmp)); a=store.ingest("one.png",base64.b64encode(png()).decode())
            data=case();data["source_ids"]=[a["id"]]
            session=ClinicalTools("B",data,EvidenceIndex(DEMO_EVIDENCE),sources=store)
            self.assertEqual(session.execute("view_source_images",{"source_ids":["SRC-"+"0"*32]},"x")["status"],"error")
            result=session.execute("view_source_images",{"source_ids":[a["id"]]},"y")
            self.assertEqual(len(session.images(result)),1)


class IntegratedWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_feed_same_agent_and_audited(self):
        class ToolsModel(DemoModel):
            async def complete_with_tools(self,task,role,payload,session):
                if role=="B":
                    result=session.execute("calculate_crcl",{},task+role)
                    assert result["value"]==56.67
                if task=="synthesize":
                    session.execute("propose_memory_update",{"topic":"test","content":"Synthetic proposal","source_ids":[payload["case"]["case_id"]],"roles":["A"]},"propose")
                return await self.complete(task,role,payload)
        result=await Workflow(ToolsModel(delay=0),EvidenceIndex(DEMO_EVIDENCE)).run(case())
        self.assertEqual(result["status"],"approved")
        self.assertEqual(result["metrics"]["tool_calls"],3)
        self.assertEqual(len(result["memory_proposals"]),1)

    async def test_missing_labs_not_false_approval_and_other_assessments_run(self):
        data=case(); del data["facts"]["serum_creatinine"]
        result=await Workflow(DemoModel(delay=0),EvidenceIndex(DEMO_EVIDENCE)).run(data)
        self.assertEqual(result["reason"],"conditional_assumptions_missing")
        self.assertIsNotNone(result["draft"]); self.assertIsNone(result["final"])

    async def test_future_source_stops_before_model(self):
        data=case(); data["facts"]["serum_creatinine"]["observed_at"]=LATER
        result=await Workflow(DemoModel(delay=0),EvidenceIndex(DEMO_EVIDENCE)).run(data)
        self.assertEqual(result["reason"],"source_verification_required")
        self.assertEqual(result["metrics"]["calls"],0)

    async def test_memory_patient_mismatch_fails(self):
        result=await Workflow(DemoModel(delay=0),EvidenceIndex(DEMO_EVIDENCE), memory_snapshot={"patient_id":"OTHER","entries":[entry()]}).run(case())
        self.assertEqual(result["status"],"failed")

    async def test_excluded_observation_not_in_agent_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SourceStore(Path(tmp)); source=store.ingest("one.png",base64.b64encode(png()).decode())
            data=case(); data.update(source_ids=[source["id"]],source_context={source["id"]:{"available_at":AT,"reviewer":"QA"}}, observations=[{
                "key":"excluded","value":"EXCLUDED_SENTINEL","unit":"","observed_at":"","available_at":"","source_id":source["id"],"location":"row","status":"excluded"}])
            result=await Workflow(DemoModel(delay=0),EvidenceIndex(DEMO_EVIDENCE),sources=store).run(data)
            self.assertEqual(result["status"],"approved")
            self.assertNotIn("EXCLUDED_SENTINEL",json.dumps(result))
