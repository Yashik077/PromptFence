"""An adapter for OpenAI-compatible ``/chat/completions`` endpoints.

Explicitly opt-in. It is never the default, it refuses to construct without a
named endpoint, and it records what the server actually supports rather than
assuming a feature is there because the API shape says it should be. Local
servers vary: some ignore ``tools``, some reject them outright, some return
usage, some do not, and a few want tool results in a ``user`` message rather
than a ``tool`` one.

Prompts and scenario content leave the machine when this adapter runs. That is
why it is separate from the offline path and why the offline unit tests never
construct it.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from promptfence.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    AdapterTimeout,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    Role,
    ToolCall,
)
from promptfence.config import RemoteModelConfig

ADAPTER_NAME = "openai_compatible"


class OpenAICompatibleAdapter:
    name = ADAPTER_NAME

    def __init__(self, config: RemoteModelConfig, *, transport: Any | None = None) -> None:
        self.config = config
        self.model = config.model
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
        )
        #: Set to False the first time a server rejects a tool request.
        self._supports_tools = True

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenAICompatibleAdapter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_tools=self._supports_tools,
            supports_system_messages=True,
            supports_parallel_tool_calls=False,
            supports_seed=True,
            reports_usage=True,
            notes=(
                f"OpenAI-compatible endpoint {self.config.base_url}. Retrieved text is sent "
                "as a plain user message, so the model cannot see its provenance. Tool "
                "support is assumed until the server says otherwise."
            ),
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [_to_wire(message) for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            payload["tools"] = request.tools
        if request.seed is not None:
            payload["seed"] = request.seed

        try:
            response = self._client.post(
                "/chat/completions", json=payload, headers=self.config.headers()
            )
        except httpx.TimeoutException as exc:
            raise AdapterTimeout(
                f"endpoint timed out after {self.config.timeout_seconds}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"could not reach {self.config.base_url}: {exc}") from exc

        if response.status_code >= 400:
            self._note_rejection(response)
            raise AdapterError(
                f"endpoint returned HTTP {response.status_code}: {_short(response.text)}"
            )
        return self._parse(response.json())

    # -- capability handling ---------------------------------------------

    def _note_rejection(self, response: httpx.Response) -> None:
        """Turn a capability mismatch into a capability flag, not a mystery 400."""
        text = response.text.lower()
        if "tool" in text and response.status_code in (400, 404, 422, 501):
            self._supports_tools = False

    # -- parsing ----------------------------------------------------------

    def _parse(self, payload: dict[str, Any]) -> ModelResponse:
        try:
            choice = payload["choices"][0]
        except (KeyError, IndexError) as exc:
            raise AdapterError(f"malformed completion payload: missing choices ({exc})") from exc

        message = choice.get("message") or {}
        tool_calls = [
            ToolCall(
                id=call.get("id", f"call-{index}"),
                name=(call.get("function") or {}).get("name", ""),
                arguments=_parse_arguments((call.get("function") or {}).get("arguments")),
            )
            for index, call in enumerate(message.get("tool_calls") or [], start=1)
        ]

        messages: list[ModelMessage] = []
        content = message.get("content")
        if content:
            messages.append(ModelMessage(Role.ASSISTANT, content))

        usage = {
            key: int(value)
            for key, value in (payload.get("usage") or {}).items()
            if isinstance(value, (int, float))
        }
        return ModelResponse(
            messages=messages,
            tool_calls=tool_calls,
            model=payload.get("model", self.config.model),
            usage=usage,
            finish_reason=choice.get("finish_reason", "stop"),
        )


def _to_wire(message: ModelMessage) -> dict[str, Any]:
    if message.role is Role.TOOL:
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content,
        }
    return {"role": str(message.role), "content": message.content}


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Providers send tool arguments as a JSON string, sometimes not valid JSON."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise AdapterError(f"tool arguments were not valid JSON: {raw[:200]!r}") from None
    if not isinstance(parsed, dict):
        raise AdapterError("tool arguments must be a JSON object")
    return parsed


def _short(text: str, limit: int = 300) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}…"
