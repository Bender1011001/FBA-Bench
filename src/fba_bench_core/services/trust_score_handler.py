from __future__ import annotations

import logging
from typing import Any

from src.fba_bench_core.event_bus import EventBus
from src.fba_bench_core.events import SaleProcessedEvent
from src.fba_bench_core.models.sales_result import SalesResult
from src.fba_bench_core.money import Money
from services.trust_score_service import TrustScoreService

logger = logging.getLogger(__name__)


class TrustScoreEventHandler:
    """
    A dedicated handler that listens for sale.processed events and triggers trust score calculations.

    This handler is resilient to both typed events (SaleProcessedEvent) and legacy dict-style
    payloads emitted by compatibility backends used in tests.
    """

    def __init__(self, trust_score_service: TrustScoreService, event_bus: EventBus):
        self._trust_score_service = trust_score_service
        self._event_bus = event_bus

    async def setup_subscriptions(self) -> None:
        """Subscribe to relevant events on the EventBus."""
        await self._event_bus.subscribe("sale.processed", self.handle_sale_processed)
        logger.info("TrustScoreEventHandler subscribed to 'sale.processed' events.")

    async def handle_sale_processed(self, event: Any) -> None:
        """
        Handle a sale processed event. Accepts either a typed SaleProcessedEvent instance
        or a legacy dict-style payload produced by compat backends/tests.
        """
        try:
            # Normalize to SalesResult instance
            sale_result: SalesResult

            if isinstance(event, SaleProcessedEvent):
                sale_result = event.payload
            elif isinstance(event, dict):
                # event may be the dict envelope produced by compat bus
                data = event.get("event_data") or event.get("payload") or event
                if isinstance(data, dict):
                    # Parse into the canonical Pydantic SalesResult model
                    sale_result = SalesResult.parse_obj(data)
                else:
                    # Fallback: if payload was already a SalesResult-like object
                    sale_result = data  # type: ignore[assignment]
            else:
                logger.warning(
                    "Received unsupported event type for trust score handler: %s",
                    type(event),
                )
                return

            # Extract an identifier for trust score target (seller/product). Use product_id as default.
            entity_id = getattr(sale_result, "product_id", "default_seller")

            # Determine sale revenue from common fields
            revenue = None
            for attr in ("total_price", "total_revenue", "total"):
                if hasattr(sale_result, attr):
                    revenue = getattr(sale_result, attr)
                    break
            if revenue is None:
                if hasattr(sale_result, "unit_price") and hasattr(
                    sale_result, "quantity"
                ):
                    try:
                        revenue = float(sale_result.unit_price) * int(
                            sale_result.quantity
                        )
                    except (TypeError, ValueError):
                        revenue = 0.0
                else:
                    revenue = 0.0

            # If revenue was represented using the canonical Money type, extract its Decimal amount.
            if isinstance(revenue, Money):
                revenue = revenue.amount

            sale_revenue = float(revenue) if revenue is not None else 0.0

            # Trigger trust score calculation. Map available data to the stateless service input.
            # Currently we don't have violations or structured feedback in the sale event,
            # so we call with conservative defaults.
            score = self._trust_score_service.calculate_trust_score(
                violations_count=0,
                buyer_feedback_scores=[],
                total_days=0,
            )

            logger.info(
                "Trust score calculation requested for entity=%s (sale_revenue=%.2f) -> score=%.2f",
                entity_id,
                sale_revenue,
                score,
            )
        except (TypeError, AttributeError, ValueError, RuntimeError):
            logger.exception("Error handling sale.processed event")
