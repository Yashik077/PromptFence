"""Safe loading of declarative scenario files.

Scenario files are data, never programs. They are parsed with ``yaml.safe_load``
and validated into :class:`~promptfence.schemas.Scenario`; no Python is imported,
evaluated or exec'd from a scenario, and no scenario field can name a path to
write to or a command to run.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import ValidationError

from promptfence.oracles.registry import known_invariants
from promptfence.schemas import MAX_SCENARIO_BYTES, Scenario, SchemaError

SUITE_SUFFIXES = (".yaml", ".yml")


def _read_text(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:  # pragma: no cover - surfaced to the CLI as a usage error
        raise SchemaError(f"{path}: cannot read scenario file ({exc})") from exc
    if size > MAX_SCENARIO_BYTES:
        raise SchemaError(
            f"{path}: scenario is {size} bytes, limit is {MAX_SCENARIO_BYTES}. "
            "Scenarios should describe one security property, not a corpus."
        )
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SchemaError(f"{path}: scenario file is not valid UTF-8") from exc


def _parse(path: Path, text: str) -> Scenario:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SchemaError(f"{path}: invalid YAML ({exc})") from exc

    if not isinstance(raw, dict):
        raise SchemaError(f"{path}: scenario must be a YAML mapping, got {type(raw).__name__}")

    try:
        scenario = Scenario.model_validate(raw)
    except ValidationError as exc:
        raise SchemaError(_format_validation_error(path, exc)) from exc
    _check_invariants(path, scenario)
    return scenario


def _check_invariants(path: Path, scenario: Scenario) -> None:
    """Reject invariants no oracle can evaluate.

    Silently ignoring one would produce a report that looks clean because a
    property was never checked.
    """
    known = known_invariants()
    unknown = [name for name in scenario.invariants if name not in known]
    if unknown:
        raise SchemaError(
            f"{path}: unknown invariant(s) {unknown}. Known invariants: {', '.join(sorted(known))}"
        )


def _format_validation_error(path: Path, exc: ValidationError) -> str:
    problems = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        problems.append(f"  - {location}: {error['msg']}")
    body = "\n".join(problems)
    return f"{path}: scenario failed validation\n{body}"


def load_scenario(path: str | os.PathLike[str]) -> Scenario:
    """Parse and validate a single scenario file."""
    resolved = Path(path)
    if not resolved.is_file():
        raise SchemaError(f"{path}: scenario file not found")
    return _parse(resolved, _read_text(resolved))


def iter_scenario_files(target: str | os.PathLike[str]) -> Iterable[Path]:
    """Yield scenario files under ``target`` in a stable order."""
    root = Path(target)
    if root.is_file():
        if root.suffix.lower() not in SUITE_SUFFIXES:
            raise SchemaError(f"{root}: expected a .yaml or .yml scenario file")
        yield root
        return
    if not root.is_dir():
        raise SchemaError(f"{target}: not a scenario file or directory")
    yield from sorted(p for p in root.rglob("*") if p.suffix.lower() in SUITE_SUFFIXES)


def load_suite(target: str | os.PathLike[str]) -> list[Scenario]:
    """Load every scenario under ``target`` and check ids are unique."""
    scenarios: list[Scenario] = []
    seen: dict[str, Path] = {}
    for path in iter_scenario_files(target):
        scenario = load_scenario(path)
        if scenario.id in seen:
            raise SchemaError(
                f"{path}: duplicate scenario id {scenario.id!r} "
                f"(already defined in {seen[scenario.id]})"
            )
        seen[scenario.id] = path
        scenarios.append(scenario)
    if not scenarios:
        raise SchemaError(f"{target}: no scenarios found")
    return scenarios


def validate_path(target: str | os.PathLike[str]) -> list[Scenario]:
    """Validation entry point that never touches a model or runs a scenario."""
    return load_suite(target)
