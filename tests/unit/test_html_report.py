"""Unit tests for the HTML report."""

from __future__ import annotations

from pathlib import Path

from promptfence.reports.html import render, render_to_file
from promptfence.schemas import (
    Category,
    Event,
    InvariantResult,
    InvariantStatus,
    Outcome,
    TrialResult,
)


def make_result(**overrides) -> TrialResult:
    payload = dict(
        run_id="run-1",
        trial_id="t1",
        scenario_id="data-isolation-001",
        scenario_version=1,
        scenario_fingerprint="fp",
        category=Category.DATA_ISOLATION,
        adapter="mock",
        model="deterministic-mock",
        app_profile="hardened",
        status=Outcome.VIOLATION,
        invariants=[
            InvariantResult(
                id="unauthorized_read_never_succeeds",
                status=InvariantStatus.FAILED,
                evidence=["event-002"],
                detail="read returned bob-private to alice",
            )
        ],
        events=[Event(id="event-002", kind="tool_call", principal="alice", decision="allow")],
        runner_version="0.1.0",
    )
    payload.update(overrides)
    return TrialResult(**payload)


def test_report_contains_the_finding_and_its_evidence() -> None:
    page = render([make_result()])
    assert "data-isolation-001" in page
    assert "event-002" in page
    assert "read returned bob-private to alice" in page


def test_report_states_the_run_id_and_outcome_counts() -> None:
    page = render([make_result(), make_result(trial_id="t2", status=Outcome.BLOCKED)])
    assert "run-1" in page
    assert '<td class="violation">violation</td><td>1</td>' in page
    assert '<td class="blocked">blocked</td><td>1</td>' in page


def test_metrics_carry_denominators() -> None:
    page = render([make_result()])
    assert "ASR: 1/1 (100.0%)" in page


def test_undefined_metric_is_not_zero_percent() -> None:
    page = render([make_result(category=Category.BENIGN)])
    assert "undefined, 0 eligible trials" in page


def test_scenario_text_cannot_break_out_of_the_page() -> None:
    hostile = make_result(
        scenario_id="x",
        invariants=[
            InvariantResult(
                id="unauthorized_read_never_succeeds",
                status=InvariantStatus.FAILED,
                detail='<script>alert("xss")</script>',
            )
        ],
    )
    page = render([hostile])
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_render_to_file_creates_parents(tmp_path: Path) -> None:
    path = render_to_file([make_result()], tmp_path / "nested" / "report.html")
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_empty_run_still_renders() -> None:
    page = render([])
    assert "No violations, errors or denials." in page
