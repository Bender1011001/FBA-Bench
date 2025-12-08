"""
Cost Tracking Service facade.

Re-exports the core CostTrackingService for backward compatibility.
"""
from fba_bench_core.services.cost_tracking_service import CostTrackingService

__all__ = ["CostTrackingService"]
