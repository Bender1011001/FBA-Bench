"""
Customer Event Service facade.

Re-exports the core customer event types and services.
"""
from fba_bench_core.services.customer_event_service import (
    CustomerBehaviorProfile,
    CustomerEvent,
    CustomerEventService,
    CustomerEventType,
    CustomerSegment,
)

__all__ = [
    "CustomerBehaviorProfile",
    "CustomerEvent",
    "CustomerEventService",
    "CustomerEventType",
    "CustomerSegment",
]
