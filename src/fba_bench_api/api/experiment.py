"""
Experiment manager module.

This is a lightweight in-process registry used by the API layer and unit tests to
track experiment runner objects by ID.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional


class ExperimentManager:
    def __init__(self) -> None:
        self._experiments: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

        # Back-compat stub storage for legacy callers.
        self.experiments: Dict[str, Dict[str, Any]] = {}

    async def set(self, experiment_id: str, experiment_manager: Any) -> None:
        async with self._lock:
            self._experiments[experiment_id] = experiment_manager

    async def get(self, experiment_id: str) -> Optional[Any]:
        async with self._lock:
            return self._experiments.get(experiment_id)

    async def remove(self, experiment_id: str) -> None:
        async with self._lock:
            self._experiments.pop(experiment_id, None)

    def list_ids(self):
        return list(self._experiments.keys())

    # ---------------------------------------------------------------------
    # Back-compat stubs
    # ---------------------------------------------------------------------

    def start_experiment(self, experiment_id: str, config: dict):
        self.experiments[experiment_id] = {"status": "running", "config": config}

    def stop_experiment(self, experiment_id: str):
        if experiment_id in self.experiments:
            self.experiments[experiment_id]["status"] = "stopped"

    def get_status(self, experiment_id: str) -> dict:
        return self.experiments.get(experiment_id, {"status": "unknown"})
