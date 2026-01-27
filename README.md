# PromptFence

PromptFence is a security testing framework for AI applications. It runs
declarative scenarios against a controlled, fully synthetic application and
inspects what the application actually *permits* — the tool calls it accepted,
the records it returned and the state it changed — rather than judging safety
from the model's wording.

Everything ships synthetic. The default path makes no network calls and needs no
credentials.

## Status

Early development. This is what exists today:

- A versioned scenario schema with a safe YAML loader (`promptfence.scenarios`).
- Typed models for scenarios, application events and trial results.

Not built yet: the mock application, the authorization layer, oracles, the
runner and the CLI beyond a `version` command. Nothing is released.

## Development setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run pytest
uv run promptfence version
```

## License

MIT — see [LICENSE](LICENSE).
