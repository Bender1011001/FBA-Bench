"""
Agent adapter for integrating existing agent_runners with the benchmarking framework.

This module provides adapters to bridge the gap between the new benchmarking framework
and the existing agent_runners system, ensuring seamless integration and compatibility.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..integration.manager import IntegrationManager

# Try to import existing agent systems
try:
    from fba_bench.core.types import SimulationState, ToolCall

    from agent_runners.base_runner import AgentRunner

    # Do not import RunnerFactory here; IntegrationManager abstracts runner creation and handles deprecations.
    AGENT_RUNNERS_AVAILABLE = True
except ImportError:
    AGENT_RUNNERS_AVAILABLE = False
    logging.warning("agent_runners module not available")

try:
    from models.product import Product

    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    logging.warning("models module not available")

logger = logging.getLogger(__name__)


@dataclass
class AgentAdapterConfig:
    """Configuration for agent adapter."""

    framework: str
    agent_id: str
    config: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 300
    retry_attempts: int = 3
    enable_monitoring: bool = True
    enable_tracing: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "framework": self.framework,
            "agent_id": self.agent_id,
            "config": self.config,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "enable_monitoring": self.enable_monitoring,
            "enable_tracing": self.enable_tracing,
        }


@dataclass
class AgentExecutionResult:
    """Result of agent execution."""

    agent_id: str
    framework: str
    success: bool
    tool_calls: List[ToolCall] = field(default_factory=list)
    execution_time: float = 0.0
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    trace_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "framework": self.framework,
            "success": self.success,
            "tool_calls": [self._tool_call_to_dict(tc) for tc in self.tool_calls],
            "execution_time": self.execution_time,
            "error_message": self.error_message,
            "metrics": self.metrics,
            "trace_data": self.trace_data,
        }

    def _tool_call_to_dict(self, tool_call: ToolCall) -> Dict[str, Any]:
        """Convert ToolCall to dictionary."""
        return {
            "tool_name": tool_call.tool_name,
            "parameters": tool_call.parameters,
            "confidence": tool_call.confidence,
            "reasoning": tool_call.reasoning,
            "priority": tool_call.priority,
        }


class AgentAdapter:
    """
    Adapter for integrating existing agent_runners with the benchmarking framework.

    This class provides a bridge between the new benchmarking framework and the
    existing agent_runners system, ensuring seamless integration and compatibility.
    """

    def __init__(
        self, config: AgentAdapterConfig, integration_manager: IntegrationManager
    ):
        """
        Initialize the agent adapter.

        Args:
            config: Agent adapter configuration
            integration_manager: Integration manager instance
        """
        self.config = config
        self.integration_manager = integration_manager
        self.agent_runner: Optional[AgentRunner] = None
        self._initialized = False

        # Monitoring and tracing
        self._execution_history: List[AgentExecutionResult] = []
        self._current_trace: Dict[str, Any] = {}

        logger.info(
            f"Initialized AgentAdapter for {config.framework} agent {config.agent_id}"
        )

    async def initialize(self) -> bool:
        """
        Initialize the agent adapter.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        if not AGENT_RUNNERS_AVAILABLE:
            logger.error("agent_runners module not available")
            return False

        try:
            # Create agent runner using the integration manager
            self.agent_runner = await self.integration_manager.create_agent_runner(
                self.config.framework, self.config.agent_id, self.config.config
            )

            if self.agent_runner is None:
                logger.error(
                    f"Failed to create agent runner for {self.config.agent_id}"
                )
                return False

            # Initialize the agent runner
            await self.agent_runner.initialize(self.config.config)

            self._initialized = True
            logger.info(
                f"Successfully initialized AgentAdapter for {self.config.agent_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to initialize AgentAdapter for {self.config.agent_id}: {e}"
            )
            return False

    async def execute_decision(
        self, simulation_state: Dict[str, Any]
    ) -> AgentExecutionResult:
        """
        Execute a decision using the adapted agent.

        Args:
            simulation_state: Simulation state dictionary

        Returns:
            AgentExecutionResult with execution details
        """
        if not self._initialized:
            if not await self.initialize():
                return AgentExecutionResult(
                    agent_id=self.config.agent_id,
                    framework=self.config.framework,
                    success=False,
                    error_message="Agent adapter not initialized",
                )

        start_time = datetime.now()

        try:
            # Convert simulation state to SimulationState object
            sim_state = self._convert_to_simulation_state(simulation_state)

            # Execute decision with retry logic
            tool_calls = await self._execute_with_retry(sim_state)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # Create result
            result = AgentExecutionResult(
                agent_id=self.config.agent_id,
                framework=self.config.framework,
                success=True,
                tool_calls=tool_calls,
                execution_time=execution_time,
                metrics=self._collect_metrics(),
                trace_data=self._current_trace.copy(),
            )

            # Store in history
            self._execution_history.append(result)

            logger.info(f"Agent {self.config.agent_id} executed decision successfully")
            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()

            result = AgentExecutionResult(
                agent_id=self.config.agent_id,
                framework=self.config.framework,
                success=False,
                execution_time=execution_time,
                error_message=str(e),
            )

            # Store in history
            self._execution_history.append(result)

            logger.error(f"Agent {self.config.agent_id} execution failed: {e}")
            return result

    async def _execute_with_retry(
        self, simulation_state: SimulationState
    ) -> List[ToolCall]:
        """
        Execute decision with retry logic.

        Args:
            simulation_state: Simulation state object

        Returns:
            List of tool calls
        """
        last_error = None

        for attempt in range(self.config.retry_attempts):
            try:
                if self.config.enable_tracing:
                    self._start_trace(f"decision_attempt_{attempt + 1}")

                # Execute decision
                tool_calls = await asyncio.wait_for(
                    self.agent_runner.decide(simulation_state),  # type: ignore[union-attr]
                    timeout=self.config.timeout,
                )

                if self.config.enable_tracing:
                    self._end_trace("success")

                return tool_calls

            except asyncio.TimeoutError:
                last_error = f"Decision timeout after {self.config.timeout} seconds"
                logger.warning(
                    f"Agent {self.config.agent_id} decision timeout (attempt {attempt + 1})"
                )

                if self.config.enable_tracing:
                    self._end_trace("timeout")

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Agent {self.config.agent_id} decision failed (attempt {attempt + 1}): {e}"
                )

                if self.config.enable_tracing:
                    self._end_trace("error", str(e))

            # Wait before retry
            if attempt < self.config.retry_attempts - 1:
                await asyncio.sleep(2**attempt)  # Exponential backoff

        # All attempts failed
        raise RuntimeError(
            f"Agent decision failed after {self.config.retry_attempts} attempts: {last_error}"
        )

    def _convert_to_simulation_state(
        self, state_dict: Dict[str, Any]
    ) -> SimulationState:
        """
        Convert dictionary to SimulationState object.

        Args:
            state_dict: Simulation state dictionary

        Returns:
            SimulationState object
        """
        if not MODELS_AVAILABLE:
            # Create a simple simulation state without Product objects
            return SimulationState(
                tick=state_dict.get("tick", 0),
                simulation_time=datetime.fromisoformat(
                    state_dict.get("simulation_time", datetime.now().isoformat())
                ),
                products=[],  # Empty list without Product objects
                recent_events=state_dict.get("recent_events", []),
                financial_position=state_dict.get("financial_position", {}),
                market_conditions=state_dict.get("market_conditions", {}),
                agent_state=state_dict.get("agent_state", {}),
            )

        # Convert products to Product objects
        products = []
        for product_dict in state_dict.get("products", []):
            try:
                product = Product(
                    asin=product_dict.get("asin", ""),
                    name=product_dict.get("name", ""),
                    price=product_dict.get("price", 0),
                    category=product_dict.get("category", ""),
                    brand=product_dict.get("brand", ""),
                )
                products.append(product)
            except Exception as e:
                logger.warning(f"Failed to convert product to Product object: {e}")

        return SimulationState(
            tick=state_dict.get("tick", 0),
            simulation_time=datetime.fromisoformat(
                state_dict.get("simulation_time", datetime.now().isoformat())
            ),
            products=products,
            recent_events=state_dict.get("recent_events", []),
            financial_position=state_dict.get("financial_position", {}),
            market_conditions=state_dict.get("market_conditions", {}),
            agent_state=state_dict.get("agent_state", {}),
        )

    def _collect_metrics(self) -> Dict[str, Any]:
        """
        Collect execution metrics.

        Returns:
            Dictionary of metrics
        """
        if not self.config.enable_monitoring:
            return {}

        metrics = {
            "total_executions": len(self._execution_history),
            "successful_executions": len(
                [r for r in self._execution_history if r.success]
            ),
            "failed_executions": len(
                [r for r in self._execution_history if not r.success]
            ),
            "average_execution_time": 0.0,
            "success_rate": 0.0,
        }

        if self._execution_history:
            successful_results = [r for r in self._execution_history if r.success]
            if successful_results:
                metrics["average_execution_time"] = sum(
                    r.execution_time for r in successful_results
                ) / len(successful_results)

            metrics["success_rate"] = (
                metrics["successful_executions"] / metrics["total_executions"]
            )

        return metrics

    def _start_trace(self, operation: str) -> None:
        """
        Start tracing an operation.

        Args:
            operation: Operation name
        """
        if not self.config.enable_tracing:
            return

        self._current_trace = {
            "operation": operation,
            "start_time": datetime.now().isoformat(),
            "agent_id": self.config.agent_id,
            "framework": self.config.framework,
            "steps": [],
        }

    def _end_trace(self, status: str, error: Optional[str] = None) -> None:
        """
        End tracing an operation.

        Args:
            status: Operation status
            error: Error message if any
        """
        if not self.config.enable_tracing or not self._current_trace:
            return

        self._current_trace["end_time"] = datetime.now().isoformat()
        self._current_trace["status"] = status
        if error:
            self._current_trace["error"] = error

        # Publish trace event
        asyncio.create_task(
            self.integration_manager.publish_event("agent_trace", self._current_trace)
        )

    def get_execution_history(self) -> List[AgentExecutionResult]:
        """
        Get execution history.

        Returns:
            List of execution results
        """
        return self._execution_history.copy()

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get agent metrics.

        Returns:
            Dictionary of metrics
        """
        return self._collect_metrics()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the agent adapter.

        Returns:
            Health check result
        """
        health = {
            "agent_id": self.config.agent_id,
            "framework": self.config.framework,
            "initialized": self._initialized,
            "healthy": False,
            "issues": [],
            "metrics": {},
        }

        if not self._initialized:
            health["issues"].append("Agent adapter not initialized")  # type: ignore[attr-defined]
            return health

        try:
            # Check agent runner health
            if self.agent_runner:
                agent_health = await self.agent_runner.health_check()
                health["agent_health"] = agent_health
                health["healthy"] = agent_health.get("status") == "healthy"
            else:
                health["issues"].append("Agent runner not available")  # type: ignore[attr-defined]

            # Collect metrics
            health["metrics"] = self.get_metrics()

            # Check execution history for issues
            if self._execution_history:
                recent_failures = len(
                    [r for r in self._execution_history[-10:] if not r.success]
                )

                if recent_failures > 5:
                    health["healthy"] = False
                    health["issues"].append(  # type: ignore[attr-defined]
                        f"High failure rate: {recent_failures}/10 recent executions failed"
                    )

        except Exception as e:
            health["healthy"] = False
            health["issues"].append(f"Health check failed: {e!s}")  # type: ignore[attr-defined]

        return health

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            if self.agent_runner and self._initialized:
                await self.agent_runner.cleanup()

            self._initialized = False
            logger.info(f"Cleaned up AgentAdapter for {self.config.agent_id}")

        except Exception as e:
            logger.error(
                f"Failed to cleanup AgentAdapter for {self.config.agent_id}: {e}"
            )


class AgentAdapterFactory:
    """Factory for creating agent adapters."""

    @staticmethod
    def create_adapter(
        framework: str,
        agent_id: str,
        config: Dict[str, Any],
        integration_manager: IntegrationManager,
        **kwargs,
    ) -> AgentAdapter:
        """
        Create an agent adapter.

        Args:
            framework: Framework name
            agent_id: Agent ID
            config: Agent configuration
            integration_manager: Integration manager
            **kwargs: Additional configuration

        Returns:
            AgentAdapter instance
        """
        adapter_config = AgentAdapterConfig(
            framework=framework, agent_id=agent_id, config=config, **kwargs
        )

        return AgentAdapter(adapter_config, integration_manager)

    @staticmethod
    async def create_and_initialize_adapter(
        framework: str,
        agent_id: str,
        config: Dict[str, Any],
        integration_manager: IntegrationManager,
        **kwargs,
    ) -> Optional[AgentAdapter]:
        """
        Create and initialize an agent adapter.

        Args:
            framework: Framework name
            agent_id: Agent ID
            config: Agent configuration
            integration_manager: Integration manager
            **kwargs: Additional configuration

        Returns:
            AgentAdapter instance or None if initialization failed
        """
        adapter = AgentAdapterFactory.create_adapter(
            framework, agent_id, config, integration_manager, **kwargs
        )

        if await adapter.initialize():
            return adapter
        else:
            await adapter.cleanup()
            return None
