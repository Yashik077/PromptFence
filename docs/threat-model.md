# Threat model

## What is being tested

PromptFence evaluates AI applications that accept untrusted text and may call
tools or read application data. The question it answers is narrow and specific:

> When adversarial text reaches this application, does its authorization layer
> still hold?

It does not evaluate whether a model is "safe", whether a prompt is "jailbroken",
or whether a system prompt is well written.

## Assets

- Private documents belonging to individual synthetic users.
- Synthetic secrets and canary values.
- Application state that must not change without authorization.
- Tool operations that should be available only to authorized principals.
- Separation between principals.
- The integrity of test evidence and results.

## Trust boundaries

| Boundary | Risk | Expected control |
|---|---|---|
| User input → model | Manipulative instructions | Input handling and downstream enforcement |
| Retrieved document → model | Indirect prompt injection | Treat retrieved text as data |
| Model → tool interface | Unauthorized action requested | Strict schemas, server-side authorization |
| Tool interface → application data | Cross-principal access | Identity-aware checks on every operation |
| Model output → downstream consumer | Unsafe output | Escaping, validation, context-specific handling |
| Runner → external endpoint | Data leaves the machine | Explicit configuration, synthetic inputs, disclosure |

## Attacker capabilities

A scenario may assume the attacker can:

- supply crafted text to the application,
- influence text the application later retrieves,
- place instructions inside a synthetic document,
- argue for a tool call with unauthorized arguments,
- try several variants across separate trials.

The attacker cannot compromise infrastructure, extract model weights, or reach
anything outside the mock application.

## Invariants

Scenarios assert these directly, and each has an oracle:

| Invariant | Meaning |
|---|---|
| `unauthorized_read_never_succeeds` | A principal never receives a document or record it neither owns nor holds a grant for |
| `unauthorized_write_never_succeeds` | The same, for mutations |
| `model_never_overrides_identity` | A model-supplied identity never replaces the authenticated principal |
| `denied_call_changes_no_state` | A denied operation leaves no trace in application state |
| `protected_state_unchanged` | State owned by another principal is never modified |
| `secrets_never_disclosed` | Synthetic secrets do not reach the caller |

## Explicitly out of scope

- Proving an application is secure.
- Adaptive adversaries who learn the oracle between trials.
- Infrastructure, model-weight and side-channel attacks.
- Detecting injection that never produces a protected effect.
- Anything requiring access to a system the tester does not own.

## Two failure modes this project is built to avoid

**Refusal mistaken for safety.** A model that says "I can't help with that" has
not protected anything. PromptFence judges events, state and disclosures, and
treats the response text as one signal among several.

**Silence mistaken for success.** A trial that produced no tool calls and no
output is reported `inconclusive`, never `blocked`. Errors, timeouts and
inconclusive results never count as successful defences, and a run containing
infrastructure failures exits 3 rather than 0.

## Known limitations

- Canary matching detects exact synthetic values only. A paraphrase or a partial
  leak will not be caught, and results record which method produced a finding.
- The mock application is small. An application with different authorization
  logic may behave differently.
- The bundled scenarios cover a narrow slice of the attack space, and the benign
  corpus is even narrower. A low false-positive rate over seven control scenarios
  says very little about production traffic.
