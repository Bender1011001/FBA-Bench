"""
Simulation manager module.

This is a lightweight in-process registry used by the API layer and unit tests to
track active SimulationOrchestrator instances.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional


class SimulationManager:
    def __init__(self) -> None:
        self._orchestrators: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

        # Back-compat stub storage (older code paths used dict status records)
        self.simulations: Dict[str, Dict[str, Any]] = {}

    async def add_orchestrator(self, sim_id: str, orchestrator: Any) -> None:
        async with self._lock:
            self._orchestrators[sim_id] = orchestrator

    async def get_orchestrator(self, sim_id: str) -> Optional[Any]:
        async with self._lock:
            return self._orchestrators.get(sim_id)

    async def remove_orchestrator(self, sim_id: str) -> None:
        async with self._lock:
            self._orchestrators.pop(sim_id, None)

    def get_simulation_status(self, sim_id: str) -> Dict[str, Any]:
        orch = self._orchestrators.get(sim_id)
        if orch is None:
            return {"status": "not_found"}
        if hasattr(orch, "get_status"):
            return orch.get_status()
        return {"status": "unknown"}

    def get_all_simulation_ids(self):
        return list(self._orchestrators.keys())

    # ---------------------------------------------------------------------
    # Back-compat stubs
    # ---------------------------------------------------------------------

    def run_simulation(self, sim_id: str, params: dict):
        self.simulations[sim_id] = {"status": "running", "params": params}

    def stop_simulation(self, sim_id: str):
        if sim_id in self.simulations:
            self.simulations[sim_id]["status"] = "stopped"

    def get_status(self, sim_id: str) -> dict:
        return self.simulations.get(sim_id, {"status": "unknown"})
