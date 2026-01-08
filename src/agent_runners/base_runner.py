from __future__ import annotations

"""
Base Agent Runner - Abstract base class for all agent runners.

This module defines the interface and common functionality for all agent runners,
regardless of the underlying framework (DIY, CrewAI, LangChain, etc.).
"""

import abc
import asyncio
import dataclasses
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class AgentRunnerStatus(str, Enum):
    """Status of an agent runner."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CLEANING_UP = "cleaning_up"
    TERMINATED = "terminated"


class AgentRunnerError(Exception):
    """Base exception for agent runner errors."""

    def __init__(
        self,
        message: str,
        agent_id: Optional[str] = None,
        framework: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.framework = framework
        super().__init__(message)


class AgentRunnerInitializationError(AgentRunnerError):
    """Exception raised when agent runner initialization fails."""


class AgentRunnerDecisionError(AgentRunnerError):
    """Exception raised when agent decision making fails."""


class AgentRunnerCleanupError(AgentRunnerError):
    """Exception raised when agent runner cleanup fails."""


class AgentRunnerTimeoutError(AgentRunnerError):
    """Exception raised when agent runner operation times out."""


# Shared data structures used across integration layers
@dataclass
class SimulationState:
    """Canonical simulation state passed to agent runners.

    Fields:
      - tick: simulation tick counter (monotonic integer)
      - simulation_time: timezone-aware timestamp for the current tick
      - products: list of product snapshots
      - recent_events: list of recent events
      - financial_position: financial state snapshot
      - market_conditions: market snapshot
      - agent_state: agent-specific state
    """

    tick: int = 0
    simulation_time: Optional[datetime] = None
    products: List[Dict[str, Any]] = field(default_factory=list)
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    financial_position: Dict[str, Any] = field(default_factory=dict)
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    agent_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """Structured action emitted by agent runners."""

    tool_name: str
    parameters: Dict[str, Any]
    confidence: float = 1.0
    reasoning: Optional[str] = None
    priority: int = 0


# Soft dependency guard: avoid hard import to agents.* in core runner base
try:
    from agents.skill_modules.base_skill import SkillOutcome  # type: ignore
except (ImportError, AttributeError, TypeError):

    class SkillOutcome(Protocol):
        """Protocol fallback for learning outcomes to avoid hard dependency."""

        success: bool
        details: Dict[str, Any]


@dataclass
class AgentConfig:
    """Configuration for constructing an agent runner.

    Attributes:
      - agent_id: unique identifier for the agent
      - agent_type: optional human-readable type/name
      - agent_class: optional fully qualified class path for dynamic loading
      - parameters: arbitrary configuration mapping
    """

    agent_id: str
    agent_type: Optional[str] = None
    agent_class: Optional[str] = None
    parameters: Dict[str, Any] = dataclasses.field(default_factory=dict)


class BaseAgentRunner(ABC):
    """Abstract base class for agent runners used by tests and integrations.

    This base defines a minimal, stable async interface. Subclasses should implement
    lifecycle and action methods. State-mutating methods must update last_updated_at.
    """

    config: AgentConfig
    is_initialized: bool
    created_at: datetime
    last_updated_at: datetime

    def __init__(self, config: AgentConfig):
        """Initialize base fields and timestamps."""
        self.config = config
        self.is_initialized = False
        now = datetime.now(timezone.utc)
        self.created_at = now
        self.last_updated_at = now

    @abstractmethod
    async def initialize(self) -> None:
        """Perform any async setup required by the agent runner."""
        self.is_initialized = True
        self.last_updated_at = datetime.now(timezone.utc)

    @abstractmethod
    async def process_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return a normalized representation suitable for decision-making."""
        self.last_updated_at = datetime.now(timezone.utc)
        raise NotImplementedError

    @abstractmethod
    async def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a proposed action and return execution metadata/results."""
        self.last_updated_at = datetime.now(timezone.utc)
        raise NotImplementedError

    @abstractmethod
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect and return current runner metrics."""
        # Does not necessarily mutate state, but update freshness timestamp for observability.
        self.last_updated_at = datetime.now(timezone.utc)
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanly shutdown and release resources."""
        self.is_initialized = False
        self.last_updated_at = datetime.now(timezone.utc)

    async def decide(self, state: SimulationState) -> List[ToolCall]:
        """Produce a list of ToolCall actions given a simulation state.

        Default adapter returns a single noop ToolCall. Subclasses should override.

        Example:
            # Return a no-op action
            return [ToolCall(tool_name="noop", parameters={}, confidence=1.0)]
        """
        self.last_updated_at = datetime.now(timezone.utc)
        return [ToolCall(tool_name="noop", parameters={}, confidence=1.0)]

    async def learn(self, outcome: Any) -> None:
        """Optional learning hook after action execution. Default is no-op."""
        self.last_updated_at = datetime.now(timezone.utc)
        return None


class AgentRunner:
    """
    Abstract base class for all agent runners.

    This class defines the interface that all agent runners must implement,
    providing a consistent way to interact with agents regardless of their
    underlying framework.
    """

    def __init__(self, agent_id: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent runner.

        Args:
            agent_id: Unique identifier for this agent instance
            config: Configuration dictionary for the agent
        """
        self.agent_id = agent_id
        self.config = config or {}
        self.status = AgentRunnerStatus.INITIALIZING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.last_activity_at = self.created_at
        self.error_message: Optional[str] = None
        self.metrics: Dict[str, Any] = {}
        self.context: Dict[str, Any] = {}
        self.callbacks: Dict[str, List[Callable]] = {
            "on_status_change": [],
            "on_decision": [],
            "on_error": [],
            "on_metric": [],
        }

        # Do not auto-initialize here; allow callers/managers to call initialize() explicitly.
        # This supports lightweight/mock runners in tests that don't implement _do_initialize.
        # self._initialize()

    def _initialize(self) -> None:
        """
        Initialize the agent-specific implementation.

        This method should be overridden by subclasses to perform
        framework-specific initialization.
        """
        try:
            self._do_initialize()
            self.status = AgentRunnerStatus.READY
            self._trigger_callbacks("on_status_change", self.status)
            logger.info(f"Agent runner {self.agent_id} initialized successfully")
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            self.status = AgentRunnerStatus.FAILED
            self.error_message = str(e)
            self._trigger_callbacks("on_status_change", self.status)
            self._trigger_callbacks("on_error", e)
            raise AgentRunnerInitializationError(
                f"Failed to initialize agent runner {self.agent_id}: {e}",
                agent_id=self.agent_id,
                framework=self.__class__.__name__,
            ) from e

    @abc.abstractmethod
    def _do_initialize(self) -> None:
        """
        Perform framework-specific initialization.

        This method must be implemented by subclasses to initialize
        the specific agent framework.
        """

    @abc.abstractmethod
    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision using the agent.

        Args:
            context: Context information for the decision

        Returns:
            Dictionary containing the decision and any metadata

        Raises:
            AgentRunnerDecisionError: If decision making fails
        """

    async def make_decision_async(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a decision using the agent asynchronously.

        Default behavior:
        - If subclass provides an async 'async_make_decision', use it directly.
        - Otherwise, run blocking 'make_decision' in a worker thread via asyncio.to_thread
          to avoid blocking the event loop.
        - Maintains status transitions and callback invocations.

        Args:
            context: Context information for the decision

        Returns:
            Dictionary containing the decision and any metadata

        Raises:
            AgentRunnerDecisionError: If decision making fails
        """
        try:
            self.status = AgentRunnerStatus.RUNNING
            self.started_at = datetime.now()
            self._trigger_callbacks("on_status_change", self.status)

            # Prefer a true async implementation if subclass exposes it
            async_decider = getattr(self, "async_make_decision", None)
            if callable(async_decider) and getattr(async_decider, "__call__", None):
                if (
                    getattr(async_decider, "__aiter__", None)
                    or getattr(async_decider, "__await__", None)
                    or getattr(async_decider, "__anext__", None)
                ):
                    # Some exotic async indicators; fall back to generic await
                    result = await async_decider(context)  # type: ignore
                else:
                    # Best-effort: if it's an async def, awaiting will work
                    try:
                        result = await async_decider(context)  # type: ignore
                    except TypeError:
                        # Not actually async, fall back to thread
                        result = await asyncio.to_thread(self.make_decision, context)
            else:
                # Run sync decision in a background thread so we never block the loop
                result = await asyncio.to_thread(self.make_decision, context)

            self.status = AgentRunnerStatus.READY
            self.last_activity_at = datetime.now()
            self._trigger_callbacks("on_status_change", self.status)
            self._trigger_callbacks("on_decision", result)

            return result
        except (AttributeError, TypeError, ValueError, RuntimeError, AgentRunnerDecisionError, AgentRunnerTimeoutError) as e:
            self.status = AgentRunnerStatus.FAILED
            self.error_message = str(e)
            self._trigger_callbacks("on_status_change", self.status)
            self._trigger_callbacks("on_error", e)
            raise AgentRunnerDecisionError(
                f"Decision making failed for agent {self.agent_id}: {e}",
                agent_id=self.agent_id,
                framework=self.__class__.__name__,
            ) from e

    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the agent runner (async compatibility wrapper).
        If already initialized, update config; otherwise perform initialization.
        """
        if config:
            self.config.update(config)
        if self.status != AgentRunnerStatus.READY:
            # Perform initialization if not done in constructor
            self._initialize()

    async def decide(self, state: SimulationState) -> List[ToolCall]:
        """
        Standard async decision API expected by integration layers.
        Converts SimulationState to a generic context, calls make_decision_async,
        then adapts the result into a list of ToolCall objects.
        """
        context: Dict[str, Any] = {
            "tick": getattr(state, "tick", 0),
            "simulation_time": getattr(state, "simulation_time", None),
            "products": getattr(state, "products", []),
            "recent_events": getattr(state, "recent_events", []),
            "financial_position": getattr(state, "financial_position", {}),
            "market_conditions": getattr(state, "market_conditions", {}),
            "agent_state": getattr(state, "agent_state", {}),
        }
        decision = await self.make_decision_async(context)
        # Default adaptation: wrap the decision dict into a single ToolCall.
        return [ToolCall(tool_name="decision", parameters=decision, confidence=1.0)]

    async def learn(self, outcome: SkillOutcome) -> None:
        """
        Process the outcome of a decision cycle for learning and adaptation.

        Args:
            outcome: The SkillOutcome object detailing the results of the last action.
        """
        # Default no-op implementation; subclasses may override to implement learning.
        return None

    async def consolidate_memory(self, context: Dict[str, Any]) -> None:
        """
        Consolidate memory by processing recent events and updating long-term memory.
        This roughly mimics 'sleep' or 'nightly processing' in biological agents.
        
        Args:
            context: Context information for memory consolidation
        """
        # Default no-op implementation; subclasses may override to implement memory consolidation.
        return None

    def update_context(self, context_update: Dict[str, Any]) -> None:
        """
        Update the agent's context.

        Args:
            context_update: Dictionary containing context updates
        """
        self.context.update(context_update)
        self.last_activity_at = datetime.now()

    def get_status(self) -> AgentRunnerStatus:
        """
        Get the current status of the agent runner.

        Returns:
            Current status of the agent runner
        """
        return self.status

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for the agent runner.

        Returns:
            Dictionary containing agent metrics
        """
        return self.metrics.copy()

    def update_metrics(self, metrics_update: Dict[str, Any]) -> None:
        """
        Update agent metrics.

        Args:
            metrics_update: Dictionary containing metric updates
        """
        self.metrics.update(metrics_update)
        self.last_activity_at = datetime.now()
        self._trigger_callbacks("on_metric", self.metrics)

    def add_callback(self, event_type: str, callback: Callable) -> None:
        """
        Add a callback for a specific event type.

        Args:
            event_type: Type of event ("on_status_change", "on_decision", "on_error", "on_metric")
            callback: Callback function to be invoked when the event occurs
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
        else:
            raise ValueError(f"Unknown event type: {event_type}")

    def remove_callback(self, event_type: str, callback: Callable) -> None:
        """
        Remove a callback for a specific event type.

        Args:
            event_type: Type of event
            callback: Callback function to be removed
        """
        if event_type in self.callbacks:
            try:
                self.callbacks[event_type].remove(callback)
            except ValueError:
                # Callback not found, ignore
                pass

    def _trigger_callbacks(self, event_type: str, *args, **kwargs) -> None:
        """
        Trigger callbacks for a specific event type.

        Args:
            event_type: Type of event
            *args: Arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
        """
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(self, *args, **kwargs)
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(f"Error in callback for {event_type}: {e}")

    def pause(self) -> None:
        """
        Pause the agent runner.

        This method should be overridden by subclasses that support pausing.
        """
        if self.status == AgentRunnerStatus.RUNNING:
            self.status = AgentRunnerStatus.PAUSED
            self._trigger_callbacks("on_status_change", self.status)
            logger.info(f"Agent runner {self.agent_id} paused")
        else:
            logger.warning(
                f"Cannot pause agent runner {self.agent_id} in status {self.status}"
            )

    def resume(self) -> None:
        """
        Resume the agent runner.

        This method should be overridden by subclasses that support resuming.
        """
        if self.status == AgentRunnerStatus.PAUSED:
            self.status = AgentRunnerStatus.READY
            self._trigger_callbacks("on_status_change", self.status)
            logger.info(f"Agent runner {self.agent_id} resumed")
        else:
            logger.warning(
                f"Cannot resume agent runner {self.agent_id} in status {self.status}"
            )

    def cleanup(self) -> None:
        """
        Clean up resources used by the agent runner.

        This method should be overridden by subclasses to perform
        framework-specific cleanup.
        """
        try:
            self.status = AgentRunnerStatus.CLEANING_UP
            self._trigger_callbacks("on_status_change", self.status)

            self._do_cleanup()

            self.status = AgentRunnerStatus.TERMINATED
            self.completed_at = datetime.now()
            self._trigger_callbacks("on_status_change", self.status)

            logger.info(f"Agent runner {self.agent_id} cleaned up successfully")
        except (AttributeError, TypeError, ValueError, RuntimeError, AgentRunnerCleanupError) as e:
            self.status = AgentRunnerStatus.FAILED
            self.error_message = str(e)
            self._trigger_callbacks("on_status_change", self.status)
            self._trigger_callbacks("on_error", e)
            raise AgentRunnerCleanupError(
                f"Cleanup failed for agent runner {self.agent_id}: {e}",
                agent_id=self.agent_id,
                framework=self.__class__.__name__,
            ) from e

    def sync_cleanup(self) -> None:
        """
        Synchronous cleanup method for compatibility with synchronous contexts.

        This method provides a synchronous interface to the cleanup functionality,
        allowing it to be called from synchronous code when needed.
        """
        self.cleanup()

    async def async_cleanup(self) -> None:
        """
        Asynchronous cleanup method for compatibility with asynchronous contexts.

        This method provides an asynchronous interface to the cleanup functionality,
        allowing it to be called from asynchronous code when needed.
        """
        await asyncio.to_thread(self.cleanup)

    def _do_cleanup(self) -> None:
        """
        Perform framework-specific cleanup.

        This method should be overridden by subclasses to perform
        framework-specific cleanup.
        """
        # Default implementation does nothing

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the agent runner to a dictionary representation.

        Returns:
            Dictionary representation of the agent runner
        """
        return {
            "agent_id": self.agent_id,
            "config": self.config,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "last_activity_at": self.last_activity_at.isoformat(),
            "error_message": self.error_message,
            "metrics": self.metrics,
            "context": self.context,
            "framework": self.__class__.__name__,
        }

    def __str__(self) -> str:
        """String representation of the agent runner."""
        return (
            f"{self.__class__.__name__}(id={self.agent_id}, status={self.status.value})"
        )

    def __repr__(self) -> str:
        """Detailed string representation of the agent runner."""
        return (
            f"{self.__class__.__name__}(agent_id={self.agent_id!r}, "
            f"status={self.status.value!r}, framework={self.__class__.__name__!r})"
        )
