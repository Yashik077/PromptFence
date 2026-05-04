"""Typed schemas for scenarios, application events and trial results.

Everything that crosses a boundary — files in, JSONL out — is modelled here so
that malformed input fails loudly instead of half-working.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Guard rails against oversized scenario files. A scenario is a security test,
# not a place to smuggle a corpus.
MAX_SCENARIO_BYTES = 256 * 1024
MAX_MESSAGE_CHARS = 16_000
MAX_DOCUMENT_CHARS = 16_000
MAX_UNTRUSTED_CHARS = 16_000
MAX_SCENARIO_DOCUMENTS = 64


class SchemaError(ValueError):
    """Raised when a scenario or result cannot be parsed or validated."""


class Category(StrEnum):
    """The security property a scenario exercises."""

    DIRECT_INJECTION = "direct_injection"
    INDIRECT_INJECTION = "indirect_injection"
    UNAUTHORIZED_TOOLS = "unauthorized_tools"
    DATA_ISOLATION = "data_isolation"
    SECRET_EXPOSURE = "secret_exposure"
    STATE_CHANGE = "state_change"
    BENIGN = "benign"

    @property
    def is_attack(self) -> bool:
        """Whether trials in this category count towards attack denominators."""
        return self is not Category.BENIGN


class Outcome(StrEnum):
    """The outcome of a single trial.

    These describe the tested behaviour only. ``ERROR``/``TIMEOUT``/``INCONCLUSIVE``
    are never treated as successful defences.
    """

    BLOCKED = "blocked"
    ATTEMPTED_DENIED = "attempted_denied"
    VIOLATION = "violation"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    TIMEOUT = "timeout"

    @property
    def counts_as_defence(self) -> bool:
        return self in (Outcome.BLOCKED, Outcome.ATTEMPTED_DENIED)


class InvariantStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class DocumentSpec(BaseModel):
    """A synthetic document planted in the mock application."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    owner: str = Field(min_length=1, max_length=64)
    content: str = Field(max_length=MAX_DOCUMENT_CHARS)
    title: str | None = Field(default=None, max_length=200)

    @field_validator("id", "owner")
    @classmethod
    def _identifier_charset(cls, value: str) -> str:
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("identifiers must be alphanumeric with - or _ only")
        return value


class RecordSpec(BaseModel):
    """A synthetic mutable application record, owned by one principal."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    owner: str = Field(min_length=1, max_length=64)
    value: str = Field(max_length=MAX_DOCUMENT_CHARS)

    @field_validator("id", "owner")
    @classmethod
    def _identifier_charset(cls, value: str) -> str:
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("identifiers must be alphanumeric with - or _ only")
        return value


class AccessGrant(BaseModel):
    """An explicit, scenario-declared permission for a principal."""

    model_config = ConfigDict(extra="forbid")

    principal: str
    document: str
    permission: str = "read"


class ScenarioSetup(BaseModel):
    """Synthetic state the trial starts from."""

    model_config = ConfigDict(extra="forbid")

    principal: str = Field(min_length=1, max_length=64)
    documents: list[DocumentSpec] = Field(default_factory=list, max_length=MAX_SCENARIO_DOCUMENTS)
    secrets: dict[str, str] = Field(default_factory=dict)
    #: Mutable application records, for scenarios about forbidden state changes.
    records: list[RecordSpec] = Field(default_factory=list, max_length=MAX_SCENARIO_DOCUMENTS)
    #: Grants an extra principal read access to a document, for positive-control
    #: scenarios that need an explicitly permitted cross-principal read.
    grants: list[AccessGrant] = Field(default_factory=list)

    @field_validator("documents")
    @classmethod
    def _unique_document_ids(cls, value: list[DocumentSpec]) -> list[DocumentSpec]:
        seen: set[str] = set()
        for document in value:
            if document.id in seen:
                raise ValueError(f"duplicate document id: {document.id}")
            seen.add(document.id)
        return value

    @field_validator("records")
    @classmethod
    def _unique_record_ids(cls, value: list[RecordSpec]) -> list[RecordSpec]:
        seen: set[str] = set()
        for record in value:
            if record.id in seen:
                raise ValueError(f"duplicate record id: {record.id}")
            seen.add(record.id)
        return value

    @model_validator(mode="after")
    def _resource_ids_are_disjoint(self) -> ScenarioSetup:
        # Authorization resolves a resource id in one namespace, so a document and
        # a record may not share an id or the tools become ambiguous.
        document_ids = {document.id for document in self.documents}
        collisions = document_ids & {record.id for record in self.records}
        if collisions:
            raise ValueError(f"document and record ids overlap: {sorted(collisions)}")
        return self


class ScenarioInput(BaseModel):
    """What the tested application is asked to do."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str | None = Field(default=None, max_length=MAX_MESSAGE_CHARS)
    message: str = Field(max_length=MAX_MESSAGE_CHARS)
    untrusted_documents: list[str] = Field(default_factory=list)
    #: Name of the mock application profile under test.
    app_profile: str = "hardened"

    @field_validator("untrusted_documents")
    @classmethod
    def _bound_untrusted_text(cls, value: list[str]) -> list[str]:
        total = sum(len(item) for item in value)
        if total > MAX_UNTRUSTED_CHARS:
            raise ValueError(f"untrusted content exceeds {MAX_UNTRUSTED_CHARS} characters")
        return value


class Scenario(BaseModel):
    """A single declarative security test."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1)
    category: Category
    description: str = Field(max_length=2_000)
    setup: ScenarioSetup
    input: ScenarioInput
    invariants: list[str] = Field(min_length=1)
    expected: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4_000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
        if not value or not set(value.lower()) <= allowed:
            raise ValueError("scenario id must match [a-z0-9-_]+")
        return value

    @field_validator("invariants")
    @classmethod
    def _unique_invariants(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate invariant names")
        return value

    def fingerprint(self) -> str:
        """A stable identity for the scenario content, used in result metadata."""
        import hashlib

        payload = "|".join(
            [
                self.id,
                str(self.version),
                self.category.value,
                self.input.message,
                *self.invariants,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class Event(BaseModel):
    """A single security-relevant operation recorded by the mock application."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    tool: str | None = None
    principal: str
    resource: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    decision: str | None = None
    reason: str | None = None
    #: Values that were actually returned to the caller.
    disclosed: list[str] = Field(default_factory=list)
    changed_state: list[str] = Field(default_factory=list)
    sequence: int = 0


class InvariantResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: InvariantStatus
    evidence: list[str] = Field(default_factory=list)
    detail: str | None = None


class TrialMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    tool_calls: int = 0
    unauthorized_attempts: int = 0
    unauthorized_denials: int = 0
    unauthorized_reads: int = 0
    unauthorized_writes: int = 0
    canary_exposures: int = 0


class TrialResult(BaseModel):
    """One structured result per trial, serialised as a single JSONL line."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    run_id: str
    trial_id: str
    scenario_id: str
    scenario_version: int
    scenario_fingerprint: str
    category: Category
    tags: list[str] = Field(default_factory=list)
    adapter: str
    model: str
    #: Identifies the adapter configuration without exposing a credential. For
    #: remote adapters this is endpoint + model + a hash prefix of the key.
    adapter_fingerprint: str | None = None
    app_profile: str
    status: Outcome
    invariants: list[InvariantResult] = Field(default_factory=list)
    metrics: TrialMetrics = Field(default_factory=TrialMetrics)
    events: list[Event] = Field(default_factory=list)
    output: str | None = None
    error: str | None = None
    duration_ms: int = 0
    runner_version: str = ""
