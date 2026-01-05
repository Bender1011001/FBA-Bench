"""
Product Sourcing Skill Module for FBA-Bench Multi-Domain Agent Architecture.

This skill is designed to bootstrap a greenfield operation by deciding on an initial
purchase order using a supplier catalog. It analyses simple margin heuristics and
emits a coordinated 'place_order' action for arbitration by the MultiDomainController.

Integration notes:
- Reads supplier catalog from WorldStore (set via WorldStore.set_supplier_catalog()).
- Publishes no events directly; instead, generates a SkillAction consumed by the coordinator.
- Uses a configurable initial investment budget in cents (config['initial_investment_cents']),
  defaulting to $2,500 if not provided.
"""

from __future__ import annotations

import logging
from math import floor
from typing import Any, Dict, List, Optional

from money import Money

# WorldStore global accessor (read-only usage for catalog)
from services.world_store import get_world_store
from fba_events.base import BaseEvent
from fba_events.time_events import TickEvent

from .base_skill import BaseSkill, SkillAction, SkillContext

logger = logging.getLogger(__name__)


class ProductSourcingSkill(BaseSkill):
    """
    Product Sourcing Skill for initial procurement.

    Behavior:
    - Activates in the first simulation ticks (0 or 1).
    - Reads supplier catalog from WorldStore.
    - Scores products by a simple margin heuristic (estimate price as 3x cost).
    - Allocates a configurable portion of budget to purchase the best product.
    - Emits a 'place_order' SkillAction for coordination/arbitration.

    Config keys:
    - initial_investment_cents: int, default 250000 (i.e., $2,500)
    - investment_ratio: float in (0,1], default 0.75 (percentage of budget to invest)
    - max_units_cap: int, optional cap on purchased units (default 1000)
    """

    def get_supported_event_types(self) -> List[str]:
        """
        Optional helper for benchmarks/utilities that introspect supported event types.
        """
        return ["TickEvent"]

    def __init__(
        self, agent_id: str, event_bus, config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("ProductSourcing", agent_id, event_bus)
        self.config = config or {}
        self._has_emitted_initial_action: bool = False

        # Tunables
        self.initial_investment_cents: int = int(
            self.config.get("initial_investment_cents", 250_000)
        )  # $2,500
        self.investment_ratio: float = float(self.config.get("investment_ratio", 0.75))
        self.max_units_cap: int = int(self.config.get("max_units_cap", 1000))

        # Bound ratio
        if not (0.0 <= self.investment_ratio <= 1.0):
            self.investment_ratio = 0.75

        logger.info(
            "ProductSourcingSkill initialized: budget_cents=%d, invest_ratio=%.2f, max_units_cap=%d",
            self.initial_investment_cents,
            self.investment_ratio,
            self.max_units_cap,
        )

    async def process_event(self, event: BaseEvent) -> Optional[List[SkillAction]]:
        """
        Generate a single initial 'place_order' action at the start of the simulation.
        """
        try:
            if isinstance(event, TickEvent):
                tick = int(getattr(event, "tick_number", 0))
                if tick <= 1 and not self._has_emitted_initial_action:
                    action = await self._build_initial_po_action()
                    if action:
                        self._has_emitted_initial_action = True
                        return [action]
            return None
        except Exception as e:
            logger.error(
                "ProductSourcingSkill.process_event error: %s", e, exc_info=True
            )
            return None

    async def generate_actions(
        self, context: SkillContext, constraints: Dict[str, Any]
    ) -> List[SkillAction]:
        """
        Not used in the current flow. This skill is event-triggered on initial ticks.
        """
        return []

    def get_priority_score(self, event: BaseEvent) -> float:
        """
        High priority on bootstrap ticks to ensure early sourcing decision.
        """
        if isinstance(event, TickEvent):
            tick = int(getattr(event, "tick_number", 0))
            return 0.95 if tick <= 1 and not self._has_emitted_initial_action else 0.1
        return 0.1

    async def _build_initial_po_action(self) -> Optional[SkillAction]:
        """
        Build a 'place_order' SkillAction using the best-margin product from the supplier catalog.
        """
        world_store = get_world_store()  # uses global singleton
        if world_store is None:
            logger.warning(
                "WorldStore is not initialized; cannot source supplier catalog."
            )
            return None

        catalog_by_id: Dict[str, Any] = {}
        try:
            catalog_by_id = world_store.get_supplier_catalog() or {}
        except Exception as e:
            logger.warning("Failed to read supplier catalog from WorldStore: %s", e)

        # Convert to a list of supplier-product entries
        entries: List[Dict[str, Any]] = list(catalog_by_id.values())
        if not entries:
            logger.info("Supplier catalog empty; skipping initial sourcing.")
            return None

        # Score by simple margin heuristic: estimated_price = 3x unit_cost; margin = 2x unit_cost
        # Among ties, prefer higher reliability, then shorter lead time.
        def score(entry: Dict[str, Any]) -> tuple:
            try:
                unit_cost = float(entry.get("unit_cost", 0.0))
                reliability = float(entry.get("reliability", 0.0))
                lead_time = int(entry.get("lead_time", 0))
                # Higher score is better; lower lead time preferred (negative for sorting)
                return (unit_cost * 2.0, reliability, -lead_time)
            except Exception:
                return (0.0, 0.0, 0)

        best = max(entries, key=score, default=None)
        if not best:
            logger.info("No suitable product found in supplier catalog.")
            return None

        supplier_id = str(best.get("supplier_id", "")).strip()
        product_id = str(
            best.get("product_id", "")
        ).strip()  # Use as ASIN in our system
        product_name = str(best.get("product_name", "")).strip()
        try:
            unit_cost = float(best.get("unit_cost", 0.0))
        except Exception:
            unit_cost = 0.0

        if not supplier_id or not product_id or unit_cost <= 0.0:
            logger.warning(
                "Invalid catalog entry for initial sourcing; skipping. Entry=%s", best
            )
            return None

        invest_cents = int(self.initial_investment_cents * self.investment_ratio)
        if invest_cents <= 0:
            logger.info("No budget available to invest; skipping initial sourcing.")
            return None

        # Compute units to buy; clamp by max_units_cap to avoid oversizing
        units_to_buy = max(0, floor((invest_cents / 100.0) / unit_cost))
        units_to_buy = min(units_to_buy, self.max_units_cap)
        if units_to_buy <= 0:
            logger.info(
                "Budget too small for unit_cost=%.2f; skipping initial sourcing.",
                unit_cost,
            )
            return None

        total_spend_cents = int(round(units_to_buy * unit_cost * 100.0))
        action_budget = Money(total_spend_cents)

        # Build parameters for downstream PlaceOrderCommand publication
        params: Dict[str, Any] = {
            "supplier_id": supplier_id,
            "asin": product_id,  # WorldStore expects ASIN semantics; we map product_id -> asin for consistency
            "quantity": int(units_to_buy),
            # Use string Money to match integration pattern (Money(str) constructor support)
            "max_price": Money.from_dollars(f"{unit_cost:.2f}"),
            "product_name": product_name or product_id,
        }

        reasoning = (
            f"Initial sourcing: '{product_name or product_id}' from supplier '{supplier_id}' "
            f"at unit_cost=${unit_cost:.2f}. Investing ${invest_cents/100:.2f} to buy {units_to_buy} units "
            f"(total spend=${total_spend_cents/100:.2f})."
        )

        # Estimate simple profit improvement signal for prioritization
        estimated_market_price = unit_cost * 3.0
        estimated_profit_per_unit = max(0.0, estimated_market_price - unit_cost)
        expected_profit_total = estimated_profit_per_unit * units_to_buy

        action = SkillAction(
            action_type="place_order",
            parameters=params,
            confidence=0.8,
            reasoning=reasoning,
            priority=0.9,  # High priority at bootstrap
            resource_requirements={
                "budget": action_budget.cents  # Coordinator accepts int cents or Money
            },
            expected_outcome={
                "inventory_increase": float(units_to_buy),
                "profit_improvement": float(expected_profit_total),
            },
            skill_source=self.skill_name,
        )
        return action
