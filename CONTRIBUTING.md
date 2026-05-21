# Contributing

Contributions are welcome, particularly good scenarios, better oracles, adapter
implementations, reproducibility fixes and documentation.

## Setup

```bash
uv sync --all-groups
uv run pytest
```

Python 3.12+ and `uv` are required. Everything runs offline; the required test
suite opens no sockets.

## Before you open a pull request

1. `uv run pytest`
2. `uv run ruff check . && uv run ruff format --check .`
3. `uv run promptfence validate scenarios/`
4. Update the documentation if behaviour changed.
5. No credentials, no private data, no exploit payloads aimed at systems you do
   not own.

Explain the security reasoning in the description. A reviewer should be able to
tell what an invariant means and what evidence proves it holds, without reading
the whole diff.

## Adding a scenario

Read [docs/scenario-authoring.md](docs/scenario-authoring.md) first. In short:

- one primary security property per scenario,
- synthetic data only,
- name the invariants explicitly,
- ship a benign control alongside anything aggressive,
- add a test proving the oracle classifies it correctly under **both** app
  profiles,
- bump `version` if you change what the scenario tests.

A scenario that passes under the vulnerable profile is not testing the seeded
defect. Usually that means the injection has no identity to steal.

## Adding an invariant

1. Write the oracle in `oracles/`, implementing one question and naming the
   events that support its answer.
2. Register the name in `oracles/registry.py`.
3. Document it in `docs/scenario-authoring.md`.
4. Add unit tests for every outcome, including the inconclusive one.

An oracle that cannot distinguish "passed" from "we do not know" is worse than
no oracle, because it produces comfortable green builds.

## Adding an adapter

Implement `ModelAdapter` in `src/promptfence/adapters/` and register it. The
runner, oracles and result format should not need to change. Report your
capabilities honestly — whether you support tools, system messages, seeds and
usage — and say what you do not support in `notes`.

Never authorize anything in an adapter. That belongs to the application.

## Changing an expected result

Changing a test's expected value to make it pass is not a fix. If an oracle's
behaviour genuinely changed, say so in the pull request with the evidence that
the new behaviour is correct. Reviewers will ask.

## Good first contributions

- Add a benign control scenario.
- Add a test for a missing authorization edge case.
- Improve a misleading validation message.
- Document an adapter capability limitation.
- Improve the HTML report.
- Add a scenario in a category the corpus does not cover yet.

## Licence

Contributions are accepted under the MIT licence in [LICENSE](LICENSE).
