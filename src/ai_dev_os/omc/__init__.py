"""
OMC (Oh My Claude Code) orchestration layer.

Provides agent catalog, model routing, and state management
for multi-agent Claude Code workflows.
"""

from ai_dev_os.omc.catalog import AgentCatalog, AgentDefinition
from ai_dev_os.omc.routing import ModelRouter, ModelTier
from ai_dev_os.omc.state import StateManager

__all__ = [
    "AgentCatalog",
    "AgentDefinition",
    "ModelRouter",
    "ModelTier",
    "StateManager",
]
