"""Unit tests for metric aggregation."""

from __future__ import annotations

from promptfence.metrics import Rate, findings, summarize
from promptfence.schemas import Category, Outcome, TrialMetrics, TrialResult


def make_result(
    *,
    category: Category = Category.DATA_ISOLATION,
    status: Outcome = Outcome.BLOCKED,
    attempts: int = 0,
    denials: int = 0,
    trial_id: str = "t1",
) -> TrialResult:
    return TrialResult(
        run_id="run-1",
        trial_id=trial_id,
        scenario_id=f"scenario-{trial_id}",
        scenario_version=1,
        scenario_fingerprint="fp",
        category=category,
        adapter="mock",
        model="deterministic-mock",
        app_profile="hardened",
        status=status,
        metrics=TrialMetrics(
            tool_calls=attempts,
            unauthorized_attempts=attempts,
            unauthorized_denials=denials,
        ),
    )


def test_rate_with_zero_denominator_is_undefined() -> None:
    rate = Rate(numerator=0, denominator=0, label="ASR")
    assert rate.value is None
    assert rate.percent() == "n/a"
    assert "undefined" in rate.describe()


def test_rate_reports_both_numbers() -> None:
    assert Rate(numerator=1, denominator=4, label="ASR").describe() == "ASR: 1/4 (25.0%)"


def test_asr_counts_only_completed_attack_trials() -> None:
    results = [
        make_result(status=Outcome.VIOLATION),
        make_result(status=Outcome.BLOCKED, trial_id="t2"),
        make_result(status=Outcome.ERROR, trial_id="t3"),
        make_result(status=Outcome.TIMEOUT, trial_id="t4"),
    ]
    summary = summarize(results)
    assert summary.attack_success_rate.numerator == 1
    assert summary.attack_success_rate.denominator == 2
    assert summary.attack_success_rate.excluded == 2
    assert summary.incomplete == 2


def test_asr_is_undefined_without_attack_trials() -> None:
    summary = summarize([make_result(category=Category.BENIGN)])
    assert summary.attack_success_rate.defined is False
    assert summary.attack_success_rate.percent() == "n/a"


def test_denial_rate_is_undefined_without_attempts() -> None:
    assert summarize([]).denial_rate.defined is False
    with_attempts = summarize([make_result(attempts=2, denials=2)])
    assert with_attempts.denial_rate.value == 1.0


def test_false_positive_rate_counts_flagged_benign_trials() -> None:
    results = [
        make_result(category=Category.BENIGN, status=Outcome.BLOCKED, trial_id="b1"),
        make_result(category=Category.BENIGN, status=Outcome.ATTEMPTED_DENIED, trial_id="b2"),
        make_result(category=Category.BENIGN, status=Outcome.VIOLATION, trial_id="b3"),
    ]
    summary = summarize(results)
    assert summary.false_positive_rate.numerator == 2
    assert summary.false_positive_rate.denominator == 3


def test_coverage_uses_the_selected_count() -> None:
    summary = summarize([make_result()], selected=4)
    assert summary.coverage.numerator == 1
    assert summary.coverage.denominator == 4
    assert summary.coverage.percent() == "25.0%"


def test_coverage_defaults_to_results_length() -> None:
    assert summarize([make_result()]).coverage.percent() == "100.0%"


def test_counts_are_grouped() -> None:
    results = [
        make_result(status=Outcome.VIOLATION, trial_id="a"),
        make_result(status=Outcome.BLOCKED, trial_id="b"),
    ]
    summary = summarize(results)
    assert summary.by_status == {"blocked": 1, "violation": 1}
    assert summary.by_category == {"data_isolation": 2}
    assert summary.violations == 1


def test_findings_are_ordered_by_severity() -> None:
    results = [
        make_result(status=Outcome.BLOCKED, trial_id="ok"),
        make_result(status=Outcome.VIOLATION, trial_id="bad"),
        make_result(status=Outcome.ERROR, trial_id="boom"),
        make_result(status=Outcome.ATTEMPTED_DENIED, trial_id="denied"),
    ]
    assert [r.status.value for r in findings(results)] == [
        "violation",
        "error",
        "attempted_denied",
        "blocked",
    ]


def test_empty_run_does_not_explode() -> None:
    summary = summarize([])
    assert summary.total_trials == 0
    assert summary.by_status == {}
    assert summary.attack_success_rate.percent() == "n/a"
