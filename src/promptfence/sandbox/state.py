"""Synthetic application state.

Everything here is fabricated: principals, documents, secrets and mutable
records. There is no path from this module to the filesystem, the network or a
real datastore, and no constructor takes a real credential.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Literal

Permission = Literal["read", "write"]


@dataclass(frozen=True, slots=True)
class Principal:
    """A synthetic authenticated identity."""

    id: str
    role: str = "user"


@dataclass(frozen=True, slots=True)
class Document:
    """A synthetic document owned by exactly one principal."""

    id: str
    owner: str
    content: str
    title: str = ""


@dataclass(slots=True)
class Record:
    """A synthetic mutable application record owned by one principal."""

    id: str
    owner: str
    value: str


@dataclass
class ApplicationState:
    """Mutable state owned by the application under test.

    The authorization layer reads this; the state-change oracle diffs a snapshot
    taken before the trial against the state afterwards.
    """

    principals: dict[str, Principal] = field(default_factory=dict)
    documents: dict[str, Document] = field(default_factory=dict)
    records: dict[str, Record] = field(default_factory=dict)
    secrets: dict[str, str] = field(default_factory=dict)
    #: Explicit scenario-declared permissions: (principal, resource) -> permissions.
    grants: dict[tuple[str, str], set[Permission]] = field(default_factory=dict)

    def snapshot(self) -> ApplicationState:
        """A deep copy suitable for later diffing."""
        return copy.deepcopy(self)

    def changed_paths(self, before: ApplicationState) -> list[str]:
        """Names of state locations that differ from ``before``.

        Only the fields a tool can actually mutate are compared; the ACL table is
        static for the duration of a trial.
        """
        changes: list[str] = []
        for document_id in sorted(set(self.documents) | set(before.documents)):
            if self.documents.get(document_id) != before.documents.get(document_id):
                changes.append(f"documents/{document_id}")
        for record_id in sorted(set(self.records) | set(before.records)):
            if self.records.get(record_id) != before.records.get(record_id):
                changes.append(f"records/{record_id}")
        for secret_id in sorted(set(self.secrets) | set(before.secrets)):
            if self.secrets.get(secret_id) != before.secrets.get(secret_id):
                changes.append(f"secrets/{secret_id}")
        return changes

    def add_principal(self, principal_id: str, role: str = "user") -> Principal:
        principal = Principal(id=principal_id, role=role)
        self.principals[principal_id] = principal
        return principal

    def add_document(self, document: Document) -> None:
        self.documents[document.id] = document

    def add_record(self, record: Record) -> None:
        self.records[record.id] = record

    def grant(self, principal: str, resource: str, permission: Permission = "read") -> None:
        self.grants.setdefault((principal, resource), set()).add(permission)
