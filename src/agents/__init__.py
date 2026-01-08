"""
Agents module for FBA-Bench.

This module provides agent-related classes, configurations, and utilities.
"""

# mypy: ignore-errors

from benchmarking.agents.unified_agent import (
    AgentAction,
    AgentCapability,
    AgentContext,
    AgentFactory,
    AgentMessage,
    AgentObservation,
    AgentState,
    BaseUnifiedAgent,
    NativeFBAAdapter,
    UnifiedAgentRunner,
    agent_factory,
)

from .advanced_agent import AdvancedAgent
from .base import AgentConfig, BaseAgent
from .baseline.baseline_agent_v1 import BaselineAgentV1
from .registry import AgentRegistry, registry as agent_registry
from .skill_coordinator import SkillCoordinator

__all__ = [
    # Legacy agents
    "AgentRegistry",
    "agent_registry",
    "BaseAgent",
    "AgentConfig",
    # Unified agent framework
    "AgentState",
    "AgentCapability",
    "AgentMessage",
    "AgentObservation",
    "AgentAction",
    "AgentContext",
    "BaseUnifiedAgent",
    "NativeFBAAdapter",
    "UnifiedAgentRunner",
    "AgentFactory",
    "agent_factory",
    "SkillCoordinator",
    "AdvancedAgent",
    "BaselineAgentV1",
]


# Auto-register built-in agents if needed
def _register_builtin_agents():
    """Register built-in agents on module import."""
    agent_registry.register("advanced_agent", AdvancedAgent)
    agent_registry.register("baseline_v1", BaselineAgentV1)


_register_builtin_agents()
