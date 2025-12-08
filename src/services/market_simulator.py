"""
Market Simulator facade.

Re-exports the core MarketSimulationService and competitor snapshots.
"""
from fba_bench_core.services.market_simulator import (
    CompetitorSnapshot,
    MarketSimulationService,
)

__all__ = ["CompetitorSnapshot", "MarketSimulationService"]
