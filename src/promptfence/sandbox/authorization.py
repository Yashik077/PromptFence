"""Server-side authorization.

The model proposes; this layer disposes. Every read and every write is checked
here against the authenticated principal, never against an identifier the model
supplied, and a denial is a hard stop — no tool may perform its effect after a
``DENY``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from promptfence.sandbox.state import ApplicationState, Permission


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    decision: Decision
    reason: str
    principal: str
    resource: str
    permission: Permission

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class AuthorizationLayer:
    """Identity-aware access control for the mock application."""

    def __init__(self, state: ApplicationState) -> None:
        self._state = state

    def check(
        self,
        principal: str,
        resource: str,
        permission: Permission = "read",
    ) -> AuthorizationDecision:
        granted = permission in self._state.grants.get((principal, resource), set())
        if granted:
            return self._allow(principal, resource, permission, "explicit grant")

        document = self._state.documents.get(resource)
        if document is None:
            if resource in self._state.secrets:
                return self._deny(
                    principal, resource, permission, "secret requires an explicit grant"
                )
            if resource in self._state.records:
                return self._deny(
                    principal, resource, permission, "record requires an explicit grant"
                )
            return self._deny(principal, resource, permission, "unknown resource")

        if principal not in self._state.principals:
            return self._deny(principal, resource, permission, "unknown principal")

        if document.owner == principal:
            return self._allow(principal, resource, permission, "resource owner")

        return self._deny(
            principal,
            resource,
            permission,
            f"principal does not own {resource} and holds no grant",
        )

    @staticmethod
    def _allow(
        principal: str, resource: str, permission: Permission, reason: str
    ) -> AuthorizationDecision:
        return AuthorizationDecision(Decision.ALLOW, reason, principal, resource, permission)

    @staticmethod
    def _deny(
        principal: str, resource: str, permission: Permission, reason: str
    ) -> AuthorizationDecision:
        return AuthorizationDecision(Decision.DENY, reason, principal, resource, permission)
