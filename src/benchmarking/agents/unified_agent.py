"""
Unified Agent Definition and Runner Simplification for FBA-Bench.

This module provides a unified interface for agents, minimizing wrapping layers
and enabling more direct integration of native FBA agents into the AgentRunner paradigm.
"""

import abc
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from ..config.pydantic_config import AgentConfig as PydanticAgentConfig, FrameworkType
from ..metrics.extensible_metrics import MetricResult

# Import services for dependency injection
try:
    from services import services
except ImportError:
    # Fallback for testing or when services module is not available
    services = None

logger = logging.getLogger(__name__)

if services is None:
    logger.warning(
        "Services module not available. Some agent functionality may be limited."
    )


class AgentState(str, Enum):
    """Agent execution states."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentCapability(str, Enum):
    """Standard agent capabilities."""

    DECISION_MAKING = "decision_making"
    PLANNING = "planning"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    TOOL_USE = "tool_use"
    MEMORY_MANAGEMENT = "memory_management"
    REASONING = "reasoning"
    ADAPTATION = "adaptation"


@dataclass
class AgentMessage:
    """Message for agent communication."""

    sender_id: str
    receiver_id: str
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: Optional[str] = None

    def __post_init__(self):
        """Generate message ID if not provided."""
        if self.message_id is None:
            self.message_id = (
                f"{self.sender_id}_{self.receiver_id}_{self.timestamp.timestamp()}"
            )


@dataclass
class AgentObservation:
    """Observation from the environment."""

    observation_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None


@dataclass
class AgentAction:
    """Action to be performed by the agent."""

    action_type: str
    parameters: Dict[str, Any]
    confidence: float = 1.0
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentContext:
    """Context for agent execution."""

    agent_id: str
    scenario_id: str
    tick: int
    world_state: Dict[str, Any] = field(default_factory=dict)
    observations: List[AgentObservation] = field(default_factory=list)
    messages: List[AgentMessage] = field(default_factory=list)
    previous_actions: List[AgentAction] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_observation(self, observation: AgentObservation) -> None:
        """Add an observation to the context."""
        self.observations.append(observation)

    def add_message(self, message: AgentMessage) -> None:
        """Add a message to the context."""
        self.messages.append(message)

    def get_observations_by_type(self, observation_type: str) -> List[AgentObservation]:
        """Get observations by type."""
        return [
            obs for obs in self.observations if obs.observation_type == observation_type
        ]

    def get_messages_from(self, sender_id: str) -> List[AgentMessage]:
        """Get messages from a specific sender."""
        return [msg for msg in self.messages if msg.sender_id == sender_id]


class BaseUnifiedAgent(abc.ABC):
    """Unified base class for all agents in FBA-Bench."""

    def __init__(self, agent_id: str, config: PydanticAgentConfig):
        """Initialize the agent."""
        self.agent_id = agent_id
        self.config = config
        self.state = AgentState.INITIALIZING
        self.capabilities: List[AgentCapability] = []
        self.metrics: List[MetricResult] = []
        self._is_initialized = False

        # Event handlers
        self._message_handlers: Dict[str, Callable[[AgentMessage], None]] = {}
        self._observation_handlers: Dict[str, Callable[[AgentObservation], None]] = {}

    @property
    def framework_type(self) -> FrameworkType:
        """Get the framework type for this agent."""
        return self.config.framework

    @abc.abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent's resources."""

    @abc.abstractmethod
    async def reset(self) -> None:
        """Reset the agent's state for a new run."""

    @abc.abstractmethod
    async def perceive(self, context: AgentContext) -> None:
        """Perceive the environment and update internal state."""

    @abc.abstractmethod
    async def decide(self, context: AgentContext) -> List[AgentAction]:
        """Decide on actions to take based on context."""

    @abc.abstractmethod
    async def act(self, actions: List[AgentAction]) -> None:
        """Execute actions."""

    @abc.abstractmethod
    async def learn(self, context: AgentContext, outcome: Dict[str, Any]) -> None:
        """Learn from the outcome of actions."""

    @abc.abstractmethod
    async def get_internal_state(self) -> Dict[str, Any]:
        """Get the agent's internal state."""

    @abc.abstractmethod
    async def shutdown(self) -> None:
        """Shutdown and cleanup resources."""

    async def run_decision_cycle(self, context: AgentContext) -> List[AgentAction]:
        """Run a complete decision cycle."""
        if self.state != AgentState.READY:
            raise RuntimeError(
                f"Agent {self.agent_id} is not ready. State: {self.state}"
            )

        self.state = AgentState.RUNNING

        try:
            # Perceive environment
            await self.perceive(context)

            # Decide on actions
            actions = await self.decide(context)

            # Execute actions
            await self.act(actions)

            # Update previous actions
            context.previous_actions.extend(actions)

            return actions

        except Exception as e:
            logger.error(f"Error in decision cycle for agent {self.agent_id}: {e}")
            self.state = AgentState.ERROR
            raise
        finally:
            if self.state == AgentState.RUNNING:
                self.state = AgentState.READY

    async def handle_message(self, message: AgentMessage) -> None:
        """Handle an incoming message."""
        handler = self._message_handlers.get(message.message_type)
        if handler:
            await handler(message)
        else:
            logger.warning(
                f"No handler for message type {message.message_type} in agent {self.agent_id}"
            )

    async def handle_observation(self, observation: AgentObservation) -> None:
        """Handle an observation."""
        handler = self._observation_handlers.get(observation.observation_type)
        if handler:
            await handler(observation)
        else:
            logger.warning(
                f"No handler for observation type {observation.observation_type} in agent {self.agent_id}"
            )

    def register_message_handler(
        self, message_type: str, handler: Callable[[AgentMessage], None]
    ) -> None:
        """Register a message handler."""
        self._message_handlers[message_type] = handler

    def register_observation_handler(
        self, observation_type: str, handler: Callable[[AgentObservation], None]
    ) -> None:
        """Register an observation handler."""
        self._observation_handlers[observation_type] = handler

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if the agent has a specific capability."""
        return capability in self.capabilities

    def add_capability(self, capability: AgentCapability) -> None:
        """Add a capability to the agent."""
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def add_metric(self, metric: MetricResult) -> None:
        """Add a metric result."""
        self.metrics.append(metric)

    def get_metrics_by_name(self, name: str) -> List[MetricResult]:
        """Get metrics by name."""
        return [m for m in self.metrics if m.name == name]

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary."""
        return {
            "agent_id": self.agent_id,
            "framework_type": self.framework_type.value,
            "state": self.state.value,
            "capabilities": [cap.value for cap in self.capabilities],
            "config": self.config.dict(),
            "metrics": [m.to_dict() for m in self.metrics],
        }


class NativeFBAAdapter(BaseUnifiedAgent):
    """Adapter for native FBA agents to work with the unified interface."""

    def __init__(self, agent_id: str, config: PydanticAgentConfig, native_agent):
        """Initialize the adapter."""
        super().__init__(agent_id, config)
        self.native_agent = native_agent

        # Add standard capabilities
        self.add_capability(AgentCapability.DECISION_MAKING)
        self.add_capability(AgentCapability.TOOL_USE)

    async def initialize(self) -> None:
        """Initialize the native agent."""
        if hasattr(self.native_agent, "initialize"):
            if asyncio.iscoroutinefunction(self.native_agent.initialize):
                await self.native_agent.initialize()
            else:
                self.native_agent.initialize()

        self._is_initialized = True
        self.state = AgentState.READY
        logger.info(f"Native FBA agent {self.agent_id} initialized")

    async def reset(self) -> None:
        """Reset the native agent."""
        if hasattr(self.native_agent, "reset"):
            if asyncio.iscoroutinefunction(self.native_agent.reset):
                await self.native_agent.reset()
            else:
                self.native_agent.reset()

        self.state = AgentState.READY
        logger.info(f"Native FBA agent {self.agent_id} reset")

    async def perceive(self, context: AgentContext) -> None:
        """Perceive the environment."""
        # Convert observations to stimulus format
        stimulus = {
            "observations": [obs.data for obs in context.observations],
            "world_state": context.world_state,
            "messages": [msg.content for msg in context.messages],
        }

        if hasattr(self.native_agent, "perceive"):
            if asyncio.iscoroutinefunction(self.native_agent.perceive):
                await self.native_agent.perceive(stimulus)
            else:
                self.native_agent.perceive(stimulus)

    async def decide(self, context: AgentContext) -> List[AgentAction]:
        """Decide on actions to take."""
        # Convert context to stimulus format
        stimulus = {
            "observations": [obs.data for obs in context.observations],
            "world_state": context.world_state,
            "messages": [msg.content for msg in context.messages],
            "previous_actions": [
                action.parameters for action in context.previous_actions
            ],
        }

        if hasattr(self.native_agent, "process_stimulus"):
            if asyncio.iscoroutinefunction(self.native_agent.process_stimulus):
                response = await self.native_agent.process_stimulus(stimulus)
            else:
                response = self.native_agent.process_stimulus(stimulus)

            # Convert response to actions
            if isinstance(response, dict):
                return [
                    AgentAction(
                        action_type="response", parameters=response, confidence=1.0
                    )
                ]
            elif isinstance(response, list):
                return [
                    AgentAction(action_type="response", parameters=item, confidence=1.0)
                    for item in response
                ]

        return []

    async def act(self, actions: List[AgentAction]) -> None:
        """Execute actions."""
        # Actions are executed by the simulation engine

    async def learn(self, context: AgentContext, outcome: Dict[str, Any]) -> None:
        """Learn from the outcome."""
        if hasattr(self.native_agent, "learn"):
            if asyncio.iscoroutinefunction(self.native_agent.learn):
                await self.native_agent.learn(outcome)
            else:
                self.native_agent.learn(outcome)

    async def get_internal_state(self) -> Dict[str, Any]:
        """Get the agent's internal state."""
        if hasattr(self.native_agent, "get_state"):
            if asyncio.iscoroutinefunction(self.native_agent.get_state):
                return await self.native_agent.get_state()
            else:
                return self.native_agent.get_state()
        return {}

    async def shutdown(self) -> None:
        """Shutdown the native agent."""
        if hasattr(self.native_agent, "shutdown"):
            if asyncio.iscoroutinefunction(self.native_agent.shutdown):
                await self.native_agent.shutdown()
            else:
                self.native_agent.shutdown()

        self.state = AgentState.SHUTDOWN
        logger.info(f"Native FBA agent {self.agent_id} shutdown")


class CrewAIAdapter(BaseUnifiedAgent):
    """Adapter for CrewAI agents to work with the unified interface."""

    def __init__(self, agent_id: str, config: PydanticAgentConfig, crewai_agent):
        """Initialize the adapter."""
        super().__init__(agent_id, config)
        self.crewai_agent = crewai_agent

        # Add CrewAI-specific capabilities
        self.add_capability(AgentCapability.DECISION_MAKING)
        self.add_capability(AgentCapability.TOOL_USE)
        self.add_capability(AgentCapability.COMMUNICATION)
        self.add_capability(AgentCapability.PLANNING)

    async def initialize(self) -> None:
        """Initialize the CrewAI agent."""
        # CrewAI agents are typically initialized during creation
        self._is_initialized = True
        self.state = AgentState.READY
        logger.info(f"CrewAI agent {self.agent_id} initialized")

    async def reset(self) -> None:
        """Reset the CrewAI agent."""
        # CrewAI doesn't have a direct reset method, so we recreate the agent
        self.state = AgentState.READY
        logger.info(f"CrewAI agent {self.agent_id} reset")

    async def perceive(self, context: AgentContext) -> None:
        """Perceive the environment."""
        # CrewAI agents perceive through their task inputs

    async def decide(self, context: AgentContext) -> List[AgentAction]:
        """Decide on actions to take."""
        # Create a task for the CrewAI agent based on the context
        from crewai import Task

        # Format the task description based on the context
        task_description = (
            "Analyze the following FBA market data and make pricing decisions:\n"
        )
        task_description += f"Products: {context.world_state.get('products', [])}\n"
        task_description += (
            f"Market conditions: {context.world_state.get('market_conditions', {})}\n"
        )
        task_description += (
            f"Recent events: {[obs.data for obs in context.observations]}\n"
        )

        task = Task(
            description=task_description,
            agent=self.crewai_agent,
            expected_output="A JSON object with pricing decisions for each product",
        )

        # Execute the task
        try:
            from crewai import Crew

            crew = Crew(agents=[self.crewai_agent], tasks=[task], verbose=False)

            result = crew.kickoff()

            # Parse the result to extract actions
            if isinstance(result, str):
                # Try to parse as JSON
                try:
                    import json

                    actions_data = json.loads(result)

                    # Convert to AgentAction objects
                    actions = []
                    for asin, price_data in actions_data.items():
                        if isinstance(price_data, dict) and "price" in price_data:
                            actions.append(
                                AgentAction(
                                    action_type="set_price",
                                    parameters={
                                        "asin": asin,
                                        "price": float(price_data["price"]),
                                    },
                                    confidence=float(price_data.get("confidence", 0.8)),
                                    reasoning=price_data.get(
                                        "reasoning", "CrewAI pricing decision"
                                    ),
                                )
                            )
                    return actions
                except json.JSONDecodeError:
                    # If not JSON, treat as a single response
                    return [
                        AgentAction(
                            action_type="response",
                            parameters={"decision": result},
                            confidence=0.7,
                        )
                    ]

            return []

        except Exception as e:
            logger.error(f"Error in CrewAI agent decision: {e}")
            return []

    async def act(self, actions: List[AgentAction]) -> None:
        """Execute actions."""
        # Actions are executed by the simulation engine

    async def learn(self, context: AgentContext, outcome: Dict[str, Any]) -> None:
        """Learn from the outcome."""
        # CrewAI agents don't have explicit learning methods

    async def get_internal_state(self) -> Dict[str, Any]:
        """Get the agent's internal state."""
        return {
            "agent_type": "crewai",
            "role": getattr(self.crewai_agent, "role", "unknown"),
            "goal": getattr(self.crewai_agent, "goal", "unknown"),
            "backstory": getattr(self.crewai_agent, "backstory", "unknown"),
        }

    async def shutdown(self) -> None:
        """Shutdown the CrewAI agent."""
        self.state = AgentState.SHUTDOWN
        logger.info(f"CrewAI agent {self.agent_id} shutdown")


class LangChainAdapter(BaseUnifiedAgent):
    """Adapter for LangChain agents to work with the unified interface."""

    def __init__(self, agent_id: str, config: PydanticAgentConfig, langchain_agent):
        """Initialize the adapter."""
        super().__init__(agent_id, config)
        self.langchain_agent = langchain_agent

        # Add LangChain-specific capabilities
        self.add_capability(AgentCapability.DECISION_MAKING)
        self.add_capability(AgentCapability.TOOL_USE)
        self.add_capability(AgentCapability.REASONING)

    async def initialize(self) -> None:
        """Initialize the LangChain agent."""
        # LangChain agents are typically initialized during creation
        self._is_initialized = True
        self.state = AgentState.READY
        logger.info(f"LangChain agent {self.agent_id} initialized")

    async def reset(self) -> None:
        """Reset the LangChain agent."""
        # LangChain agents maintain conversation history, so we need to clear it
        if hasattr(self.langchain_agent, "memory"):
            self.langchain_agent.memory.clear()

        self.state = AgentState.READY
        logger.info(f"LangChain agent {self.agent_id} reset")

    async def perceive(self, context: AgentContext) -> None:
        """Perceive the environment."""
        # LangChain agents perceive through their input prompts

    async def decide(self, context: AgentContext) -> List[AgentAction]:
        """Decide on actions to take."""
        # Format the input for the LangChain agent
        input_text = "You are an FBA pricing expert. Analyze the following data and make pricing decisions:\n\n"
        input_text += f"Products: {context.world_state.get('products', [])}\n\n"
        input_text += (
            f"Market conditions: {context.world_state.get('market_conditions', {})}\n\n"
        )
        input_text += f"Recent events: {[obs.data for obs in context.observations]}\n\n"
        input_text += "Provide your response as a JSON object with 'asin' as keys and 'price' as values."

        try:
            # Execute the agent
            result = await self.langchain_agent.arun(input_text)

            # Parse the result to extract actions
            if isinstance(result, str):
                # Try to parse as JSON
                try:
                    import json

                    actions_data = json.loads(result)

                    # Convert to AgentAction objects
                    actions = []
                    for asin, price_data in actions_data.items():
                        if isinstance(price_data, dict) and "price" in price_data:
                            actions.append(
                                AgentAction(
                                    action_type="set_price",
                                    parameters={
                                        "asin": asin,
                                        "price": float(price_data["price"]),
                                    },
                                    confidence=float(price_data.get("confidence", 0.8)),
                                    reasoning=price_data.get(
                                        "reasoning", "LangChain pricing decision"
                                    ),
                                )
                            )
                        elif isinstance(price_data, (int, float)):
                            # Simple price value
                            actions.append(
                                AgentAction(
                                    action_type="set_price",
                                    parameters={
                                        "asin": asin,
                                        "price": float(price_data),
                                    },
                                    confidence=0.8,
                                    reasoning="LangChain pricing decision",
                                )
                            )
                    return actions
                except json.JSONDecodeError:
                    # If not JSON, treat as a single response
                    return [
                        AgentAction(
                            action_type="response",
                            parameters={"decision": result},
                            confidence=0.7,
                        )
                    ]

            return []

        except Exception as e:
            logger.error(f"Error in LangChain agent decision: {e}")
            return []

    async def act(self, actions: List[AgentAction]) -> None:
        """Execute actions."""
        # Actions are executed by the simulation engine

    async def learn(self, context: AgentContext, outcome: Dict[str, Any]) -> None:
        """Learn from the outcome."""
        # LangChain agents learn through their conversation history

    async def get_internal_state(self) -> Dict[str, Any]:
        """Get the agent's internal state."""
        return {
            "agent_type": "langchain",
            "agent_type_name": type(self.langchain_agent).__name__,
            "input_keys": getattr(self.langchain_agent, "input_keys", []),
            "output_keys": getattr(self.langchain_agent, "output_keys", []),
        }

    async def shutdown(self) -> None:
        """Shutdown the LangChain agent."""
        self.state = AgentState.SHUTDOWN
        logger.info(f"LangChain agent {self.agent_id} shutdown")


class DIYAdapter(BaseUnifiedAgent):
    """Adapter for DIY agents to work with the unified interface."""

    def __init__(self, agent_id: str, config: PydanticAgentConfig, diy_agent):
        """Initialize the adapter."""
        super().__init__(agent_id, config)
        self.diy_agent = diy_agent

        # Add DIY-specific capabilities based on agent type
        self.add_capability(AgentCapability.DECISION_MAKING)

        agent_type = config.parameters.get("agent_type", "default")
        if agent_type == "advanced":
            self.add_capability(AgentCapability.PLANNING)
            self.add_capability(AgentCapability.MEMORY_MANAGEMENT)
        elif agent_type == "llm":
            self.add_capability(AgentCapability.REASONING)

    async def initialize(self) -> None:
        """Initialize the DIY agent."""
        if hasattr(self.diy_agent, "initialize"):
            if asyncio.iscoroutinefunction(self.diy_agent.initialize):
                await self.diy_agent.initialize()
            else:
                self.diy_agent.initialize()

        self._is_initialized = True
        self.state = AgentState.READY
        logger.info(f"DIY agent {self.agent_id} initialized")

    async def reset(self) -> None:
        """Reset the DIY agent."""
        if hasattr(self.diy_agent, "reset"):
            if asyncio.iscoroutinefunction(self.diy_agent.reset):
                await self.diy_agent.reset()
            else:
                self.diy_agent.reset()

        self.state = AgentState.READY
        logger.info(f"DIY agent {self.agent_id} reset")

    async def perceive(self, context: AgentContext) -> None:
        """Perceive the environment."""
        # Convert observations to stimulus format
        stimulus = {
            "observations": [obs.data for obs in context.observations],
            "world_state": context.world_state,
            "messages": [msg.content for msg in context.messages],
        }

        if hasattr(self.diy_agent, "perceive"):
            if asyncio.iscoroutinefunction(self.diy_agent.perceive):
                await self.diy_agent.perceive(stimulus)
            else:
                self.diy_agent.perceive(stimulus)

    async def decide(self, context: AgentContext) -> List[AgentAction]:
        """Decide on actions to take."""
        # Convert context to the format expected by the DIY agent
        if hasattr(self.diy_agent, "decide"):
            # Create a simulation state object for the DIY agent
            from fba_bench.core.types import SimulationState

            sim_state = SimulationState(
                tick=context.tick,
                simulation_time=context.metadata.get("simulation_time", datetime.now()),
                products=context.world_state.get("products", []),
                recent_events=[obs.data for obs in context.observations],
            )

            # Get decision from the DIY agent
            if asyncio.iscoroutinefunction(self.diy_agent.decide):
                actions = await self.diy_agent.decide(sim_state)
            else:
                actions = self.diy_agent.decide(sim_state)

            # Convert actions to AgentAction objects
            agent_actions = []
            for action in actions:
                if hasattr(action, "tool_name") and hasattr(action, "parameters"):
                    agent_actions.append(
                        AgentAction(
                            action_type=action.tool_name,
                            parameters=action.parameters,
                            confidence=getattr(action, "confidence", 0.8),
                            reasoning=getattr(
                                action, "reasoning", "DIY agent decision"
                            ),
                        )
                    )
                elif isinstance(action, dict):
                    agent_actions.append(
                        AgentAction(
                            action_type=action.get("type", "response"),
                            parameters=action,
                            confidence=action.get("confidence", 0.8),
                            reasoning=action.get("reasoning", "DIY agent decision"),
                        )
                    )

            return agent_actions

        return []

    async def act(self, actions: List[AgentAction]) -> None:
        """Execute actions."""
        # Actions are executed by the simulation engine

    async def learn(self, context: AgentContext, outcome: Dict[str, Any]) -> None:
        """Learn from the outcome."""
        if hasattr(self.diy_agent, "learn"):
            if asyncio.iscoroutinefunction(self.diy_agent.learn):
                await self.diy_agent.learn(outcome)
            else:
                self.diy_agent.learn(outcome)

    async def get_internal_state(self) -> Dict[str, Any]:
        """Get the agent's internal state."""
        if hasattr(self.diy_agent, "get_state"):
            if asyncio.iscoroutinefunction(self.diy_agent.get_state):
                return await self.diy_agent.get_state()
            else:
                return self.diy_agent.get_state()
        return {"agent_type": "diy"}

    async def shutdown(self) -> None:
        """Shutdown the DIY agent."""
        if hasattr(self.diy_agent, "shutdown"):
            if asyncio.iscoroutinefunction(self.diy_agent.shutdown):
                await self.diy_agent.shutdown()
            else:
                self.diy_agent.shutdown()

        self.state = AgentState.SHUTDOWN
        logger.info(f"DIY agent {self.agent_id} shutdown")


class UnifiedAgentRunner:
    """Unified runner for all agent types."""

    def __init__(self, agent: BaseUnifiedAgent):
        """Initialize the runner."""
        self.agent = agent
        self._is_initialized = False

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the agent runner."""
        await self.agent.initialize()
        self._is_initialized = True
        logger.info(f"Unified agent runner initialized for agent {self.agent.agent_id}")

    async def decide(self, context: Any) -> List[Any]:
        """Run the agent's decision cycle."""
        if not self._is_initialized:
            raise RuntimeError("Agent runner not initialized")

        # Convert simulation state to agent context
        agent_context = self._convert_to_agent_context(context)

        # Run decision cycle
        actions = await self.agent.run_decision_cycle(agent_context)

        # Convert actions back to simulation format
        return self._convert_actions_to_simulation_format(actions)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.agent.shutdown()
        logger.info(f"Unified agent runner cleaned up for agent {self.agent.agent_id}")

    def _convert_to_agent_context(self, simulation_state: Any) -> AgentContext:
        """
        Convert simulation state to agent context.

        Args:
            simulation_state: The current state of the simulation

        Returns:
            AgentContext: Formatted context for the agent
        """
        # Extract relevant information from simulation state
        scenario_id = getattr(
            simulation_state,
            "scenario_id",
            simulation_state.get("scenario_id", "unknown"),
        )
        tick = getattr(simulation_state, "tick", simulation_state.get("tick", 0))

        # Extract world state with proper fallback
        world_state = getattr(
            simulation_state, "world_state", simulation_state.get("world_state", {})
        )

        # Ensure world_state is a dictionary
        if not isinstance(world_state, dict):
            world_state = {"raw_state": world_state}

        # Create agent context with properly structured data
        return AgentContext(
            agent_id=self.agent.agent_id,
            scenario_id=scenario_id,
            tick=tick,
            world_state=world_state,
        )

    def _convert_actions_to_simulation_format(
        self, actions: List[AgentAction]
    ) -> List[Any]:
        """
        Convert agent actions to simulation format.

        Args:
            actions: List of agent actions to convert

        Returns:
            List of formatted actions compatible with the simulation
        """
        formatted_actions = []

        for action in actions:
            # Create a structured action object for the simulation
            sim_action = {
                "agent_id": self.agent.agent_id,
                "action_type": action.action_type,
                "parameters": action.parameters,
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "priority": getattr(action, "priority", "normal"),
                    "confidence": getattr(action, "confidence", 1.0),
                },
            }

            # Add any additional context from the action
            if hasattr(action, "context"):
                sim_action["context"] = action.context

            formatted_actions.append(sim_action)

        return formatted_actions


class AgentFactory:
    """Factory for creating unified agents."""

    def __init__(self):
        """Initialize the factory."""
        self._agent_types: Dict[str, Type[BaseUnifiedAgent]] = {}
        self._adapters: Dict[FrameworkType, Type[BaseUnifiedAgent]] = {
            FrameworkType.DIRECT: NativeFBAAdapter,
            FrameworkType.DIY: DIYAdapter,
            FrameworkType.CREWAI: CrewAIAdapter,
            FrameworkType.LANGCHAIN: LangChainAdapter,
            FrameworkType.ADAPTED: NativeFBAAdapter,
        }

    def register_agent_type(
        self, agent_type: str, agent_class: Type[BaseUnifiedAgent]
    ) -> None:
        """Register a new agent type."""
        self._agent_types[agent_type] = agent_class
        logger.info(f"Registered agent type: {agent_type}")

    def register_adapter(
        self, framework: FrameworkType, adapter_class: Type[BaseUnifiedAgent]
    ) -> None:
        """Register an adapter for a framework."""
        self._adapters[framework] = adapter_class
        logger.info(f"Registered adapter for framework: {framework}")

    def create_agent(
        self,
        agent_id: str,
        config: PydanticAgentConfig,
        native_agent: Optional[Any] = None,
    ) -> BaseUnifiedAgent:
        """Create an agent instance."""
        framework = config.framework

        # Get the appropriate adapter
        adapter_class = self._adapters.get(framework)
        if not adapter_class:
            raise ValueError(f"No adapter registered for framework: {framework}")

        # Create the agent
        if native_agent is not None:
            return adapter_class(agent_id, config, native_agent)
        else:
            # Create a framework-specific agent
            return self._create_framework_agent(agent_id, config, adapter_class)

    def _create_framework_agent(
        self,
        agent_id: str,
        config: PydanticAgentConfig,
        adapter_class: Type[BaseUnifiedAgent],
    ) -> BaseUnifiedAgent:
        """Create a framework-specific agent instance."""
        framework = config.framework

        if framework == FrameworkType.CREWAI:
            return self._create_crewai_agent(agent_id, config, adapter_class)
        elif framework == FrameworkType.LANGCHAIN:
            return self._create_langchain_agent(agent_id, config, adapter_class)
        elif framework == FrameworkType.DIY:
            return self._create_diy_agent(agent_id, config, adapter_class)
        else:
            # For other frameworks, create a default agent
            return adapter_class(agent_id, config, self._create_default_agent(config))

    def _create_crewai_agent(
        self,
        agent_id: str,
        config: PydanticAgentConfig,
        adapter_class: Type[BaseUnifiedAgent],
    ) -> BaseUnifiedAgent:
        """Create a CrewAI agent instance."""
        try:
            from crewai import Agent

            # Extract CrewAI-specific configuration
            llm_config = config.llm_config or {}
            agent_params = config.parameters or {}

            # Create the CrewAI agent
            crewai_agent = Agent(
                role=agent_params.get("role", "FBA Pricing Specialist"),
                goal=agent_params.get(
                    "goal", "Optimize FBA product pricing for maximum profit"
                ),
                backstory=agent_params.get(
                    "backstory",
                    "You are an experienced FBA pricing expert with deep knowledge of e-commerce markets.",
                ),
                verbose=False,
                allow_delegation=False,
            )

            return adapter_class(agent_id, config, crewai_agent)

        except ImportError:
            logger.error("CrewAI not available. Install with: pip install crewai")
            raise
        except Exception as e:
            logger.error(f"Error creating CrewAI agent: {e}")
            raise

    def _create_langchain_agent(
        self,
        agent_id: str,
        config: PydanticAgentConfig,
        adapter_class: Type[BaseUnifiedAgent],
    ) -> BaseUnifiedAgent:
        """Create a LangChain agent instance."""
        try:
            from langchain.agents import AgentType, initialize_agent
            from langchain.llms import OpenAI
            from langchain.tools import Tool

            # Extract LangChain-specific configuration
            llm_config = config.llm_config or {}
            agent_params = config.parameters or {}

            # Create the LLM
            llm = OpenAI(
                model_name=llm_config.get("model", "gpt-3.5-turbo-instruct"),
                temperature=llm_config.get("temperature", 0.1),
                openai_api_key=llm_config.get("api_key"),
            )

            # Define tools for the agent
            tools = [
                Tool(
                    name="FBA Pricing",
                    func=self._make_pricing_decision,
                    description="Useful for making FBA pricing decisions based on market conditions",
                ),
                Tool(
                    name="Market Analysis",
                    func=self._analyze_market_conditions,
                    description="Useful for analyzing current market conditions and competition",
                ),
                Tool(
                    name="Inventory Check",
                    func=self._check_inventory_levels,
                    description="Useful for checking current inventory levels and availability",
                ),
            ]

            # Create the LangChain agent
            langchain_agent = initialize_agent(
                tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False
            )

            return adapter_class(agent_id, config, langchain_agent)

        except ImportError:
            logger.error("LangChain not available. Install with: pip install langchain")
            raise
        except Exception as e:
            logger.error(f"Error creating LangChain agent: {e}")
            raise

    def _create_diy_agent(
        self,
        agent_id: str,
        config: PydanticAgentConfig,
        adapter_class: Type[BaseUnifiedAgent],
    ) -> BaseUnifiedAgent:
        """
        Create a DIY/baseline agent instance (Greedy/LLM/Advanced) in a unified way.

        This consolidates the legacy BotFactory behavior into the unified factory. The selection
        is controlled via config.parameters and optional config.custom_config values:
          - parameters.agent_type: 'baseline' | 'llm' | 'advanced'
          - parameters.bot_name: 'GreedyScript' | 'GPT-3.5' | 'GPT-4o mini-budget' | 'Grok-4' | 'Claude 3.5 Sonnet'
          - parameters.strategy / other fields are passed through
          - custom_config._services: injected by AgentManager, contains world_store, budget_enforcer,
            trust_metrics, agent_gateway, openrouter_api_key
        """

        agent_params = config.parameters or {}
        custom_config = config.custom_config or {}
        services = custom_config.get("_services") or {}

        agent_type = agent_params.get("agent_type", "baseline").lower()
        bot_name = agent_params.get("bot_name") or agent_params.get(
            "bot_type"
        )  # support both keys

        try:
            if agent_type == "baseline" and (
                bot_name is None or bot_name == "GreedyScript"
            ):
                # Greedy rule-based bot
                from baseline_bots.greedy_script_bot import GreedyScriptBot

                # Allow tier-style knobs via parameters or custom_config
                reorder_threshold = agent_params.get(
                    "reorder_threshold"
                ) or custom_config.get("reorder_threshold", 10)
                reorder_quantity = agent_params.get(
                    "reorder_quantity"
                ) or custom_config.get("reorder_quantity", 50)
                diy_agent = GreedyScriptBot(
                    reorder_threshold=int(reorder_threshold),
                    reorder_quantity=int(reorder_quantity),
                )
                return adapter_class(agent_id, config, diy_agent)

            if agent_type in ("llm", "baseline"):
                # Build LLM-based baseline bots using shared dependencies
                from baseline_bots.claude_sonnet_bot import ClaudeSonnetBot
                from baseline_bots.gpt_3_5_bot import GPT35Bot
                from baseline_bots.gpt_4o_mini_bot import GPT4oMiniBot
                from baseline_bots.grok_4_bot import Grok4Bot
                from llm_interface.openrouter_client import OpenRouterClient
                from llm_interface.prompt_adapter import PromptAdapter
                from llm_interface.response_parser import LLMResponseParser

                # Check if services module is available
                if services is None:
                    raise ValueError(
                        "Services module not available. Cannot create DIY LLM agent."
                    )

                world_store = services.get("world_store")
                budget_enforcer = services.get("budget_enforcer")
                trust_metrics = services.get("trust_metrics")
                agent_gateway = services.get("agent_gateway")
                event_bus = services.get("event_bus")

                if not all(
                    [
                        world_store,
                        budget_enforcer,
                        trust_metrics,
                        agent_gateway,
                        event_bus,
                    ]
                ):
                    raise ValueError(
                        "Unified DIY LLM agent requires world_store, budget_enforcer, trust_metrics, agent_gateway, and event_bus services."
                    )

                api_key = (config.llm_config or {}).get("api_key") or (
                    services.get("openrouter_api_key") if services else None
                )
                model_name = (config.llm_config or {}).get("model")
                temperature = (config.llm_config or {}).get("temperature", 0.1)
                max_tokens = (config.llm_config or {}).get("max_tokens", 1000)
                top_p = (config.llm_config or {}).get("top_p", 1.0)

                import os

                from llm_interface.llm_config import LLMConfig

                llm_cfg = LLMConfig(
                    provider="openrouter",
                    model=(model_name or "moonshotai/kimi-k2:free"),
                    api_key_env="OPENROUTER_API_KEY",
                    base_url=os.getenv("OPENROUTER_BASE_URL") or None,
                    temperature=float(temperature),
                    max_tokens=int(max_tokens),
                    top_p=float(top_p),
                    custom_params={},
                )
                llm_client = OpenRouterClient(llm_cfg)
                prompt_adapter = PromptAdapter(world_store, budget_enforcer)
                response_parser = LLMResponseParser(event_bus)
                model_params = {
                    "temperature": temperature,
                    "max_tokens_per_action": max_tokens,
                    "top_p": top_p,
                }

                # Choose concrete bot by bot_name or fallback to GPT-3.5
                chosen = (bot_name or "").lower() if bot_name else ""
                if "claude" in chosen or "sonnet" in chosen:
                    diy_agent = ClaudeSonnetBot(
                        agent_id,
                        llm_client,
                        prompt_adapter,
                        response_parser,
                        agent_gateway,
                        model_params,
                    )
                elif "4o" in chosen:
                    diy_agent = GPT4oMiniBot(
                        agent_id,
                        llm_client,
                        prompt_adapter,
                        response_parser,
                        agent_gateway,
                        model_params,
                    )
                elif "grok" in chosen:
                    diy_agent = Grok4Bot(
                        agent_id,
                        llm_client,
                        prompt_adapter,
                        response_parser,
                        agent_gateway,
                        model_params,
                    )
                else:
                    diy_agent = GPT35Bot(
                        agent_id,
                        llm_client,
                        prompt_adapter,
                        response_parser,
                        agent_gateway,
                        model_params,
                    )

                return adapter_class(agent_id, config, diy_agent)

            if agent_type == "advanced":
                from agents.advanced_agent import AdvancedAgent

                diy_agent = AdvancedAgent(config.dict())
                return adapter_class(agent_id, config, diy_agent)

            # Default fallback
            return adapter_class(agent_id, config, self._create_default_agent(config))

        except ImportError as e:
            logger.error(f"DIY agent type '{agent_type}' not available: {e}")
            return adapter_class(agent_id, config, self._create_default_agent(config))
        except Exception as e:
            logger.error(f"Error creating DIY agent: {e}")
            raise

    def _create_default_agent(self, config: PydanticAgentConfig) -> Any:
        """Create a default agent implementation."""

        # This would create a basic agent implementation
        # For now, we'll return a simple placeholder
        class DefaultAgent:
            def __init__(self, config):
                self.config = config

            async def initialize(self):
                pass

            async def reset(self):
                pass

            async def process_stimulus(self, stimulus):
                return {"response": "Default agent response"}

            async def get_state(self):
                return {"state": "default"}

            async def shutdown(self):
                pass

        return DefaultAgent(config)

    def _make_pricing_decision(self, input_data: str) -> dict:
        """
        Make a pricing decision based on input data.

        Args:
            input_data: String containing market and product information

        Returns:
            dict: Pricing decision with recommended price and reasoning
        """
        try:
            # Parse input data to extract relevant information
            import json

            # Try to parse as JSON first
            try:
                data = json.loads(input_data)
            except json.JSONDecodeError:
                # If not JSON, extract key information using regex
                data = {
                    "product_cost": self._extract_number(
                        input_data, r"cost[s]?\s*[:\$]?\s*(\d+\.?\d*)"
                    ),
                    "competitor_price": self._extract_number(
                        input_data, r"competitor[s]?\s*price[s]?\s*[:\$]?\s*(\d+\.?\d*)"
                    ),
                    "demand": self._extract_number(
                        input_data, r"demand\s*[:\-]?\s*(\d+\.?\d*)"
                    ),
                    "market_share": self._extract_number(
                        input_data, r"market\s*share\s*[:\-]?\s*(\d+\.?\d*)"
                    ),
                }

            # Calculate recommended price using a simple pricing algorithm
            product_cost = data.get("product_cost", 10.0)
            competitor_price = data.get("competitor_price", 15.0)
            demand = data.get("demand", 1.0)
            market_share = data.get("market_share", 0.1)

            # Base price calculation
            base_price = product_cost * 1.5  # 50% margin

            # Adjust based on competition
            if competitor_price > base_price * 1.2:
                # We can charge more than base
                recommended_price = (base_price + competitor_price) / 2
            elif competitor_price < base_price * 0.8:
                # Competitor is much cheaper, match or slightly undercut
                recommended_price = competitor_price * 0.95
            else:
                # Close to competitor price
                recommended_price = competitor_price

            # Adjust based on demand
            if demand > 1.5:
                recommended_price *= 1.1  # Increase price for high demand
            elif demand < 0.5:
                recommended_price *= 0.9  # Decrease price for low demand

            # Adjust based on market share
            if market_share > 0.3:
                recommended_price *= 1.05  # Slight premium for market leader
            elif market_share < 0.05:
                recommended_price *= 0.95  # Discount for small player

            # Ensure minimum margin
            minimum_price = product_cost * 1.2
            recommended_price = max(recommended_price, minimum_price)

            return {
                "price": round(recommended_price, 2),
                "reasoning": f"Based on product cost (${product_cost}), competitor price (${competitor_price}), "
                f"demand factor ({demand}), and market share ({market_share:.1%})",
                "confidence": min(0.9, 0.5 + market_share * 2),
                "margin_percentage": round(
                    (recommended_price - product_cost) / product_cost * 100, 1
                ),
            }

        except Exception as e:
            logger.error(f"Error in pricing decision: {e}")
            return {
                "price": 15.0,
                "reasoning": "Default pricing due to error in analysis",
                "confidence": 0.3,
                "error": str(e),
            }

    def _analyze_market_conditions(self, input_data: str) -> dict:
        """
        Analyze market conditions based on input data.

        Args:
            input_data: String containing market information

        Returns:
            dict: Market analysis with trends and recommendations
        """
        try:
            # Extract market data
            market_trend = self._extract_trend(
                input_data, r"market\s*trend\s*[:\-]?\s*(\w+)"
            )
            competition_level = self._extract_level(
                input_data, r"competition\s*[:\-]?\s*(\w+)"
            )
            seasonality = self._extract_seasonality(input_data)

            # Determine market conditions
            if market_trend == "growing" and competition_level == "low":
                market_condition = "favorable"
                recommendation = "Consider premium pricing and expansion"
            elif market_trend == "declining" and competition_level == "high":
                market_condition = "challenging"
                recommendation = "Focus on cost reduction and differentiation"
            else:
                market_condition = "stable"
                recommendation = "Maintain current strategy with minor adjustments"

            return {
                "market_condition": market_condition,
                "trend": market_trend,
                "competition_level": competition_level,
                "seasonality": seasonality,
                "recommendation": recommendation,
                "confidence": 0.7,
            }

        except Exception as e:
            logger.error(f"Error in market analysis: {e}")
            return {
                "market_condition": "unknown",
                "trend": "stable",
                "competition_level": "moderate",
                "seasonality": "normal",
                "recommendation": "Proceed with caution",
                "error": str(e),
            }

    def _check_inventory_levels(self, input_data: str) -> dict:
        """
        Check inventory levels and provide recommendations.

        Args:
            input_data: String containing inventory information

        Returns:
            dict: Inventory status and recommendations
        """
        try:
            # Extract inventory data
            current_stock = self._extract_number(
                input_data, r"current\s*stock\s*[:\-]?\s*(\d+)"
            )
            min_stock = self._extract_number(
                input_data, r"min(?:imum)?\s*stock\s*[:\-]?\s*(\d+)"
            )
            max_stock = self._extract_number(
                input_data, r"max(?:imum)?\s*stock\s*[:\-]?\s*(\d+)"
            )
            sales_rate = self._extract_number(
                input_data, r"sales\s*rate\s*[:\-]?\s*(\d+\.?\d*)"
            )

            # Calculate days of inventory
            if sales_rate > 0:
                days_of_inventory = current_stock / sales_rate
            else:
                days_of_inventory = float("inf")

            # Determine inventory status
            if current_stock <= min_stock:
                status = "critical"
                action = "Immediate restocking required"
            elif current_stock <= min_stock * 1.5:
                status = "low"
                action = "Plan restocking soon"
            elif current_stock >= max_stock:
                status = "overstocked"
                action = "Consider promotions or discounts"
            else:
                status = "adequate"
                action = "Maintain current levels"

            return {
                "current_stock": current_stock,
                "min_stock": min_stock,
                "max_stock": max_stock,
                "days_of_inventory": round(days_of_inventory, 1),
                "status": status,
                "recommended_action": action,
                "sales_rate": sales_rate,
            }

        except Exception as e:
            logger.error(f"Error in inventory check: {e}")
            return {
                "current_stock": 0,
                "min_stock": 0,
                "max_stock": 0,
                "days_of_inventory": 0,
                "status": "unknown",
                "recommended_action": "Manual inventory check required",
                "error": str(e),
            }

    def _extract_number(self, text: str, pattern: str) -> float:
        """Extract a number from text using regex pattern."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 0.0

    def _extract_trend(self, text: str, pattern: str) -> str:
        """Extract trend information from text."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            trend = match.group(1).lower()
            if trend in ["growing", "increasing", "rising", "up"]:
                return "growing"
            elif trend in ["declining", "decreasing", "falling", "down"]:
                return "declining"
            else:
                return "stable"
        return "stable"

    def _extract_level(self, text: str, pattern: str) -> str:
        """Extract level information from text."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            level = match.group(1).lower()
            if level in ["high", "intense", "strong"]:
                return "high"
            elif level in ["low", "weak", "minimal"]:
                return "low"
            else:
                return "moderate"
        return "moderate"

    def _extract_seasonality(self, text: str) -> str:
        """Extract seasonality information from text."""
        text_lower = text.lower()
        if any(
            word in text_lower
            for word in ["holiday", "christmas", "thanksgiving", "black friday"]
        ):
            return "peak"
        elif any(word in text_lower for word in ["summer", "winter", "spring", "fall"]):
            return "seasonal"
        else:
            return "normal"


# Global factory instance
agent_factory = AgentFactory()
