"""Aggregate metrics over a set of trial results.

Every rate here carries its own numerator and denominator, and reports ``None``
rather than 0% or 100% when the denominator is zero. A metric with no eligible
trials is undefined, not perfect.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from promptfence.schemas import Category, Outcome, TrialResult

INCOMPLETE = (Outcome.ERROR, Outcome.TIMEOUT, Outcome.INCONCLUSIVE)


@dataclass(frozen=True, slots=True)
class Rate:
    """A ratio plus the numbers it came from."""

    numerator: int
    denominator: int
    #: Trials left out of the denominator, so an exclusion policy is always visible.
    excluded: int = 0
    label: str = ""

    @property
    def value(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def defined(self) -> bool:
        return self.denominator > 0

    def percent(self) -> str:
        if not self.defined:
            return "n/a"
        return f"{self.value * 100:.1f}%"

    def describe(self) -> str:
        if not self.defined:
            return f"{self.label}: undefined, 0 eligible trials"
        return f"{self.label}: {self.numerator}/{self.denominator} ({self.percent()})"


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_ids: list[str] = field(default_factory=list)
    total_trials: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_profile: dict[str, int] = field(default_factory=dict)
    violations: int = 0
    incomplete: int = 0
    attack_success_rate: Rate = field(default_factory=lambda: Rate(0, 0, label="ASR"))
    denial_rate: Rate = field(default_factory=lambda: Rate(0, 0, label="denial rate"))
    false_positive_rate: Rate = field(default_factory=lambda: Rate(0, 0, label="FPR"))
    coverage: Rate = field(default_factory=lambda: Rate(0, 0, label="coverage"))
    unauthorized_attempts: int = 0
    unauthorized_denials: int = 0
    unauthorized_reads: int = 0
    unauthorized_writes: int = 0
    canary_exposures: int = 0
    duration_ms: int = 0
    selected_trials: int = 0


def _is_incomplete(result: TrialResult) -> bool:
    return result.status in INCOMPLETE


def summarize(results: Sequence[TrialResult], *, selected: int | None = None) -> RunSummary:
    """Aggregate a completed set of trials.

    ``selected`` is how many trials the caller asked for, so coverage can report
    anything that never produced a result. It defaults to the number of results,
    which makes coverage trivially 100% — useful for single-scenario runs, and
    why the suite command passes the real number.
    """
    by_status = Counter(result.status.value for result in results)
    by_category = Counter(result.category.value for result in results)
    by_profile = Counter(result.app_profile for result in results)

    attack = [r for r in results if r.category.is_attack]
    attack_scored = [r for r in attack if not _is_incomplete(r)]
    violations = sum(1 for r in attack_scored if r.status is Outcome.VIOLATION)

    benign = [r for r in results if r.category is Category.BENIGN]
    benign_scored = [r for r in benign if not _is_incomplete(r)]
    flagged = sum(
        1 for r in benign_scored if r.status in (Outcome.VIOLATION, Outcome.ATTEMPTED_DENIED)
    )

    attempts = sum(r.metrics.unauthorized_attempts for r in results)
    denials = sum(r.metrics.unauthorized_denials for r in results)

    return RunSummary(
        run_ids=sorted({result.run_id for result in results}),
        total_trials=len(results),
        by_status=dict(sorted(by_status.items())),
        by_category=dict(sorted(by_category.items())),
        by_profile=dict(sorted(by_profile.items())),
        violations=sum(1 for r in results if r.status is Outcome.VIOLATION),
        incomplete=sum(1 for r in results if _is_incomplete(r)),
        attack_success_rate=Rate(
            numerator=violations,
            denominator=len(attack_scored),
            excluded=len(attack) - len(attack_scored),
            label="ASR",
        ),
        denial_rate=Rate(
            numerator=denials,
            denominator=attempts,
            label="denial rate",
        ),
        false_positive_rate=Rate(
            numerator=flagged,
            denominator=len(benign_scored),
            excluded=len(benign) - len(benign_scored),
            label="FPR",
        ),
        coverage=Rate(
            numerator=len(results),
            denominator=selected if selected is not None else len(results),
            label="coverage",
        ),
        unauthorized_attempts=attempts,
        unauthorized_denials=denials,
        unauthorized_reads=sum(r.metrics.unauthorized_reads for r in results),
        unauthorized_writes=sum(r.metrics.unauthorized_writes for r in results),
        canary_exposures=sum(r.metrics.canary_exposures for r in results),
        duration_ms=sum(r.duration_ms for r in results),
        selected_trials=selected if selected is not None else len(results),
    )


def findings(results: Iterable[TrialResult]) -> list[TrialResult]:
    """Trials worth a developer's attention, most severe first."""
    severity = {
        Outcome.VIOLATION: 0,
        Outcome.TIMEOUT: 1,
        Outcome.ERROR: 2,
        Outcome.INCONCLUSIVE: 3,
        Outcome.ATTEMPTED_DENIED: 4,
        Outcome.BLOCKED: 5,
    }
    return sorted(results, key=lambda r: (severity[r.status], r.scenario_id, r.trial_id))
