"""Security oracles.

An oracle reads the evidence a trial produced and answers one question about a
declared invariant. It never reads the model's opinion of what happened; it
looks at tool calls, authorization decisions, state and output.
"""

from promptfence.oracles.access_control import AccessControlOracle
from promptfence.oracles.base import Evidence, Oracle
from promptfence.oracles.output_leakage import OutputLeakageOracle
from promptfence.oracles.registry import INVARIANTS, known_invariants
from promptfence.oracles.state_change import StateChangeOracle

__all__ = [
    "AccessControlOracle",
    "Evidence",
    "INVARIANTS",
    "Oracle",
    "OutputLeakageOracle",
    "StateChangeOracle",
    "known_invariants",
]
