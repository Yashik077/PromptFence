# Architecture

PromptFence has six layers. Each one only knows about the layer below it.

```text
scenario corpus ──► runner ──┬──► model adapter ──┐
                              └──► mock application┤
                                                ▼
                                     evidence + oracles
                                                │
                                                ▼
                                     JSONL ──► HTML / CI exit code
```

## Scenario corpus

Declarative YAML. No Python, no shell, no file paths to write, no code
evaluation. Each scenario names a stable id, a category, synthetic setup, the
input, and the invariants it asserts.

## Runner

Owns the trial lifecycle: build a fresh application, build the adapter, hold a
deadline around every adapter call, execute the conversation, hand the evidence
to the oracles, emit one result. It does not decide whether anything was secure.
A fresh application per trial is what keeps one trial's documents and grants out
of the next trial's state.

## Model adapter

Converts the runner's normalized request into something a provider understands
and converts the answer back into tool calls. Adapters report their
capabilities rather than assuming them. Adapters never authorize anything — that
is the application's job, and keeping the two apart is the entire point.

## Mock application

Owns the synthetic state, implements the tools, authenticates the trial
principal and enforces permissions independently of anything the model said.
Every security-relevant operation emits a structured event.

The `vulnerable` profile is the same application with one documented defect. It
exists so the oracles have something they are supposed to catch.

## Oracles

Read events, state and output; answer one question per declared invariant;
name the events that support the answer. An oracle that cannot tell passes from
unknown says `inconclusive` rather than guessing.

## Reports

Aggregate without discarding failures or missing data, write JSONL first and
derive the HTML report from it. Every rate carries its numerator, denominator
and excluded count.

## Where the security decisions live

| Decision | Enforced in |
|---|---|
| May this principal read this document? | `sandbox/authorization.py` |
| Who is the caller? | `sandbox/app.py`, from the trial context only |
| Did an invariant hold? | `oracles/` |
| Does a metric mean anything? | `metrics.py`, with explicit denominators |
| May this string reach the report? | `reports/`, escaped |

The model is not on that list, and it should not be.

## Extending

- **A scenario** — drop a YAML file in `scenarios/`. No code change.
- **An invariant** — add an oracle and register its name in
  `oracles/registry.py`. The loader will then accept scenarios that use it, and
  reject ones that do not exist.
- **An adapter** — implement `ModelAdapter` in `adapters/` and register it. The
  runner, oracles and result format do not change.
