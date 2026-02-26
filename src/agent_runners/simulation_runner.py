"""
SimulationRunner - Minimal simulation loop utilities used by tests.

This module provides a lightweight runner that tracks ticks and exposes
a canonical SimulationState compatible with agent runners.

Public API:
- SimulationRunner(config)
- SimulationRunner.configure(sim_config)
- SimulationRunner.step_once() -> (SimulationState, meta)
- SimulationRunner.run(max_ticks=None, stop_condition=None) -> snapshot dict
- SimulationRunner.get_snapshot() -> snapshot dict
- SimulationRunner.stop() -> None

Private utilities required by tests:
- _format_key_parameters(params: Dict[str, Any]) -> str
- _setup_competitor_manager(params: Dict[str, Any]) -> object
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

# Re-export the canonical SimulationState used by agent runners
from agent_runners.base_runner import SimulationState as SimulationState


class SimulationRunner:
    """Simple simulation loop helper tracking ticks and basic metadata.

    Attributes:
      - current_tick: current tick counter (starts at 0)
      - start_time: UTC timestamp when the runner was created
      - last_update: UTC timestamp of the last step
      - _stopped: internal flag to stop the loop
      - _params: shallow dict of parameters/configuration

    Example:
      runner = SimulationRunner({"initial_price": 9.99})
      state, meta = runner.step_once()
      # state.tick == 1, meta["tick"] == 1
    """

    def __init__(self, config: Any):
        """Initialize the runner with an optional configuration object.

        Args:
          config: Any object; if dict-like, its items are shallow-copied
                  into internal parameters for snapshot metadata.
        """
        self.current_tick: int = 0
        self.start_time: datetime = datetime.now(timezone.utc)
        self.last_update: datetime = self.start_time
        self._stopped: bool = False
        self._params: Dict[str, Any] = dict(config) if isinstance(config, dict) else {}
        self.config: Any = config

    def configure(self, sim_config: Any) -> None:
        """Update runner configuration.

        If sim_config is a dict, perform a shallow update of internal params.

        Args:
          sim_config: new configuration to merge into parameters.
        """
        if isinstance(sim_config, dict):
            self._params.update(sim_config)

    def step_once(self) -> Tuple[SimulationState, Dict[str, Any]]:
        """Advance the simulation by one tick and return state and metadata.

        Returns:
          - state: SimulationState with current tick and simulation_time set.
          - meta: Dict with basic information about the step, e.g.:
              {"tick": 1, "timestamp": "...", "events": 0}

        Example:
          state, meta = runner.step_once()
          # state.tick == 1
          # meta == {"tick": 1, "timestamp": "...", "events": 0}
        """
        self.current_tick += 1
        now = datetime.now(timezone.utc)
        self.last_update = now

        state = SimulationState(
            tick=self.current_tick,
            simulation_time=now,
        )
        meta: Dict[str, Any] = {
            "tick": self.current_tick,
            "timestamp": now.isoformat(),
            "events": 0,
        }
        return state, meta

    def run(
        self,
        max_ticks: Optional[int] = None,
        stop_condition: Optional[Callable[[int], bool]] = None,
    ) -> Dict[str, Any]:
        """Run the simulation loop until stopped, reaching max_ticks, or condition.

        Args:
          max_ticks: optional limit on number of ticks to execute.
          stop_condition: optional callable receiving current_tick and
                          returning True to stop the loop.

        Returns:
          Snapshot dictionary from get_snapshot().
        """
        while not self._stopped and (
            max_ticks is None or self.current_tick < max_ticks
        ):
            if stop_condition and stop_condition(self.current_tick):
                break
            self.step_once()
        return self.get_snapshot()

    def get_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of current simulation metrics and metadata.

        Returns:
          Dict with fields: current_tick, simulation_time, last_update,
          uptime_seconds, agents, event_stats, metadata.
        """
        uptime_seconds = max(0.0, (self.last_update - self.start_time).total_seconds())
        return dict(
            current_tick=self.current_tick,
            simulation_time=self.last_update.isoformat(),
            last_update=self.last_update.isoformat(),
            uptime_seconds=uptime_seconds,
            agents=[],
            event_stats={
                "ticks_per_second": (
                    (self.current_tick / uptime_seconds) if uptime_seconds > 0 else None
                )
            },
            metadata={"params": self._params},
        )

    def stop(self) -> None:
        """Signal the loop to stop on the next check."""
        self._stopped = True

    # ---------- Private utilities required by tests ----------

    def _format_key_parameters(self, params: Dict[str, Any]) -> str:
        """Deterministically serialize key=value pairs sorted by key.

        Values are cast to str. No escaping is performed.

        Example:
          {"b": 2, "a": 1} -> "a=1;b=2"
        """
        if not isinstance(params, dict):
            raise ValueError("params must be a dict")
        items = [f"{k}={params[k]!s}" for k in sorted(params.keys())]
        return ";".join(items)

    def _setup_competitor_manager(self, params: Dict[str, Any]) -> object:
        """Create a minimal competitor manager-like object used by tests.

        The object only needs to carry the provided params.

        Args:
          params: arbitrary configuration dictionary

        Returns:
          An object with a .params attribute referencing the provided dict.
        """
        if not isinstance(params, dict):
            raise ValueError("params must be a dict")

        class CompetitorManager:
            def __init__(self, p: Dict[str, Any]) -> None:
                self.params = p

        return CompetitorManager(params)


__all__ = ["SimulationRunner", "SimulationState"]
