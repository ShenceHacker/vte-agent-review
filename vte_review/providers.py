"""Provider boundary: independent calls with no shared conversation history."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from .contracts import ContractError
from .prompts import system_prompt


@dataclass
class ModelReply:
    data: dict
    model: str
    usage: dict = field(default_factory=dict)
    requests: int = 1


class Model(Protocol):
    async def complete(self, task: str, role: str, payload: dict) -> ModelReply: ...


class ProviderError(RuntimeError):
    pass


def parse_json(value):
    def invalid_constant(_):
        raise ValueError("Non-finite JSON number")
    return json.loads(value, parse_constant=invalid_constant)


class ChatCompletionsModel:
    def __init__(self, base_url: str, api_key: str, model: str, *, role_models: dict | None = None,
                 timeout: float = 60, max_tokens: int = 3000, transport=None,
                 api_style: str = "chat_completions", max_tool_rounds: int = 4,
                 reasoning_effort: str | None = None):
        import httpx

        parsed = urlparse(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base URL must not contain credentials, query, or fragment")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("use HTTPS except for a local model server")
        if not api_key.strip() or not model.strip() or type(max_tokens) is not int or max_tokens < 1:
            raise ValueError("API key, model, and positive token limit are required")
        if reasoning_effort not in {None, "none", "minimal", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("Invalid reasoning effort")
        self.reasoning_effort = reasoning_effort
        self.model = model
        self.role_models = role_models or {}
        self.max_tokens = max_tokens
        if api_style not in {"chat_completions", "responses"} or not 1 <= max_tool_rounds <= 8:
            raise ValueError("Invalid API style or tool-round limit")
        self.api_style, self.max_tool_rounds = api_style, max_tool_rounds
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": "Bearer " + api_key,
                     "User-Agent": "VTE-Anticoagulation-Assistant/0.4.0"},
            timeout=timeout, transport=transport if transport is not None else httpx.AsyncHTTPTransport(retries=2),
            follow_redirects=False,
        )

    async def close(self):
        await self.client.aclose()

    async def complete(self, task: str, role: str, payload: dict) -> ModelReply:
        return await self._dialog(task, role, payload)

    async def complete_with_tools(self, task: str, role: str, payload: dict, session) -> ModelReply:
        return await self._dialog(task, role, payload, session=session)

    async def extract(self, payload: dict, images: list[dict]) -> ModelReply:
        return await self._dialog("extract", "D", payload, images=images)

    def _user(self, text: str, images=None):
        if self.api_style == "responses":
            parts = [{"type": "input_text", "text": text}]
            for image in images or []:
                parts += [{"type": "input_text", "text": "Source image ID: " + image["source_id"]},
                          {"type": "input_image", "image_url": image["data_url"], "detail": "high"}]
        else:
            if not images:
                return {"role": "user", "content": text}
            parts = [{"type": "text", "text": text}]
            for image in images:
                parts += [{"type": "text", "text": "Source image ID: " + image["source_id"]},
                          {"type": "image_url", "image_url": {"url": image["data_url"], "detail": "high"}}]
        return {"role": "user", "content": parts}

    async def _post(self, endpoint: str, body: dict) -> dict:
        import httpx
        try:
            if endpoint == "responses":
                async with self.client.stream("POST", endpoint, json={**body, "stream": True}) as response:
                    response.raise_for_status()
                    if "application/json" in response.headers.get("content-type", ""):
                        # Compatibility endpoints may still return a complete JSON response.
                        await response.aread()
                        return response.json()
                    if "text/event-stream" not in response.headers.get("content-type", ""):
                        raise ProviderError("model endpoint returned an unsupported response type")
                    data, size = [], 0
                    async for line in response.aiter_lines():
                        size += len(line)
                        if size > 16 * 1024 * 1024:
                            raise ProviderError("model response stream exceeded the size limit")
                        if line.startswith("data:"):
                            data.append(line[5:].lstrip())
                        elif not line and data:
                            payload = "\n".join(data)
                            data = []
                            if payload == "[DONE]":
                                continue
                            event = parse_json(payload)
                            if event.get("type") in {"response.completed", "response.incomplete"}:
                                return event["response"]
                            if event.get("type") in {"error", "response.failed"}:
                                raise ProviderError("model response stream failed")
                    raise ProviderError("model response stream ended without a completion event")
            response = await self.client.post(endpoint, json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Do not print remote error bodies, headers, or secrets.
            raise ProviderError(f"model endpoint returned HTTP {exc.response.status_code}") from None
        except httpx.RequestError as exc:
            # The exception class is safe; raw messages may expose request details.
            raise ProviderError("model endpoint network/timeout error (" + type(exc).__name__ + ")") from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ProviderError("model endpoint returned invalid JSON/events") from None
        try:
            return response.json()
        except ValueError:
            raise ProviderError("model endpoint returned invalid JSON") from None

    async def _dialog(self, task, role, payload, session=None, images=None):
        selected = self.role_models.get(role, self.model)
        prompt = system_prompt(task, role)
        # JSON mode checks the input messages, not only Responses instructions.
        state = [self._user("Return a JSON object following the system schema.\nInput data:\n"
                            + json.dumps(payload, ensure_ascii=False, allow_nan=False), images)]
        if self.api_style == "chat_completions":
            state.insert(0, {"role": "system", "content": prompt})
        usage, seen_ids = {}, set()
        for turn in range(self.max_tool_rounds + 1):
            definitions = session.definitions if session else []
            if self.api_style == "responses":
                request = {"model": selected, "instructions": prompt, "input": state, "store": False,
                           "text": {"format": {"type": "json_object"}}, "max_output_tokens": self.max_tokens,
                           "include": ["reasoning.encrypted_content"]}
                if definitions:
                    request["tools"] = [{"type": "function", **d["function"], "strict": False} for d in definitions]
                endpoint = "responses"
                if self.reasoning_effort is not None:
                    request["reasoning"] = {"effort": self.reasoning_effort}
            else:
                request = {"model": selected, "messages": state, "response_format": {"type": "json_object"},
                           "max_completion_tokens": self.max_tokens}
                if definitions:
                    request["tools"] = definitions
                endpoint = "chat/completions"
                if self.reasoning_effort is not None:
                    request["reasoning_effort"] = self.reasoning_effort
            if definitions:
                request["tool_choice"] = "auto"
            body = await self._post(endpoint, request)
            try:
                for key, value in (body.get("usage") or {}).items():
                    key = {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens"}.get(key, key)
                    if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and type(value) is int and value >= 0:
                        usage[key] = usage.get(key, 0) + value
                if self.api_style == "responses":
                    if body.get("status") != "completed":
                        raise ProviderError("model response refused, truncated, or incomplete")
                    output = body["output"]
                    calls = [{"id": o["call_id"], "function": {"name": o["name"], "arguments": o["arguments"]}}
                             for o in output if o.get("type") == "function_call"]
                    parts = [p for o in output if o.get("type") == "message" for p in o.get("content", [])]
                    if any(p.get("type") == "refusal" for p in parts):
                        raise ProviderError("model refused")
                    content = "".join(p.get("text", "") for p in parts if p.get("type") == "output_text")
                    state.extend(output)  # Preserve reasoning items between tool turns.
                else:
                    choice = body["choices"][0]
                    message = choice["message"]
                    if message.get("refusal") or choice.get("finish_reason") not in {"stop", "tool_calls"}:
                        raise ProviderError("model output refused, truncated, or not complete")
                    calls = message.get("tool_calls") or []
                    if bool(calls) != (choice.get("finish_reason") == "tool_calls"):
                        raise ProviderError("inconsistent tool-call response")
                    content = message.get("content")
                    if calls:
                        # Preserve provider reasoning fields, if returned, for compatible reasoning endpoints.
                        state.append({"role": "assistant", **{k: v for k, v in message.items() if k in {"content", "tool_calls", "reasoning_content"}}})
                if not calls:
                    parsed = parse_json(content)
                    if not isinstance(parsed, dict):
                        raise ProviderError("model output must be a JSON object")
                    return ModelReply(parsed, body.get("model", selected), usage, turn + 1)
                if not session or turn >= self.max_tool_rounds or len(calls) > 8:
                    raise ProviderError("tool call limit reached or tools unavailable")
                for call in calls:
                    call_id, function = call["id"], call["function"]
                    if not isinstance(call_id, str) or not call_id or call_id in seen_ids:
                        raise ProviderError("invalid or duplicate tool call ID")
                    seen_ids.add(call_id)
                    args = parse_json(function["arguments"])
                    result = session.execute(function["name"], args, call_id)
                    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
                    if self.api_style == "responses":
                        state.append({"type": "function_call_output", "call_id": call_id, "output": encoded})
                    else:
                        state.append({"role": "tool", "tool_call_id": call_id, "content": encoded})
                    attached = session.images(result)
                    if attached:
                        state.append(self._user("Requested original sources in order: " + ", ".join(i["source_id"] for i in attached), attached))
            except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                raise ProviderError("model endpoint returned an invalid response/JSON") from None
        raise ProviderError("tool call limit reached")
