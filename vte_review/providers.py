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


class Model(Protocol):
    async def complete(self, task: str, role: str, payload: dict) -> ModelReply: ...


class ProviderError(RuntimeError):
    pass


class ChatCompletionsModel:
    def __init__(self, base_url: str, api_key: str, model: str, *, role_models: dict | None = None,
                 timeout: float = 60, max_tokens: int = 3000, transport=None):
        import httpx

        parsed = urlparse(base_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base URL must not contain credentials, query, or fragment")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("use HTTPS except for a local model server")
        if not api_key.strip() or not model.strip() or max_tokens < 1:
            raise ValueError("API key, model, and positive token limit are required")
        self.model = model
        self.role_models = role_models or {}
        self.max_tokens = max_tokens
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": "Bearer " + api_key},
            timeout=timeout, transport=transport, follow_redirects=False,
        )

    async def close(self):
        await self.client.aclose()

    async def complete(self, task: str, role: str, payload: dict) -> ModelReply:
        import httpx

        selected = self.role_models.get(role, self.model)
        try:
            response = await self.client.post("chat/completions", json={
                "model": selected,
                "messages": [
                    {"role": "system", "content": system_prompt(task, role)},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, allow_nan=False)},
                ],
                "response_format": {"type": "json_object"},
                "max_completion_tokens": self.max_tokens,
            })
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Do not print remote error bodies, headers, or secrets.
            raise ProviderError(f"model endpoint returned HTTP {exc.response.status_code}") from None
        except httpx.RequestError:
            raise ProviderError("model endpoint network/timeout error") from None
        try:
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
            if choice.get("finish_reason") != "stop" or message.get("refusal"):
                raise ProviderError("model output refused, truncated, or not complete")
            parsed = json.loads(message["content"])
            if not isinstance(parsed, dict):
                raise ContractError("model output must be a JSON object")
            usage = body.get("usage") or {}
            usage = {k: v for k, v in usage.items() if k in {"prompt_tokens", "completion_tokens", "total_tokens"} and type(v) is int and v >= 0}
            return ModelReply(parsed, body.get("model", selected), usage)
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise ProviderError("model endpoint returned an invalid response/JSON") from None
