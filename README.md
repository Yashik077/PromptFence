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

> **Status:** early development. Everything described below runs today and is
> covered by tests. Hosted-model support exists but is opt-in and untested
> against any particular provider.

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
and records, with harmless tools. It ships in two profiles.

- `hardened` authorizes every call against the authenticated principal.
- `vulnerable` carries exactly one documented defect — it authorizes using the
  `as_user` argument the model supplied. It exists so a passing suite means
  something and so the oracles have a defect they are expected to catch.

Try it:

```bash
uv run promptfence run-suite scenarios/ --app-profile vulnerable --output results/vuln.jsonl
```

## What exists today

- Versioned scenario schema with a safe YAML loader (no code execution from
  scenario files, size limits, unknown invariants rejected).
- Synthetic application with identity-aware authorization and a structured event
  log.
- Deterministic, offline mock adapter, plus an opt-in OpenAI-compatible adapter.
- Access-control, state-change and output-leakage oracles.
- JSONL results, an HTML report, metrics with explicit denominators.
- A regression suite that pins the seeded defect and the benign controls.

Not built yet: an LLM judge, confidence intervals, scenario property-based
testing, framework integrations.

## Limitations

PromptFence cannot prove an AI application secure. Its findings depend on
scenario coverage, the fidelity of the tested application, the model, and the
correctness of the oracles. Prompt injection has no universally reliable
text-only detector, and a score from this suite is evidence about the tested
configuration — not a certification of the model.

## Responsible use

Run these tests only against systems you own or have explicit permission to
assess. Everything built in here is synthetic and offline by design.

## License

MIT — see [LICENSE](LICENSE).
