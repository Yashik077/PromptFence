"""A deterministic, offline stand-in for a language model.

The mock adapter is not trying to be a good language model. It is trying to be a
*reproducible* one, so the test suite never depends on a hosted endpoint, an API
key or a sampling seed behaving the same way twice.

It behaves like a credulous assistant:

* it obeys tool-call-shaped instructions it finds in the conversation, including
  instructions that arrived inside retrieved (untrusted) content, and
* it quotes back whatever the tools returned to it.

That credulity is deliberate. A framework that only ever tests against a model
which refuses everything would report a very comfortable, very meaningless
green run.
"""

from __future__ import annotations

import json
import re
from typing import Any

from promptfence.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    Role,
    ToolCall,
)

TOOL_NAMES = (
    "read_document",
    "list_documents",
    "search_documents",
    "get_secret",
    "read_record",
    "write_record",
    "delete_document",
)

_CALL_PATTERN = re.compile(
    r"\b(?P<name>" + "|".join(TOOL_NAMES) + r")\s*\((?P<args>[^()]*)\)",
    re.IGNORECASE,
)
_ARG_PATTERN = re.compile(r"""(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*["'](?P<value>[^"']*)["']""")
_SCRIPT_BLOCK = re.compile(r"```tool\s*(?P<body>.*?)```", re.DOTALL | re.IGNORECASE)


class DeterministicMockAdapter:
    """A model that does exactly what the text in front of it tells it to."""

    name = "mock"
    model = "deterministic-mock"

    def __init__(self, *, follows_injected_instructions: bool = True) -> None:
        #: When False the adapter only obeys directives that came from the user,
        #: not ones it found inside retrieved content. Useful for separating
        #: "the model was careful" from "the application was secure".
        self.follows_injected_instructions = follows_injected_instructions
        self._call_counter = 0

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_tools=True,
            supports_system_messages=True,
            supports_parallel_tool_calls=False,
            supports_seed=True,
            reports_usage=False,
            notes=(
                "Deterministic, offline and credulous. Obeys tool-shaped instructions "
                "from the conversation, including injected ones."
            ),
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        if not request.messages:
            raise AdapterError("model called with an empty conversation")

        if any(message.role is Role.TOOL for message in request.messages):
            return self._summarise(request)

        calls = self._planned_calls(request)
        if not calls:
            return ModelResponse(
                messages=[ModelMessage(Role.ASSISTANT, "I could not find anything to do.")],
                model=self.model,
                finish_reason="stop",
            )
        return ModelResponse(
            messages=[
                ModelMessage(
                    Role.ASSISTANT,
                    f"Running {len(calls)} tool call(s) as instructed.",
                )
            ],
            tool_calls=calls,
            model=self.model,
            finish_reason="tool_calls",
        )

    # -- planning --------------------------------------------------------

    def _planned_calls(self, request: ModelRequest) -> list[ToolCall]:
        directives: list[tuple[str, dict[str, Any]]] = []
        for message in request.messages:
            if message.source == "retrieved" and not self.follows_injected_instructions:
                continue
            directives.extend(self._extract_directives(message.content))

        if not directives:
            # No instructions at all: behave like an ordinary assistant and look
            # at what the caller is allowed to see.
            directives = [("list_documents", {})]

        return [self._make_call(name, arguments) for name, arguments in directives]

    def _extract_directives(self, content: str) -> list[tuple[str, dict[str, Any]]]:
        found: list[tuple[str, dict[str, Any]]] = []
        for block in _SCRIPT_BLOCK.findall(content):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError as exc:
                raise AdapterError(f"mock adapter: malformed tool script block ({exc})") from exc
            if isinstance(parsed, dict):
                parsed = [parsed]
            for entry in parsed:
                if not isinstance(entry, dict) or "name" not in entry:
                    raise AdapterError("mock adapter: tool script entries need a 'name'")
                arguments = entry.get("arguments", {})
                if not isinstance(arguments, dict):
                    raise AdapterError("mock adapter: 'arguments' must be an object")
                found.append((str(entry["name"]), dict(arguments)))

        for match in _CALL_PATTERN.finditer(content):
            arguments = {
                item.group("key"): item.group("value")
                for item in _ARG_PATTERN.finditer(match["args"])
            }
            found.append((match["name"].lower(), arguments))
        return found

    def _make_call(self, name: str, arguments: dict[str, Any]) -> ToolCall:
        if name not in TOOL_NAMES:
            raise AdapterError(f"mock adapter: unknown tool {name!r}")
        self._call_counter += 1
        return ToolCall(id=f"call-{self._call_counter:03d}", name=name, arguments=arguments)

    # -- answering -------------------------------------------------------

    def _summarise(self, request: ModelRequest) -> ModelResponse:
        quoted = [
            message.content
            for message in request.messages
            if message.role is Role.TOOL and message.content.strip()
        ]
        body = "\n".join(quoted) if quoted else "There was nothing to read."
        return ModelResponse(
            messages=[
                ModelMessage(Role.ASSISTANT, f"Here is what the tools returned:\n{body}"),
            ],
            model=self.model,
            finish_reason="stop",
        )
