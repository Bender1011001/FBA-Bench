"""
MarketingService

Manages active advertising campaigns and connects marketing spend to sales demand
via a "marketing visibility" multiplier stored in WorldStore.

Responsibilities:
- Subscribe to RunMarketingCampaignCommand (from fba_events.marketing)
- Maintain active campaigns with per-day budgets over duration
- On each TickEvent:
    * Simulate ad auction spend for each active campaign
    * Publish AdSpendEvent with spend, clicks, impressions
    * Update WorldStore marketing visibility for the target ASIN with decay + increment
- Provide lightweight inspection helpers for tests/metrics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from money import Money
from services.world_store import WorldStore

from fba_bench_core.event_bus import EventBus, get_event_bus
from fba_events.marketing import AdSpendEvent, RunMarketingCampaignCommand
from fba_events.time_events import TickEvent  # via shim

logger = logging.getLogger(__name__)


@dataclass
class ActiveCampaign:
    campaign_id: str
    asin: str
    daily_budget: Money
    remaining_days: int
    remaining_budget: Money


class MarketingService:
    """
    Deterministic marketing campaign simulator with visibility coupling.

    Visibility model:
    - WorldStore holds a "marketing_visibility" multiplier per ASIN (default 1.0)
    - Each tick, for each active campaign:
        * Spend ~= daily_budget (bounded by remaining_budget)
        * Compute effect_incr = 1.0 + alpha * dollars_spent, with alpha small
        * New visibility = 1.0 + retention * (current - 1.0) + (effect_incr - 1.0)
        * Bound visibility to [0.1, 5.0] via WorldStore safeguards
    - Campaigns end when remaining_days == 0 or remaining_budget == 0
    """

    def __init__(
        self,
        world_store: WorldStore,
        event_bus: Optional[EventBus] = None,
        alpha_per_dollar: float = 0.002,  # +0.2 visibility per $100 spend before smoothing
        retention: float = 0.8,  # 80% of prior effect retained per tick
        default_click_cpc_dollars: float = 1.0,  # clicks ~= dollars / CPC
        assumed_ctr: float = 0.02,  # 2% CTR => impressions ~= clicks / 0.02
    ) -> None:
        self.world_store = world_store
        self.event_bus = event_bus or get_event_bus()

        # Tunable parameters
        self.alpha_per_dollar = max(0.0, float(alpha_per_dollar))
        self.retention = min(1.0, max(0.0, float(retention)))
        self.default_click_cpc_dollars = max(0.01, float(default_click_cpc_dollars))
        self.assumed_ctr = min(1.0, max(0.0001, float(assumed_ctr)))

        # State
        self._started: bool = False
        self._current_tick: int = 0
        self._campaigns: Dict[str, ActiveCampaign] = {}  # campaign_id -> ActiveCampaign

    async def start(self) -> None:
        if self._started:
            return
        await self.event_bus.subscribe(
            RunMarketingCampaignCommand, self._on_run_campaign
        )
        await self.event_bus.subscribe(TickEvent, self._on_tick)
        self._started = True
        logger.info(
            "MarketingService started and subscribed to RunMarketingCampaignCommand and TickEvent."
        )

    async def stop(self) -> None:
        self._started = False
        logger.info("MarketingService stopped.")

    async def _on_run_campaign(self, event: RunMarketingCampaignCommand) -> None:
        """
        Handle incoming marketing campaign command.

        Notes:
        - RunMarketingCampaignCommand does not define 'asin' in the dataclass.
          We support agents/scenarios setting 'asin' as a dynamic attribute on the event.
        - A daily budget is derived as (total budget / duration_days), rounded down to cents.
        """
        try:
            asin = getattr(event, "asin", None)
            if not asin or not isinstance(asin, str):
                logger.warning(
                    "RunMarketingCampaignCommand missing asin attribute; ignoring command."
                )
                return

            total_budget: Money = event.budget
            duration_days: int = max(1, int(event.duration_days))
            # Even per-day split; remainder stays in remaining_budget and will be consumed on last day(s)
            daily_cents = total_budget.cents // duration_days
            if daily_cents <= 0:
                logger.warning(
                    "RunMarketingCampaignCommand has near-zero daily budget; ignoring command."
                )
                return

            daily_budget = Money(daily_cents)
            campaign_id = event.event_id
            self._campaigns[campaign_id] = ActiveCampaign(
                campaign_id=campaign_id,
                asin=asin,
                daily_budget=daily_budget,
                remaining_days=duration_days,
                remaining_budget=Money(total_budget.cents),
            )
            logger.info(
                "MarketingService activated campaign: id=%s asin=%s daily_budget=%s days=%d",
                campaign_id,
                asin,
                str(daily_budget),
                duration_days,
            )
        except (TypeError, AttributeError, ValueError) as e:
            logger.error(
                f"Error handling RunMarketingCampaignCommand {getattr(event, 'event_id', 'unknown')}: {e}",
                exc_info=True,
            )

    async def _on_tick(self, event: TickEvent) -> None:
        try:
            self._current_tick = int(getattr(event, "tick_number", self._current_tick))
            await self.process_tick()
        except (TypeError, AttributeError, ValueError) as e:
            logger.error(
                f"Error processing TickEvent in MarketingService: {e}", exc_info=True
            )

    async def process_tick(self) -> None:
        """
        Process active campaigns: spend daily budgets, publish AdSpendEvent,
        and update world_store marketing visibility with decay and bounded increment.
        """
        if not self._campaigns:
            return

        finished: List[str] = []
        for campaign_id, camp in list(self._campaigns.items()):
            if camp.remaining_days <= 0 or camp.remaining_budget.cents <= 0:
                finished.append(campaign_id)
                continue

            # Spend for this tick
            spend_cents = min(camp.daily_budget.cents, camp.remaining_budget.cents)
            spend = Money(spend_cents)

            # Simple exposure model
            dollars = spend.cents / 100.0
            clicks = int(max(0, dollars / self.default_click_cpc_dollars))
            impressions = int(max(0, clicks / self.assumed_ctr))

            # Emit AdSpendEvent
            ad_event = AdSpendEvent(
                event_id=f"adspend_{camp.asin}_{campaign_id}_{self._current_tick}",
                timestamp=datetime.now(),
                asin=camp.asin,
                campaign_id=campaign_id,
                spend=spend,
                clicks=clicks,
                impressions=impressions,
            )
            await self.event_bus.publish(ad_event)

            # Update marketing visibility in WorldStore
            current_vis = 1.0
            try:
                current_vis = float(
                    self.world_store.get_marketing_visibility(camp.asin)
                )
            except (TypeError, AttributeError):
                current_vis = 1.0

            # Effect increment from this tick's spend
            effect_incr = 1.0 + (self.alpha_per_dollar * dollars)
            # Retain portion of previous effect (above baseline 1.0)
            new_vis = 1.0 + (self.retention * (current_vis - 1.0)) + (effect_incr - 1.0)
            try:
                self.world_store.set_marketing_visibility(camp.asin, new_vis)
            except (TypeError, AttributeError, ValueError) as e:
                logger.error(
                    f"Failed to set marketing visibility for {camp.asin}: {e}",
                    exc_info=True,
                )

            # Decrement campaign counters
            camp.remaining_budget = Money(camp.remaining_budget.cents - spend.cents)
            camp.remaining_days -= 1
            if camp.remaining_days <= 0 or camp.remaining_budget.cents <= 0:
                finished.append(campaign_id)

            logger.info(
                "MarketingService tick processed: asin=%s campaign=%s spend=%s clicks=%d impressions=%d vis=%.3f->%.3f",
                camp.asin,
                campaign_id,
                str(spend),
                clicks,
                impressions,
                current_vis,
                new_vis,
            )

        # Cleanup finished
        for cid in finished:
            self._campaigns.pop(cid, None)

    # Introspection helpers
    def get_active_campaigns(self) -> List[Dict[str, object]]:
        return [
            {
                "campaign_id": c.campaign_id,
                "asin": c.asin,
                "daily_budget_cents": c.daily_budget.cents,
                "remaining_days": c.remaining_days,
                "remaining_budget_cents": c.remaining_budget.cents,
            }
            for c in self._campaigns.values()
        ]

    def get_current_tick(self) -> int:
        return self._current_tick
