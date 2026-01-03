# metrics/cost_metrics.py
import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from money import USD_ZERO, Money  # Assuming Money class and USD_ZERO are implemented

from fba_events import (  # Explicitly import event types
    ApiCostEvent,
    BaseEvent,
    PenaltyEvent,
    TokenUsageEvent,
)
from fba_events.bus import EventBus

logger = logging.getLogger(__name__)


class PenaltyType(Enum):
    """Defines types of penalties that can be applied to cost metrics."""

    BUDGET_EXCEEDED = "budget_exceeded"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"
    HIGH_COST_OPERATION = "high_cost_operation"
    # Add other penalty types as needed


@dataclass
class CostMetricsConfig:
    """Configurable parameters for CostMetrics."""

    default_token_cost_per_million: float = 15.0  # Example: $15 per million tokens
    max_acceptable_cost_usd: float = 50.0  # Max cost (in USD) for a raw score of 0
    high_cost_threshold_usd: float = 5.0  # Threshold to flag an operation as high cost
    # Penalty weights for different types of violations (multiplier on base penalty)
    penalty_weights: Dict[PenaltyType, float] = field(
        default_factory=lambda: {
            PenaltyType.BUDGET_EXCEEDED: 20.0,  # High penalty
            PenaltyType.RATE_LIMIT_VIOLATION: 10.0,  # Medium penalty
            PenaltyType.HIGH_COST_OPERATION: 5.0,  # Lower penalty, more of a warning
        }
    )


class CostMetrics:
    """
    Tracks token consumption and monetary costs for LLM interactions and API calls.
    Applies penalties for budget violations or high-cost operations.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        config: Optional[CostMetricsConfig] = None,
    ):
        self.event_bus = event_bus
        self.config = config if config else CostMetricsConfig()

        self.total_tokens_consumed: int = 0
        self.total_api_costs: Money = USD_ZERO
        self.total_penalty_score_deductions: float = 0.0  # Tracks score points deducted
        self.total_penalty_events_published: int = 0

        self.token_cost_per_million: float = self.config.default_token_cost_per_million
        self._last_update_time: Optional[datetime] = None

        # Unit-test compatibility: lightweight metric registry
        self._metrics: Dict[str, Any] = {}

        logger.info("CostMetrics initialized.")

    async def record_token_usage(self, tokens_used: int, event: BaseEvent) -> None:
        """
        Records token usage from a specific source (BaseEvent).
        Publishes a TokenUsageEvent.
        """
        if not isinstance(tokens_used, int) or tokens_used < 0:
            logger.warning(
                f"Invalid tokens_used value: {tokens_used}. Must be a non-negative integer."
            )
            return

        self.total_tokens_consumed += tokens_used

        # Publish TokenUsageEvent
        try:
            token_event = TokenUsageEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                source_event_id=event.event_id,
                source_event_type=event.event_type,
                tokens_consumed=tokens_used,
                estimated_cost_usd=(
                    Money.from_dollars(
                        (tokens_used / 1_000_000) * self.token_cost_per_million, "USD"
                    )
                ),
            )
            await self.event_bus.publish(token_event)
            logger.debug(
                f"Published TokenUsageEvent for {tokens_used} tokens from event {event.event_id}."
            )
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Failed to publish TokenUsageEvent: {e}", exc_info=True)

        self._check_and_penalize_high_cost_operation(
            token_event.estimated_cost_usd
        )  # Check for high cost even on usage

    async def record_api_cost_event(
        self, event: BaseEvent, cost_amount: Optional[Money] = None
    ) -> None:
        """
        Records an API call event and its associated cost. Publishes an ApiCostEvent.
        If cost_amount is not provided, it's assumed to be handled by `record_token_usage`
        or derived from the event itself.
        """
        if cost_amount:
            self.total_api_costs += cost_amount

        try:
            api_cost_event = ApiCostEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                source_event_id=event.event_id,
                source_event_type=event.event_type,
                cost_incurred=(
                    cost_amount if cost_amount else USD_ZERO
                ),  # Store the actual Money object or zero
            )
            await self.event_bus.publish(api_cost_event)
            logger.debug(f"Published ApiCostEvent for event {event.event_id}.")
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Failed to publish ApiCostEvent: {e}", exc_info=True)

        if cost_amount:
            self._check_and_penalize_high_cost_operation(cost_amount)

    async def apply_penalty(
        self, event: BaseEvent, penalty_type: PenaltyType, base_value: float = 1.0
    ) -> None:
        """
        Applies a penalty to the cost metrics and publishes a PenaltyEvent.
        Allows for discrete penalty categories and severities.
        """
        if not isinstance(penalty_type, PenaltyType):
            raise TypeError(
                f"penalty_type must be an instance of PenaltyType Enum, got {type(penalty_type)}"
            )

        penalty_weight = self.config.penalty_weights.get(penalty_type, 1.0)
        penalty_amount = base_value * penalty_weight

        self.total_penalty_score_deductions += penalty_amount
        self.total_penalty_events_published += 1

        try:
            penalty_event = PenaltyEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                source_event_id=event.event_id,
                source_event_type=event.event_type,
                penalty_type=penalty_type.value,
                penalty_value=penalty_amount,
                reason=f"Applied {penalty_type.value} penalty due to event {event.event_id}",
            )
            await self.event_bus.publish(penalty_event)
            logger.info(
                f"Published PenaltyEvent: {penalty_type.value} for event {event.event_id}, amount {penalty_amount:.2f}."
            )
        except (AttributeError, RuntimeError) as e:
            logger.error(f"Failed to publish PenaltyEvent: {e}", exc_info=True)

    def _check_and_penalize_high_cost_operation(self, incurred_cost: Money) -> None:
        """Internal check to apply penalty if a single operation incurs a high cost."""
        threshold = Money.from_dollars(self.config.high_cost_threshold_usd, "USD")
        if incurred_cost > threshold:
            # Issue 93: Use proper BaseEvent instead of dynamic type creation
            system_event = BaseEvent(
                event_id=str(uuid.uuid4()),
                event_type="HighCostOperationCheck",
                timestamp=datetime.now(),
            )
            base_value = (
                incurred_cost.to_float() / self.config.high_cost_threshold_usd
                if self.config.high_cost_threshold_usd > 0
                else 1.0
            )
            asyncio.create_task(
                self.apply_penalty(
                    system_event, PenaltyType.HIGH_COST_OPERATION, base_value=base_value
                )
            )

    def calculate_current_total_cost_usd(self) -> Money:
        """Calculates total cost from token usage and direct API costs."""
        token_cost = Money.from_dollars(
            (self.total_tokens_consumed / 1_000_000) * self.token_cost_per_million,
            "USD",
        )
        return token_cost + self.total_api_costs

    def get_metrics_breakdown(self) -> Dict[str, Any]:
        """
        Calculates and returns a detailed breakdown of cost metrics.
        Returns a score (0-100) where lower cost (and fewer penalties) is better.
        """
        current_total_cost = self.calculate_current_total_cost_usd()

        # Calculate raw cost score (higher is better, 0 cost = 100 score)
        # Using configurable max_acceptable_cost_usd
        max_acceptable_cost_money = Money.from_dollars(
            self.config.max_acceptable_cost_usd, "USD"
        )

        # Avoid division by zero if max_acceptable_cost_money is zero (shouldn't happen with valid config)
        if max_acceptable_cost_money.to_decimal() <= 0:
            logger.warning(
                "Configured max_acceptable_cost_usd is zero or negative. Cost score will be 0."
            )
            raw_cost_score = 0.0
        else:
            cost_ratio = (
                current_total_cost.to_decimal() / max_acceptable_cost_money.to_decimal()
            )
            raw_cost_score = (
                max(0.0, (1 - float(cost_ratio))) * 100
            )  # Invert ratio, scale to 0-100

        # Apply additional penalties from budget violations and direct penalties
        final_cost_score = raw_cost_score - self.total_penalty_score_deductions
        final_cost_score = max(0.0, min(100.0, final_cost_score))  # Clamp between 0-100

        return {
            "overall_score": final_cost_score,  # Primary score for this domain
            "total_tokens_consumed": self.total_tokens_consumed,
            "total_estimated_cost_usd": self.calculate_current_total_cost_usd().to_float(),
            "cost_penalty_score": final_cost_score,
            "total_direct_penalties": self.total_penalty_score_deductions,
            "num_penalty_events": self.total_penalty_events_published,
        }

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides a summary of the current state of the CostMetrics module."""
        return {
            "last_update_time": (
                self._last_update_time.isoformat() if self._last_update_time else "N/A"
            ),
            "total_tokens_consumed": self.total_tokens_consumed,
            "total_api_costs_usd": self.total_api_costs.to_float(),
            "total_penalties_applied": self.total_penalty_score_deductions,
            "config": asdict(self.config),
        }

    def reset_metrics(self) -> None:
        """Resets all metrics history for a new simulation run."""
        self.total_tokens_consumed = 0
        self.total_api_costs = USD_ZERO
        self.total_penalty_score_deductions = 0.0
        self.total_penalty_events_published = 0
        self._last_update_time = None
        logger.info("CostMetrics reset successfully.")

    # ---- Unit-test compatible calculation helpers (dict-based) ----
    def calculate_total_cost(self, data: Dict[str, float]) -> float:
        keys = (
            "compute_cost",
            "storage_cost",
            "network_cost",
            "api_cost",
            "labor_cost",
        )
        return float(sum(float(data.get(k, 0.0)) for k in keys))

    def calculate_cost_per_unit(self, data: Dict[str, float]) -> float:
        total_cost = float(data.get("total_cost", 0.0))
        units = data.get("units_sold")
        if units is None:
            units = data.get("units_produced", 0.0)
        units = float(units)
        return total_cost / units if units > 0 else 0.0

    def calculate_cost_efficiency(self, data: Dict[str, float]) -> float:
        total_cost = float(data.get("total_cost", 0.0))
        revenue = float(data.get("revenue", 0.0))
        return revenue / total_cost if total_cost > 0 else 0.0

    def calculate_cost_variance(self, data: Dict[str, float]) -> float:
        actual = float(data.get("actual_cost", 0.0))
        budgeted = float(data.get("budgeted_cost", 0.0))
        return actual - budgeted

    def calculate_cost_savings(self, data: Dict[str, float]) -> float:
        original = float(data.get("original_cost", 0.0))
        optimized = float(data.get("optimized_cost", 0.0))
        return original - optimized

    def generate_cost_report(self, data: Dict[str, float]) -> Dict[str, float]:
        total_cost = self.calculate_total_cost(
            {
                "compute_cost": data.get("compute_cost", 0.0),
                "storage_cost": data.get("storage_cost", 0.0),
                "network_cost": data.get("network_cost", 0.0),
                "api_cost": data.get("api_cost", 0.0),
                "labor_cost": data.get("labor_cost", 0.0),
            }
        )
        # Ensure downstream methods receive expected keys
        cost_per_unit = self.calculate_cost_per_unit(
            {
                "total_cost": total_cost,
                "units_sold": data.get("units_sold", data.get("units_produced", 0.0)),
                "units_produced": data.get("units_produced", 0.0),
            }
        )
        cost_efficiency = self.calculate_cost_efficiency(
            {
                "total_cost": total_cost,
                "revenue": data.get("revenue", 0.0),
            }
        )
        cost_variance = self.calculate_cost_variance(
            {
                "actual_cost": (
                    total_cost
                    if "actual_cost" not in data
                    else data.get("actual_cost", total_cost)
                ),
                "budgeted_cost": data.get("budgeted_cost", 0.0),
            }
        )
        cost_savings = self.calculate_cost_savings(
            {
                "original_cost": data.get("original_cost", total_cost),
                "optimized_cost": data.get("optimized_cost", total_cost),
            }
        )
        return {
            "total_cost": total_cost,
            "cost_per_unit": cost_per_unit,
            "cost_efficiency": cost_efficiency,
            "cost_variance": cost_variance,
            "cost_savings": cost_savings,
        }
