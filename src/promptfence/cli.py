"""The ``promptfence`` command line.

Four commands and a stable exit-code contract, so CI can rely on it:

===  ==========================================================================
0    ran to completion, no configured regression was found
1    a security invariant was violated, or a configured threshold failed
2    bad arguments, bad configuration, or a scenario that would not validate
3    the run could not complete: adapter or infrastructure failure
===  ==========================================================================

A suite that contains both violations and execution errors exits 3, because the
errors mean the run is not trustworthy and the violations may be an artefact of
them. Both stay in the output either way.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from promptfence import __version__
from promptfence.adapters.openai_compatible import ADAPTER_NAME as REMOTE_ADAPTER
from promptfence.adapters.registry import available_adapters
from promptfence.config import ConfigError, RemoteModelConfig
from promptfence.metrics import summarize
from promptfence.reports.html import render_to_file
from promptfence.reports.jsonl import read_jsonl, write_jsonl
from promptfence.runner import RunConfig, Runner, new_run_id
from promptfence.scenarios.loader import load_scenario, load_suite
from promptfence.schemas import Outcome, SchemaError, TrialResult

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2
EXIT_INFRASTRUCTURE = 3

FAIL_ON_CHOICES = ("violation", "inconclusive", "error", "never")

EndpointOption = Annotated[
    str | None,
    typer.Option(
        "--endpoint",
        help="Base URL of an OpenAI-compatible endpoint. Required for --model openai_compatible.",
    ),
]
RemoteModelOption = Annotated[
    str | None,
    typer.Option("--remote-model", help="Model id to request from the endpoint."),
]

app = typer.Typer(
    name="promptfence",
    help="Security testing framework for AI applications.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the installed PromptFence version."""
    typer.echo(__version__)


@app.command()
def validate(
    target: Annotated[
        Path,
        typer.Argument(help="A scenario file or a directory of scenarios."),
    ],
) -> None:
    """Parse and validate scenarios without running anything."""
    try:
        scenarios = load_suite(target)
    except SchemaError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE) from exc

    for scenario in scenarios:
        typer.echo(
            f"ok  {scenario.id} v{scenario.version}  "
            f"[{scenario.category.value}] {', '.join(scenario.invariants)}"
        )
    typer.echo(f"\n{len(scenarios)} scenario(s) valid.")


@app.command()
def run(
    scenario: Annotated[Path, typer.Argument(help="Scenario file to execute.")],
    model: Annotated[str, typer.Option("--model", "-m", help="Adapter to use.")] = "mock",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write results here as JSONL.")
    ] = None,
    app_profile: Annotated[
        str | None,
        typer.Option("--app-profile", help="Override the scenario's app profile."),
    ] = None,
    timeout: Annotated[float, typer.Option(help="Per-request timeout in seconds.")] = 30.0,
    max_retries: Annotated[int, typer.Option(help="Retries for transport errors only.")] = 1,
    trials: Annotated[int, typer.Option(help="Repeat the scenario this many times.")] = 1,
    fail_on: Annotated[
        str, typer.Option(help="Which outcomes should exit non-zero.")
    ] = "violation",
    endpoint: EndpointOption = None,
    remote_model: RemoteModelOption = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    """Run a single scenario."""
    config = _config(model, endpoint, remote_model, app_profile, timeout, max_retries, fail_on)
    try:
        loaded = load_scenario(scenario)
    except SchemaError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE) from exc

    runner = Runner(config)
    run_id = new_run_id()
    results = [
        runner.run_scenario(loaded, run_id=run_id, trial_index=index)
        for index in range(1, max(trials, 1) + 1)
    ]

    if output is not None:
        write_jsonl(results, output)
        if not quiet:
            typer.echo(f"wrote {len(results)} result(s) to {output}")
    _print_results(results, quiet=quiet)
    raise typer.Exit(_exit_code(results, fail_on))


@app.command("run-suite")
def run_suite(
    suite: Annotated[Path, typer.Argument(help="Directory of scenarios to execute.")],
    model: Annotated[str, typer.Option("--model", "-m", help="Adapter to use.")] = "mock",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write results here as JSONL.")
    ] = None,
    app_profile: Annotated[
        str | None,
        typer.Option("--app-profile", help="Override every scenario's app profile."),
    ] = None,
    timeout: Annotated[float, typer.Option(help="Per-request timeout in seconds.")] = 30.0,
    max_retries: Annotated[int, typer.Option(help="Retries for transport errors only.")] = 1,
    fail_on: Annotated[
        str, typer.Option(help="Which outcomes should exit non-zero.")
    ] = "violation",
    endpoint: EndpointOption = None,
    remote_model: RemoteModelOption = None,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    """Run every scenario in a directory."""
    config = _config(model, endpoint, remote_model, app_profile, timeout, max_retries, fail_on)
    try:
        scenarios = load_suite(suite)
    except SchemaError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE) from exc

    results = Runner(config).run_suite(scenarios)
    if output is not None:
        write_jsonl(results, output)
        if not quiet:
            typer.echo(f"wrote {len(results)} result(s) to {output}")

    summary = summarize(results, selected=len(scenarios))
    if not quiet:
        _print_summary(summary)
    raise typer.Exit(_exit_code(results, fail_on))


@app.command()
def report(
    input: Annotated[Path, typer.Option("--input", "-i", help="JSONL results to read.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="HTML file to write.")],
    title: Annotated[str, typer.Option(help="Report heading.")] = "PromptFence report",
) -> None:
    """Render an HTML report from saved JSONL results."""
    try:
        results = read_jsonl(input)
    except (FileNotFoundError, ValueError) as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE) from exc

    if not results:
        typer.secho(f"error: {input} contains no results", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USAGE)

    path = render_to_file(results, output, title=title)
    typer.echo(f"wrote report to {path}")


# -- helpers ---------------------------------------------------------------


def _config(
    model: str,
    endpoint: str | None,
    remote_model: str | None,
    app_profile: str | None,
    timeout: float,
    max_retries: int,
    fail_on: str,
) -> RunConfig:
    if fail_on not in FAIL_ON_CHOICES:
        typer.secho(
            f"error: --fail-on must be one of {', '.join(FAIL_ON_CHOICES)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(EXIT_USAGE)
    if model not in available_adapters():
        known = ", ".join(sorted(available_adapters()))
        typer.secho(
            f"error: unknown adapter {model!r}; available: {known}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(EXIT_USAGE)

    options: dict[str, object] = {}
    if model == REMOTE_ADAPTER:
        try:
            remote = RemoteModelConfig.resolve(
                base_url=endpoint, model=remote_model, timeout=timeout
            )
        except ConfigError as exc:
            typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_USAGE) from exc
        options["config"] = remote
        typer.secho(
            f"note: prompts and scenario content will be sent to {remote.base_url}",
            fg=typer.colors.YELLOW,
            err=True,
        )

    return RunConfig(
        adapter_name=model,
        adapter_options=options,
        app_profile=app_profile,
        timeout_seconds=timeout,
        max_retries=max_retries,
    )


def _exit_code(results: list[TrialResult], fail_on: str) -> int:
    statuses = {result.status for result in results}
    if {Outcome.ERROR, Outcome.TIMEOUT} & statuses:
        return EXIT_INFRASTRUCTURE
    if fail_on == "never":
        return EXIT_OK
    triggers = {
        "violation": {Outcome.VIOLATION},
        "inconclusive": {Outcome.VIOLATION, Outcome.INCONCLUSIVE},
        "error": {Outcome.VIOLATION, Outcome.INCONCLUSIVE, Outcome.ERROR, Outcome.TIMEOUT},
    }[fail_on]
    return EXIT_VIOLATION if statuses & triggers else EXIT_OK


def _print_results(results: list[TrialResult], *, quiet: bool) -> None:
    if quiet:
        return
    for result in results:
        colour = typer.colors.RED if result.status is Outcome.VIOLATION else None
        typer.secho(
            f"{result.status.value:<18} {result.scenario_id} "
            f"({result.app_profile}, {result.duration_ms} ms)",
            fg=colour,
        )
        for invariant in result.invariants:
            if invariant.status.value == "failed":
                typer.echo(f"    {invariant.id}: {invariant.detail}")
        if result.error:
            typer.echo(f"    error: {result.error}")


def _print_summary(summary) -> None:  # noqa: ANN001 - RunSummary, kept untyped for brevity
    typer.echo(
        json.dumps({"trials": summary.total_trials, "outcomes": summary.by_status}, indent=2)
    )
    typer.echo(f"ASR         {summary.attack_success_rate.describe()}")
    typer.echo(f"denial rate {summary.denial_rate.describe()}")
    typer.echo(f"false pos.   {summary.false_positive_rate.describe()}")
    typer.echo(f"coverage     {summary.coverage.describe()}")


def main() -> None:
    try:
        app()
    except BrokenPipeError:  # pragma: no cover - `| head` and friends
        sys.exit(EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    main()
