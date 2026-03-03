"""The provider-neutral adapter interface.

Everything the runner needs from a model is expressed in the types below. A new
provider means a new module implementing :class:`ModelAdapter`; it does not mean
touching the runner, the oracles or the scenario format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class AdapterError(RuntimeError):
    """A provider-side failure.

    Raised for transport problems, not for security findings. The runner treats
    it as incomplete evidence and never as a pass.
    """


class AdapterTimeout(AdapterError):
    """The provider did not answer within the configured budget."""


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: Role
    content: str
    #: For tool messages: the call this result answers.
    tool_call_id: str | None = None
    #: Where the text came from: ``system``, ``user``, ``retrieved`` or ``tool``.
    #: Not every provider offers a distinct "untrusted data" channel, so
    #: provenance is tracked here instead of being guessed from the role.
    source: str | None = None

    def __post_init__(self) -> None:
        if self.source is None:
            object.__setattr__(self, "source", str(self.role))


def ToolResultMessage(*, tool_call_id: str, name: str, content: str) -> ModelMessage:  # noqa: N802
    """A tool result as the model sees it."""
    return ModelMessage(Role.TOOL, content, tool_call_id=tool_call_id, source="tool")


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A model's request to invoke a tool. A proposal, not a permission."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    messages: list[ModelMessage]
    tools: list[dict[str, Any]] = field(default_factory=list)
    temperature: float = 0.0
    max_tokens: int = 512
    seed: int | None = None
    timeout_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """What a provider actually supports.

    Recorded with every result. Compatibility varies between OpenAI-compatible
    servers and guessing gets you a confusing failure at 2am.
    """

    supports_tools: bool = True
    supports_system_messages: bool = True
    supports_parallel_tool_calls: bool = False
    supports_seed: bool = False
    reports_usage: bool = False
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ModelResponse:
    messages: list[ModelMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"


@runtime_checkable
class ModelAdapter(Protocol):
    """The contract every adapter implements."""

    name: str
    model: str

    def capabilities(self) -> AdapterCapabilities:
        """Report what this adapter can do, including known limitations."""
        ...

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer one request, or raise :class:`AdapterError`."""
        ...
