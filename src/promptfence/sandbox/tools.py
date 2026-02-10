"""Tool implementations for the mock application.

These are deliberately boring. Every tool:

1. takes the authenticated principal from its :class:`ToolContext`, never from
   its arguments,
2. asks :class:`~promptfence.sandbox.authorization.AuthorizationLayer` before it
   does anything, and
3. performs no effect at all when that check comes back ``DENY``.

None of them touch the network, the filesystem or any real credential store.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from promptfence.sandbox.authorization import AuthorizationDecision, AuthorizationLayer, Decision
from promptfence.sandbox.state import ApplicationState, Permission


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Everything a tool handler is allowed to see."""

    state: ApplicationState
    authorization: AuthorizationLayer
    #: The authenticated trial principal. Model-supplied identity claims are not
    #: accepted here; see :mod:`promptfence.sandbox.app`.
    principal: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    decision: Decision
    reason: str
    content: str = ""
    disclosed: list[str] = field(default_factory=list)
    changed_state: list[str] = field(default_factory=list)

    @classmethod
    def denied(cls, decision: AuthorizationDecision) -> ToolResult:
        return cls(
            ok=False,
            decision=Decision.DENY,
            reason=decision.reason,
            content=f"Access denied: {decision.reason}",
        )

    @classmethod
    def allowed(
        cls,
        decision: AuthorizationDecision,
        content: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        return cls(
            ok=True,
            decision=Decision.ALLOW,
            reason=decision.reason,
            content=content,
            **kwargs,
        )


Handler = Callable[[ToolContext, dict[str, Any]], ToolResult]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler

    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid string argument: {key}")
    return value


def _guard(
    ctx: ToolContext,
    resource: str,
    permission: Permission,
    arguments: dict[str, Any],
) -> AuthorizationDecision | ToolResult:
    decision = ctx.authorization.check(ctx.principal, resource, permission)
    if not decision.allowed:
        return ToolResult.denied(decision)
    return decision


def read_document(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    document_id = _string(arguments, "document_id")
    guard = _guard(ctx, document_id, "read", arguments)
    if isinstance(guard, ToolResult):
        return guard
    document = ctx.state.documents[document_id]
    return ToolResult.allowed(
        guard,
        content=document.content,
        disclosed=[document.content],
    )


def list_documents(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    visible = [
        document
        for document in ctx.state.documents.values()
        if ctx.authorization.check(ctx.principal, document.id, "read").allowed
    ]
    listing = "\n".join(f"{document.id}: {document.title or document.id}" for document in visible)
    return ToolResult(
        ok=True,
        decision=Decision.ALLOW,
        reason="listing filtered to authorized resources",
        content=listing,
        disclosed=[document.id for document in visible],
    )


def search_documents(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    query = _string(arguments, "query").lower()
    hits: list[str] = []
    disclosed: list[str] = []
    for document in ctx.state.documents.values():
        if query not in document.content.lower():
            continue
        decision = ctx.authorization.check(ctx.principal, document.id, "read")
        if not decision.allowed:
            continue
        hits.append(document.id)
        disclosed.append(document.content)
    return ToolResult(
        ok=True,
        decision=Decision.ALLOW,
        reason="search results filtered to authorized resources",
        content="\n".join(hits),
        disclosed=disclosed,
    )


def get_secret(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    name = _string(arguments, "name")
    guard = _guard(ctx, name, "read", arguments)
    if isinstance(guard, ToolResult):
        return guard
    value = ctx.state.secrets[name]
    return ToolResult.allowed(guard, content=value, disclosed=[value])


def read_record(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    record_id = _string(arguments, "record_id")
    guard = _guard(ctx, record_id, "read", arguments)
    if isinstance(guard, ToolResult):
        return guard
    value = ctx.state.records[record_id]
    return ToolResult.allowed(guard, content=value, disclosed=[value])


def write_record(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    record_id = _string(arguments, "record_id")
    value = _string(arguments, "value")
    guard = _guard(ctx, record_id, "write", arguments)
    if isinstance(guard, ToolResult):
        return guard
    ctx.state.records[record_id] = value
    return ToolResult.allowed(guard, content="updated", changed_state=[f"records/{record_id}"])


def delete_document(ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    document_id = _string(arguments, "document_id")
    guard = _guard(ctx, document_id, "write", arguments)
    if isinstance(guard, ToolResult):
        return guard
    ctx.state.documents.pop(document_id, None)
    return ToolResult.allowed(guard, content="deleted", changed_state=[f"documents/{document_id}"])


TOOLS: dict[str, ToolSpec] = {}


def _register(spec: ToolSpec) -> None:
    TOOLS[spec.name] = spec


_register(
    ToolSpec(
        name="read_document",
        description="Read a synthetic document by id.",
        parameters={
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
            "additionalProperties": False,
        },
        handler=read_document,
    )
)
_register(
    ToolSpec(
        name="list_documents",
        description="List the documents the caller is allowed to read.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=list_documents,
    )
)
_register(
    ToolSpec(
        name="search_documents",
        description="Search document contents the caller is allowed to read.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search_documents,
    )
)
_register(
    ToolSpec(
        name="get_secret",
        description="Read a synthetic application secret.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        handler=get_secret,
    )
)
_register(
    ToolSpec(
        name="read_record",
        description="Read an application record.",
        parameters={
            "type": "object",
            "properties": {"record_id": {"type": "string"}},
            "required": ["record_id"],
            "additionalProperties": False,
        },
        handler=read_record,
    )
)
_register(
    ToolSpec(
        name="write_record",
        description="Update an application record.",
        parameters={
            "type": "object",
            "properties": {
                "record_id": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["record_id", "value"],
            "additionalProperties": False,
        },
        handler=write_record,
    )
)
_register(
    ToolSpec(
        name="delete_document",
        description="Delete a document.",
        parameters={
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
            "additionalProperties": False,
        },
        handler=delete_document,
    )
)


def tool_schemas() -> list[dict[str, Any]]:
    return [TOOLS[name].json_schema() for name in sorted(TOOLS)]
