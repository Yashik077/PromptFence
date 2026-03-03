"""Adapter lookup by name."""

from __future__ import annotations

from promptfence.adapters.base import ModelAdapter
from promptfence.adapters.mock import DeterministicMockAdapter


def available_adapters() -> dict[str, type]:
    """Adapters this build can construct, keyed by the name the CLI accepts."""
    return {"mock": DeterministicMockAdapter}


def create_adapter(name: str, **options: object) -> ModelAdapter:
    adapters = available_adapters()
    try:
        factory = adapters[name]
    except KeyError as exc:
        known = ", ".join(sorted(adapters))
        raise ValueError(f"unknown adapter {name!r}; available adapters: {known}") from exc
    return factory(**options)  # type: ignore[arg-type]
