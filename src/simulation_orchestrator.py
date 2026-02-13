"""
Root-level compatibility shim for simulation orchestrator imports.

The canonical implementation lives in `fba_bench_core.simulation_orchestrator`,
but older code/tests import directly from `simulation_orchestrator`.
"""

from fba_bench_core.simulation_orchestrator import (  # noqa: F401
    SimulationConfig,
    SimulationOrchestrator,
)

__all__ = ["SimulationConfig", "SimulationOrchestrator"]
