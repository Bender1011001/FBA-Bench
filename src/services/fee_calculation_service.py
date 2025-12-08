"""
Fee Calculation Service facade.

Re-exports the core FeeCalculationService and fee models.
"""
from fba_bench_core.services.fee_calculation_service import (
    ComprehensiveFeeBreakdown,
    FeeCalculation,
    FeeCalculationService,
    FeeType,
)

__all__ = [
    "ComprehensiveFeeBreakdown",
    "FeeCalculation",
    "FeeCalculationService",
    "FeeType",
]
