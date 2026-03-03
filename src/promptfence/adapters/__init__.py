"""Model adapters.

An adapter turns PromptFence's normalized request into whatever a particular
provider speaks, and turns the answer back into tool calls. Adapters never
authorize anything — that is the application's job, and the whole point of the
project is to keep those two concerns apart.
"""

from promptfence.adapters.base import (
    AdapterCapabilities,
    AdapterError,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolResultMessage,
)
from promptfence.adapters.mock import DeterministicMockAdapter
from promptfence.adapters.registry import available_adapters, create_adapter

__all__ = [
    "AdapterCapabilities",
    "AdapterError",
    "DeterministicMockAdapter",
    "ModelMessage",
    "ModelRequest",
    "ModelResponse",
    "ToolCall",
    "ToolResultMessage",
    "available_adapters",
    "create_adapter",
]
