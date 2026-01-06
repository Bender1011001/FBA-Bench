"""
MarketSimulationService

Initial coherent world model step for FBA-Bench.
- Listens to SetPriceCommand and CompetitorPricesUpdated events
- Computes demand/sales using a simple, stateful model OR customer agent pool
- Publishes SaleOccurred and updates inventory via InventoryUpdate

**NEW**: Supports agent-based shopping mode with utility-based customer decisions.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from money import Money
from collections import deque

from fba_bench_core.domain.market.customer import Customer, CustomerPool
from services.trust_score_service import TrustScoreService
from services.world_store import WorldStore
from fba_events.bus import EventBus, get_event_bus
from fba_events.competitor import CompetitorPricesUpdated
from fba_events.inventory import InventoryUpdate
from fba_events.pricing import SetPriceCommand
from fba_events.sales import SaleOccurred

logger = logging.getLogger(__name__)


@dataclass
class CompetitorSnapshot:
    asin: str
    price: Money
    bsr: Optional[int] = None
    sales_velocity: Optional[float] = None


class MarketSimulationService:
    """
    Stateful demand/sales simulation with optional agent-based mode.

    Demand model (elasticity mode - default):
      demand = base_demand * (p / p_ref)^(-elasticity)
      where p_ref = min(average competitor price, previous known price), if available
      If no competitor data is available, use the last known canonical price as p_ref.

    Agent-based mode (new):
      - Customer pool is sampled each tick
      - Each customer evaluates products using utility function
      - Purchases based on utility threshold
      - More realistic purchasing patterns

    - units_sold = min(demand, inventory)
    - revenue = units_sold * price
    - fees: initially set to $0.00 (can be integrated with FeeCalculationService later)
    - profit = revenue - fees - cost_basis * units_sold
    - publishes SaleOccurred and updates inventory via InventoryUpdate
    """

    def __init__(
        self,
        world_store: WorldStore,
        event_bus: Optional[EventBus] = None,
        base_demand: int = 100,
        demand_elasticity: float = 1.5,
        # Agent-based mode parameters
        use_agent_mode: bool = False,
        customers_per_tick: int = 100,
        customer_seed: Optional[int] = None,
    ) -> None:
        self.world_store = world_store
        self.event_bus = event_bus or get_event_bus()
        self.base_demand = base_demand
        self.demand_elasticity = demand_elasticity

        # Agent-based mode configuration
        self._use_agent_mode = use_agent_mode
        self._customers_per_tick = customers_per_tick
        self._customer_seed = customer_seed
        self._customer_pool: Optional[CustomerPool] = None
        self._rng = random.Random(customer_seed)
        
        if use_agent_mode:
            self._customer_pool = CustomerPool.generate(
                count=customers_per_tick * 10,  # Pool 10x for variety
                seed=customer_seed,
            )

        # Internal caches
        self._competitors_by_asin: Dict[str, deque[CompetitorSnapshot]] = {}
        self._price_reference_by_asin: Dict[str, Money] = {}

        # Services
        self._trust_service = TrustScoreService()

        # Control flags
        self._started = False
        
        # Statistics for agent mode
        self._agent_stats = {
            "total_customers_served": 0,
            "total_purchases": 0,
            "purchase_rate": 0.0,
        }


    async def start(self) -> None:
        """Subscribe to relevant events."""
        if self._started:
            return
        await self.event_bus.subscribe(SetPriceCommand, self._on_set_price_command)
        await self.event_bus.subscribe(
            CompetitorPricesUpdated, self._on_competitor_prices_updated
        )
        self._started = True
        logger.info("MarketSimulationService started and subscribed to events.")

    async def _on_competitor_prices_updated(
        self, event: CompetitorPricesUpdated
    ) -> None:
        """Update competitor cache on incoming updates."""
        try:
            updated: List[CompetitorSnapshot] = []
            for comp in getattr(event, "competitors", []):
                # comp has fields: asin, price (Money), bsr, sales_velocity
                updated.append(
                    CompetitorSnapshot(
                        asin=comp.asin,
                        price=comp.price,
                        bsr=getattr(comp, "bsr", None),
                        sales_velocity=getattr(comp, "sales_velocity", None),
                    )
                )
            # We don't know mapping from product ASIN -> competitor list here; this event likely contains many competitor ASINs.
            # For simplicity, we bucket by each competitor's ASIN (downstream can map as needed).
            # If the target product ASIN equals competitor.asin, it represents alternate sellers on same listing;
            # otherwise it represents related SKUs/close substitutes (future refinement).
            for comp in updated:
                if comp.asin not in self._competitors_by_asin:
                    self._competitors_by_asin[comp.asin] = deque(maxlen=25)
                self._competitors_by_asin[comp.asin].append(comp)
        except (TypeError, AttributeError, ValueError) as e:
            logger.error(f"Error handling CompetitorPricesUpdated: {e}", exc_info=True)

    async def _on_set_price_command(self, event: SetPriceCommand) -> None:
        """
        Hook for awareness. WorldStore arbitrates and applies prices.
        We don't compute sales directly here because WorldStore must first update the canonical price.
        Scenarios can explicitly call process_for_asin after publishing to sequence the tick deterministically.
        """
        # No-op here; orchestration via scenario.tick calls process_for_asin

    def _compute_price_reference(self, asin: str, current_price: Money) -> Money:
        """
        Determine reference price p_ref for demand calculation:
        - If competitors known for this ASIN: use min(avg competitor price, current reference)
        - Else use cached reference or fall back to current canonical price
        """
        ref = self._price_reference_by_asin.get(asin)
        if ref is None:
            ref = current_price

        comps = self._competitors_by_asin.get(asin, [])
        if comps:
            # Use average competitor price across most recent snapshots for this ASIN
            # Consider last up to 10 snapshots for smoothing
            # Deque doesn't support slicing directly, but is efficient to iterate
            window = list(comps)[-10:]
            if window:
                avg_cents = sum(c.price.cents for c in window) / len(window)
                avg_price = Money(int(round(avg_cents)))
                # Reference is min of prior ref and avg competitor (aggressive market pressure)
                ref = avg_price if avg_price.cents < ref.cents else ref

        # Cache and return
        self._price_reference_by_asin[asin] = ref
        return ref

    def _safe_div(self, a: float, b: float, default: float = 1.0) -> float:
        try:
            if b <= 0.0:
                return default
            return a / b
        except (TypeError, AttributeError, ZeroDivisionError):
            return default

    def _demand(self, price: Money, ref_price: Money) -> int:
        """
        Compute integer units demanded with elasticity.
        demand = base_demand * (p / p_ref)^(-elasticity)
        """
        from decimal import Decimal
        
        p = Decimal(price.cents) / Decimal("100.0")
        p_ref = Decimal(ref_price.cents) / Decimal("100.0")
        
        try:
            if p_ref <= 0:
                ratio = Decimal("1.0")
            else:
                ratio = p / p_ref
        except (TypeError, ValueError, ZeroDivisionError):
             ratio = Decimal("1.0")

        # clamp ratio to avoid extremes
        if ratio <= Decimal("0.0"):
            ratio = Decimal("0.01")
            
        # Power function with Decimal: x**y where y is float is supported but keeping y as Decimal is better if possible.
        # However, demand_elasticity is likely float.
        # Decimal(ratio) ** Decimal(float) is valid.
        
        elasticity = Decimal(str(self.demand_elasticity))
        quantity = Decimal(self.base_demand) * (ratio ** (-elasticity))
        # integer demand
        return max(0, int(round(quantity)))

    def _demand_agent_based(
        self,
        price: Money,
        product_data: Dict[str, Any],
    ) -> int:
        """
        Compute demand using customer agent pool.
        
        Each customer evaluates the product using their utility function
        and decides whether to purchase based on their threshold.
        
        Args:
            price: Current product price.
            product_data: Dict with reviews, shipping_days, review_count.
            
        Returns:
            Number of units demanded by customer pool.
        """
        if not self._customer_pool:
            return 0
        
        # Sample customers for this tick
        pool_size = len(self._customer_pool)
        sample_size = min(self._customers_per_tick, pool_size)
        
        # Get random sample of customers (deterministic with seed)
        sample_indices = self._rng.sample(range(pool_size), sample_size)
        sampled_customers = [self._customer_pool[i] for i in sample_indices]
        
        # Build product offering
        product_offering = {
            "price": float(price.cents) / 100.0,
            "reviews": product_data.get("reviews", 4.0),
            "shipping_days": product_data.get("shipping_days", 3),
            "review_count": product_data.get("review_count", 100),
            "sku": product_data.get("asin", "unknown"),
        }
        
        # Count purchases
        purchases = 0
        for customer in sampled_customers:
            self._agent_stats["total_customers_served"] += 1
            
            # Check if customer can afford and wants to buy
            if not customer.can_afford(product_offering["price"]):
                continue
            
            utility = customer.calculate_utility(
                price=product_offering["price"],
                reviews=product_offering["reviews"],
                shipping_days=product_offering["shipping_days"],
                review_count=product_offering["review_count"],
            )
            
            if customer.will_purchase(utility):
                purchases += 1
                self._agent_stats["total_purchases"] += 1
        
        # Update purchase rate
        if self._agent_stats["total_customers_served"] > 0:
            self._agent_stats["purchase_rate"] = (
                self._agent_stats["total_purchases"] /
                self._agent_stats["total_customers_served"]
            )
        
        return purchases

    def set_agent_mode(
        self,
        enabled: bool,
        customers_per_tick: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> None:
        """Enable or disable agent-based demand mode.
        
        Args:
            enabled: Whether to use agent-based mode.
            customers_per_tick: Number of customers to sample per tick.
            seed: Random seed for deterministic sampling.
        """
        self._use_agent_mode = enabled
        
        if customers_per_tick is not None:
            self._customers_per_tick = customers_per_tick
        
        if seed is not None:
            self._customer_seed = seed
            self._rng = random.Random(seed)
        
        if enabled and self._customer_pool is None:
            self._customer_pool = CustomerPool.generate(
                count=self._customers_per_tick * 10,
                seed=self._customer_seed,
            )
        
        logger.info(
            "Agent mode %s: customers_per_tick=%d",
            "enabled" if enabled else "disabled",
            self._customers_per_tick,
        )

    def get_agent_stats(self) -> Dict[str, Any]:
        """Return agent-mode statistics."""
        return {
            **self._agent_stats,
            "agent_mode_enabled": self._use_agent_mode,
            "pool_size": len(self._customer_pool) if self._customer_pool else 0,
            "customers_per_tick": self._customers_per_tick,
        }

    async def process_for_asin(self, asin: str) -> None:
        """
        Execute market simulation for a single ASIN for the current tick:
        - Read canonical price and inventory from WorldStore
        - Compute demand and realized sales
        - Publish SaleOccurred
        - Update inventory via InventoryUpdate
        """
        try:
            product = self.world_store.get_product_state(asin)
            if not product:
                logger.debug(
                    f"No product state for ASIN {asin}, skipping market processing."
                )
                return

            current_price = product.price
            ref_price = self._compute_price_reference(asin, current_price)

            # Marketing visibility multiplier from WorldStore (default 1.0)
            marketing_multiplier = 1.0
            if hasattr(self.world_store, "get_marketing_visibility"):
                try:
                    marketing_multiplier = float(
                        self.world_store.get_marketing_visibility(asin)
                    )
                except (TypeError, AttributeError, ValueError, KeyError):
                    marketing_multiplier = 1.0

            # Calculate demand based on mode
            if self._use_agent_mode:
                # Agent-based mode: customers evaluate product using utility function
                product_data = {
                    "asin": asin,
                    "reviews": 4.0,  # Default
                    "shipping_days": 3,  # Default FBA
                    "review_count": 100,
                }
                # Extract review data from product metadata if available
                if hasattr(product, "metadata") and isinstance(product.metadata, dict):
                    md = product.metadata
                    product_data["reviews"] = float(md.get("review_rating", 4.0) or 4.0)
                    product_data["review_count"] = int(md.get("review_count", 100) or 100)
                    product_data["shipping_days"] = int(md.get("shipping_days", 3) or 3)
                
                units_demanded_raw = self._demand_agent_based(current_price, product_data)
                # Marketing multiplier affects how many customers see the product
                units_demanded = max(
                    0, int(round(units_demanded_raw * max(0.0, marketing_multiplier)))
                )
            else:
                # Elasticity formula mode (original)
                units_demanded_raw = self._demand(current_price, ref_price)
                units_demanded = max(
                    0, int(round(units_demanded_raw * max(0.0, marketing_multiplier)))
                )
            
            inventory_qty = self.world_store.get_product_inventory_quantity(asin)
            units_sold = min(units_demanded, max(0, inventory_qty))


            revenue = current_price * units_sold
            total_fees = Money.zero()  # integrate FeeCalculationService later
            # WorldStore returns per-unit average cost basis as Money; enforce consistent Money usage
            cost_basis = self.world_store.get_product_cost_basis(asin)
            total_cost = cost_basis * units_sold

            total_profit = Money(revenue.cents - total_fees.cents - total_cost.cents)

            # Compute trust score using TrustScoreService with available metadata (robust defaults)
            violations = 0
            feedback: List[float] = []
            total_days = 1
            if hasattr(product, "metadata") and isinstance(product.metadata, dict):
                md = product.metadata
                violations = int(md.get("violations_count", 0) or 0)
                raw_fb = md.get("buyer_feedback_scores", [])
                if isinstance(raw_fb, list):
                    # Keep only numeric values within 0..5 range
                    feedback = [float(x) for x in raw_fb if isinstance(x, (int, float))]
                    feedback = [max(0.0, min(5.0, x)) for x in feedback]
                total_days = int(
                    md.get("total_days_observed", total_days) or total_days
                )

            raw_trust = float(
                self._trust_service.calculate_trust_score(
                    violations_count=violations,
                    buyer_feedback_scores=feedback,
                    total_days=total_days,
                )
            )
            # Normalize to [0.0, 1.0] as required by SaleOccurred validation
            try:
                min_s = float(getattr(self._trust_service, "min_score", 0.0))
                max_s = float(getattr(self._trust_service, "max_score", 100.0))
                denom = (max_s - min_s) if (max_s - min_s) != 0 else 100.0
                trust_score = max(0.0, min(1.0, (raw_trust - min_s) / denom))
            except (TypeError, AttributeError, ZeroDivisionError, ValueError):
                # Conservative fallback
                trust_score = max(0.0, min(1.0, raw_trust / 100.0))
            # BSR: derive from metadata if present; otherwise estimate from demand proxy
            if (
                hasattr(product, "metadata")
                and isinstance(product.metadata, dict)
                and "bsr" in product.metadata
            ):
                bsr = int(product.metadata.get("bsr") or 1000)
            else:
                # Simple heuristic: higher demand -> better (lower) BSR within a bounded range
                # Map units_demanded to a rank in [100, 200000]
                max_rank = 200_000
                min_rank = 100
                demand_clamped = max(0, min(units_demanded, 10_000))
                # Inverse proportion; add 1 to avoid div-by-zero
                bsr = int(
                    max(
                        min_rank,
                        min(
                            max_rank,
                            max_rank
                            - (demand_clamped * (max_rank - min_rank) // 10_000),
                        ),
                    )
                )

            sale = SaleOccurred(
                event_id=f"sale_{asin}_{int(datetime.now().timestamp()*1000)}",
                timestamp=datetime.now(),
                asin=asin,
                units_sold=units_sold,
                units_demanded=units_demanded,
                unit_price=current_price,
                total_revenue=revenue,
                total_fees=total_fees,
                total_profit=total_profit,
                cost_basis=total_cost,
                trust_score_at_sale=float(trust_score),
                bsr_at_sale=int(bsr),
                conversion_rate=(
                    (float(units_sold) / float(units_demanded))
                    if units_demanded > 0
                    else 0.0
                ),
                fee_breakdown={},
                market_conditions={
                    "reference_price": str(ref_price),
                    "elasticity": self.demand_elasticity,
                    "base_demand": self.base_demand,
                },
                customer_segment=None,
            )
            inv_update = InventoryUpdate(
                event_id=f"inv_{asin}_{int(datetime.now().timestamp()*1000)}",
                timestamp=datetime.now(),
                asin=asin,
                new_quantity=inventory_qty - units_sold,
                previous_quantity=inventory_qty,
                change_reason="sale",
                agent_id=product.last_agent_id if product else None,
            )

            # Parallelize event publishing for performance
            await asyncio.gather(
                self.event_bus.publish(sale),
                self.event_bus.publish(inv_update)
            )

            logger.info(
                f"MarketSimulationService processed ASIN {asin}: price={current_price}, "
                f"demand={units_demanded}, sold={units_sold}, revenue={revenue}"
            )

        except (TypeError, AttributeError, RuntimeError) as e:
            logger.error(
                f"Error in MarketSimulationService.process_for_asin for {asin}: {e}",
                exc_info=True,
            )
