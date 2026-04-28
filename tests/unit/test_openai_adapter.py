"""Unit tests for the OpenAI-compatible adapter and its configuration.

Every test here runs against a fake transport. None of them opens a socket, and
the offline suite must stay that way.
"""

from __future__ import annotations

import json

import httpx
import pytest

from promptfence.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    AdapterTimeout,
    ModelMessage,
    ModelRequest,
    Role,
)
from promptfence.adapters.openai_compatible import OpenAICompatibleAdapter
from promptfence.config import ConfigError, RemoteModelConfig

CONFIG = RemoteModelConfig(base_url="http://model.invalid/v1", model="test-model", api_key="k")


def transport_returning(status: int, payload: dict, *, text: str | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload if text is None else None, text=text)

    return httpx.MockTransport(handler)


def make_request() -> ModelRequest:
    return ModelRequest(
        messages=[ModelMessage(Role.USER, "hello")],
        tools=[{"type": "function", "function": {"name": "read_document"}}],
    )


def test_tool_calls_are_normalised() -> None:
    payload = {
        "model": "test-model-0613",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "read_document",
                                "arguments": '{"document_id": "alice-notes"}',
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }
    adapter = OpenAICompatibleAdapter(CONFIG, transport=transport_returning(200, payload))
    response = adapter.complete(make_request())

    assert response.model == "test-model-0613"
    assert response.tool_calls[0].name == "read_document"
    assert response.tool_calls[0].arguments == {"document_id": "alice-notes"}
    assert response.usage == {"prompt_tokens": 12, "completion_tokens": 4}


def test_plain_answer_is_normalised() -> None:
    payload = {"choices": [{"message": {"content": "hello there"}, "finish_reason": "stop"}]}
    adapter = OpenAICompatibleAdapter(CONFIG, transport=transport_returning(200, payload))
    response = adapter.complete(make_request())
    assert response.messages[0].content == "hello there"
    assert response.tool_calls == []


def test_arguments_that_are_not_json_are_an_adapter_error() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"id": "c", "function": {"name": "read_document", "arguments": "{oops"}}
                    ]
                }
            }
        ]
    }
    adapter = OpenAICompatibleAdapter(CONFIG, transport=transport_returning(200, payload))
    with pytest.raises(AdapterError, match="not valid JSON"):
        adapter.complete(make_request())


def test_missing_choices_is_an_adapter_error() -> None:
    adapter = OpenAICompatibleAdapter(CONFIG, transport=transport_returning(200, {"id": "x"}))
    with pytest.raises(AdapterError, match="malformed completion payload"):
        adapter.complete(make_request())


def test_http_error_is_reported_with_the_status() -> None:
    adapter = OpenAICompatibleAdapter(
        CONFIG, transport=transport_returning(429, {}, text="rate limited")
    )
    with pytest.raises(AdapterError, match="HTTP 429.*rate limited"):
        adapter.complete(make_request())


def test_transport_failure_is_an_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    adapter = OpenAICompatibleAdapter(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(AdapterError, match="could not reach"):
        adapter.complete(make_request())


def test_request_timeout_is_reported_as_a_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    adapter = OpenAICompatibleAdapter(CONFIG, transport=httpx.MockTransport(handler))
    with pytest.raises(AdapterTimeout):
        adapter.complete(make_request())


def test_api_key_is_sent_as_a_bearer_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    adapter = OpenAICompatibleAdapter(CONFIG, transport=httpx.MockTransport(handler))
    adapter.complete(make_request())
    assert seen["authorization"] == "Bearer k"


def test_capabilities_start_optimistic_and_are_corrected_by_the_server() -> None:
    payload = {"choices": [{"message": {"content": "ok"}}]}
    adapter = OpenAICompatibleAdapter(CONFIG, transport=transport_returning(200, payload))
    assert adapter.capabilities().supports_tools is True

    rejecting = OpenAICompatibleAdapter(
        CONFIG, transport=transport_returning(400, {}, text="unknown parameter: tools")
    )
    with pytest.raises(AdapterError):
        rejecting.complete(make_request())
    assert rejecting.capabilities().supports_tools is False


def test_tool_results_are_sent_as_tool_role_messages() -> None:
    body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "done"}}]})

    adapter = OpenAICompatibleAdapter(CONFIG, transport=httpx.MockTransport(handler))
    request = ModelRequest(
        messages=[
            ModelMessage(Role.ASSISTANT, "calling"),
            ModelMessage(Role.TOOL, "ALICE_NOTE", tool_call_id="call_1", source="tool"),
        ]
    )
    adapter.complete(request)
    assert body["messages"][1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "ALICE_NOTE",
    }


# -- configuration --------------------------------------------------------


def test_endpoint_must_be_named_explicitly(monkeypatch) -> None:
    for name in ("PROMPTFENCE_BASE_URL", "PROMPTFENCE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError, match="no endpoint configured"):
        RemoteModelConfig.resolve()


def test_model_id_must_be_named_explicitly(monkeypatch) -> None:
    monkeypatch.delenv("PROMPTFENCE_MODEL", raising=False)
    with pytest.raises(ConfigError, match="no model id configured"):
        RemoteModelConfig.resolve(base_url="http://model.invalid/v1")


def test_configuration_can_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("PROMPTFENCE_BASE_URL", "http://model.invalid/v1/")
    monkeypatch.setenv("PROMPTFENCE_MODEL", "env-model")
    monkeypatch.setenv("PROMPTFENCE_API_KEY", "secret-key")
    config = RemoteModelConfig.resolve()
    assert config.base_url == "http://model.invalid/v1"
    assert config.model == "env-model"


def test_api_key_never_appears_in_repr_or_fingerprint() -> None:
    config = RemoteModelConfig(base_url="http://x/v1", model="m", api_key="super-secret")
    assert "super-secret" not in repr(config)
    assert "super-secret" not in config.fingerprint()
    assert config.fingerprint().startswith("http://x/v1|m|key:")


def test_same_endpoint_and_key_produce_the_same_fingerprint() -> None:
    a = RemoteModelConfig(base_url="http://x/v1", model="m", api_key="k")
    b = RemoteModelConfig(base_url="http://x/v1", model="m", api_key="k")
    c = RemoteModelConfig(base_url="http://x/v1", model="m", api_key="different")
    assert a.fingerprint() == b.fingerprint()
    assert a.fingerprint() != c.fingerprint()


def test_adapter_capabilities_describe_the_tradeoff() -> None:
    capabilities = OpenAICompatibleAdapter(CONFIG).capabilities()
    assert isinstance(capabilities, AdapterCapabilities)
    assert "provenance" in capabilities.notes
