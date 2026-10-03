"""Tests for the local web server and GUI endpoints."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from vte_review.demo import DEMO_CASE, DEMO_EVIDENCE
from vte_review.server import App, make_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.runs_dir = Path(cls.temp_dir.name) / "runs"
        cls.runs_dir.mkdir(parents=True, exist_ok=True)
        cls.server = make_server(host="127.0.0.1", port=0, runs_dir=cls.runs_dir)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp_dir.cleanup()

    def request(self, path: str, method: str = "GET", body: dict | None = None, headers: dict | None = None):
        url = self.base_url + path
        hdrs = headers or {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=hdrs, method=method)
        with urlopen(req) as resp:
            content = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return resp.status, json.loads(content.decode("utf-8"))
            return resp.status, content

    def test_static_index_and_assets(self):
        status, content = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"VTE Review", content)

        status, css = self.request("/static/styles.css")
        self.assertEqual(status, 200)
        self.assertIn(b":root", css)

        status, js = self.request("/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"VTE Review", js)

    def test_info_endpoint(self):
        status, info = self.request("/api/info")
        self.assertEqual(status, 200)
        self.assertIn("version", info)
        self.assertIn("scenarios", info)
        self.assertEqual(info["roles"]["A"], "Anticoagulation benefit and duration")

    def test_demo_endpoint(self):
        status, data = self.request("/api/demo")
        self.assertEqual(status, 200)
        self.assertEqual(data["case"]["case_id"], DEMO_CASE["case_id"])
        self.assertTrue(len(data["evidence"]) >= 1)

    def test_validation_endpoint(self):
        status, res = self.request("/api/validate", method="POST", body={
            "case": DEMO_CASE,
            "evidence": DEMO_EVIDENCE,
        })
        self.assertEqual(status, 200)
        self.assertTrue(res["case"]["ok"])
        self.assertTrue(res["evidence"]["ok"])
        self.assertEqual(res["evidence"]["synthetic"], 1)

    def test_run_demo_and_signoff(self):
        # 1. Start a demo run with fast pace
        status, start_res = self.request("/api/runs", method="POST", body={
            "mode": "demo",
            "scenario": "targeted",
            "pace": 0.0,
            "case": DEMO_CASE,
            "evidence": DEMO_EVIDENCE,
        })
        self.assertEqual(status, 201)
        run_id = start_res["id"]
        self.assertTrue(run_id)

        # 2. Wait for completion
        import time
        max_wait = 5.0
        start_t = time.time()
        detail = None
        while time.time() - start_t < max_wait:
            status, detail = self.request(f"/api/runs/{run_id}")
            self.assertEqual(status, 200)
            if detail["status"] != "running":
                break
            time.sleep(0.1)

        self.assertIsNotNone(detail)
        self.assertEqual(detail["status"], "approved")
        self.assertIsNotNone(detail["result"])
        self.assertIn("draft", detail["result"])

        # 3. Perform physician signoff
        status, sign_res = self.request(f"/api/runs/{run_id}/signoff", method="POST", body={
            "decision": "accept",
            "reviewer": "Dr. Zhang",
            "comment": "经核对，方案符合预期，同意执行。",
        })
        self.assertEqual(status, 201)
        self.assertEqual(sign_res["reviewer"], "Dr. Zhang")
        self.assertEqual(sign_res["decision"], "accept")
        self.assertTrue(sign_res["draft_sha256"])

        # 4. Verify detail reflects signoff
        status, detail_after = self.request(f"/api/runs/{run_id}")
        self.assertEqual(len(detail_after["signoffs"]), 1)
        self.assertEqual(detail_after["signoff"]["reviewer"], "Dr. Zhang")

    def test_forbidden_host_header(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/info", headers={"Host": "evil.com"})
        self.assertEqual(ctx.exception.code, 403)

    def test_invalid_settings_do_not_create_runs(self):
        before = len(self.server.app.list_runs())
        for settings in ("bad", {"timeout": "nan"}, {"timeout": "inf"},
                         {"top_k": 1.5}, {"concurrency": 0}, {"max_revisions": -1}):
            with self.subTest(settings=settings), self.assertRaises(HTTPError) as ctx:
                self.request("/api/runs", method="POST", body={"settings": settings})
            self.assertEqual(ctx.exception.code, 400)
        self.assertEqual(len(self.server.app.list_runs()), before)

    def test_invalid_stream_cursor_is_a_client_error(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/runs/missing/stream?after=not-a-number")
        self.assertEqual(ctx.exception.code, 400)

    def test_foreign_origin_cannot_start_run(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/runs", method="POST", body={}, headers={"Origin": "https://example.com"})
        self.assertEqual(ctx.exception.code, 403)

    def test_completed_stream_replays_and_exports_exact_reviewed_result(self):
        _, start = self.request("/api/runs", method="POST", body={"scenario": "targeted", "pace": 0})
        run_id = start["id"]
        _, stream = self.request(f"/api/runs/{run_id}/stream")
        self.assertIn(b"event: done", stream)
        events = [json.loads(line[6:]) for line in stream.decode().splitlines() if line.startswith("data: {")][:-1]
        rounds = [event["roles"] for event in events if event.get("event") == "review_round"]
        self.assertEqual(rounds, [["A", "B", "C"], ["A"]])
        self.assertTrue(all("input" not in event for event in events))
        _, export = self.request(f"/api/runs/{run_id}/result.json")
        self.assertEqual(export["status"], "approved")
        self.assertEqual(export["final"], export["draft"])
        _, report = self.request(f"/api/runs/{run_id}/report.md")
        self.assertIn(export["draft"]["sections"]["A"]["text"], report.decode())

    def test_knowledge_add_search_snapshot_and_run(self):
        document = {key: value for key, value in DEMO_EVIDENCE[0].items() if key != "id"}
        _, added = self.request("/api/knowledge", method="POST", body=document)
        document_id = added["ids"][0]
        _, found = self.request("/api/knowledge/search?q=VTE&role=A")
        self.assertTrue(any(row["document_id"] == document_id for row in found["results"]))
        _, start = self.request("/api/runs", method="POST", body={"mode": "demo", "knowledge_ids": [document_id], "pace": 0})
        run_id = start["id"]
        self.request(f"/api/runs/{run_id}/stream")
        _, detail = self.request(f"/api/runs/{run_id}")
        self.assertEqual(detail["status"], "approved")
        self.assertEqual(detail["meta"]["retrieval"], "SQLite FTS5 / BM25")
        evidence = json.loads((self.runs_dir / run_id / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(detail["result"]["evidence"][0]["id"], evidence[0]["id"])
        self.assertTrue(evidence[0]["id"].startswith(document_id))
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/runs", method="POST", body={"mode": "llm", "case": DEMO_CASE, "knowledge_ids": [document_id]})
        self.assertEqual(ctx.exception.code, 400)

    def test_invalid_knowledge_batch_is_rejected(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/knowledge", method="POST", body={"documents": [{"title": "Incomplete"}]})
        self.assertEqual(ctx.exception.code, 400)

    def test_empty_pdf_has_clear_extraction_error(self):
        import base64
        import io
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("optional PDF dependency not installed")
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        stream = io.BytesIO()
        writer.write(stream)
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/knowledge/extract", method="POST", body={"filename": "empty.pdf", "content_base64": base64.b64encode(stream.getvalue()).decode()})
        self.assertIn("No extractable text", ctx.exception.read().decode())

    def test_pdf_text_extraction(self):
        import base64
        import io
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest("optional PDF dependency not installed")
        writer = PdfWriter()
        page = writer.add_blank_page(width=400, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 24 250 Td (Synthetic VTE PDF extraction test.) Tj ET")
        page[NameObject("/Contents")] = content
        stream = io.BytesIO()
        writer.write(stream)
        status, result = self.request("/api/knowledge/extract", method="POST", body={"filename": "synthetic.pdf", "content_base64": base64.b64encode(stream.getvalue()).decode()})
        self.assertEqual(status, 200)
        self.assertIn("Synthetic VTE PDF extraction test.", result["text"])
        self.assertEqual(result["pages"], 1)


if __name__ == "__main__":
    unittest.main()
