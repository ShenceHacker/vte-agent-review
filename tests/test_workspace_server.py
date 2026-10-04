import base64
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from vte_review.demo import DEMO_EVIDENCE
from vte_review.providers import ModelReply
from vte_review.server import make_server
from tests.test_clinical_workspace import AT, EARLIER, case, entry, png


class WorkspaceServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=make_server(port=0,runs_dir=self.temp.name)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def request(self,path,body=None):
        data=None if body is None else json.dumps(body).encode()
        with urlopen(Request(self.base+path,data=data,headers={"Content-Type":"application/json"})) as res:
            raw=res.read()
            return json.loads(raw) if "json" in res.headers.get("Content-Type","") else raw
    def completed(self,run):
        for _ in range(100):
            result=self.request("/api/runs/"+run)
            if result["status"]!="running":return result
            time.sleep(.02)
        self.fail("Run did not finish")
    def test_memory_api_and_patient_time_scope(self):
        self.request("/api/patients/SYN-P1/entries",{"entry":entry(),"actor":"QA"})
        self.assertEqual(len(self.request("/api/patients")["patients"]),1)
        snap=self.request("/api/patients/SYN-P1/snapshot",{"as_of":AT,"encounter_id":"V2"})
        self.assertEqual(len(snap["entries"]),1)
        self.assertEqual(len(snap["sha256"]),64)
    def test_upload_and_clinical_check(self):
        source=self.request("/api/sources",{"filename":"lab.png","content_base64":base64.b64encode(png()).decode()})
        self.assertEqual(self.request("/api/sources/"+source["id"])["id"],source["id"])
        self.assertEqual(self.request("/api/sources/"+source["id"]+"/image"),png())
        self.assertFalse(self.request("/api/clinical/check",{"case":case()})["blocking"])
    def test_extraction_boundary_marks_output_unverified_and_no_key_saved(self):
        source=self.request("/api/sources",{"filename":"lab.png","content_base64":base64.b64encode(png()).decode()})
        class Mock:
            async def extract(self,payload,images):
                assert images and payload["image_ids"]==[source["id"]]
                return ModelReply({"observations":[{"key":"hemoglobin","value":130,"unit":"g/L","observed_at":AT,"available_at":AT,"source_id":source["id"],"location":"row 2","status":"confirmed"}],"issues":[]},"mock")
            async def close(self):pass
        with patch("vte_review.workspace.configured_model",return_value=(Mock(),{"model":"mock"})):
            data=self.request("/api/intake/extract",{"source_ids":[source["id"]],"llm":{"api_key":"SENSITIVE"}})
        self.assertEqual(data["output"]["observations"][0]["status"],"unverified")
        logs="".join(p.read_text() for p in Path(self.temp.name).rglob("INT-*.json"))
        self.assertNotIn("SENSITIVE",logs)
    def test_labels_never_reach_model_context_and_memory_frozen(self):
        old=self.request("/api/patients/SYN-P1/entries",{"entry":entry(),"actor":"QA"})
        label={"kind":"outcome","content":"HELD_OUT_SENTINEL","source":"synthetic follow-up","recorded_by":"QA","occurred_at":AT}
        run=self.request("/api/runs",{"mode":"demo","pace":0,"case":case(),"evidence":DEMO_EVIDENCE,"research_labels":[label]})["id"]
        result=self.completed(run)
        self.assertEqual(result["status"],"approved")
        self.assertNotIn("HELD_OUT_SENTINEL",json.dumps(result["result"]))
        self.assertNotIn("HELD_OUT_SENTINEL",(Path(self.temp.name)/run/"events.jsonl").read_text())
        self.assertEqual(result["research_labels"][0]["content"],"HELD_OUT_SENTINEL")
        self.request("/api/patients/SYN-P1/entries",{"entry":entry(content="later edit"),"actor":"QA"})
        self.assertEqual(len(result["result"]["memory_snapshot"]["entries"]),1)
        self.assertEqual(result["result"]["memory_snapshot"]["entries"][0]["id"],old["id"])
        self.request("/api/runs/"+run+"/labels",{"labels":[{**label,"kind":"expert_audit"}]})
        self.assertEqual(len(self.request("/api/runs/"+run)["research_labels"]),2)
    def test_invalid_memory_requests_rejected(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/patients/P1/entries",{"entry":entry(),"actor":""})
        self.assertEqual(err.exception.code,400)
        with self.assertRaises(HTTPError):
            self.request("/api/patients/P1/snapshot",{"as_of":"yesterday"})

    def test_information_api_and_followup_preserve_original(self):
        from tests.test_conditional_information import response
        c=case();c['facts']['active_bleeding']=None
        parent=self.request('/api/runs',{'mode':'demo','pace':0,'case':c,'evidence':DEMO_EVIDENCE})['id']
        old=self.completed(parent)
        self.assertEqual(len(old['information_followup']['table']),22)
        saved=self.request('/api/runs/'+parent+'/information',{'responses':[response()]})
        self.assertTrue(saved['original_report_unchanged'])
        self.assertEqual(self.request('/api/runs/'+parent)['result'],old['result'])
        evidence=self.request('/api/runs/'+parent+'/evidence.json')
        child=self.request('/api/runs',{'mode':'demo','pace':0,'case':saved['case'],'evidence':evidence,'parent_run_id':parent})['id']
        result=self.completed(child)
        self.assertEqual(result['meta']['parent_run_id'],parent)
        self.assertIs(result['result']['clinical_checks']['normalized_facts']['active_bleeding'],False)
        self.assertIsNone(result['case']['facts']['active_bleeding'])
        self.assertIsNone(self.request('/api/runs/'+parent)['case']['facts']['active_bleeding'])
        with self.assertRaises(HTTPError):
            self.request('/api/runs/'+parent+'/information',{'responses':[{**response(),'field':'serum_creatinine'}]})
        self.assertEqual(len(self.request('/api/runs/'+parent)['information_followup']['history']),1)
