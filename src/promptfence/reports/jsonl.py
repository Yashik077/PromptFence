"""JSONL results.

One JSON object per trial, one line per object, UTF-8, LF endings. The format is
the contract between a run and everything downstream, so it is versioned and
anything unreadable is an error rather than a skipped line.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from promptfence.schemas import TrialResult

SCHEMA_VERSION = 1


def dumps(result: TrialResult) -> str:
    payload = result.model_dump(mode="json")
    payload["schema_version"] = SCHEMA_VERSION
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def write_jsonl(
    results: Iterable[TrialResult],
    path: str | os.PathLike[str],
    *,
    overwrite: bool = True,
) -> Path:
    """Write results to ``path``, creating parent directories as needed."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "a"
    with destination.open(mode, encoding="utf-8", newline="\n") as handle:
        for result in results:
            handle.write(dumps(result))
            handle.write("\n")
    return destination


def read_jsonl(path: str | os.PathLike[str]) -> list[TrialResult]:
    """Load results written by :func:`write_jsonl`."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"{source}: no such results file")

    results: list[TrialResult] = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source}:{number}: not valid JSON ({exc})") from exc
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"{source}:{number}: result schema version {version!r} is not supported "
                f"(this build reads version {SCHEMA_VERSION})"
            )
        try:
            results.append(TrialResult.model_validate(payload))
        except ValidationError as exc:
            raise ValueError(f"{source}:{number}: result failed validation ({exc})") from exc
    return results
