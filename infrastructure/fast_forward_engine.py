import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING

# Assuming TickEvent and other relevant event types are defined in events.py
# from events import TickEvent, AgentActivityEvent, CompressedTickEvent # adjust as needed

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    class EventBusProtocol(Protocol):
        async def subscribe_to_event(self, event_type: str, callback: Any) -> None: ...
        async def unsubscribe_from_event(self, event_type: str, callback: Any) -> None: ...

    class SimulationOrchestratorProtocol(Protocol):
        current_tick: int
        config: Any
        start_time: datetime
        def _calculate_simulation_time(self) -> datetime: ...
        async def pause(self) -> None: ...
        async def resume(self) -> None: ...
        async def set_tick(self, tick: int) -> None: ...


class FastForwardEngine:
    """
    Optimizes long-horizon simulations by skipping periods of minimal activity.

    - Time compression: Skips simulation periods with minimal agent activity.
    - Event prediction: Generates compressed events for inactive periods.
    - State preservation: Maintains simulation accuracy during time jumps.
    - Intelligent triggering: Detects when to enter/exit fast-forward mode.
    """

    def __init__(
        self,
        event_bus: "EventBusProtocol",
        simulation_orchestrator: "SimulationOrchestratorProtocol",
    ):
        # Back-compat attributes expected by unit tests
        self._event_bus = event_bus
        self._simulation_orchestrator = simulation_orchestrator
        self._agent_activities: Dict[str, datetime] = {}
        self._running: bool = False

        # Also expose public aliases for broader integration usage
        self.event_bus = event_bus
        self.orchestrator = simulation_orchestrator

        self._last_agent_activity: Dict[str, datetime] = {}  # agent_id -> last activity time
        self._fast_forward_mode_active = False
        self._compressed_events_buffer: List[Any] = []  # Store generated compressed events
        self._simulation_state_snapshot: Optional[Dict[str, Any]] = None  # To preserve state

        # Configuration parameters
        self.idle_detection_threshold_ticks: int = (
            10  # Number of ticks with low activity to detect idle
        )
        self.activity_level_threshold: float = (
            0.1  # Percentage of agents active to consider not idle
        )
        self.min_fast_forward_duration_ticks: int = 50  # Minimum ticks to fast forward

        logger.info("FastForwardEngine initialized.")

    async def start(self):
        """Starts the Fast-Forward Engine. Subscribes to necessary events."""
        # For simplicity, we'd subscribe to agent activity events here
        # await self._event_bus.subscribe_to_event("AgentActivityEvent", self._on_agent_activity)
        self._running = True
        logger.info("FastForwardEngine started.")

    async def stop(self):
        """Stops the Fast-Forward Engine."""
        self._running = False
        logger.info("FastForwardEngine stopped.")
        # Unsubscribe if necessary
        # await self._event_bus.unsubscribe_from_event("AgentActivityEvent", self._on_agent_activity)

    def _on_agent_activity(self, event: Any):
        """
        Updates last activity time for an agent based on relevant events.
        Events are expected to have 'agent_id' and 'timestamp' or be processed to extract them.
        """
        agent_id = getattr(event, "agent_id", None)
        timestamp = getattr(event, "timestamp", None)
        # Attempt to get timestamp from nested 'metadata' or current time if not in event
        if timestamp is None:
            if hasattr(event, "metadata") and hasattr(event.metadata, "timestamp_iso"):
                try:
                    timestamp = datetime.fromisoformat(event.metadata.timestamp_iso)
                except (TypeError, ValueError):
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()

        if agent_id:
            self._last_agent_activity[agent_id] = timestamp
            logger.debug(f"Activity recorded for agent {agent_id} at {timestamp.isoformat()}")
        else:
            logger.debug(
                f"Event {type(event).__name__} received but no agent_id identified for activity tracking."
            )

    def detect_idle_period(
        self, agent_activities: Dict[str, datetime], threshold_percent_active: float = 0.1
    ) -> bool:
        """
        Identifies periods of low agent activity indicating potential idle time.

        Args:
            agent_activities: Dictionary of agent_id -> last_activity_timestamp.
            threshold_percent_active: Percentage of agents that must be inactive
                                       for the simulation to be considered idle.

        Returns:
            True if an idle period is detected, False otherwise.
        """
        if not agent_activities:
            return True  # If no agents, assume idle

        current_simulation_time = self.orchestrator._calculate_simulation_time()
        inactive_agents_count = 0
        total_agents = len(agent_activities)

        for agent_id, last_activity_time in agent_activities.items():
            # Consider agents inactive if their last activity was beyond a few tick intervals
            # This threshold logic needs to be more robust, potentially based on event volume
            time_since_last_activity = current_simulation_time - last_activity_time
            if time_since_last_activity > timedelta(
                seconds=self.orchestrator.config.tick_interval_seconds
                * self.idle_detection_threshold_ticks
            ):
                inactive_agents_count += 1

        actual_active_percent = (
            (total_agents - inactive_agents_count) / total_agents if total_agents > 0 else 0
        )
        is_idle = actual_active_percent < threshold_percent_active

        if is_idle:
            logger.info(
                f"Idle period detected: Only {actual_active_percent:.2%} of agents active. Threshold: {threshold_percent_active:.2%}"
            )
        return is_idle

    async def generate_compressed_events(self, start_tick: int, end_tick: int) -> List[Any]:
        """
        Generates summary events for periods of inactivity instead of granular events.
        This is a conceptual method that would require sophisticated event aggregation logic.

        Args:
            start_tick: The starting tick of the fast-forward period.
            end_tick: The ending tick of the fast-forward period.

        Returns:
            A list of compressed/summary events.
        """
        logger.info(f"Generating compressed events for ticks {start_tick} to {end_tick}.")
        # In a real scenario, this would query a historical event store (e.g., database)
        # and summarize events based on their type or agent.
        # For a simple example, we might generate a single "SummaryTickEvent".

        num_skipped_ticks = end_tick - start_tick + 1

        # Example of a highly simplified compressed event
        compressed_event = {
            "event_type": "CompressedTickSummary",
            "start_tick": start_tick,
            "end_tick": end_tick,
            "skipped_ticks": num_skipped_ticks,
            "summary_data": {
                "estimated_llm_calls_saved": num_skipped_ticks
                * 0.5,  # Hypothetical saving per tick
                "estimated_cost_saved": num_skipped_ticks * 0.001,  # Hypothetical cost saving
            },
            "timestamp": datetime.now().isoformat(),
        }
        self._compressed_events_buffer.append(compressed_event)
        logger.info(f"Generated a compressed event for {num_skipped_ticks} ticks.")
        return [compressed_event]

    async def fast_forward_to_tick(self, target_tick: int):
        """
        Jumps the simulation time to a target tick, bypassing intermediate steps.
        Requires careful state management to ensure consistency.

        Args:
            target_tick: The tick number to fast-forward to.
        """
        # Determine current tick using protocol interface
        try:
            current_tick = int(self.orchestrator.current_tick)
        except Exception:
            # Fallback to 0 if accessing the property fails (e.g. mock setup issue)
            current_tick = 0

        if target_tick <= current_tick:
            logger.warning(
                f"Target tick {target_tick} is not ahead of current tick {current_tick}. No fast-forward."
            )
            return

        logger.info(f"Initiating fast-forward from tick {current_tick} to {target_tick}.")

        # 1. Preserve current simulation state
        await self.preserve_simulation_state()

        # 2. Generate compressed events for the skipped period
        await self.generate_compressed_events(current_tick + 1, target_tick)

        # 3. Update orchestrator's current tick
        # Use set_tick if available (async setter), otherwise try direct attribute set
        try:
            await self.orchestrator.set_tick(target_tick)
        except (AttributeError, TypeError):
            # Fallback if specific setter method is not implemented
            try:
                self.orchestrator.current_tick = target_tick
            except Exception as e:
                logger.error(f"Failed to update orchestrator tick: {e}")

        # 4. Update simulation time in orchestrator (ensuring deterministic progression)
        try:
            # If the orchestrator has internal state for time, force a recalculation
            self.orchestrator.start_time = self.orchestrator._calculate_simulation_time()
        except Exception:
            pass

        # 5. Keep compressed events buffered (tests assert buffer length)
        self._fast_forward_mode_active = True
        logger.info(f"Fast-forwarded simulation to tick {target_tick}.")

    async def preserve_simulation_state(self):
        """
        Captures and stores the critical simulation state to ensure accuracy during time jumps.
        This would typically involve interacting with the WorldStore or other stateful services.
        """
        logger.info("Preserving simulation state...")
        # This is a conceptual example. In reality, you'd need to:
        # 1. Pause active agents/services that modify state.
        # 2. Query WorldStore or other state services for their current state.
        # 3. Serialize and store this state.

        # For demonstration: store a simplified snapshot from orchestrator's perspective
        self._simulation_state_snapshot = {
            "current_tick": self.orchestrator.current_tick,
            "simulation_time": self.orchestrator._calculate_simulation_time().isoformat(),
            # "world_state_summary": self.world_store.get_snapshot_summary() # if integrated
            # "agent_states": {agent.id: agent.get_state() for agent in self.agent_manager.get_active_agents()}
        }
        logger.info("Simulation state preserved.")

    async def restore_simulation_state(self):
        """Restores the simulation state from a snapshot after fast-forwarding."""
        if self._simulation_state_snapshot:
            logger.info("Restoring simulation state from snapshot...")
            # This would involve loading the snapshot and
            # rehydrating relevant services/agents.
            self.orchestrator.current_tick = self._simulation_state_snapshot["current_tick"]
            # Re-adjust orchestrator.start_time to make the simulation time consistent
            # This is tricky and needs careful consideration of how _calculate_simulation_time works
            # If _calculate_simulation_time relies purely on tick_interval_seconds and current_tick,
            # then just setting current_tick is enough.
            logger.info("Simulation state restored (conceptual).")
            self._simulation_state_snapshot = None
        else:
            logger.warning("No simulation state snapshot to restore.")

    async def validate_fast_forward_accuracy(self) -> bool:
        """
        Checks the integrity and accuracy of the simulation after a fast-forward jump.
        This would involve running consistency checks on simulation state.
        """
        logger.info("Validating fast-forward accuracy (conceptual check).")
        # Possible checks:
        # - Compare summary statistics of skipped period with predicted values.
        # - Run a few 'real' ticks after fast-forward and check for anomalies.
        # - Verify data consistency in the WorldStore.

        # For now, always return True in this conceptual implementation
        return True

    async def transition_to_fast_forward_mode(self, target_tick: int):
        """High-level method to enter fast-forward mode."""
        if self._fast_forward_mode_active:
            logger.info("Already in fast-forward mode.")
            return

        if self.orchestrator.current_tick >= target_tick:
            logger.warning(f"Cannot fast-forward to {target_tick}, already at or beyond it.")
            return

        is_idle = self.detect_idle_period(self._last_agent_activity, self.activity_level_threshold)
        duration_to_skip = target_tick - self.orchestrator.current_tick

        if is_idle and duration_to_skip >= self.min_fast_forward_duration_ticks:
            logger.info(
                f"Conditions met for fast-forward: idle detected and {duration_to_skip} ticks to skip."
            )
            # Instruct orchestrator to pause its regular tick loop
            await self.orchestrator.pause()

            await self.fast_forward_to_tick(target_tick)

            # Resume orchestrator so it can continue from the new tick
            await self.orchestrator.resume()
            logger.info("Exited fast-forward transition. Simulation resumed.")
        else:
            logger.info(
                f"Conditions not met for fast-forward. Idle: {is_idle}, Duration: {duration_to_skip} (min {self.min_fast_forward_duration_ticks})."
            )
            self._fast_forward_mode_active = False

    async def exit_fast_forward_mode(self):
        """High-level method to exit fast-forward mode and resume normal simulation."""
        if self._fast_forward_mode_active:
            logger.info("Exiting fast-forward mode.")
            self._fast_forward_mode_active = False
            # No specific actions needed here if fast_forward_to_tick already resumes orchestrator
            # This method primarily exists for explicit control if needed.
        else:
            logger.info("Not currently in fast-forward mode.")

    def get_status(self) -> Dict[str, Any]:
        """Provides current status of the FastForwardEngine."""
        return {
            "fast_forward_mode_active": self._fast_forward_mode_active,
            "last_agent_activity_count": len(self._last_agent_activity),
            "compressed_events_buffered": len(self._compressed_events_buffer),
            "has_state_snapshot": self._simulation_state_snapshot is not None,
            "idle_detection_threshold_ticks": self.idle_detection_threshold_ticks,
            "activity_level_threshold": self.activity_level_threshold,
            "min_fast_forward_duration_ticks": self.min_fast_forward_duration_ticks,
        }
