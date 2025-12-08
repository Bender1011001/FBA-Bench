"""
Customer Reputation Service facade.

Re-exports the core CustomerReputationService and ReputationEvent.
"""
from fba_bench_core.services.customer_reputation_service import (
    CustomerReputationService,
    ReputationEvent,
)

__all__ = ["CustomerReputationService", "ReputationEvent"]
