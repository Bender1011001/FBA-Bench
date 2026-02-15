from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fba_bench.core.types import (
    AgentObservation,
    SimulationState,
    TickEvent,
    ToolCall,
)
from money import Money

from agents.multi_domain_controller import MultiDomainController
from agents.skill_coordinator import SkillCoordinator
from agents.skill_modules.base_skill import SkillAction, SkillOutcome
from agents.skill_modules.product_sourcing import ProductSourcingSkill
from fba_events.base import BaseEvent
from fba_events.pricing import SetPriceCommand
from fba_events.supplier import PlaceOrderCommand
from fba_events.agent import AgentDecisionEvent

# Import AgentRegistration, AgentRunnerDecisionError, AgentRunnerCleanupError from base_runner
from .base_runner import (
    AgentRunner,
    AgentRunnerCleanupError,
    AgentRunnerDecisionError,
    AgentRunnerError,
    AgentRunnerInitializationError,
    AgentRunnerStatus,
    AgentRunnerTimeoutError,
)

# Refactored: Moved AgentRegistration, BackCompatRegistration, and AgentRegistry to .agent_registry
from .agent_registry import (
    AgentRegistration,
    AgentRegistry,
    BackCompatRegistration,
)


if TYPE_CHECKING:
    # Type-only imports to avoid circular dependencies at runtime
    from services.world_store import WorldStore

    from benchmarking.agents.unified_agent import (
        AgentContext,
        PydanticAgentConfig,
        UnifiedAgentRunner,
    )
    from constraints.agent_gateway import AgentGateway
    from constraints.budget_enforcer import BudgetEnforcer
    from fba_bench_core.event_bus import EventBus
    from metrics.trust_metrics import TrustMetrics


logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages the lifecycle and interaction of multiple agent runners.

    The AgentManager is responsible for:
    - Registering different agent instances, potentially using different frameworks.
    - Orchestrating decision-making cycles for all active agents.
    - Passing canonical simulation state to agents.
    - Collecting and validating tool calls (actions) from agents.
    - Publishing agent-related events (e.g., AgentDecisionEvent).
    - Handling agent-specific constraints (e.g., budget enforcement via AgentGateway).
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,  # Use forward reference
        world_store: Optional[WorldStore] = None,  # Use forward reference
        budget_enforcer: Optional[BudgetEnforcer] = None,  # Use forward reference
        trust_metrics: Optional[TrustMetrics] = None,  # Use forward reference
        agent_gateway: Optional[AgentGateway] = None,  # Use forward reference
        bot_config_dir: str = "baseline_bots/configs",
        openrouter_api_key: Optional[str] = None,
        use_unified_agents: bool = False,  # Back-compat: optional flag accepted by tests
    ) -> None:
        # Lazy import to avoid import-time cycles
        if event_bus is None:
            from event_bus import get_event_bus as _get_event_bus

            resolved_bus = _get_event_bus()
        else:
            resolved_bus = event_bus
            # If a DI provider (dependency_injector) was injected, resolve it to the concrete instance
            try:
                from dependency_injector.providers import Provider as _DIProvider  # type: ignore
            except Exception:
                _DIProvider = tuple()  # type: ignore
            try:
                if "_DIProvider" in locals() and isinstance(resolved_bus, _DIProvider):  # type: ignore[arg-type]
                    resolved_bus = resolved_bus()
                elif callable(resolved_bus) and not hasattr(resolved_bus, "subscribe"):
                    # Fallback: provider-like callable that isn't yet an EventBus instance
                    resolved_bus = resolved_bus()
            except (AttributeError, TypeError, ImportError, RuntimeError):
                # Leave unresolved; subsequent usage will surface misconfiguration
                pass
        self.event_bus = resolved_bus
        self.world_store = world_store
        self.budget_enforcer = budget_enforcer
        self.trust_metrics = trust_metrics
        self.agent_gateway = agent_gateway
        self.bot_config_dir = bot_config_dir
        self.openrouter_api_key = openrouter_api_key

        self.agent_registry: AgentRegistry = (
            AgentRegistry()
        )  # agent_id -> AgentRegistration
        self.last_global_state: Optional[SimulationState] = (
            None  # Last state provided to agents
        )
        # CEO-level controller per agent for action arbitration across skills/tools
        self.multi_domain_controllers: Dict[str, MultiDomainController] = {}

        # Back-compat simple registry for tests expecting manager.agents with counters
        # Shape: { agent_id: { "runner": AgentRunner, "active": bool, "created_at": datetime, "total_decisions": int, "total_tool_calls": int } }
        self.agents: Dict[str, Dict[str, Any]] = {}

        # Simple manager stats expected by tests
        self.stats: Dict[str, Any] = {
            "total_agents": 0,
            "active_agents": 0,
        }

        # Unified agent system components (lazy import to avoid circulars)
        self.use_unified_agents = bool(use_unified_agents)
        self.unified_agent_factory = None
        self.unified_agent_runners: Dict[str, Any] = {}
        if self.use_unified_agents:
            try:
                from benchmarking.agents.unified_agent import (
                    AgentFactory,
                )  # runtime import

                self.unified_agent_factory = AgentFactory()
                logger.info("AgentManager initialized with unified agent system.")
            except (ImportError, AttributeError, TypeError):
                # Do not fail initialization if unified agent system is unavailable
                logger.warning("Unified agent system components unavailable.")
                self.unified_agent_factory = None

        # Keep track of subscription handles so we can unsubscribe correctly
        self._subscription_handles: List[Any] = []

        # Statistics
        self.decision_cycles_completed = 0
        self.total_tool_calls = 0
        self.total_decisions_skipped = 0
        self.total_errors = 0

        # Policy: how many consecutive decision timeouts before agent is considered unresponsive
        self.timeout_unresponsive_threshold: int = int(
            os.getenv("AGENT_TIMEOUT_THRESHOLD", "3") or "3"
        )

        # ---------------------------------------------------------------------
        # Tick-aware event buffering + decision history
        # ---------------------------------------------------------------------
        # These buffers let us provide "yesterday's events" to agents even when
        # EventBus recording is disabled (default), and power per-day memory consolidation.
        self._current_tick: int = 0
        self._current_simulation_time: Optional[datetime] = None
        self._events_by_tick: Dict[int, List[Dict[str, Any]]] = {}
        self._tool_calls_by_tick: Dict[int, Dict[str, List[ToolCall]]] = {}

        # Keep bounded history to avoid unbounded growth in long runs.
        self._keep_event_history_ticks: int = int(
            os.getenv("AGENT_EVENT_HISTORY_TICKS", "3") or "3"
        )
        self._max_events_per_tick: int = int(
            os.getenv("AGENT_EVENTS_PER_TICK_MAX", "250") or "250"
        )

        # Track last tick consolidated (manager-level guard; runners may also guard internally).
        self._last_memory_consolidation_tick: int = -1

    # -------------------------------------------------------------------------
    # Back-compat lightweight AgentManager surface expected by tests
    # -------------------------------------------------------------------------
    def create_agent(self, agent_config: Any) -> str:
        """
        Create/register an agent based on a provided config object.
        Returns the agent_id.
        """
        # Resolve agent_id from config
        aid = (
            getattr(agent_config, "agent_id", None)
            or getattr(agent_config, "name", None)
            or str(uuid.uuid4())
        )
        framework = str(
            getattr(agent_config, "framework", getattr(agent_config, "type", "diy"))
        )

        # Minimal runner stub (tests patch decision execution separately)
        class _StubRunner:
            def __init__(self, cfg):
                self.config = cfg

        runner = _StubRunner(agent_config)

        # Register in primary registry and back-compat dict
        reg = self.agent_registry.add_agent(
            str(aid),
            runner,
            framework,
            config=getattr(agent_config, "model_dump", dict)(),
        )
        # Mark as LLM-only if framework is LangChain or CrewAI
        if framework.lower() in ("langchain", "crewai"):
            reg.is_llm_only = True

        self.agents[str(aid)] = {
            "runner": runner,
            "active": True,
            "created_at": datetime.now(),
            "total_decisions": 0,
            "total_tool_calls": 0,
            "is_llm_only": reg.is_llm_only,
        }
        # CEO controller placeholder (optional; avoid strict dependency on controller impl)
        try:
            # Prefer not to import here to keep environment light; store a simple placeholder
            self.multi_domain_controllers[str(aid)] = {"agent_id": str(aid)}
        except (AttributeError, TypeError):
            self.multi_domain_controllers[str(aid)] = None
        # Stats
        self.stats["total_agents"] = self.agent_registry.agent_count()
        self.stats["active_agents"] = self.agent_registry.active_agent_count()
        return str(aid)

    def remove_agent(self, agent_id: str) -> bool:
        """
        Deregister/remove an agent from the manager.
        """
        # Remove from back-compat dict
        if agent_id in self.agents:
            try:
                del self.agents[agent_id]
            except KeyError:
                pass
        # Remove controller
        self.multi_domain_controllers.pop(agent_id, None)
        # Deregister primary registry
        ok = self.agent_registry.deregister(agent_id)
        self.stats["total_agents"] = self.agent_registry.agent_count()
        self.stats["active_agents"] = self.agent_registry.active_agent_count()
        return ok

    def decision_cycle(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a single decision cycle across all active agents.
        Tests patch `_execute_agent_decision` to control behavior.
        Returns a list of decision dicts (each includes 'agent_id').
        """
        decisions: List[Dict[str, Any]] = []
        for aid, reg in self.agent_registry.active_agents().items():
            try:
                result = self._execute_agent_decision(aid, context)
                if isinstance(result, dict):
                    result = dict(result)
                    result.setdefault("agent_id", aid)
                    decisions.append(result)
                    # Counters
                    self.agents.get(aid, {}).setdefault("total_decisions", 0)
                    self.agents[aid]["total_decisions"] = (
                        self.agents[aid]["total_decisions"] + 1
                    )
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.warning(f"Decision cycle error for agent {aid}: {e}")
                continue
        self.decision_cycles_completed += 1
        return decisions

    def _execute_agent_decision(
        self, agent_id: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Default decision execution path. Tests patch this method.
        """
        raise NotImplementedError(
            "Agent decision execution is not implemented in the stub manager."
        )

    async def start(self) -> None:
        """Start the AgentManager and its agents."""
        logger.info(
            f"AgentManager for {self.agent_registry.agent_count()} agents starting."
        )

        # Ensure the event bus is started (idempotent)
        if self.event_bus:
            await self.event_bus.start()

        # AgentManager needs to subscribe to relevant events for its operations
        if self.event_bus:
            # Example subscriptions - agent manager might listen to ticks to trigger decisions
            h1 = await self.event_bus.subscribe(
                TickEvent, self._handle_tick_event_for_decision_cycle
            )
            h2 = await self.event_bus.subscribe(
                SetPriceCommand, self._handle_agent_command_acknowledgement
            )  # Monitor agent actions

            # Subscribe skills pipeline to ticks: ensure skills register, dispatch, arbitrate, and execute
            h3 = await self.event_bus.subscribe(
                TickEvent, self._handle_tick_event_for_skills
            )
            # Subscribe to all canonical events so we can build tick-scoped summaries for agents/memory.
            h4 = await self.event_bus.subscribe(
                BaseEvent, self._handle_any_event_for_buffer
            )
            # Record handles for clean unsubscription later
            self._subscription_handles.extend([h1, h2, h3, h4])
            logger.info(
                "AgentManager subscribed to core events (decision cycle, command ack, skills pipeline)."
            )

        # Perform setup for each agent runner
        for agent_id, agent_reg in self.agent_registry.all_agents().items():
            try:
                # Ensure runner exists before initializing
                if agent_reg.runner:
                    await agent_reg.runner.initialize(agent_reg.config)
            except AgentRunnerInitializationError as e:
                logger.error(f"Failed to initialize agent {agent_id}: {e}")
                self.agent_registry.mark_agent_as_failed(agent_id, str(e))
        logger.info(
            f"AgentManager started. {self.agent_registry.active_agent_count()} agents active."
        )

    async def stop(self) -> None:
        """Stop the AgentManager and its agents."""
        logger.info("AgentManager stopping.")

        # Attempt best-effort unsubscription; fall back gracefully if unsupported
        try:
            if self.event_bus:
                # Unsubscribe using stored handles returned by subscribe()
                unsubscribe = getattr(self.event_bus, "unsubscribe", None)
                if callable(unsubscribe):
                    for handle in self._subscription_handles:
                        try:
                            await self.event_bus.unsubscribe(handle)  # type: ignore[arg-type]
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                            RuntimeError,
                        ) as ue:
                            logger.debug(f"Issue unsubscribing handle {handle}: {ue}")
                    self._subscription_handles.clear()
                    logger.info("AgentManager unsubscribed from core events.")
                else:
                    logger.debug(
                        "EventBus does not support unsubscribe; proceeding without explicit unsubscription."
                    )
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.warning(f"Unsubscription encountered an issue: {e}")

        # Cleanup all agent runners
        for agent_id, agent_reg in self.agent_registry.all_agents().items():
            try:
                runner = getattr(agent_reg, "runner", None)
                if not runner:
                    continue

                # AgentRunner.cleanup() is synchronous; prefer async_cleanup() when available.
                async_cleanup = getattr(runner, "async_cleanup", None)
                if callable(async_cleanup):
                    await async_cleanup()
                    continue

                cleanup = getattr(runner, "cleanup", None)
                if callable(cleanup):
                    maybe = cleanup()
                    # Defensive: some legacy runners expose an async cleanup.
                    if asyncio.iscoroutine(maybe):
                        await maybe
            except AgentRunnerCleanupError as e:
                logger.warning(f"Failed to cleanup agent {agent_id}: {e}")

        logger.info("AgentManager stopped.")

    # ---------------------------
    # Back-compat helper methods
    # ---------------------------
    async def initialize(self) -> None:
        """Back-compat alias for start()."""
        await self.start()

    async def cleanup(self) -> None:
        """Back-compat alias for stop()."""
        await self.stop()

    def get_registered_agents(self) -> Dict[str, Any]:
        """Back-compat helper expected by some tests."""
        return self.agents.copy()

    def _is_active(self, rec: Any) -> bool:
        """
        Safely determine whether a registration mirror entry is active.
        Supports both dict-based mirrors and BackCompatRegistration dataclass entries.
        """
        try:
            if isinstance(rec, dict):
                return bool(rec.get("active", False))
            return bool(getattr(rec, "active", False))
        except (AttributeError, TypeError):
            return False

    async def _process_agent_decision(
        self, registration: Any, simulation_state: SimulationState
    ) -> None:
        """
        Back-compat helper expected by tests.
        Runs a single decision cycle for the provided registration-like object and updates counters.
        """
        try:
            # registration may be the dict from self.agents or an AgentRegistration
            if isinstance(registration, dict):
                runner = registration.get("runner")
                aid = next(
                    (k for k, v in self.agents.items() if v is registration), None
                )
            else:
                runner = getattr(registration, "runner", None)
                aid = getattr(registration, "agent_id", None)

            if not runner:
                return

            tool_calls = await runner.decide(simulation_state)  # type: ignore[arg-type]
            # Update counters in self.agents mirror if present
            if aid and aid in self.agents:
                mirror = self.agents[aid]
                if isinstance(mirror, dict):
                    mirror["total_decisions"] = (
                        int(mirror.get("total_decisions", 0)) + 1
                    )
                    mirror["total_tool_calls"] = int(
                        mirror.get("total_tool_calls", 0)
                    ) + (len(tool_calls) if tool_calls else 0)
                else:
                    # BackCompatRegistration
                    mirror.total_decisions = (
                        int(getattr(mirror, "total_decisions", 0)) + 1
                    )
                    mirror.total_tool_calls = int(
                        getattr(mirror, "total_tool_calls", 0)
                    ) + (len(tool_calls) if tool_calls else 0)
        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            AgentRunnerDecisionError,
        ) as e:
            logger.error(f"_process_agent_decision error: {e}", exc_info=True)

    async def register_agent(
        self, agent_id: str, framework: str, config: Dict[str, Any]
    ) -> Any:
        """
        Registers a new agent runner with the manager.
        Returns the created runner for backward-compatibility with tests.
        """
        # Prevent duplicate registration
        existing = self.agent_registry.get_agent(agent_id)
        if existing is not None and existing.runner is not None:
            logger.warning(f"Agent {agent_id} already registered. Skipping.")
            return existing.runner

        runner = None
        try:
            # 1. Try modern registry/factory path
            try:
                from .registry import create_runner as _create_runner

                runner = _create_runner(framework, config or {}, agent_id=agent_id)
                logger.info(f"Agent {agent_id} ({framework}) created via registry.")
            except (ImportError, AttributeError, ValueError, AgentRunnerError) as e:
                logger.debug(f"Primary registry path failed for '{framework}': {e}")

            # 2. Unified agent system fallback
            if not runner and self.use_unified_agents and self.unified_agent_factory:
                try:
                    pydantic_config = self._create_pydantic_config_from_dict(
                        agent_id, framework, config or {}
                    )
                    unified_agent = self.unified_agent_factory.create_agent(
                        agent_id, pydantic_config
                    )
                    from benchmarking.agents.unified_agent import UnifiedAgentRunner

                    unified_runner = UnifiedAgentRunner(unified_agent)
                    runner = UnifiedAgentRunnerWrapper(unified_runner, agent_id)
                    self.unified_agent_runners[agent_id] = unified_runner
                    logger.info(
                        f"Unified agent {agent_id} ({framework}) registered successfully."
                    )
                except Exception as e:
                    logger.warning(
                        f"Unified agent system fallback failed for {agent_id}: {e}"
                    )

            if runner:
                self._add_to_registries(agent_id, runner, framework, config)
                return runner

            raise RuntimeError(f"No suitable runner found for framework '{framework}'")

        except Exception as e:
            logger.error(f"Failed to register agent {agent_id} ({framework}): {e}")
            self._handle_registration_failure(agent_id, framework, config, e)
            return None

    def _add_to_registries(
        self,
        agent_id: str,
        runner: Any,
        framework: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal helper to update both the modern registry and back-compat mirror."""
        reg = self.agent_registry.add_agent(agent_id, runner, framework, config or {})

        # Mark as LLM-only if framework is LangChain or CrewAI
        is_llm_only = False
        if framework.lower() in ("langchain", "crewai"):
            reg.is_llm_only = True
            is_llm_only = True

        # Update back-compat mirror
        self.agents[agent_id] = BackCompatRegistration(
            agent_id=agent_id,
            runner=runner,
            active=True,
            created_at=datetime.now(),
            total_decisions=0,
            total_tool_calls=0,
            is_llm_only=is_llm_only,
        )
        self._update_stats()

    def _handle_registration_failure(
        self, agent_id: str, framework: str, config: Dict[str, Any], error: Exception
    ) -> None:
        """Handle registration failure by updating registries with failed state."""
        self.agent_registry.add_agent(agent_id, None, framework, config or {})
        self.agent_registry.mark_agent_as_failed(agent_id, str(error))

        # Mirror failure into back-compat map
        self.agents[agent_id] = {
            "runner": None,
            "active": False,
            "created_at": datetime.now(),
            "total_decisions": 0,
            "total_tool_calls": 0,
            "failure_reason": str(error),
        }
        self._update_stats()
        self.total_errors += 1

    def _update_stats(self) -> None:
        """Update manager stats dictionary."""
        self.stats["total_agents"] = self.agent_registry.agent_count()
        self.stats["active_agents"] = self.agent_registry.active_agent_count()

    def deregister_agent(self, agent_id: str) -> None:
        """Deregisters an agent from the manager and its registry."""
        if self.agent_registry.deregister(agent_id):
            if agent_id in self.unified_agent_runners:
                del self.unified_agent_runners[agent_id]
            if agent_id in self.agents:
                del self.agents[agent_id]
            self._update_stats()
            logger.info(f"Agent {agent_id} successfully deregistered.")
        else:
            logger.warning(
                f"Agent {agent_id} not found in registry, cannot deregister."
            )

    def get_agent_runner(self, agent_id: str) -> Optional[AgentRunner]:
        """Retrieve the AgentRunner instance for a registered agent."""
        reg = self.agent_registry.get_agent(agent_id)
        return reg.runner if reg else None

    async def run_decision_cycle(self) -> None:
        """Executes a decision-making cycle for all active agents using an optimized, shared state context."""
        active_regs = list(self.agent_registry.active_agents().values())
        if not active_regs:
            logger.debug("No active agents to run decision cycle.")
            self.total_decisions_skipped += 1
            return

        shared_context = self._build_shared_context()
        logger.debug(
            f"Running decision cycle for {len(active_regs)} agents at tick {shared_context['tick']}..."
        )

        # Create tasks for all active agents
        decision_tasks = [
            asyncio.create_task(self._get_agent_decision(reg.runner, shared_context))
            for reg in active_regs
            if reg.runner
        ]

        results = await asyncio.gather(*decision_tasks, return_exceptions=True)

        # Process results
        for reg, result in zip(active_regs, results):
            await self._process_decision_result(reg.agent_id, result, shared_context)

        self.decision_cycles_completed += 1
        logger.debug(f"Decision cycle completed for tick {shared_context['tick']}.")

    def _build_shared_context(self) -> Dict[str, Any]:
        """Build a shared context for agent decisions."""
        tick = int(self._current_tick or 0)
        # For decisions at tick T, provide a bounded set of events from tick T-1 ("yesterday").
        prev_tick = max(0, tick - 1)
        recent_events = list(self._events_by_tick.get(prev_tick, []))
        return {
            "tick": tick,
            "simulation_time": self._current_simulation_time or datetime.now(timezone.utc),
            "products": self._serialize_products_for_agents() if self.world_store else [],
            "recent_events": recent_events,
        }

    async def _process_decision_result(
        self, agent_id: str, result: Any, context: Dict[str, Any]
    ) -> None:
        """Handle the result of an agent decision (success or failure)."""
        if isinstance(result, Exception):
            self._handle_decision_error(agent_id, result)
            return

        # Emit AgentDecisionEvent for observability
        await self._publish_decision_event(agent_id, result, context)

        # Run arbitration and dispatch
        processed = await self._arbitrate_and_dispatch(agent_id, result)

        # Store raw tool calls for memory consolidation ("what did I do today?")
        try:
            tick = int(context.get("tick", 0))
            self._tool_calls_by_tick.setdefault(tick, {})[agent_id] = list(result or [])
        except Exception:
            pass

        # Update statistics in primary registry
        reg = self.agent_registry.get_agent(agent_id)
        if reg:
            reg.total_decisions += 1
            reg.total_tool_calls += processed

        # Sync with back-compat mirror
        self._sync_back_compat_mirror(agent_id, decisions_inc=1, tools_inc=processed)

        self.total_tool_calls += processed

    def _handle_decision_error(self, agent_id: str, error: Exception) -> None:
        """Handle errors during decision making."""
        if isinstance(error, AgentRunnerTimeoutError):
            logger.warning(f"Decision timeout from agent {agent_id}: {error}")
            self.agent_registry.mark_agent_timeout(
                agent_id, threshold=self.timeout_unresponsive_threshold
            )
        else:
            if isinstance(error, AgentRunnerDecisionError):
                logger.error(f"Decision error from agent {agent_id}: {error}")
            else:
                logger.error(
                    f"Unexpected error getting decision from agent {agent_id}: {error}",
                    exc_info=True,
                )
            self.agent_registry.mark_agent_as_failed(agent_id, str(error))
            self.total_errors += 1

        # Synchronize mirror
        self._sync_back_compat_mirror(agent_id, active=False, failure_reason=str(error))
        self._update_stats()

    def _sync_back_compat_mirror(
        self,
        agent_id: str,
        active: Optional[bool] = None,
        failure_reason: Optional[str] = None,
        decisions_inc: int = 0,
        tools_inc: int = 0,
    ) -> None:
        """Internal helper to synchronize the back-compat 'agents' mirror with registry state."""
        if agent_id not in self.agents:
            return

        mirror = self.agents[agent_id]
        if isinstance(mirror, dict):
            if active is not None:
                mirror["active"] = active
            if failure_reason is not None:
                mirror["failure_reason"] = failure_reason
            mirror["total_decisions"] = (
                int(mirror.get("total_decisions", 0)) + decisions_inc
            )
            mirror["total_tool_calls"] = (
                int(mirror.get("total_tool_calls", 0)) + tools_inc
            )
        else:
            # BackCompatRegistration dataclass
            if active is not None:
                mirror.active = active
            if hasattr(mirror, "failure_reason") and failure_reason is not None:
                mirror.failure_reason = failure_reason
            mirror.total_decisions += decisions_inc
            mirror.total_tool_calls += tools_inc

    async def _publish_decision_event(
        self, agent_id: str, tool_calls: List[ToolCall], context: Dict[str, Any]
    ) -> None:
        """Publish an AgentDecisionEvent for observability."""
        reasoning = " ".join([tc.reasoning for tc in tool_calls if tc.reasoning])
        if not reasoning:
            reasoning = "Agent performing routine analysis."

        usage_info = {}
        if self.budget_enforcer:
            try:
                usage_snapshot = self.budget_enforcer.get_usage_snapshot(agent_id)
                tick_usage = usage_snapshot.get("tick", {})
                usage_info = {
                    "prompt_tokens": tick_usage.get("tokens", 0),
                    "completion_tokens": 0,
                    "total_tokens": tick_usage.get("tokens", 0),
                    "total_cost_usd": tick_usage.get("cost_cents", 0) / 100.0,
                }
            except Exception as e:
                logger.warning(f"Failed to get usage for {agent_id}: {e}")

        decision_event = AgentDecisionEvent(
            event_id=f"decision_{agent_id}_{uuid.uuid4()}",
            timestamp=datetime.now(),
            agent_id=agent_id,
            turn=int(context.get("tick", 0)),
            simulation_time=context.get("simulation_time", datetime.now()),
            reasoning=reasoning,
            tool_calls=[
                {
                    "function": {
                        "name": tc.tool_name,
                        "arguments": (
                            json.dumps(tc.parameters)
                            if isinstance(tc.parameters, dict)
                            else str(tc.parameters)
                        ),
                    }
                }
                for tc in tool_calls
            ],
            llm_usage=usage_info,
            prompt_metadata={},
        )
        await self.event_bus.publish(decision_event)

    async def _get_agent_decision(
        self, runner: AgentRunner, context: Dict[str, Any]
    ) -> List[ToolCall]:
        """Get decision from a single agent runner using the shared context."""
        try:
            # Agents receive the shared context directly.
            # The SimulationState can be constructed within the runner if needed.
            state = SimulationState(**context)
            return await runner.decide(state)
        except AgentRunnerDecisionError as e:
            logger.error(f"Agent '{runner.agent_id}' decision failed: {e}")
            return []
        except AgentRunnerTimeoutError as e:
            # Surface timeout to caller so manager can apply specialized policy (mark unresponsive / retry)
            logger.warning(f"Agent '{runner.agent_id}' decision timed out: {e}")
            raise
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(
                f"Unexpected error during agent '{runner.agent_id}' decision: {e}",
                exc_info=True,
            )
            return []

    def _get_multi_domain_controller(self, agent_id: str) -> MultiDomainController:
        """
        Lazily create or fetch the MultiDomainController for an agent.
        """
        controller = self.multi_domain_controllers.get(agent_id)
        if controller is None:
            coordinator = SkillCoordinator(agent_id, self.event_bus, config={})
            controller = MultiDomainController(
                agent_id=agent_id, skill_coordinator=coordinator, config={}
            )
            self.multi_domain_controllers[agent_id] = controller
        return controller

    async def _handle_tick_event_for_skills(self, event: TickEvent) -> None:
        """
        Tick-driven skills pipeline:
        - Ensure core skills (e.g., ProductSourcing) are registered with the coordinator
        - Dispatch the event to the SkillCoordinator to generate actions
        - Run CEO-level arbitration via MultiDomainController
        - Execute approved actions by publishing canonical commands to the EventBus
        """
        try:
            # Iterate over active agents; create controller on demand
            for agent_id, reg in self.agent_registry.active_agents().items():
                # For LLM-only (verified) agents, we skip automated skill-based heuristics
                # to ensure 100% LLM autonomy in decision making for the leaderboard.
                if getattr(reg, "is_llm_only", False):
                    continue

                controller = self._get_multi_domain_controller(agent_id)
                await self._ensure_product_sourcing_skill_registered(
                    agent_id, controller
                )

                # Dispatch to skills via coordinator
                actions = await controller.skill_coordinator.dispatch_event(event)
                if not actions:
                    continue

                # CEO-level arbitration
                approved = await controller.arbitrate_actions(actions)
                if not approved:
                    continue

                # Execute approved actions (publish commands)
                await self._execute_skill_actions(agent_id, approved)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Skills tick pipeline failed: {e}", exc_info=True)

    async def _ensure_product_sourcing_skill_registered(
        self, agent_id: str, controller: MultiDomainController
    ) -> None:
        """
        Register ProductSourcingSkill with the SkillCoordinator once per agent.
        """
        try:
            coordinator = controller.skill_coordinator
            if "ProductSourcing" in coordinator.skill_subscriptions:
                return
            # Instantiate and register the skill to early TickEvent processing
            skill = ProductSourcingSkill(
                agent_id=agent_id, event_bus=self.event_bus, config={}
            )
            await coordinator.register_skill(
                skill,
                skill.get_supported_event_types(),
                priority_multiplier=1.0,
            )
            logger.info(f"Registered ProductSourcingSkill for agent {agent_id}")
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to register ProductSourcingSkill for agent {agent_id}: {e}",
                exc_info=True,
            )

    async def _execute_skill_actions(
        self, agent_id: str, actions: List[SkillAction]
    ) -> None:
        """
        Execute approved skill actions by translating them into canonical commands and publishing to the EventBus.
        Currently supports:
        - place_order -> fba_events.supplier.PlaceOrderCommand
        """
        for action in actions:
            try:
                if action.action_type == "place_order":
                    params = action.parameters or {}
                    supplier_id = params.get("supplier_id") or "S001"
                    asin = params.get("asin")
                    quantity = int(params.get("quantity", 0))
                    max_price_raw = params.get("max_price")
                    # Defensive Money parsing
                    if isinstance(max_price_raw, Money):
                        max_price = max_price_raw
                    else:
                        max_price = (
                            Money.from_dollars(str(max_price_raw))
                            if max_price_raw is not None
                            else Money(0)
                        )

                    po = PlaceOrderCommand(
                        event_id=f"po_{agent_id}_{uuid.uuid4()}",
                        timestamp=datetime.now(),
                        agent_id=agent_id,
                        supplier_id=supplier_id,
                        asin=asin,
                        quantity=quantity,
                        max_price=max_price,
                        reason=action.reasoning or "product_sourcing",
                    )
                    await self.event_bus.publish(po)
                    logger.info(
                        f"Published PlaceOrderCommand from ProductSourcingSkill for agent {agent_id}: asin={asin} qty={quantity}"
                    )

                # Extend here with other mappings, e.g., run_marketing_campaign -> Marketing command

            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(
                    f"Failed to execute skill action {action.action_type} for agent {agent_id}: {e}",
                    exc_info=True,
                )

    def _toolcall_to_skillaction(self, tool_call: ToolCall) -> SkillAction:
        """
        Adapt a ToolCall (from an agent runner) into a SkillAction for arbitration.
        """
        try:
            pr = getattr(tool_call, "priority", 0)
            priority = max(0.0, min(1.0, float(pr) / 100.0))
        except Exception:
            priority = 0.5
        reasoning = getattr(tool_call, "reasoning", "") or ""
        confidence = getattr(tool_call, "confidence", 0.5)
        return SkillAction(
            action_type=tool_call.tool_name,
            parameters=tool_call.parameters or {},
            confidence=float(confidence),
            reasoning=reasoning,
            priority=priority,
            resource_requirements={},
            expected_outcome={},
            skill_source="agent_runner",
        )

    def _skillaction_to_toolcall(self, action: SkillAction) -> ToolCall:
        """
        Convert an approved SkillAction back into a ToolCall for execution.
        """
        try:
            pr_int = int(round(max(0.0, min(1.0, float(action.priority))) * 100))
        except Exception:
            pr_int = 50
        return ToolCall(
            tool_name=action.action_type,
            parameters=action.parameters,
            confidence=float(action.confidence),
            reasoning=action.reasoning,
            priority=pr_int,
        )

    async def _arbitrate_and_dispatch(
        self, agent_id: str, tool_calls: List[ToolCall]
    ) -> int:
        """
        Convert tool calls to skill actions, run CEO-level arbitration, and dispatch approved actions.
        Returns the number of tool calls processed.
        """
        if not tool_calls:
            return 0
        try:
            # Unpack 'decision' tool calls from LLM runners if present.
            # This allows runners to return a single block of decisions which are then arbitrated individually.
            unpacked_calls: List[ToolCall] = []
            for tc in tool_calls:
                if (
                    tc.tool_name == "decision"
                    and isinstance(tc.parameters, dict)
                    and "decisions" in tc.parameters
                ):
                    # Unpack bulk decisions
                    decisions = tc.parameters["decisions"]
                    if isinstance(decisions, list):
                        for d in decisions:
                            if not isinstance(d, dict):
                                continue
                            # Map dict field names to known tool names
                            if "new_price" in d:
                                unpacked_calls.append(
                                    ToolCall(
                                        tool_name="set_price",
                                        parameters={
                                            "asin": d.get("asin"),
                                            "price": d.get("new_price"),
                                        },
                                        reasoning=d.get("reasoning", tc.reasoning),
                                        confidence=tc.confidence,
                                    )
                                )
                            elif "quantity" in d:
                                unpacked_calls.append(
                                    ToolCall(
                                        tool_name="place_order",
                                        parameters=d,
                                        reasoning=d.get("reasoning", tc.reasoning),
                                        confidence=tc.confidence,
                                    )
                                )
                    else:
                        unpacked_calls.append(tc)
                else:
                    unpacked_calls.append(tc)

            controller = self._get_multi_domain_controller(agent_id)
            skill_actions = [self._toolcall_to_skillaction(tc) for tc in unpacked_calls]
            approved_actions = await controller.arbitrate_actions(skill_actions)
            count = 0
            for action in approved_actions:
                tc = self._skillaction_to_toolcall(action)
                await self._process_tool_call(agent_id, tc)
                count += 1
            return count
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Error in arbitration for agent {agent_id}: {e}")
            return 0

    async def _process_tool_call(self, agent_id: str, tool_call: ToolCall) -> None:
        """Processes a tool call from an agent."""
        logger.info(
            f"Agent {agent_id} proposes ToolCall: {tool_call.tool_name} with {tool_call.parameters}"
        )

        # In a real system, this would involve routing to the actual tool implementation
        # We now implement explicit routing for core tools to enable full LLM autonomy.

        # 1. Budget and Safety Check via Gateway
        if self.agent_gateway:
            allowed = await self.agent_gateway.process_tool_call(
                agent_id, tool_call, self.world_store, self.event_bus
            )
            if not allowed:
                logger.warning(
                    f"Tool call '{tool_call.tool_name}' for agent {agent_id} was BLOCKED by AgentGateway."
                )
                return

        # 2. Command Dispatch
        params = tool_call.parameters or {}
        if tool_call.tool_name == "set_price":
            asin = params.get("asin")
            price_raw = params.get("price", params.get("new_price"))
            if asin and price_raw is not None:
                # Tool calls usually specify dollars. Canonical SetPriceCommand expects Money.
                try:
                    if isinstance(price_raw, Money):
                        new_price = price_raw
                    else:
                        s = str(price_raw).strip().replace("$", "").replace(",", "")
                        new_price = Money.from_dollars(s)
                except Exception:
                    new_price = Money.zero()

                if getattr(new_price, "cents", 0) > 0:
                    cmd = SetPriceCommand(
                        event_id=f"sp_{agent_id}_{uuid.uuid4().hex[:8]}",
                        timestamp=datetime.now(),
                        agent_id=agent_id,
                        asin=str(asin),
                        new_price=new_price,
                        reason=tool_call.reasoning,
                    )
                    await self.event_bus.publish(cmd)
                    logger.info(
                        f"Dispatched SetPriceCommand from LLM tool for {agent_id}: {asin} @ {new_price}"
                    )

        elif tool_call.tool_name == "place_order":
            supplier_id = (
                params.get("supplier_id") or "S001"
            )  # Default if not specified
            asin = params.get("asin")
            quantity = int(params.get("quantity", 0))
            max_price_raw = params.get("max_price", params.get("max_price_dollars"))

            if asin and quantity > 0:
                # Defensive Money parsing
                if isinstance(max_price_raw, Money):
                    max_price = max_price_raw
                else:
                    try:
                        s = str(max_price_raw).strip().replace("$", "").replace(",", "")
                        max_price = (
                            Money.from_dollars(s)
                            if max_price_raw is not None
                            else Money.zero()
                        )
                    except Exception:
                        max_price = Money.zero()

                po = PlaceOrderCommand(
                    event_id=f"po_{agent_id}_{uuid.uuid4().hex[:8]}",
                    timestamp=datetime.now(),
                    agent_id=agent_id,
                    supplier_id=supplier_id,
                    asin=asin,
                    quantity=quantity,
                    max_price=max_price,
                    reason=tool_call.reasoning or "LLM-driven sourcing",
                )
                await self.event_bus.publish(po)
                logger.info(
                    f"Dispatched PlaceOrderCommand from LLM tool for {agent_id}: {asin} Qty={quantity}"
                )

        else:
            logger.warning(f"No explicit handler for tool call: {tool_call.tool_name}")

    # -------------------------------------------------------------------------
    # Tick-aware event buffering + memory consolidation support
    # -------------------------------------------------------------------------
    def _serialize_products_for_agents(self) -> List[Dict[str, Any]]:
        """
        Convert WorldStore ProductState objects into plain dicts suitable for LLM prompts.

        We intentionally return dicts (not dataclass objects) to keep runner inputs
        stable across frameworks and avoid Pydantic validation issues.
        """
        if not self.world_store:
            return []
        try:
            states = list(self.world_store.get_all_product_states().values())
        except Exception:
            return []

        out: List[Dict[str, Any]] = []
        for st in states:
            if isinstance(st, dict):
                out.append(dict(st))
                continue
            to_dict = getattr(st, "to_dict", None)
            if callable(to_dict):
                try:
                    d = to_dict()
                    if isinstance(d, dict):
                        out.append(d)
                        continue
                except Exception:
                    pass
            # Best-effort fallback
            try:
                out.append(dict(vars(st)))
            except Exception:
                out.append({"repr": repr(st)})
        return out

    def _summarize_event_for_agents(self, event: Any) -> Dict[str, Any]:
        """
        Best-effort event summary for UI/debugging and LLM prompting.

        Stable schema (similar to EventBus recording):
          {"event_type": str, "timestamp": str, "tick": int, "data": dict}
        """
        event_type = getattr(event, "__class__", type(event)).__name__
        ts_obj = getattr(event, "timestamp", None)
        try:
            ts = ts_obj.isoformat() if hasattr(ts_obj, "isoformat") else None
        except Exception:
            ts = None
        if not ts:
            ts = datetime.now(timezone.utc).isoformat()

        # Prefer explicit to_summary_dict()
        data: Dict[str, Any] = {}
        try:
            to_sum = getattr(event, "to_summary_dict", None)
            if callable(to_sum):
                payload = to_sum()
                if isinstance(payload, dict):
                    data = payload
        except Exception:
            data = {}
        if not data:
            try:
                raw = vars(event)
                data = raw if isinstance(raw, dict) else {"repr": repr(event)}
            except Exception:
                data = {"repr": repr(event)}

        # Normalize to JSON-friendly primitives (avoid leaking Money/datetime objects)
        def _jsonable(v: Any) -> Any:
            if v is None or isinstance(v, (bool, int, float, str)):
                return v
            if hasattr(v, "isoformat"):
                try:
                    return v.isoformat()
                except Exception:
                    pass
            try:
                return str(v)
            except Exception:
                return repr(v)

        safe_data: Dict[str, Any] = {}
        for k, v in (data or {}).items():
            try:
                if isinstance(v, dict):
                    safe_data[str(k)] = {
                        str(kk): _jsonable(vv) for kk, vv in v.items()
                    }
                elif isinstance(v, list):
                    safe_data[str(k)] = [_jsonable(i) for i in v]
                else:
                    safe_data[str(k)] = _jsonable(v)
            except Exception:
                safe_data[str(k)] = _jsonable(v)

        tick = self._current_tick
        try:
            if hasattr(event, "tick_number") and isinstance(
                getattr(event, "tick_number"), int
            ):
                tick = int(getattr(event, "tick_number"))
        except Exception:
            tick = self._current_tick

        return {
            "event_type": event_type,
            "timestamp": ts,
            "tick": int(tick),
            "data": safe_data,
        }

    async def _handle_any_event_for_buffer(self, event: BaseEvent) -> None:
        """
        Capture all simulation events into a bounded per-tick buffer.

        This provides stable, tick-scoped "recent_events" even when EventBus recording
        is disabled (default), and enables end-of-day memory consolidation.
        """
        try:
            summary = self._summarize_event_for_agents(event)
            tick = int(summary.get("tick", self._current_tick))
            buf = self._events_by_tick.setdefault(tick, [])
            # Enforce per-tick cap (drop oldest)
            if len(buf) >= self._max_events_per_tick:
                del buf[0 : max(1, len(buf) - self._max_events_per_tick + 1)]
            buf.append(summary)
        except Exception:
            # Never let buffering impact the simulation loop
            return None

    def _trim_event_history(self) -> None:
        """Drop tick buffers older than the configured retention window."""
        try:
            keep_from = max(
                0, int(self._current_tick) - int(self._keep_event_history_ticks)
            )
        except Exception:
            keep_from = 0
        to_delete = [t for t in list(self._events_by_tick.keys()) if int(t) < keep_from]
        for t in to_delete:
            self._events_by_tick.pop(t, None)
            self._tool_calls_by_tick.pop(t, None)

    async def _maybe_consolidate_memory_for_previous_tick(self) -> None:
        """
        Trigger per-agent memory consolidation for the previous simulation day.

        We run consolidation at the start of tick T for tick T-1 to give the
        event loop time to process and buffer all events from the previous day.
        """
        prev_tick = int(self._current_tick) - 1
        if prev_tick < 0:
            return
        if prev_tick <= self._last_memory_consolidation_tick:
            return

        # Trim history before consolidation to keep memory bounded.
        self._trim_event_history()

        events = list(self._events_by_tick.get(prev_tick, []))
        if not events:
            self._last_memory_consolidation_tick = prev_tick
            return

        active_regs = list(self.agent_registry.active_agents().values())
        if not active_regs:
            self._last_memory_consolidation_tick = prev_tick
            return

        async def _consolidate_one(reg: Any) -> None:
            runner = getattr(reg, "runner", None)
            if not runner:
                return
            try:
                agent_tool_calls = list(
                    self._tool_calls_by_tick.get(prev_tick, {}).get(reg.agent_id, [])
                )
                ctx = {
                    "tick": prev_tick,
                    "simulation_time": self._current_simulation_time,
                    "products": self._serialize_products_for_agents(),
                    "recent_events": events,
                    "agent_tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "parameters": tc.parameters,
                            "reasoning": tc.reasoning,
                            "confidence": tc.confidence,
                            "priority": getattr(tc, "priority", 0),
                        }
                        for tc in agent_tool_calls
                    ],
                }
                await runner.consolidate_memory(ctx)
            except Exception as e:
                logger.debug(f"Memory consolidation failed for {reg.agent_id}: {e}")

        await asyncio.gather(
            *(_consolidate_one(r) for r in active_regs), return_exceptions=True
        )
        self._last_memory_consolidation_tick = prev_tick

    def _create_pydantic_config_from_dict(
        self, agent_id: str, framework: str, config: Dict[str, Any]
    ) -> PydanticAgentConfig:
        """Create a PydanticAgentConfig instance from a raw dictionary and inject core services for DIY/LLM bots.

        Adds defensive validation to avoid silently propagating malformed configs.
        """
        cfg = config or {}
        if not isinstance(cfg, dict):
            raise ValueError(
                f"Agent '{agent_id}' provided non-dict configuration: {type(cfg).__name__}"
            )

        # Normalize llm_config
        llm_config_dict = cfg.get("llm_config") or {}
        if not isinstance(llm_config_dict, dict):
            logger.warning(f"Agent '{agent_id}' llm_config is not a dict; ignoring.")
            llm_config_dict = {}
        llm_config = {
            "model": llm_config_dict.get("model", "gpt-3.5-turbo"),
            "temperature": llm_config_dict.get("temperature", 0.1),
            "max_tokens": llm_config_dict.get("max_tokens", 1000),
            "api_key": llm_config_dict.get("api_key", self.openrouter_api_key),
            "base_url": llm_config_dict.get("base_url"),
            "timeout": llm_config_dict.get("timeout", 60),
            "top_p": llm_config_dict.get("top_p", 1.0),
        }

        # Extract general parameters
        agent_params = cfg.get("parameters") or {}
        if not isinstance(agent_params, dict):
            logger.warning(
                f"Agent '{agent_id}' parameters is not a dict; defaulting to empty."
            )
            agent_params = {}

        # Minimal schema hints for DIY agent
        if (framework or "").lower() == "diy":
            agent_params.setdefault(
                "agent_type", agent_params.get("agent_type", "advanced")
            )
            agent_params.setdefault(
                "target_asin", agent_params.get("target_asin", "B0DEFAULT")
            )

        custom_config = (cfg.get("custom_config", {}) or {}).copy()
        if not isinstance(custom_config, dict):
            logger.warning(
                f"Agent '{agent_id}' custom_config is not a dict; defaulting to empty."
            )
            custom_config = {}

        # Inject core services to enable unified factory to build DIY/LLM baseline bots
        custom_config.setdefault("_services", {})
        custom_config["_services"].update(
            {
                "world_store": self.world_store,
                "budget_enforcer": self.budget_enforcer,
                "trust_metrics": self.trust_metrics,
                "agent_gateway": self.agent_gateway,
                "event_bus": self.event_bus,
                "openrouter_api_key": self.openrouter_api_key,
            }
        )

        # Import at runtime to ensure availability when TYPE_CHECKING is False
        try:
            from benchmarking.agents.unified_agent import PydanticAgentConfig  # type: ignore
        except (ImportError, AttributeError, TypeError) as e:
            raise RuntimeError(f"PydanticAgentConfig unavailable: {e}") from e
        return PydanticAgentConfig(
            agent_id=agent_id,
            framework=framework,
            llm_config=llm_config,
            parameters=agent_params,
            custom_config=custom_config,
        )

    async def _handle_tick_event_for_decision_cycle(self, event: TickEvent) -> None:
        """Handle TickEvent to trigger agent decision cycles."""
        logger.debug(
            f"AgentManager received TickEvent for tick {event.tick_number}. Triggering decision cycle."
        )
        # Update tick context (used by _build_shared_context and event buffering)
        try:
            self._current_tick = int(getattr(event, "tick_number", 0))
        except Exception:
            self._current_tick = 0
        self._current_simulation_time = getattr(event, "simulation_time", None) or None

        # Consolidate memory for the previous day (tick-1) before agents act today.
        await self._maybe_consolidate_memory_for_previous_tick()

        await self.run_decision_cycle()

    async def _handle_agent_command_acknowledgement(
        self, event: SetPriceCommand
    ) -> None:
        """Handle agent commands being acknowledged or processed by WorldStore."""
        logger.debug(
            f"Agent manager received acknowledgement for command: {event.event_id} from agent {event.agent_id}"
        )
        # In a real system, this might update internal agent state on command status

    async def health_check(self) -> Dict[str, Any]:
        """
        Returns a health check payload for the AgentManager, including counts of
        registered agents and their states, and a timestamp.
        """
        logger.debug("AgentManager: Performing health check.")
        total_agents = self.agent_registry.agent_count()
        active_agents = self.agent_registry.active_agent_count()

        failed_count = 0
        running_count = 0
        # Iterate over all registered agents to determine their states (best effort)
        for agent_id, agent_reg in self.agent_registry.all_agents().items():
            if not agent_reg.is_active:
                failed_count += 1
            # Check runner status if available for more granular 'running' state
            if (
                agent_reg.runner
                and getattr(agent_reg.runner, "status", None)
                == AgentRunnerStatus.RUNNING
            ):
                running_count += 1
            # If agent_reg.is_active is true, and runner is not explicitly failed, consider it active
            elif agent_reg.is_active and (
                not agent_reg.runner
                or getattr(agent_reg.runner, "status", None) != AgentRunnerStatus.FAILED
            ):
                # This could be more refined, but for basic health, active is 'not failed'.
                pass

        stats = {
            "status": "operational" if total_agents == active_agents else "degraded",
            "timestamp_utc": datetime.now(timezone.utc).isoformat() + "Z",
            "total_registered_agents": total_agents,
            "active_agents": active_agents,
            "failed_agents": failed_count,
            "running_agents_experimental": running_count,
            "decision_cycles_completed": self.decision_cycles_completed,
            "total_errors_encountered": self.total_errors,
        }
        # Build agent status map for tests
        agent_map = {}
        for agent_id, agent_reg in self.agent_registry.all_agents().items():
            agent_map[agent_id] = {
                "active": agent_reg.is_active,
                "status": (
                    getattr(agent_reg.runner, "status", "unknown")
                    if agent_reg.runner
                    else "failed"
                ),
                "total_decisions": agent_reg.total_decisions,
            }

        return {**stats, "agents": agent_map, "manager_stats": stats}

    async def get_agent_info(self, agent_id: str) -> Dict[str, Any]:
        """
        Returns basic information for a specific agent.
        Raises KeyError if the agent is not found.
        """
        logger.debug(f"AgentManager: Retrieving info for agent_id: {agent_id}")
        agent_reg = self.agent_registry.get_agent(agent_id)

        if not agent_reg:
            raise KeyError(f"Agent with ID '{agent_id}' not found.")

        # Normalize runner status value safely (supports enums, strings, other types)
        if agent_reg.runner:
            _status_attr = getattr(agent_reg.runner, "status", None)
            if hasattr(_status_attr, "value"):
                _runner_status_value = _status_attr.value
            elif isinstance(_status_attr, (str, int)):
                _runner_status_value = _status_attr
            elif _status_attr is None:
                _runner_status_value = "N/A"
            else:
                _runner_status_value = str(_status_attr)
        else:
            _runner_status_value = "N/A"

        agent_info = {
            "agent_id": agent_reg.agent_id,
            "status": "active" if agent_reg.is_active else "failed",
            "framework": agent_reg.framework,
            "created_at_utc": agent_reg.created_at.isoformat() + "Z",
            "last_update_utc": datetime.now(timezone.utc).isoformat()
            + "Z",  # Best effort last update
            "runner_type": (
                getattr(agent_reg.runner, "__class__", None).__name__
                if agent_reg.runner
                else None
            ),
            "runner_status": _runner_status_value,
            "config_summary": {
                "strategy": agent_reg.config.get("strategy"),
                "limits": agent_reg.config.get("limits"),
                "model": agent_reg.config.get("llm_config", {}).get("model"),
            },
            "failure_reason": getattr(agent_reg, "failure_reason", None),
        }
        return agent_info


class UnifiedAgentRunnerWrapper(AgentRunner):
    """
    Wrapper class that adapts the UnifiedAgentRunner to the AgentRunner interface.
    This allows the unified agent system to work with the existing AgentManager.
    """

    def __init__(self, unified_runner: UnifiedAgentRunner, agent_id: str):
        """Initialize the wrapper."""
        super().__init__(agent_id)
        self.unified_runner = unified_runner
        self.agent_id = agent_id

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the unified agent runner."""
        try:
            await self.unified_runner.initialize()
            logger.info(f"Unified agent runner wrapper {self.agent_id} initialized")
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            raise AgentRunnerInitializationError(
                f"Failed to initialize unified agent runner {self.agent_id}: {e}"
            )

    async def decide(self, state: SimulationState) -> List[ToolCall]:
        """Get decision from the unified agent runner."""
        try:
            # Convert SimulationState to AgentContext
            agent_context = self._convert_to_agent_context(state)

            # Get actions from the unified agent
            actions = await self.unified_runner.decide(agent_context)

            # Convert AgentAction to ToolCall
            tool_calls = []
            for action in actions:
                tool_calls.append(
                    ToolCall(
                        tool_name=action.action_type,
                        parameters=action.parameters,
                        confidence=action.confidence,
                        reasoning=action.reasoning,
                    )
                )

            return tool_calls

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            AgentRunnerDecisionError,
            AgentRunnerTimeoutError,
        ) as e:
            raise AgentRunnerDecisionError(
                f"Failed to get decision from unified agent {self.agent_id}: {e}"
            )

    async def cleanup(self) -> None:
        """Cleanup the unified agent runner."""
        try:
            await self.unified_runner.cleanup()
            logger.info(f"Unified agent runner wrapper {self.agent_id} cleaned up")
        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
            AgentRunnerCleanupError,
        ) as e:
            raise AgentRunnerCleanupError(
                f"Failed to cleanup unified agent runner {self.agent_id}: {e}"
            )

    async def learn(self, outcome: SkillOutcome) -> None:
        """
        Forward learning signal to the underlying unified agent if supported.
        Falls back to no-op if the agent doesn't expose a learn method.
        """
        try:
            # Prefer a direct learn on unified runner
            target = getattr(self.unified_runner, "learn", None)
            if callable(target):
                await target(outcome)
                return
            # Fallback to underlying agent's learn
            agent_obj = getattr(self.unified_runner, "agent", None)
            if agent_obj is not None:
                agent_learn = getattr(agent_obj, "learn", None)
                if callable(agent_learn):
                    await agent_learn(outcome)
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.warning(
                f"Unified agent {self.agent_id} learn() forwarding failed: {e}"
            )

    def _convert_to_agent_context(self, state: SimulationState) -> AgentContext:
        """Convert a SimulationState to an AgentContext."""
        # Convert recent events to observations
        observations = []
        for event in state.recent_events:
            if isinstance(event, dict):
                observations.append(
                    AgentObservation(
                        observation_type="event", data=event, source="event_bus"
                    )
                )

        # Create the agent context
        return AgentContext(
            agent_id=self.agent_id,
            scenario_id=(
                (
                    state.agent_state.get("scenario_id")
                    if isinstance(state.agent_state, dict)
                    else None
                )
                or (
                    state.agent_state.get("scenario")
                    if isinstance(state.agent_state, dict)
                    else None
                )
                or "default"
            ),
            tick=state.tick,
            world_state={
                "products": state.products,
                "simulation_time": (
                    state.simulation_time.isoformat() if state.simulation_time else None
                ),
            },
            observations=observations,
            messages=[],  # No messages in the current SimulationState
            previous_actions=[],  # No previous actions in the current SimulationState
            metadata={"simulation_time": state.simulation_time},
        )
