"""
Dispute Service facade.

Re-exports the core DisputeService and related data models.
"""
from fba_bench_core.services.dispute_service import (
    DisputeDetails,
    DisputeRecord,
    DisputeResolution,
    DisputeService,
)

__all__ = [
    "DisputeDetails",
    "DisputeRecord",
    "DisputeResolution",
    "DisputeService",
]
