import json
import unittest

try:
    import httpx
except ImportError:
    httpx = None

from vte_review.providers import ChatCompletionsModel, ProviderError


@unittest.skipIf(httpx is None, 'Install ".[llm]" to test the HTTP adapter')
class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def create(self, handler):
        return ChatCompletionsModel("https://example.invalid/v1", "fake-test-key", "test-model", transport=httpx.MockTransport(handler))

    async def test_request_shape_and_role_override(self):
        seen = []
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}], "usage": {"total_tokens": 9}})
        model = self.create(handler)
        model.role_models["A"] = "test-specialist"
        try:
            reply = await model.complete("assess", "A", {"case": {}, "evidence": []})
        finally:
            await model.close()
        self.assertEqual(str(seen[0].url), "https://example.invalid/v1/chat/completions")
        body = json.loads(seen[0].content)
        self.assertEqual(body["model"], "test-specialist")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn("JSON", body["messages"][0]["content"])
        self.assertEqual(reply.usage, {"total_tokens": 9})

    async def test_chinese_output_preserves_contract_language(self):
        seen=[]
        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]})
        model=ChatCompletionsModel("https://example.invalid/v1","fake-test-key","test-model",transport=httpx.MockTransport(handler),output_language="zh")
        try:await model.complete("synthesize","D",{})
        finally:await model.close()
        prompt=seen[0]["messages"][0]["content"]
        self.assertIn("Simplified Chinese",prompt)
        self.assertNotIn("Return a single JSON object in English",prompt)
        self.assertIn("shared_plan",prompt)

    async def test_refusal_truncation_and_malformed_output_fail_closed(self):
        variants = [
            {"finish_reason": "length", "message": {"content": '{}'}},
            {"finish_reason": "stop", "message": {"content": '{}', "refusal": "no"}},
            {"finish_reason": "stop", "message": {"content": 'not json'}},
            {"finish_reason": "stop", "message": {"content": '[]'}},
        ]
        for choice in variants:
            with self.subTest(choice=choice):
                model = self.create(lambda request: httpx.Response(200, json={"choices": [choice]}))
                try:
                    with self.assertRaises(ProviderError):
                        await model.complete("assess", "A", {})
                finally:
                    await model.close()

    async def test_http_error_does_not_expose_body(self):
        model = self.create(lambda request: httpx.Response(401, text="secret-body"))
        try:
            with self.assertRaises(ProviderError) as error:
                await model.complete("assess", "A", {})
            self.assertNotIn("secret-body", str(error.exception))
            self.assertNotIn("fake-test-key", str(error.exception))
        finally:
            await model.close()

    async def test_insecure_remote_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            ChatCompletionsModel("http://example.invalid/v1", "test", "model")
