"""A small self-contained HTML report.

The report is written to a single file with no external assets so it can be
attached to a CI run or opened from a file:// URL.
"""

from __future__ import annotations

import html
import os
from collections.abc import Sequence
from pathlib import Path

from promptfence import __version__
from promptfence.metrics import RunSummary, findings, summarize
from promptfence.schemas import Outcome, TrialResult

STATUS_ORDER = [
    Outcome.VIOLATION,
    Outcome.ATTEMPTED_DENIED,
    Outcome.BLOCKED,
    Outcome.INCONCLUSIVE,
    Outcome.TIMEOUT,
    Outcome.ERROR,
]

STYLE = """
:root { color-scheme: light dark; }
body { font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       margin: 2rem auto; max-width: 60rem; padding: 0 1rem; }
h1 { font-size: 1.6rem; margin-bottom: 0.2rem; }
h2 { font-size: 1.2rem; margin-top: 2.2rem; }
table { border-collapse: collapse; width: 100%; margin: 0.6rem 0; }
th, td { border-bottom: 1px solid #8884; padding: 0.35rem 0.5rem; text-align: left;
         vertical-align: top; font-size: 0.92rem; }
th { font-weight: 600; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; }
pre { white-space: pre-wrap; word-break: break-word; }
.violation { color: #b00020; font-weight: 600; }
.attempted_denied { color: #a06000; }
.blocked { color: #1a7f37; }
.error, .timeout, .inconclusive { color: #666; font-style: italic; }
.muted { color: #777; font-size: 0.85rem; }
"""


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render(results: Sequence[TrialResult], *, title: str = "PromptFence report") -> str:
    summary = summarize(results, selected=len(results))
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{_esc(title)}</title>",
        f"<style>{STYLE}</style>",
        "</head><body>",
        f"<h1>{_esc(title)}</h1>",
        _environment(summary),
        _metrics(summary),
        _status_table(summary),
        _findings(results),
        "</body></html>",
    ]
    return "\n".join(parts)


def render_to_file(
    results: Sequence[TrialResult],
    path: str | os.PathLike[str],
    *,
    title: str = "PromptFence report",
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render(results, title=title), encoding="utf-8")
    return destination


def _environment(summary: RunSummary) -> str:
    runs = ", ".join(summary.run_ids) or "n/a"
    return (
        "<h2>Run</h2><table>"
        f"<tr><th>Run id</th><td>{_esc(runs)}</td></tr>"
        f"<tr><th>Trials</th><td>{summary.total_trials}</td></tr>"
        f"<tr><th>App profiles</th><td>{_esc(summary.by_profile)}</td></tr>"
        f"<tr><th>Runner</th><td>{_esc(__version__)}</td></tr>"
        f"<tr><th>Total time</th><td>{summary.duration_ms} ms</td></tr>"
        "</table>"
    )


def _metrics(summary: RunSummary) -> str:
    asr = summary.attack_success_rate
    rows = [
        ("Attack success rate", asr.describe() + _excluded(asr.excluded)),
        ("Unauthorized-action denial rate", summary.denial_rate.describe()),
        ("False-positive rate", summary.false_positive_rate.describe()),
        ("Coverage", summary.coverage.describe()),
    ]
    body = "".join(f"<tr><th>{_esc(name)}</th><td>{_esc(value)}</td></tr>" for name, value in rows)
    return f"<h2>Metrics</h2><table>{body}</table>"


def _excluded(excluded: int) -> str:
    return f" ({excluded} trial(s) excluded as incomplete)" if excluded else ""


def _status_table(summary: RunSummary) -> str:
    rows = []
    for status in STATUS_ORDER:
        count = summary.by_status.get(status.value, 0)
        rows.append(
            f"<tr><td class=\"{status.value}\">{_esc(status.value)}</td>"
            f"<td>{count}</td></tr>"
        )
    body = "".join(rows)
    return f"<h2>Outcomes</h2><table><tr><th>Outcome</th><th>Trials</th></tr>{body}</table>"


def _findings(results: Sequence[TrialResult]) -> str:
    rows = []
    for result in findings(results):
        if result.status is Outcome.BLOCKED:
            continue
        failed = [i for i in result.invariants if i.status.value == "failed"]
        detail = "<br>".join(
            f"{_esc(i.id)}: {_esc(i.detail)} (evidence: {_esc(', '.join(i.evidence))})"
            for i in failed
        )
        if result.error:
            detail = f"{detail}<br>{_esc(result.error)}" if detail else _esc(result.error)
        rows.append(
            f"<tr><td class=\"{result.status.value}\">{_esc(result.status.value)}</td>"
            f"<td>{_esc(result.scenario_id)} v{result.scenario_version}<br>"
            f"<span class=\"muted\">{_esc(result.trial_id)} &middot; {_esc(result.app_profile)}"
            f"</span></td><td>{detail}</td></tr>"
        )
    if not rows:
        return "<h2>Findings</h2><p class=\"muted\">No violations, errors or denials.</p>"
    body = "".join(rows)
    return f"<h2>Findings</h2><table><tr><th>Outcome</th><th>Scenario</th><th>Evidence</th></tr>{body}</table>"
