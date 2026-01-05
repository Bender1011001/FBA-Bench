from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import asyncio

if TYPE_CHECKING:
    from .base_runner import AgentRunner

logger = logging.getLogger(__name__)


class AgentRegistration:
    """Registration information for an agent."""

    def __init__(
        self, agent_id: str, runner: Any, framework: str, config: Dict[str, Any]
    ):
        self.agent_id = agent_id
        self.runner = runner  # Type: AgentRunner
        self.framework = framework
        self.config = config
        self.is_active = True
        self.created_at = datetime.now()
        # Resiliency/health tracking
        self.timeout_count: int = 0
        self.last_timeout_at: Optional[datetime] = None
        self.is_unresponsive: bool = False
        # Failure cause tracking
        self.failure_reason: Optional[str] = None
        # Statistics
        self.total_decisions: int = 0
        self.total_tool_calls: int = 0


@dataclass
class BackCompatRegistration:
    """Back-compat mirror record used for tests expecting attributes on manager.agents[aid]"""
    runner: Any
    active: bool
    created_at: datetime
    total_decisions: int = 0
    total_tool_calls: int = 0


class AgentRegistry:
    """Manages the registration and state of individual agents for easy lookup."""

    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}

    def add_agent(
        self, agent_id: str, runner: Any, framework: str, config: Dict[str, Any]
    ) -> AgentRegistration:
        """Register a new agent."""
        if agent_id in self._agents:
            logger.warning(f"Agent {agent_id} already exists in registry, overwriting.")
        
        registration = AgentRegistration(agent_id, runner, framework, config)
        self._agents[agent_id] = registration
        logger.debug(f"Agent {agent_id} added to registry.")
        return registration

    def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        """Look up an agent by ID."""
        return self._agents.get(agent_id)

    def all_agents(self) -> Dict[str, AgentRegistration]:
        """List all registered agents."""
        return self._agents.copy()

    def active_agents(self) -> Dict[str, AgentRegistration]:
        """List all active (non-failed) agents."""
        return {
            agent_id: reg for agent_id, reg in self._agents.items() 
            if reg.is_active and not reg.is_unresponsive
        }

    def agent_count(self) -> int:
        """Total number of registered agents."""
        return len(self._agents)

    def active_agent_count(self) -> int:
        """Number of active agents."""
        return len(self.active_agents())

    def mark_agent_timeout(self, agent_id: str, *, threshold: int = 3) -> None:
        """
        Record a timeout for an agent. If consecutive timeouts exceed threshold, mark as unresponsive.
        """
        reg = self._agents.get(agent_id)
        if not reg:
            logger.warning(
                f"Attempted to mark timeout for non-existent agent {agent_id}."
            )
            return
        reg.timeout_count = int(getattr(reg, "timeout_count", 0)) + 1
        reg.last_timeout_at = datetime.now()
        if reg.timeout_count >= max(1, int(threshold)):
            if not getattr(reg, "is_unresponsive", False):
                logger.warning(
                    f"Agent {agent_id} marked as unresponsive after {reg.timeout_count} timeouts."
                )
            reg.is_unresponsive = True
            reg.is_active = False  # Also mark as inactive for decision cycles
        else:
            logger.info(
                f"Agent {agent_id} timeout recorded ({reg.timeout_count}/{threshold})."
            )

    def mark_agent_as_failed(self, agent_id: str, reason: str) -> None:
        """Mark an agent as failed."""
        agent = self.get_agent(agent_id)
        if agent:
            agent.is_active = False
            agent.failure_reason = reason
            logger.error(f"Agent {agent_id} marked as failed: {reason}")
        else:
            logger.warning(
                f"Attempted to mark non-existent agent {agent_id} as failed."
            )

    def deregister(self, agent_id: str) -> bool:
        """Remove the agent from the registry, disposing the associated runner if present.
        Returns True if an agent was found and removed, False otherwise."""
        if agent_id not in self._agents:
            logger.debug(
                f"Attempted to deregister non-existent agent {agent_id}. No-op."
            )
            return False

        agent_registration = self._agents[agent_id]
        if agent_registration.runner:
            try:
                # Prioritize synchronous cleanup methods
                if hasattr(agent_registration.runner, "sync_cleanup") and callable(
                    agent_registration.runner.sync_cleanup
                ):
                    agent_registration.runner.sync_cleanup()
                    logger.debug(
                        f"Synchronously cleaned up runner for agent {agent_id}."
                    )
                elif hasattr(agent_registration.runner, "close") and callable(
                    agent_registration.runner.close
                ):
                    agent_registration.runner.close()
                    logger.debug(f"Closed runner for agent {agent_id}.")
                elif hasattr(agent_registration.runner, "cleanup") and callable(
                    agent_registration.runner.cleanup
                ):
                    # Schedule async cleanup if only async is available and we're in a sync context.
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(agent_registration.runner.cleanup())
                            logger.warning(
                                f"Scheduled async cleanup for agent {agent_id}. Ensure event loop is active."
                            )
                        else:
                            logger.warning(
                                f"Cannot schedule async cleanup for agent {agent_id}: event loop not running."
                            )
                    except RuntimeError:
                        logger.warning(
                            f"Cannot schedule async cleanup for agent {agent_id}: no active event loop."
                        )
                else:
                    logger.debug(
                        f"No specific cleanup/close method found for runner of agent {agent_id}. Skipping runner disposal."
                    )
            except Exception as e:
                # Keep deregistration resilient but log unexpected exceptions
                logger.error(
                    f"Unexpected error during runner disposal for agent {agent_id}: {e}",
                    exc_info=True,
                )

        # Remove the agent entry
        del self._agents[agent_id]
        logger.info(f"Agent {agent_id} successfully deregistered.")
        return True

    def clear(self) -> None:
        """Clear all registrations."""
        self._agents.clear()
