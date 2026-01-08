"""
Advanced heuristic-based agent optimized for FBA-Bench scenarios.

This agent implements robust, production-grade pricing logic designed to perform
well across a variety of benchmark scenarios without relying on external LLMs.

It consumes a lightweight configuration dict (as created by the Pydantic
AgentConfig used in the unified agent factory) and exposes an async `decide`
method compatible with DIYAdapter in the unified agent system.

Key behaviors:
- Competitive pricing: undercut or match nearest competitor within safe bounds
- Margin protection: never price below cost floor (configurable margin)
- Demand-aware adjustments: react to recent demand signals and inventory levels
- Smoothing: limit per-tick price changes to avoid oscillation

Integration points:
- Unified agent factory creates this agent when DIY `agent_type` is "advanced"
  [AgentFactory._create_diy_agent()](benchmarking/agents/unified_agent.py:911)
- DIYAdapter converts returned ToolCall objects to AgentAction
  [DIYAdapter.decide()](benchmarking/agents/unified_agent.py:657)
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Core runner protocol types (canonical for DIY agents)
from fba_bench.core.types import SimulationState, ToolCall

from config.model_config import get_model_params
from .base import BaseAgent


# Backwards-compat lightweight AgentConfig expected by some tests
@dataclass
class AgentConfig:
    agent_id: str
    target_asin: str = "B0DEFAULT"


logger = logging.getLogger(__name__)


@dataclass
class PriceMemory:
    """Tracks recent demand and price decisions for smoothing and trend detection."""

    demand_history: deque = field(default_factory=lambda: deque(maxlen=30))
    price_history: deque = field(default_factory=lambda: deque(maxlen=30))
    last_price: Optional[float] = None

    def push(self, demand: float, price: float) -> None:
        self.demand_history.append(float(max(demand, 0.0)))
        self.price_history.append(float(max(price, 0.0)))
        self.last_price = price

    def avg_demand(self, window: int = 7) -> float:
        if not self.demand_history:
            return 0.0
        if window <= 0:
            window = len(self.demand_history)
        items = list(self.demand_history)[-window:]
        return sum(items) / max(len(items), 1)

    def avg_price(self, window: int = 7) -> float:
        if not self.price_history:
            return 0.0
        if window <= 0:
            window = len(self.price_history)
        items = list(self.price_history)[-window:]
        return sum(items) / max(len(items), 1)


class AdvancedAgent(BaseAgent):
    """
    Advanced heuristic agent for FBA-Bench DIY framework.

    Expected construction path:
      agent = AdvancedAgent(config_dict)

    Where config_dict typically comes from PydanticAgentConfig.dict():
      {
        "framework": "diy",
        "parameters": {
          "agent_type": "advanced",
          "target_asin": "B0DEFAULT",
          "min_margin": 0.12,
          "undercut": 0.01,
          "max_change_pct": 0.15,
          "price_sensitivity": 0.10,
          "reaction_speed": 1,
          "inventory_low_threshold": 10,
          "inventory_target": 100
        },
        ...
      }

    The agent returns a list[ToolCall] where each ToolCall has:
      - tool_name: "set_price"
      - parameters: {"asin": str, "price": float}
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        budget_enforcer: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        **kwargs,
    ) -> None:
        # Support both patterns:
        # 1. AdvancedAgent(config_dict) - existing pattern for DIY framework
        # 2. AdvancedAgent(agent_id=..., budget_enforcer=..., event_bus=...) - metering test pattern

        if config is None and agent_id is not None:
            # Pattern 2: Direct keyword arguments
            self._raw_config = kwargs
            params = kwargs
            self.agent_id = agent_id
            self.budget_enforcer = budget_enforcer
            self.event_bus = event_bus
        else:
            # Pattern 1: Config dict (existing behavior)
            self._raw_config = config or {}
            params = (
                (self._raw_config.get("parameters") or {})
                if isinstance(self._raw_config, dict)
                else {}
            )
            # Core parameters with robust defaults
            self.agent_id: str = (
                agent_id
                or params.get("agent_id")
                or self._raw_config.get("id")
                or self._raw_config.get("agent_id")
                or "advanced_agent"
            )
            self.budget_enforcer = budget_enforcer
            self.event_bus = event_bus
        
        # Ensure base class is initialized
        super().__init__(self.agent_id, self.event_bus)
        
        self.target_asin: str = params.get("target_asin", "B0DEFAULT")

        # Centralized model params
        self._mp = get_model_params().advanced_agent

        # Pricing controls
        self.min_margin: float = float(
            params.get("min_margin", self._mp.min_margin)
        )  # minimum margin over cost
        self.undercut: float = float(
            params.get("undercut", self._mp.undercut)
        )  # undercut competitor
        self.max_change_pct: float = float(
            params.get("max_change_pct", self._mp.max_change_pct)
        )  # limit per-tick price change
        self.price_sensitivity: float = float(
            params.get("price_sensitivity", self._mp.price_sensitivity)
        )  # demand elasticity heuristic

        # Inventory-aware behavior
        self.reaction_speed: float = float(
            params.get("reaction_speed", self._mp.reaction_speed)
        )  # amplify/dampen adjustments
        self.days_of_supply_target: int = int(
            params.get("days_of_supply_target", 14)
        )  # Target 14 days of stock
        self.days_of_supply_low_threshold: int = int(
            params.get("days_of_supply_low_threshold", 5)
        )  # Raise price if stock is less than 5 days

        # Legacy inventory target for backward compatibility
        self.inventory_target: int = int(
            params.get("inventory_target", 100)
        )  # Default target inventory level

        # Tunables for inventory pressure and demand fallback
        self.inventory_up_pressure: float = float(
            params.get("inventory_up_pressure", 0.15)
        )  # upward price pressure when low inventory
        self.inventory_down_pressure: float = float(
            params.get("inventory_down_pressure", -0.10)
        )  # downward pressure when overstocked
        self.baseline_demand: float = float(
            params.get("baseline_demand", 1.0)
        )  # safe baseline when signals missing

        # Internal memory per ASIN
        self._mem: Dict[str, PriceMemory] = {}

        # Lifecycle flags
        self._initialized: bool = False
        self._shutdown: bool = False

        # Validate parameters sanity
        if self.min_margin < 0.0:
            self.min_margin = 0.0
        if self.undercut < 0.0:
            self.undercut = 0.0
        if self.max_change_pct <= 0.0:
            self.max_change_pct = 0.10

        logger.info(
            f"AdvancedAgent[{self.agent_id}] configured for ASIN={self.target_asin} "
            f"min_margin={self.min_margin} undercut={self.undercut} "
            f"max_change_pct={self.max_change_pct} price_sensitivity={self.price_sensitivity}"
        )

    # Optional sync initialize for DIYAdapter compatibility
    def initialize(self) -> None:
        self._initialized = True
        self._shutdown = False
        logger.info(f"AdvancedAgent[{self.agent_id}] initialized")

    # Optional async initialize if called by adapter
    async def _async_initialize(self) -> None:
        self.initialize()

    # Optional reset hook
    def reset(self) -> None:
        self._mem.clear()
        logger.info(f"AdvancedAgent[{self.agent_id}] reset state")

    # Optional shutdown hook
    def shutdown(self) -> None:
        self._shutdown = True
        logger.info(f"AdvancedAgent[{self.agent_id}] shutdown")

    def get_config(self) -> Dict[str, Any]:
        """Return the agent's configuration."""
        return self._raw_config

    # Core decision API expected by DIYAdapter
    async def decide(self, state: SimulationState) -> List[ToolCall]:
        """
        Compute next action(s) as ToolCalls. Primary action is "set_price".

        Robustness: Works with partial state information. If required data is missing,
        falls back to safe, conservative adjustments and never prices below a reasonable floor.
        """
        if not self._initialized:
            # Support both sync and async init patterns
            if asyncio.iscoroutinefunction(self._async_initialize):
                await self._async_initialize()
            else:
                self.initialize()

        asin = self._resolve_target_asin(state)
        product = self._extract_product(state, asin)
        current_price = self._get_current_price(product)
        cost = self._get_cost(product, fallback_ratio=0.6, fallback_price=current_price)
        floor_price = max(cost * (1.0 + self.min_margin), 0.01)

        competitor_price = self._estimate_competitor_price(
            product, default=current_price or max(floor_price, 1.0)
        )
        demand = self._estimate_recent_demand(state, asin, product)
        inventory = self._get_inventory(product)

        # Initialize memory for ASIN
        mem = self._mem.setdefault(asin, PriceMemory())

        # Derive target price using a composite heuristic:
        # 1) Start from competitive anchor (competitor - undercut) but respect floor
        # 2) Adjust by demand and inventory pressure
        # 3) Smooth by limiting per-tick change from last known price
        anchor_price = max(competitor_price * (1.0 - self.undercut), floor_price)

        demand_factor = self._compute_demand_factor(
            demand, mem.avg_demand(self._mp.demand_avg_window)
        )
        avg_daily_demand = max(
            mem.avg_demand(window=7), 0.1
        )  # Use 7-day avg demand, with a minimum to avoid division by zero
        inventory_factor = self._compute_inventory_factor(inventory, avg_daily_demand)

        # Reaction scaling
        adjustment_multiplier = 1.0 + (self.price_sensitivity * self.reaction_speed) * (
            demand_factor + inventory_factor
        )
        raw_target = max(anchor_price * adjustment_multiplier, floor_price)

        # Smooth against last price when available
        target_price = self._smooth_price(
            raw_target, reference_price=(mem.last_price or current_price or raw_target)
        )

        # Book-keeping: record current demand and target price
        mem.push(demand=demand, price=target_price)

        # Ensure final sanity: price should be at least the floor price
        final_price = max(round(float(target_price), 2), round(floor_price, 2))

        days_of_supply = inventory / avg_daily_demand if avg_daily_demand > 0 else 0
        logger.debug(
            f"AdvancedAgent[{self.agent_id}] asin={asin} "
            f"current={current_price} competitor={competitor_price} cost={cost} floor={floor_price} "
            f"demand={demand} inv={inventory} days_supply={days_of_supply:.2f} "
            f"anchor={anchor_price} adj_mult={adjustment_multiplier:.3f} "
            f"raw_target={raw_target} smoothed={target_price} final={final_price}"
        )

        # If price is unchanged and we lack sufficient signal to adjust, we still emit the command
        # to keep the control loop explicit.
        return [
            ToolCall(
                tool_name="set_price",
                parameters={"asin": asin, "price": final_price},
                confidence=self._compute_confidence(current_price, final_price, demand),
                reasoning=self._build_reasoning(
                    asin=asin,
                    current_price=current_price,
                    competitor_price=competitor_price,
                    floor=floor_price,
                    demand=demand,
                    inventory=inventory,
                    target=final_price,
                ),
                priority=1,
            )
        ]

    # -----------------------
    # Heuristic subroutines
    # -----------------------

    def _resolve_target_asin(self, state: SimulationState) -> str:
        if self.target_asin and self.target_asin != "B0DEFAULT":
            return self.target_asin
        # Fallback to first product asin if available
        if state.products:
            first = state.products[0]
            asin = first.get("asin") or first.get("ASIN") or self.target_asin
            return asin or self.target_asin
        return self.target_asin

    def _extract_product(self, state: SimulationState, asin: str) -> Dict[str, Any]:
        # Attempt to find the product matching ASIN
        for p in state.products or []:
            if (p.get("asin") or p.get("ASIN")) == asin:
                return p
        # If not found, return an empty dict with minimal defaults
        return {"asin": asin}

    def _get_current_price(self, product: Dict[str, Any]) -> Optional[float]:
        price = (
            product.get("price")
            or product.get("current_price")
            or product.get("our_price")
        )
        try:
            return float(price) if price is not None else None
        except (TypeError, ValueError):
            return None

    def _get_cost(
        self,
        product: Dict[str, Any],
        fallback_ratio: float,
        fallback_price: Optional[float],
    ) -> float:
        cost = product.get("cost") or product.get("unit_cost") or product.get("COGS")
        try:
            return (
                float(cost)
                if cost is not None
                else float(fallback_price or 10.0) * float(fallback_ratio)
            )
        except (TypeError, ValueError):
            return float(fallback_price or 10.0) * float(fallback_ratio)

    def _estimate_competitor_price(
        self, product: Dict[str, Any], default: float
    ) -> float:
        # Search common structures for competitor pricing
        competitors = product.get("competitors") or product.get("offers") or []
        prices: List[float] = []
        for c in competitors:
            # Common keys: price, offer_price, listing_price
            for key in ("price", "offer_price", "listing_price"):
                v = c.get(key)
                if v is not None:
                    try:
                        prices.append(float(v))
                    except (TypeError, ValueError):
                        continue
        if prices:
            # Return the lowest visible competitor price
            return max(min(prices), 0.01)
        # Fallback to any known market reference on the product
        market_price = product.get("market_price") or product.get("avg_market_price")
        try:
            if market_price is not None:
                return float(market_price)
        except (TypeError, ValueError):
            pass
        return max(float(default), 0.01)

    def _estimate_recent_demand(
        self, state: SimulationState, asin: str, product: Dict[str, Any]
    ) -> float:
        """
        Estimate recent demand using available signals:
        - Sum of units_sold in recent_events for the ASIN (canonical)
        - product-level demand field if present (fallback)
        - else small baseline to avoid zero-division
        """
        # 1. Prioritize canonical event data from recent_events
        total_units_sold = 0.0
        for evt in state.recent_events or []:
            # Check if the event is for the target ASIN
            if evt.get("asin") == asin or evt.get("ASIN") == asin:
                # Sum up units_sold if available and valid
                units_sold = evt.get("units_sold")
                if units_sold is not None:
                    try:
                        total_units_sold += float(units_sold)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Could not convert units_sold to float for ASIN {asin}: {units_sold}"
                        )
                        continue

        if (
            total_units_sold > 0.1
        ):  # Use a small threshold to consider significant demand
            return total_units_sold

        # 2. Fallback to product-level demand fields if event data is insufficient
        # These keys are checked in order of assumed reliability
        for key in ["demand", "recent_demand", "avg_daily_demand", "sales_velocity"]:
            product_demand = product.get(key)
            if product_demand is not None:
                try:
                    demand_value = float(product_demand)
                    if demand_value > 0.1:  # Use a small threshold
                        return demand_value
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert product demand '{key}' to float for ASIN {asin}: {product_demand}"
                    )
                    continue

        # 3. Return a stable baseline if no other significant signal is found
        # This prevents division by zero and ensures a default behavior.
        return float(
            self.baseline_demand
        )  # Configurable baseline demand if no data is available.

    def _get_inventory(self, product: Dict[str, Any]) -> int:
        inv = (
            product.get("inventory")
            or product.get("stock")
            or product.get("qty_on_hand")
        )
        try:
            return int(inv) if inv is not None else 100  # Default fallback inventory
        except (TypeError, ValueError):
            return 100  # Default fallback inventory

    def _compute_inventory_ratio(self, inventory: int) -> float:
        # Ratio < 1.0 indicates below target, > 1.0 above target
        target = max(self.inventory_target, 1)
        return float(inventory) / float(target)

    def _compute_demand_factor(self, demand_now: float, demand_avg: float) -> float:
        """
        Positive when demand_now > demand_avg (increase price), negative otherwise.
        Scales modestly to avoid overreaction.
        """
        # Explicit zero guard and near-zero guard to avoid division blowups
        if demand_avg == 0.0 or abs(demand_avg) < 1e-6:
            return 0.0
        delta = (float(demand_now) - float(demand_avg)) / float(demand_avg)
        # Clamp delta to avoid extreme price adjustments.
        delta = float(max(min(delta, 1.0), -1.0))  # Clamp between -1.0 and 1.0
        return delta * 0.5  # Scale down the factor to prevent overreactions

    def _compute_inventory_factor(
        self, current_inventory: int, avg_daily_demand: float
    ) -> float:
        """
        Calculates an inventory pressure factor based on "days of supply".
        - Returns a positive value (to increase price) if inventory is low.
        - Returns a negative value (to decrease price) if inventory is high.
        """
        # Guard against zero/near-zero demand
        if avg_daily_demand <= 0:
            return 0.0
        days_of_supply = float(current_inventory) / float(avg_daily_demand)

        if days_of_supply < float(self.days_of_supply_low_threshold):
            # Inventory is critically low, apply upward price pressure
            return float(self.inventory_up_pressure)
        elif days_of_supply > float(self.days_of_supply_target) * 2.0:
            # Inventory is excessive (more than 2x target), apply downward price pressure
            return float(self.inventory_down_pressure)
        return 0.0

    def _smooth_price(self, target: float, reference_price: float) -> float:
        """
        Limit the change relative to reference_price to +/- max_change_pct.
        """
        if reference_price is None or reference_price <= 0:
            return target
        max_up = reference_price * (1.0 + self.max_change_pct)
        max_down = reference_price * (1.0 - self.max_change_pct)
        return float(min(max(target, max_down), max_up))

    def _compute_confidence(
        self, current: Optional[float], new: float, demand: float
    ) -> float:
        """
        Higher confidence when demand is strong and adjustment is modest; lower when large swings.
        """
        if new <= 0:
            return 0.5
        if current is None or current <= 0:
            base = 0.7
            swing = 0.0
        else:
            rel_change = abs(new - current) / max(current, 1e-6)
            swing = max(0.0, 1.0 - min(rel_change / (self.max_change_pct + 1e-6), 1.0))
            base = 0.6 + 0.2 * swing
        demand_boost = min(
            math.log1p(max(demand, 0.0)) / float(self._mp.confidence_log_divisor),
            float(self._mp.confidence_demand_cap),
        )
        return float(max(min(base + demand_boost, 0.99), 0.5))

    def _build_reasoning(
        self,
        asin: str,
        current_price: Optional[float],
        competitor_price: float,
        floor: float,
        demand: float,
        inventory: int,
        target: float,
    ) -> str:
        return (
            f"ASIN={asin}; current={current_price}; competitor={competitor_price}; floor={floor}; "
            f"demand={demand}; inventory={inventory}; target={target}. "
            f"Price set to balance competition, margin floor, demand signal, and inventory pressure "
            f"with smoothing constraints."
        )

    async def meter_api_call(
        self,
        tool_name: str,
        tokens_prompt: int = 0,
        tokens_completion: int = 0,
        cost_cents: int = 0,
    ) -> Dict[str, Any]:
        """
        Meter API call usage through the budget enforcer.

        Args:
            tool_name: Name of the tool/API being called
            tokens_prompt: Number of prompt tokens used
            tokens_completion: Number of completion tokens used
            cost_cents: Cost in cents

        Returns:
            Dict with "exceeded" boolean indicating if budget was exceeded

        Raises:
            RuntimeError: If hard budget limit is exceeded
        """
        if self.budget_enforcer is None:
            # No budget enforcer available, return success
            return {"exceeded": False}

        try:
            # Forward to budget enforcer's meter_api_call method
            result = await self.budget_enforcer.meter_api_call(
                agent_id=self.agent_id,
                tool_name=tool_name,
                tokens_prompt=tokens_prompt,
                tokens_completion=tokens_completion,
                cost_cents=cost_cents,
            )

            # Check if budget was exceeded with hard failure
            if result.get("exceeded") and result.get("severity") == "hard_fail":
                budget_type = result.get("budget_type", "unknown")
                usage = result.get("usage", 0)
                limit = result.get("limit", 0)
                raise RuntimeError(
                    f"Budget exceeded for {budget_type}: usage {usage} > limit {limit}"
                )

            return result
        except RuntimeError:
            # Re-raise RuntimeError for hard budget violations
            raise
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            # Log other exceptions but don't fail the agent
            logger.warning(f"Error in meter_api_call for agent {self.agent_id}: {e}")
            return {"exceeded": False}
