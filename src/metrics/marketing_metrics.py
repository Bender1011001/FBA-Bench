# metrics/marketing_metrics.py
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from money import USD_ZERO, Money  # Assuming Money class and USD_ZERO are implemented

from fba_events import (
    AdClickEvent,
    AdSpendEvent,
    BaseEvent,
    CustomerAcquisitionEvent,
    SaleOccurred,
    VisitEvent,
)

logger = logging.getLogger(__name__)


# --- Abstract Service Interfaces (from metric_suite.py or a shared contracts module) ---
class AbstractSalesService(Protocol):
    """Protocol for a sales service."""

    def get_status_summary(self) -> Dict[str, Any]: ...


@dataclass
class CampaignPerformance:
    """Dataclass to store performance metrics for individual campaigns."""

    campaign_id: str
    revenue: Money = field(default_factory=lambda: USD_ZERO)
    ad_spend: Money = field(default_factory=lambda: USD_ZERO)
    conversions: int = 0
    # Add other campaign-specific metrics as needed

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["revenue"] = (
            self.revenue.to_dict()
            if hasattr(self.revenue, "to_dict")
            else str(self.revenue)
        )
        data["ad_spend"] = (
            self.ad_spend.to_dict()
            if hasattr(self.ad_spend, "to_dict")
            else str(self.ad_spend)
        )
        return data


@dataclass
class MarketingMetricsConfig:
    """Configurable parameters for MarketingMetrics."""

    # Threshold for what constitutes a "low" success rate for warnings
    low_conversion_rate_threshold: float = 0.05  # 5%
    # Weights for ROAS/ACoS calculation
    roas_weight: float = 0.5
    acos_weight: float = 0.5
    # Value to return if a metric cannot be calculated due to zero denominator
    default_on_zero_division: float = 0.0  # Can be 0.0 or 100.0 or float('nan')
    # Minimum required length of revenue history before calculating trend
    min_campaign_revenue_for_weighting: float = (
        100.0  # e.g., only campaigns with >= $100 revenue contribute to weighted score
    )


class MarketingMetrics:
    """
    Tracks and calculates marketing performance indicators.
    """

    def __init__(
        self,
        config: Optional[MarketingMetricsConfig] = None,
    ):
        # Issue 94: Removed unused sales_service parameter
        self.config = config if config else MarketingMetricsConfig()

        self.total_revenue: Money = USD_ZERO
        self.total_ad_spend: Money = USD_ZERO
        self.total_conversions: int = 0
        self.total_customer_acquisitions: int = 0
        self.total_opportunities: int = 0  # visits/clicks tracked from events
        self.campaign_performance: Dict[str, CampaignPerformance] = {}

        self._last_update_time: Optional[datetime] = None

        # Unit-test compatibility: lightweight metric registry
        self._metrics: Dict[str, Any] = {}

        logger.info("MarketingMetrics initialized.")

    def update(self, events: List[BaseEvent]) -> None:
        """
        Updates marketing metrics based on a list of structured BaseEvent objects.
        This method replaces brittle manual event extraction with a more robust, type-aware approach.
        """
        for event in events:
            if isinstance(event, SaleOccurred):
                # Assuming SaleOccurred has .unit_price (Money) and .units_sold (int)
                if isinstance(event.unit_price, Money) and isinstance(
                    event.units_sold, int
                ):
                    sale_amount = event.unit_price * event.units_sold
                    self.total_revenue += sale_amount
                    self.total_conversions += 1  # A sale is a conversion

                    # Campaign attribution with validation
                    campaign_id = getattr(event, "campaign_id", None)
                    if isinstance(campaign_id, str) and campaign_id:
                        if campaign_id not in self.campaign_performance:
                            self.campaign_performance[campaign_id] = (
                                CampaignPerformance(campaign_id=campaign_id)
                            )
                        self.campaign_performance[campaign_id].revenue += sale_amount
                        self.campaign_performance[campaign_id].conversions += 1
                    elif campaign_id is not None:
                        logger.warning(
                            f"SaleOccurred event {event.event_id} has invalid campaign_id: {campaign_id}"
                        )

            elif isinstance(event, AdSpendEvent):
                # Assuming AdSpendEvent has .cost (Money) and .campaign_id (str)
                if isinstance(event.cost, Money):
                    self.total_ad_spend += event.cost
                    campaign_id = getattr(event, "campaign_id", None)
                    if isinstance(campaign_id, str) and campaign_id:
                        if campaign_id not in self.campaign_performance:
                            self.campaign_performance[campaign_id] = (
                                CampaignPerformance(campaign_id=campaign_id)
                            )
                        self.campaign_performance[campaign_id].ad_spend += event.cost
                    elif campaign_id is not None:
                        logger.warning(
                            f"AdSpendEvent event {event.event_id} has invalid campaign_id: {campaign_id}"
                        )

            elif isinstance(event, (VisitEvent, AdClickEvent)):
                self.total_opportunities += 1

            elif isinstance(event, CustomerAcquisitionEvent):
                self.total_customer_acquisitions += 1

            else:
                logger.debug(
                    f"MarketingMetrics did not process unhandled event type: {event.event_type}"
                )

        self._last_update_time = datetime.now()

    def calculate_roas(self) -> float:
        """Calculates Return on Ad Spend (ROAS). Returns `default_on_zero_division` if total_ad_spend is zero."""
        total_ad_spend_float = self.total_ad_spend.to_float()
        total_revenue_float = self.total_revenue.to_float()
        if total_ad_spend_float > 0:
            return total_revenue_float / total_ad_spend_float
        logger.warning(
            "Total Ad Spend is zero, cannot calculate ROAS. Returning default."
        )
        return self.config.default_on_zero_division

    def calculate_acos(self) -> float:
        """Calculates Advertising Cost of Sale (ACoS). Returns `default_on_zero_division` if total_revenue is zero."""
        total_revenue_float = self.total_revenue.to_float()
        total_ad_spend_float = self.total_ad_spend.to_float()
        if total_revenue_float > 0:
            return (total_ad_spend_float / total_revenue_float) * 100
        logger.warning(
            "Total Revenue is zero, cannot calculate ACoS. Returning default."
        )
        return self.config.default_on_zero_division

    def calculate_weighted_roas_acos(self) -> float:
        """
        Calculates a weighted score combining ROAS and ACoS, normalized to 0-100.
        Uses config.target_roas to scale the ROAS component appropriately.
        """
        if not self.campaign_performance:
            return 0.0

        total_weighted_score = 0.0
        contributing_campaigns = [
            cp
            for cp in self.campaign_performance.values()
            if cp.revenue.to_float() >= self.config.min_campaign_revenue_for_weighting
        ]

        if not contributing_campaigns:
            return 0.0

        total_contributing_revenue = sum(
            cp.revenue.to_float() for cp in contributing_campaigns
        )
        if total_contributing_revenue == 0:
            return 0.0

        for cp in contributing_campaigns:
            revenue = cp.revenue.to_float()
            spend = cp.ad_spend.to_float()

            roas = revenue / spend if spend > 0 else 0.0
            # Normalize ROAS: min(roas / target_roas, 1.0) * 100
            roas_score = min(roas / self.config.target_roas, 1.0) * 100

            # ACoS Score: 100 - ACoS% (clamped at 0)
            acos_val = (spend / revenue * 100) if revenue > 0 else 100.0
            acos_score = max(0.0, 100.0 - acos_val)

            combined_campaign_score = (
                roas_score * self.config.roas_weight
                + acos_score * self.config.acos_weight
            )

            weight = revenue / total_contributing_revenue
            total_weighted_score += combined_campaign_score * weight

        return total_weighted_score

    # ---- Unit-test compatible helpers expected by tests ----
    def calculate_customer_lifetime_value(self, data: Dict[str, float]) -> float:
        apv = float(data.get("average_purchase_value", 0.0))
        freq = float(data.get("purchase_frequency", 0.0))
        lifespan = float(data.get("customer_lifespan", 0.0))
        return apv * freq * lifespan

    def calculate_return_on_ad_spend(self, data: Dict[str, float]) -> float:
        revenue = float(data.get("revenue", 0.0))
        ad_spend = float(data.get("ad_spend", 0.0))
        return revenue / ad_spend if ad_spend > 0 else 0.0

    def calculate_market_share(self, data: Dict[str, float]) -> float:
        company_sales = float(data.get("company_sales", 0.0))
        total_market_sales = float(data.get("total_market_sales", 0.0))
        return company_sales / total_market_sales if total_market_sales > 0 else 0.0

    def generate_marketing_report(self, data: Dict[str, float]) -> Dict[str, float]:
        conversion_rate = self.calculate_conversion_rate(
            {
                "conversions": data.get("conversions", 0.0),
                "visitors": data.get("visitors", 0.0),
            }
        )
        cac = self.calculate_customer_acquisition_cost(
            {
                "marketing_cost": data.get("marketing_cost", 0.0),
                "new_customers": data.get("new_customers", 0.0),
            }
        )
        clv = self.calculate_customer_lifetime_value(data)
        roas = self.calculate_return_on_ad_spend(
            {"revenue": data.get("revenue", 0.0), "ad_spend": data.get("ad_spend", 0.0)}
        )
        market_share = self.calculate_market_share(
            {
                "company_sales": data.get("company_sales", 0.0),
                "total_market_sales": data.get("total_market_sales", 0.0),
            }
        )
        return {
            "conversion_rate": conversion_rate,
            "customer_acquisition_cost": cac,
            "customer_lifetime_value": clv,
            "return_on_ad_spend": roas,
            "market_share": market_share,
        }

    def calculate_conversion_rate(
        self, data: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculates the conversion rate.
        - If data is provided: conversions / visitors (fraction, not percentage) to match unit tests.
        - Else: uses internal counters and returns percentage (backward-compat).
        """
        if data is not None:
            visitors = float(data.get("visitors", 0.0))
            conversions = float(data.get("conversions", 0.0))
            return conversions / visitors if visitors > 0 else 0.0
        if self.total_opportunities > 0:
            return (self.total_conversions / self.total_opportunities) * 100.0
        return 0.0

    def calculate_customer_acquisition_cost(
        self, data: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculates Customer Acquisition Cost (CAC).
        - If data is provided: marketing_cost / new_customers.
        - Else: uses internal totals.
        """
        if data is not None:
            marketing_cost = float(data.get("marketing_cost", 0.0))
            new_customers = float(data.get("new_customers", 0.0))
            return (
                marketing_cost / new_customers
                if new_customers > 0
                else self.config.default_on_zero_division
            )
        if self.total_customer_acquisitions > 0:
            return self.total_ad_spend.to_float() / self.total_customer_acquisitions
        logger.warning(
            "No customer acquisitions, cannot calculate CAC. Returning default."
        )
        return self.config.default_on_zero_division

    def get_metrics_breakdown(self) -> Dict[str, Any]:
        """
        Calculates and returns a detailed breakdown of all marketing metrics.
        Returns a dictionary with metric names and their calculated float values.
        """
        weighted_roas_acos = self.calculate_weighted_roas_acos()
        conversion_rate = self.calculate_conversion_rate()
        customer_acquisition_cost = self.calculate_customer_acquisition_cost()

        campaign_performance_dicts = {
            cid: cp.to_dict() for cid, cp in self.campaign_performance.items()
        }

        return {
            "overall_score": weighted_roas_acos,  # Use weighted_roas_acos as primary score for marketing
            "weighted_roas_acos": weighted_roas_acos,
            "conversion_rate": conversion_rate,
            "customer_acquisition_cost": customer_acquisition_cost,
            "total_revenue": self.total_revenue.to_float(),
            "total_ad_spend": self.total_ad_spend.to_float(),
            "total_conversions": self.total_conversions,
            "total_opportunities": self.total_opportunities,
            "campaign_performance": campaign_performance_dicts,
        }

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides a summary of the current state of the MarketingMetrics module."""
        return {
            "last_update_time": (
                self._last_update_time.isoformat() if self._last_update_time else "N/A"
            ),
            "total_revenue_usd": self.total_revenue.to_float(),
            "total_ad_spend_usd": self.total_ad_spend.to_float(),
            "total_conversions": self.total_conversions,
            "total_opportunities": self.total_opportunities,
            "num_campaigns_tracked": len(self.campaign_performance),
            "config": asdict(self.config),
        }

    def reset_metrics(self) -> None:
        """Resets all metrics history for a new simulation run."""
        self.total_revenue = USD_ZERO
        self.total_ad_spend = USD_ZERO
        self.total_conversions = 0
        self.total_customer_acquisitions = 0
        self.total_opportunities = 0
        self.campaign_performance.clear()
        self._last_update_time = None
        logger.info("MarketingMetrics reset successfully.")
