"""Unit tests for JSONL result serialisation."""

from __future__ import annotations

from pathlib import Path

import pytest

from promptfence.reports.jsonl import dumps, read_jsonl, write_jsonl
from promptfence.schemas import Event, Outcome, TrialResult


def make_result(**overrides) -> TrialResult:
    payload = dict(
        run_id="run-1",
        trial_id="s-trial-001",
        scenario_id="s",
        scenario_version=1,
        scenario_fingerprint="abc123",
        category="data_isolation",
        adapter="mock",
        model="deterministic-mock",
        app_profile="hardened",
        status=Outcome.ATTEMPTED_DENIED,
        events=[Event(id="event-001", kind="tool_call", principal="alice", decision="deny")],
        output="Access denied",
        runner_version="0.1.0",
    )
    payload.update(overrides)
    return TrialResult(**payload)


def test_round_trip(tmp_path: Path) -> None:
    original = [make_result(), make_result(trial_id="s-trial-002", status=Outcome.BLOCKED)]
    path = write_jsonl(original, tmp_path / "nested" / "run.jsonl")
    assert path.exists()
    assert [r.model_dump() for r in read_jsonl(path)] == [r.model_dump() for r in original]


def test_one_object_per_line(tmp_path: Path) -> None:
    path = write_jsonl([make_result(), make_result()], tmp_path / "run.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(line.startswith("{") for line in lines)


def test_schema_version_is_recorded(tmp_path: Path) -> None:
    path = write_jsonl([make_result()], tmp_path / "run.jsonl")
    assert '"schema_version": 1' in path.read_text(encoding="utf-8")


def test_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text(dumps(make_result()).replace('"schema_version": 1', '"schema_version": 9'))
    with pytest.raises(ValueError, match="schema version 9"):
        read_jsonl(path)


def test_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        read_jsonl(path)


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_jsonl(tmp_path / "absent.jsonl")


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text(f"{dumps(make_result())}\n\n{dumps(make_result())}\n", encoding="utf-8")
    assert len(read_jsonl(path)) == 2


def test_append_mode(tmp_path: Path) -> None:
    path = write_jsonl([make_result()], tmp_path / "run.jsonl")
    write_jsonl([make_result(trial_id="s-trial-002")], path, overwrite=False)
    assert len(read_jsonl(path)) == 2
