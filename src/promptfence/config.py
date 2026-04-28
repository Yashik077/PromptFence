"""Configuration for adapters that talk to something outside the process.

The offline workflow never reads any of this. Values come from environment
variables or explicit flags, credentials are read from the environment and are
never echoed into results, logs or reports.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

ENV_BASE_URL = "PROMPTFENCE_BASE_URL"
ENV_MODEL = "PROMPTFENCE_MODEL"
ENV_API_KEY = "PROMPTFENCE_API_KEY"
ENV_TIMEOUT = "PROMPTFENCE_TIMEOUT"

DEFAULT_TIMEOUT = 60.0


class ConfigError(RuntimeError):
    """Missing or contradictory remote-adapter configuration."""


@dataclass(frozen=True, slots=True)
class RemoteModelConfig:
    """Everything needed to reach an OpenAI-compatible endpoint.

    Nothing here is a default that would silently send traffic somewhere: an
    endpoint has to be named explicitly, every time.
    """

    base_url: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = DEFAULT_TIMEOUT
    requires_api_key: bool = False

    @classmethod
    def resolve(
        cls,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
    ) -> RemoteModelConfig:
        resolved_base = base_url or os.environ.get(ENV_BASE_URL)
        if not resolved_base:
            raise ConfigError(
                "no endpoint configured. Pass --endpoint or set "
                f"{ENV_BASE_URL}. The offline 'mock' adapter needs none of this."
            )
        resolved_model = model or os.environ.get(ENV_MODEL)
        if not resolved_model:
            raise ConfigError(f"no model id configured. Pass --remote-model or set {ENV_MODEL}.")
        resolved_key = api_key or os.environ.get(ENV_API_KEY)
        return cls(
            base_url=resolved_base.rstrip("/"),
            model=resolved_model,
            api_key=resolved_key,
            timeout_seconds=timeout
            if timeout is not None
            else float(os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT)),
        )

    def fingerprint(self) -> str:
        """A stable identifier safe to write into a result file.

        Includes the key only as a hash prefix, so two runs against the same
        endpoint are recognisably the same configuration without the credential
        ever being recoverable from the output.
        """
        digest = hashlib.sha256((self.api_key or "").encode("utf-8")).hexdigest()[:8]
        return f"{self.base_url}|{self.model}|key:{digest or 'none'}"

    def headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def __repr__(self) -> str:  # pragma: no cover - trivial, but keeps keys out of tracebacks
        return (
            f"RemoteModelConfig(base_url={self.base_url!r}, model={self.model!r}, "
            f"api_key={'<redacted>' if self.api_key else None!r})"
        )
