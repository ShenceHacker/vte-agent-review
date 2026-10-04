import json
import unittest

import httpx

from vte_review.clinical_tools import ClinicalTools
from vte_review.demo import DEMO_EVIDENCE
from vte_review.providers import ChatCompletionsModel, ProviderError
from vte_review.retrieval import EvidenceIndex
from tests.test_clinical_workspace import case


class ToolProviderTests(unittest.IsolatedAsyncioTestCase):
    def model(self, handler, **kw):
        return ChatCompletionsModel("https://example.invalid/v1", "synthetic-secret", "test",
                                    transport=httpx.MockTransport(handler), **kw)

    def session(self): return ClinicalTools("B", case(), EvidenceIndex(DEMO_EVIDENCE))

    async def test_chat_tool_result_returns_to_same_conversation(self):
        seen=[]
        def respond(request):
            data=json.loads(request.content); seen.append(data)
            if len(seen)==1:
                return httpx.Response(200,json={"choices":[{"finish_reason":"tool_calls","message":{"role":"assistant","content":None,"tool_calls":[{"id":"call1","type":"function","function":{"name":"calculate_crcl","arguments":"{}"}}]}}],"usage":{"total_tokens":10}})
            output=json.loads(data["messages"][-1]["content"])
            self.assertEqual(output["value"],56.67)
            self.assertEqual(data["messages"][-1]["tool_call_id"],"call1")
            return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":'{"ok":true}'}}],"usage":{"total_tokens":7}})
        model=self.model(respond)
        try: reply=await model.complete_with_tools("assess","B",{"case":case()},self.session())
        finally: await model.close()
        self.assertEqual(reply.requests,2); self.assertEqual(reply.usage["total_tokens"],17)
        self.assertTrue(seen[0]["tools"])

    async def test_responses_preserves_reasoning_and_call_ids(self):
        seen=[]
        reasoning={"id":"r1","type":"reasoning","summary":[],"encrypted_content":"synthetic-encrypted"}
        def respond(request):
            data=json.loads(request.content); seen.append(data)
            if len(seen)==1:
                return httpx.Response(200,json={"status":"completed","output":[reasoning,{"type":"function_call","call_id":"c1","name":"calculate_crcl","arguments":"{}"}],"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15}})
            self.assertIn(reasoning,data["input"])
            self.assertEqual(data["input"][-1]["type"],"function_call_output")
            self.assertEqual(data["input"][-1]["call_id"],"c1")
            return httpx.Response(200,json={"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":'{"ok":true}'}]}]})
        model=self.model(respond,api_style="responses")
        try: reply=await model.complete_with_tools("assess","B",{},self.session())
        finally: await model.close()
        self.assertEqual(reply.requests,2); self.assertFalse(seen[0]["store"])
        self.assertEqual(reply.usage["prompt_tokens"],10)

    async def test_tool_round_limit_stops_infinite_dialogue(self):
        n=0
        def respond(request):
            nonlocal n; n+=1
            return httpx.Response(200,json={"choices":[{"finish_reason":"tool_calls","message":{"tool_calls":[{"id":str(n),"type":"function","function":{"name":"calculate_crcl","arguments":"{}"}}]}}]})
        model=self.model(respond,max_tool_rounds=2); session=self.session()
        try:
            with self.assertRaises(ProviderError): await model.complete_with_tools("assess","B",{},session)
        finally: await model.close()
        self.assertEqual(n,3); self.assertEqual(len(session.trace),2)

    async def test_duplicate_tool_id_rejected(self):
        def respond(request):
            return httpx.Response(200,json={"choices":[{"finish_reason":"tool_calls","message":{"tool_calls":[{"id":"same","function":{"name":"calculate_crcl","arguments":"{}"}}]}}]})
        model=self.model(respond)
        try:
            with self.assertRaises(ProviderError): await model.complete_with_tools("assess","B",{},self.session())
        finally: await model.close()

    async def test_vision_message_in_both_protocols(self):
        for style in ("chat_completions","responses"):
            seen=[]
            def respond(request):
                seen.append(json.loads(request.content))
                if style=="responses":
                    return httpx.Response(200,json={"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":'{"observations":[],"issues":[]}'}]}]})
                return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":'{"observations":[],"issues":[]}'}}]})
            model=self.model(respond,api_style=style)
            try: await model.extract({},[{"source_id":"SRC-test","data_url":"data:image/png;base64,test"}])
            finally: await model.close()
            raw=json.dumps(seen)
            self.assertIn("data:image/png;base64,test",raw); self.assertIn("SRC-test",raw)

    async def test_unknown_tool_yields_controlled_error(self):
        session=self.session(); seen=[]
        def respond(request):
            data=json.loads(request.content);seen.append(data)
            if len(seen)==1:
                return httpx.Response(200,json={"choices":[{"finish_reason":"tool_calls","message":{"tool_calls":[{"id":"c1","function":{"name":"read_other_patient","arguments":"{}"}}]}}]})
            self.assertEqual(json.loads(data["messages"][-1]["content"])["status"],"error")
            return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":'{"needs_information":true}'}}]})
        model=self.model(respond)
        try: result=await model.complete_with_tools("assess","B",{},session)
        finally: await model.close()
        self.assertTrue(result.data["needs_information"])

    async def test_nonfinite_tool_arguments_rejected_before_execution(self):
        response={"choices":[{"finish_reason":"tool_calls","message":{"tool_calls":[{"id":"c1","function":{"name":"convert_units","arguments":'{"value":NaN}'}}]}}]}
        model=self.model(lambda request:httpx.Response(200,json=response));session=self.session()
        try:
            with self.assertRaises(ProviderError):await model.complete_with_tools("assess","B",{},session)
        finally:await model.close()
        self.assertEqual(session.trace,[])
