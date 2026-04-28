"""Adapter lookup by name.

``mock`` is the only adapter that is always available. Anything that talks to a
network has to be named explicitly and configured explicitly; there is no
default endpoint and no credential is read unless the adapter is selected.
"""

from __future__ import annotations

from typing import Any

from promptfence.adapters.base import ModelAdapter
from promptfence.adapters.mock import DeterministicMockAdapter


def available_adapters() -> dict[str, type]:
    """Adapters this build can construct, keyed by the name the CLI accepts."""
    from promptfence.adapters.openai_compatible import OpenAICompatibleAdapter

    return {
        "mock": DeterministicMockAdapter,
        "openai_compatible": OpenAICompatibleAdapter,
    }


def create_adapter(name: str, **options: Any) -> ModelAdapter:
    adapters = available_adapters()
    try:
        factory = adapters[name]
    except KeyError as exc:
        known = ", ".join(sorted(adapters))
        raise ValueError(f"unknown adapter {name!r}; available adapters: {known}") from exc
    return factory(**options)
