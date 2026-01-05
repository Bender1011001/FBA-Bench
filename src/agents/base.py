import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from fba_events.base import EventBus


def get_registry():
    """Lazy load AgentRegistry to avoid circular import."""
    return importlib.import_module("agents.registry").registry


class BaseAgent(ABC):
    """Base class for all agents in the FBA-Bench framework."""

    def __init__(self, agent_id: str, event_bus: EventBus):
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.config = {}  # Agent-specific configuration

    @abstractmethod
    async def decide(self, state: Any) -> List[Any]:
        """Make a decision based on the current state."""
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return the agent's configuration."""
        return self.config


class AgentConfig:
    """Configuration for an agent."""

    def __init__(
        self,
        agent_id: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        self.agent_id = agent_id
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Additional config fields can be added here
