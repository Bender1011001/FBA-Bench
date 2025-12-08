"""
Dashboard API Service facade.

Re-exports the core DashboardAPIService and metric aggregators.
"""
from fba_bench_core.services.dashboard_api_service import (
    DashboardAPIService,
    FeeMetricsAggregatorService,
)

__all__ = ["DashboardAPIService", "FeeMetricsAggregatorService"]
