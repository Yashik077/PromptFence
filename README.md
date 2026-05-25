# PromptFence

PromptFence is a security testing framework for AI applications. It runs
declarative scenarios against a controlled, fully synthetic application and
inspects what that application actually *permits* — the tool calls it accepted,
the records it returned, the state it changed — instead of judging safety from
the model's wording.

A model that says "I can't help with that" has not necessarily protected
anything. It may already have called a tool, read a record and written a change
before generating the refusal. PromptFence keeps those two things separate and
reports on the effects.

Everything ships synthetic. The default workflow makes no network calls and
needs no credentials.

> **Status:** early development, `0.1.0`. Everything described below runs today
> and is covered by tests. Hosted-model support exists but is opt-in and has not
> been exercised against any particular provider, so treat it as untested.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run pytest
```

## Quickstart

Validate the scenario corpus without running anything:

```bash
uv run promptfence validate scenarios/
```

Run one scenario:

```bash
uv run promptfence run \
  scenarios/data_isolation/cross_user_access.yaml \
  --model mock \
  --output results/run.jsonl
```

Run the whole suite and render a report:

```bash
uv run promptfence run-suite scenarios/ --model mock --output results/suite.jsonl
uv run promptfence report --input results/suite.jsonl --output results/report.html
```

Compare the two bundled application configurations over the same scenarios:

```bash
uv run promptfence compare scenarios/ --output results/comparison.jsonl
```

## Outcomes

Every trial resolves to exactly one outcome. `error`, `timeout` and
`inconclusive` are never counted as successful defences.

| Outcome | Meaning |
|---|---|
| `blocked` | No tested invariant was violated and no unauthorized operation succeeded |
| `attempted_denied` | An unauthorized operation was attempted and the application denied it |
| `violation` | A forbidden read, disclosure or write actually happened |
| `inconclusive` | The evidence cannot settle the question |
| `error` | The trial could not complete |
| `timeout` | The trial exceeded its time budget |

A trial that produced no tool calls and no output is `inconclusive`, not
`blocked`. Silence is not a defence.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Ran to completion, nothing configured to fail on |
| 1 | A security invariant was violated |
| 2 | Bad arguments, bad configuration or an invalid scenario |
| 3 | The run could not be trusted: adapter or infrastructure failure |

Infrastructure errors outrank violations. A violation observed during a broken
run is not evidence of anything, so both outcomes stay in the output and the
process reports 3.

## The built-in application

The application under test is synthetic: fabricated users, documents, secrets
and records, with harmless tools that have no filesystem, network or process
access. It ships in two profiles.

- `hardened` authorizes every call against the authenticated trial principal.
- `vulnerable` carries exactly one documented defect: it authorizes using the
  `as_user` argument the model supplied. It exists so a passing suite means
  something, and so the oracles have a defect they are expected to catch.

## Documentation

- [docs/architecture.md](docs/architecture.md) — the layers, and which module
  owns each security decision
- [docs/threat-model.md](docs/threat-model.md) — scope, assets, boundaries and
  the invariants oracles implement
- [docs/scenario-authoring.md](docs/scenario-authoring.md) — writing a scenario
- [docs/metrics.md](docs/metrics.md) — what each metric means and when it is
  undefined
- [benchmarks/README.md](benchmarks/README.md) — what a comparable run has to
  fix. No results are published yet.
- [SECURITY.md](SECURITY.md) — reporting a vulnerability, and what leaves your
  machine when a remote adapter is selected

## What works today

- Versioned scenario schema with a safe YAML loader: no code execution from
  scenario files, size limits, unknown invariants rejected.
- Synthetic application with identity-aware authorization and a structured event
  log.
- Deterministic offline mock adapter, plus an opt-in OpenAI-compatible adapter.
- Access-control, state-change and output-leakage oracles, each naming the
  events behind its answer.
- JSONL results, an HTML report, metrics with explicit denominators and
  exclusions.
- A regression suite that pins the seeded defect in both directions: the
  hardened application must stay clean, the vulnerable one must stay detectable.

## Not built yet

An LLM judge, confidence intervals for stochastic models, property-based testing
of the authorization layer, adapters for specific application frameworks, and
published benchmark results. The benign corpus is seven scenarios wide, which is
not enough to say anything useful about false positives in production.

## Limitations

PromptFence cannot prove an AI application secure. Its findings depend on
scenario coverage, the fidelity of the tested application, the model, and the
correctness of the oracles. Prompt injection has no universally reliable
text-only detector, canary matching only catches exact synthetic values, and a
score from this suite is evidence about one tested configuration — not a
certification of the model.

## Responsible use

Run these tests only against systems you own or have explicit permission to
assess. Everything bundled here is synthetic and offline by design.

## License

MIT — see [LICENSE](LICENSE).
