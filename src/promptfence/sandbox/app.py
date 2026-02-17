"""The mock application under test.

PromptFence does not try to attack a real product. It runs a small, synthetic
application with real access-control logic and real audit events, so a scenario
can attempt something it should not do and we can say, with evidence, whether it
was stopped or actually happened.
"""

from __future__ import annotations

from typing import Any

from promptfence.sandbox.authorization import AuthorizationLayer
from promptfence.sandbox.state import ApplicationState, Document, Record
from promptfence.sandbox.tools import TOOLS, ToolContext, ToolResult, tool_schemas
from promptfence.schemas import Event, Scenario

RESOURCE_ARGUMENTS = {
    "read_document": "document_id",
    "search_documents": None,
    "list_documents": None,
    "read_record": "record_id",
    "write_record": "record_id",
    "delete_document": "document_id",
    "get_secret": "name",
}


class UnknownToolError(LookupError):
    """Raised when a scenario or adapter asks for a tool that does not exist."""


class MockApplication:
    """A deterministic, offline application with synthetic data."""

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._state = self._build_state(scenario)
        self._authorization = AuthorizationLayer(self._state)
        self._events: list[Event] = []
        self._baseline = self._state.snapshot()
        self.authenticated_principal = scenario.setup.principal
        self.identity_overrides: list[str] = []

    # -- construction ----------------------------------------------------

    @staticmethod
    def _build_state(scenario: Scenario) -> ApplicationState:
        state = ApplicationState()
        state.add_principal(scenario.setup.principal)
        for document in scenario.setup.documents:
            if document.owner not in state.principals:
                state.add_principal(document.owner)
            state.add_document(
                Document(
                    id=document.id,
                    owner=document.owner,
                    content=document.content,
                    title=document.title or document.id,
                )
            )
        state.secrets.update(scenario.setup.secrets)
        for record in scenario.setup.records:
            if record.owner not in state.principals:
                state.add_principal(record.owner)
            state.add_record(Record(id=record.id, owner=record.owner, value=record.value))
        for grant in scenario.setup.grants:
            state.grant(grant.principal, grant.document, grant.permission)  # type: ignore[arg-type]
        return state

    # -- introspection ---------------------------------------------------

    @property
    def state(self) -> ApplicationState:
        return self._state

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    @property
    def baseline(self) -> ApplicationState:
        return self._baseline

    @property
    def tools(self) -> list[dict[str, Any]]:
        return tool_schemas()

    # -- execution -------------------------------------------------------

    def effective_principal(self, arguments: dict[str, Any]) -> str:
        """The principal a tool call runs as.

        Tools may legitimately be asked to act on behalf of somebody, so an
        ``as_user`` argument is honoured here.
        """
        claimed = arguments.get("as_user")
        if isinstance(claimed, str) and claimed:
            self.identity_overrides.append(claimed)
            self._record(
                Event(
                    id=self._next_id(),
                    kind="identity_claim",
                    principal=self.authenticated_principal,
                    arguments={"as_user": claimed},
                    decision="noted",
                    reason="tool call carried an as_user argument",
                )
            )
            return claimed
        return self.authenticated_principal

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        spec = TOOLS.get(name)
        if spec is None:
            raise UnknownToolError(name)
        arguments = dict(arguments or {})
        principal = self.effective_principal(arguments)
        context = ToolContext(
            state=self._state,
            authorization=self._authorization,
            principal=principal,
        )
        try:
            result = spec.handler(context, arguments)
        except ValueError as exc:
            result = ToolResult(
                ok=False,
                decision="deny",
                reason=f"invalid arguments: {exc}",
                content=str(exc),
            )
        self._record(
            Event(
                id=self._next_id(),
                kind="tool_call",
                tool=name,
                principal=principal,
                resource=self._resource_for(name, arguments),
                arguments={k: v for k, v in arguments.items() if k != "as_user"},
                decision=result.decision,
                reason=result.reason,
                disclosed=result.disclosed,
                changed_state=result.changed_state,
            )
        )
        return result

    def changed_state(self) -> list[str]:
        return self._state.changed_paths(self._baseline)

    # -- events ----------------------------------------------------------

    @staticmethod
    def _resource_for(name: str, arguments: dict[str, Any]) -> str | None:
        key = RESOURCE_ARGUMENTS.get(name)
        if key is None:
            return None
        value = arguments.get(key)
        return value if isinstance(value, str) else None

    def _next_id(self) -> str:
        return f"event-{len(self._events) + 1:03d}"

    def _record(self, event: Event) -> None:
        event.sequence = len(self._events) + 1
        self._events.append(event)
