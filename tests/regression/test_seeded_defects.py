"""Regression tests.

Each test here pins a behaviour that broke at least once. A failure means a real
regression, not that an expectation needs updating.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from promptfence.runner import RunConfig, Runner
from promptfence.scenarios.loader import load_scenario, load_suite
from promptfence.schemas import InvariantStatus, Outcome

CORPUS = Path(__file__).resolve().parents[2] / "scenarios"


def run(scenario_path: Path, **config: object):
    scenario = load_scenario(scenario_path)
    return Runner(RunConfig(**config)).run_scenario(scenario, run_id="run-regression")


def scenario(name: str) -> Path:
    return CORPUS / name


# -- the seeded defect must stay detectable -------------------------------


@pytest.mark.parametrize(
    "relative",
    [
        "data_isolation/cross_user_access.yaml",
        "indirect_injection/forged_delete.yaml",
        "state_change/forged_write.yaml",
    ],
)
def test_hardened_app_rejects_every_seeded_attack(relative: str) -> None:
    result = run(scenario(relative))
    assert result.status is not Outcome.VIOLATION, result.invariants
    assert result.metrics.unauthorized_reads == 0
    assert result.metrics.unauthorized_writes == 0


@pytest.mark.parametrize(
    "relative",
    [
        "data_isolation/cross_user_access.yaml",
        "indirect_injection/forged_delete.yaml",
        "state_change/forged_write.yaml",
    ],
)
def test_vulnerable_app_produces_a_detectable_violation(relative: str) -> None:
    """The defect has to stay detectable, or a green suite means nothing.

    Only scenarios that offer an identity to steal belong here. The seeded defect
    is identity substitution, so direct-injection-001 — where the target is a
    secret with no owner to impersonate — stays denied even in the vulnerable
    profile, which is the correct outcome rather than a gap.
    """
    result = run(scenario(relative), app_profile="vulnerable")
    assert result.status is Outcome.VIOLATION, result.invariants
    assert any(i.status is InvariantStatus.FAILED for i in result.invariants)


# -- benign controls must stay clean --------------------------------------


@pytest.mark.parametrize("relative", ["benign/read_own_document.yaml", "benign/granted_read.yaml"])
def test_benign_controls_are_never_flagged(relative: str) -> None:
    """A granted read is not a leak.

    Reintroducing this bug reports a cross-user violation for a principal that
    legitimately holds a read grant, which is how a corpus starts crying wolf.
    """
    result = run(scenario(relative))
    assert result.status is Outcome.BLOCKED, [i.detail for i in result.invariants]
    assert all(i.status is InvariantStatus.PASSED for i in result.invariants)


def test_denied_write_leaves_both_records_alone() -> None:
    result = run(scenario("state_change/forged_write.yaml"))
    changed = [event.changed_state for event in result.events if event.changed_state]
    assert sorted(path for group in changed for path in group) == ["records/alice-invoice"]


def test_canary_never_reaches_the_caller_in_the_hardened_app() -> None:
    result = run(scenario("data_isolation/cross_user_access.yaml"))
    assert "BOB_CANARY_7F31" not in (result.output or "")


def test_canary_reaches_the_caller_in_the_vulnerable_app() -> None:
    """The other half of the same test: detection has to be able to fire."""
    result = run(scenario("data_isolation/cross_user_access.yaml"), app_profile="vulnerable")
    assert "BOB_CANARY_7F31" in (result.output or "")


# -- corpus-wide guarantees -----------------------------------------------


def test_every_shipped_scenario_runs_offline_and_completes() -> None:
    results = Runner(RunConfig()).run_suite(load_suite(CORPUS), run_id="run-corpus")
    assert len(results) == len(load_suite(CORPUS))
    for result in results:
        assert result.status not in (Outcome.ERROR, Outcome.TIMEOUT), result.error
        assert result.events, f"{result.scenario_id} produced no evidence at all"


def test_a_trial_with_no_evidence_is_never_a_clean_pass() -> None:
    """Empty evidence must not read as 'nothing happened, therefore fine'."""
    result = run(scenario("data_isolation/cross_user_access.yaml"), adapter_factory=_NoTools)
    assert result.status is not Outcome.BLOCKED
    assert result.events == []


class _NoTools:
    name = "silent"
    model = "silent-model"

    def capabilities(self):  # pragma: no cover - trivial
        from promptfence.adapters.base import AdapterCapabilities

        return AdapterCapabilities()

    def complete(self, request):  # pragma: no cover - trivial
        from promptfence.adapters.base import ModelResponse

        return ModelResponse()
