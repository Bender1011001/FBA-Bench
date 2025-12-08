"""
Marketing Service facade.

Re-exports the core MarketingService and campaign models.
"""
from fba_bench_core.services.marketing_service import (
    ActiveCampaign,
    MarketingService,
)

__all__ = ["ActiveCampaign", "MarketingService"]
