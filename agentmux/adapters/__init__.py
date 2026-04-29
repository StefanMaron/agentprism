"""Provider-specific adapters for agentmux.

Each adapter implements the :class:`AgentAdapter` interface defined in
:mod:`agentmux.adapters.base`, wrapping a coding agent's native protocol
(stdio JSON-RPC, HTTP, etc.) behind a uniform async API.
"""

from agentmux.adapters.base import AgentAdapter
from agentmux.adapters.copilot import CopilotAdapter

__all__ = ["AgentAdapter", "CopilotAdapter"]
