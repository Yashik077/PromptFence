## What are you proposing?

<!-- One or two sentences. If this is a scenario, name the security property. -->

## Why does it matter?

<!-- The risk, not the implementation. What could go wrong in an application
     that behaves the way your change describes? -->

## Checklist

- [ ] `uv run pytest`
- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `uv run promptfence validate scenarios/` (if you touched scenarios)
- [ ] Tests added or updated for the new behaviour
- [ ] Documentation updated if behaviour changed
- [ ] Synthetic data only — no real credentials, no real user content
- [ ] No exploit payloads aimed at systems you do not own

## For scenarios and oracles

- [ ] Invariants are named explicitly and are implemented by a registered oracle
- [ ] Passes under the hardened profile and fails under the vulnerable one, or
      you have explained why that does not apply
- [ ] A benign control ships alongside, if this is an attack scenario
- [ ] `version` bumped if the scenario's meaning changed
