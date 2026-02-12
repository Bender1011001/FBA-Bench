#!/usr/bin/env python3
"""
FBA-Bench Enterprise: PROPER Tick-Based Simulation with Feedback Loop

This is a REAL simulation where:
1. Each day is a separate LLM call
2. Agent sees results of previous decisions
3. State evolves based on actions
4. Agent learns from consequences

Model: Grok 4.1 Fast via OpenRouter
Duration: 2 years (730 days) 
Starting Capital: $10,000
"""

import asyncio
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient
from memory_experiments.reflective_memory_v1 import ReflectiveMemoryV1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TickSim")


# ============================================================================
# SIMULATION STATE
# ============================================================================

@dataclass
class Product:
    """A product in the catalog."""
    sku: str
    name: str
    cost: Decimal  # What we pay supplier
    price: Decimal  # Current selling price
    stock: int
    daily_demand_base: int  # Average units sold per day
    demand_multiplier: float = 1.0  # Modified by events
    rating: float = 4.5  # Product rating (affects demand)
    ad_boost: float = 1.0  # Effective marketing lift for today's demand
    next_day_ad_boost: float = 1.0  # Applied at next order generation
    
    def calculate_daily_demand(self, rng: random.Random) -> int:
        """Calculate actual demand for today with randomness."""
        base = self.daily_demand_base * self.demand_multiplier * max(0.2, self.ad_boost)
        # Rating affects demand: 5-star = 1.2x, 1-star = 0.4x
        rating_factor = 0.4 + (self.rating / 5.0) * 0.8
        adjusted = base * rating_factor
        # Add ±30% noise
        noise = rng.uniform(0.7, 1.3)
        return max(0, int(adjusted * noise))


@dataclass
class Order:
    """An incoming customer order."""
    order_id: str
    sku: str
    quantity: int
    max_price: Decimal  # Customer will only buy at or below this price


@dataclass 
class Competitor:
    """A competitor in the market."""
    name: str
    sku: str
    price: Decimal
    aggression: float  # 0-1, how likely to undercut


@dataclass
class AdversarialEvent:
    """An active adversarial event."""
    event_id: str
    event_type: str
    affected_sku: str
    severity: float
    days_remaining: int
    description: str


@dataclass
class SupplierOffer:
    """Supplier quote terms for a specific SKU."""
    supplier_id: str
    sku: str
    unit_cost: Decimal
    lead_time_days: int
    reliability: float
    min_order_qty: int


@dataclass
class PendingInboundOrder:
    """Inbound supplier order waiting for delivery."""
    po_id: str
    supplier_id: str
    sku: str
    quantity: int
    unit_cost: Decimal
    reliability: float
    days_until_arrival: int
    

@dataclass
class SimulationState:
    """Full state of the simulation."""
    day: int = 0
    capital: Decimal = Decimal("10000.00")
    products: Dict[str, Product] = field(default_factory=dict)
    competitors: List[Competitor] = field(default_factory=list)
    active_events: List[AdversarialEvent] = field(default_factory=list)
    suppliers: Dict[str, List[SupplierOffer]] = field(default_factory=dict)
    pending_inbound_orders: List[PendingInboundOrder] = field(default_factory=list)
    customer_backlog: Dict[str, int] = field(default_factory=dict)
    
    # Historical tracking
    daily_revenue: List[Decimal] = field(default_factory=list)
    daily_costs: List[Decimal] = field(default_factory=list)
    daily_profit: List[Decimal] = field(default_factory=list)
    daily_ad_spend: List[Decimal] = field(default_factory=list)
    daily_ad_attributed_revenue: List[Decimal] = field(default_factory=list)
    decisions_made: List[Dict] = field(default_factory=list)
    
    # Cumulative stats
    total_revenue: Decimal = Decimal("0.00")
    total_costs: Decimal = Decimal("0.00") 
    total_orders_fulfilled: int = 0
    total_stockouts: int = 0
    total_ad_spend: Decimal = Decimal("0.00")
    
    def get_profit(self) -> Decimal:
        return self.total_revenue - self.total_costs
    
    def get_roi(self) -> float:
        initial = Decimal("10000.00")
        return float((self.capital - initial) / initial * 100)


# ============================================================================
# MARKET SIMULATION ENGINE
# ============================================================================

class MarketSimulator:
    """
    Simulates a realistic e-commerce market.
    
    This handles:
    - Order generation based on demand
    - Competitor behavior
    - Adversarial event injection
    - State updates based on agent decisions
    """
    
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.state = SimulationState()
        self._initialize_products()
        self._initialize_competitors()
        self._initialize_suppliers()
        self._initialize_backlog()
        
    def _initialize_products(self):
        """Create initial product catalog."""
        products = [
            ("P001", "Wireless Earbuds", 15.00, 39.99, 100, 8),
            ("P002", "Phone Charger", 5.00, 14.99, 200, 15),
            ("P003", "Laptop Stand", 22.00, 59.99, 50, 3),
            ("P004", "USB Hub", 12.00, 29.99, 80, 5),
            ("P005", "Bluetooth Speaker", 25.00, 69.99, 60, 4),
            ("P006", "Webcam HD", 18.00, 49.99, 70, 6),
            ("P007", "Mouse Pad XL", 4.00, 12.99, 150, 10),
            ("P008", "HDMI Cable", 3.00, 9.99, 300, 20),
        ]
        
        for sku, name, cost, price, stock, demand in products:
            self.state.products[sku] = Product(
                sku=sku,
                name=name,
                cost=Decimal(str(cost)),
                price=Decimal(str(price)),
                stock=stock,
                daily_demand_base=demand,
            )
    
    def _initialize_competitors(self):
        """Create competitor landscape."""
        competitor_names = ["ValueMart", "BudgetKing", "TechDeals", "PrimeGoods"]
        
        for sku, product in self.state.products.items():
            # Each product has 1-2 competitors
            num_competitors = self.rng.randint(1, 2)
            for i in range(num_competitors):
                name = self.rng.choice(competitor_names)
                # Competitors price within ±15% of our price
                comp_price = product.price * Decimal(str(self.rng.uniform(0.85, 1.15)))
                aggression = self.rng.uniform(0.2, 0.8)
                
                self.state.competitors.append(Competitor(
                    name=f"{name}_{sku}",
                    sku=sku,
                    price=comp_price.quantize(Decimal("0.01")),
                    aggression=aggression,
                ))

    def _initialize_suppliers(self):
        """Create supplier options for each SKU with lead-time and reliability."""
        for sku, product in self.state.products.items():
            offers: List[SupplierOffer] = []
            for idx in range(2):
                unit_cost = product.cost * Decimal(str(self.rng.uniform(0.9, 1.2)))
                offers.append(
                    SupplierOffer(
                        supplier_id=f"SUP-{sku}-{idx + 1}",
                        sku=sku,
                        unit_cost=unit_cost.quantize(Decimal("0.01")),
                        lead_time_days=self.rng.randint(3, 12),
                        reliability=round(self.rng.uniform(0.78, 0.98), 2),
                        min_order_qty=self.rng.choice([20, 25, 30, 40]),
                    )
                )
            self.state.suppliers[sku] = offers

    def _initialize_backlog(self):
        """Initialize customer-service backlog counters."""
        self.state.customer_backlog = {sku: 0 for sku in self.state.products}

    def process_inbound_orders(self) -> List[str]:
        """
        Process pending supplier deliveries at start of each day.
        Returns textual events for observability.
        """
        events: List[str] = []
        remaining: List[PendingInboundOrder] = []

        for po in self.state.pending_inbound_orders:
            po.days_until_arrival -= 1
            if po.days_until_arrival > 0:
                remaining.append(po)
                continue

            product = self.state.products.get(po.sku)
            if not product:
                continue

            fill_ratio = 1.0 if self.rng.random() <= po.reliability else self.rng.uniform(0.65, 0.95)
            delivered_qty = max(0, int(round(po.quantity * fill_ratio)))
            if delivered_qty > 0:
                product.stock += delivered_qty
                # Smooth cost basis toward delivered unit cost.
                product.cost = (
                    (product.cost * Decimal("0.7")) + (po.unit_cost * Decimal("0.3"))
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            if delivered_qty < po.quantity:
                events.append(
                    f"Inbound {po.po_id} partial fill: {delivered_qty}/{po.quantity} units for {po.sku}"
                )
            else:
                events.append(f"Inbound {po.po_id} delivered: +{delivered_qty} units for {po.sku}")

        self.state.pending_inbound_orders = remaining
        return events

    def _roll_forward_daily_effects(self):
        """
        Apply next-day effects at order generation boundary.
        Keeps ad decisions forward-looking instead of instantly affecting same-day demand.
        """
        for product in self.state.products.values():
            product.ad_boost = max(0.2, product.next_day_ad_boost)
            product.next_day_ad_boost = 1.0
    
    def generate_daily_orders(self) -> List[Order]:
        """Generate customer orders for today based on demand."""
        self._roll_forward_daily_effects()
        orders = []
        order_counter = self.state.day * 100
        
        for sku, product in self.state.products.items():
            demand = product.calculate_daily_demand(self.rng)
            
            for i in range(demand):
                order_counter += 1
                # Customer max price = our price ± 10%
                max_price = product.price * Decimal(str(self.rng.uniform(0.9, 1.1)))
                
                orders.append(Order(
                    order_id=f"ORD-{order_counter:06d}",
                    sku=sku,
                    quantity=self.rng.randint(1, 3),
                    max_price=max_price.quantize(Decimal("0.01")),
                ))
        
        self.rng.shuffle(orders)
        return orders
    
    def maybe_inject_event(self) -> Optional[AdversarialEvent]:
        """Randomly inject adversarial events."""
        # 5% chance per day of a new event
        if self.rng.random() > 0.05:
            return None
        
        event_types = [
            ("supply_shock", "Supplier delays - stock replenishment halted", 0.7),
            ("price_war", "Competitor slashed prices by 25%", 0.6),
            ("demand_spike", "Viral social media - demand 3x", 0.5),
            ("demand_crash", "Negative press - demand halved", 0.6),
            ("review_bomb", "Coordinated negative reviews", 0.5),
        ]
        
        event_type, desc, severity = self.rng.choice(event_types)
        affected_sku = self.rng.choice(list(self.state.products.keys()))
        duration = self.rng.randint(3, 14)  # 3-14 days
        
        event = AdversarialEvent(
            event_id=f"EVT-{self.state.day}-{event_type}",
            event_type=event_type,
            affected_sku=affected_sku,
            severity=severity * self.rng.uniform(0.8, 1.2),
            days_remaining=duration,
            description=f"{desc} for {self.state.products[affected_sku].name}",
        )
        
        # Apply immediate effects
        product = self.state.products[affected_sku]
        if event_type == "demand_spike":
            product.demand_multiplier = 3.0
        elif event_type == "demand_crash":
            product.demand_multiplier = 0.5
        elif event_type == "review_bomb":
            product.rating = max(1.0, product.rating - 1.5)
        elif event_type == "price_war":
            # Competitor drops price
            for comp in self.state.competitors:
                if comp.sku == affected_sku:
                    comp.price = comp.price * Decimal("0.75")
        
        self.state.active_events.append(event)
        return event
    
    def update_events(self):
        """Tick down active events and remove expired ones."""
        still_active = []
        
        for event in self.state.active_events:
            event.days_remaining -= 1
            
            if event.days_remaining <= 0:
                # Event ended - restore normal state
                product = self.state.products[event.affected_sku]
                if event.event_type in ("demand_spike", "demand_crash"):
                    product.demand_multiplier = 1.0
                elif event.event_type == "review_bomb":
                    product.rating = min(5.0, product.rating + 0.5)  # Slow recovery
            else:
                still_active.append(event)
        
        self.state.active_events = still_active

    def _select_supplier(self, sku: str, supplier_id: Optional[str]) -> Optional[SupplierOffer]:
        offers = self.state.suppliers.get(sku, [])
        if not offers:
            return None
        if supplier_id:
            for offer in offers:
                if offer.supplier_id == supplier_id:
                    return offer
        # Prefer cheaper and more reliable suppliers.
        ranked = sorted(
            offers,
            key=lambda o: (o.unit_cost, o.lead_time_days, -o.reliability),
        )
        return ranked[0]

    def _place_supplier_order(
        self,
        *,
        sku: str,
        quantity: int,
        supplier_id: Optional[str] = None,
    ) -> Tuple[bool, str, Decimal]:
        """Create a supplier PO if valid and affordable."""
        if sku not in self.state.products:
            return False, f"FAILED supplier order {sku}: unknown SKU", Decimal("0.00")
        if quantity <= 0:
            return False, f"FAILED supplier order {sku}: quantity must be > 0", Decimal("0.00")

        offer = self._select_supplier(sku, supplier_id)
        if offer is None:
            return False, f"FAILED supplier order {sku}: no supplier available", Decimal("0.00")

        final_qty = max(int(quantity), int(offer.min_order_qty))
        total_cost = (offer.unit_cost * final_qty).quantize(Decimal("0.01"))
        if total_cost > self.state.capital:
            return (
                False,
                f"FAILED supplier order {sku}: insufficient capital for ${total_cost}",
                Decimal("0.00"),
            )

        po_id = f"PO-{self.state.day:03d}-{len(self.state.pending_inbound_orders) + 1:03d}"
        self.state.pending_inbound_orders.append(
            PendingInboundOrder(
                po_id=po_id,
                supplier_id=offer.supplier_id,
                sku=sku,
                quantity=final_qty,
                unit_cost=offer.unit_cost,
                reliability=offer.reliability,
                days_until_arrival=offer.lead_time_days,
            )
        )
        msg = (
            f"Placed {po_id}: {sku} x{final_qty} from {offer.supplier_id} "
            f"(ETA {offer.lead_time_days}d @ ${offer.unit_cost})"
        )
        return True, msg, total_cost
    
    def apply_agent_decisions(
        self, 
        decisions: Dict[str, Any],
        orders: List[Order],
    ) -> Dict[str, Any]:
        """
        Apply agent's decisions and calculate results.
        
        Returns summary of what happened.
        """
        results = {
            "orders_received": len(orders),
            "orders_fulfilled": 0,
            "orders_rejected": 0,
            "stockouts": 0,
            "revenue": Decimal("0.00"),
            "costs": Decimal("0.00"),
            "profit": Decimal("0.00"),
            "ad_spend": Decimal("0.00"),
            "ad_attributed_revenue": Decimal("0.00"),
            "supplier_orders_placed": 0,
            "service_tickets_resolved": 0,
            "events": [],
        }
        
        # Apply price changes
        price_changes = decisions.get("price_changes", {})
        for sku, new_price in price_changes.items():
            if sku in self.state.products:
                old_price = self.state.products[sku].price
                self.state.products[sku].price = Decimal(str(new_price))
                results["events"].append(f"Changed {sku} price: ${old_price} → ${new_price}")
        
        # Apply restock orders
        restock_orders = decisions.get("restock", {})
        for sku, quantity in restock_orders.items():
            if sku in self.state.products:
                product = self.state.products[sku]
                try:
                    qty_i = int(quantity)
                except (TypeError, ValueError):
                    qty_i = 0
                if qty_i <= 0:
                    continue
                cost = product.cost * qty_i
                if cost <= self.state.capital:
                    self.state.capital -= cost
                    product.stock += qty_i
                    results["costs"] += cost
                    results["events"].append(f"Restocked {sku}: +{qty_i} units (cost ${cost})")
                else:
                    results["events"].append(f"FAILED restock {sku}: insufficient capital")

        # Apply supplier orders (lead-time based inbound replenishment)
        supplier_orders_raw = decisions.get("supplier_orders", {})
        supplier_orders: List[Dict[str, Any]] = []
        if isinstance(supplier_orders_raw, dict):
            for sku, qty in supplier_orders_raw.items():
                supplier_orders.append({"sku": sku, "quantity": qty})
        elif isinstance(supplier_orders_raw, list):
            for item in supplier_orders_raw:
                if isinstance(item, dict):
                    supplier_orders.append(item)

        for order_req in supplier_orders:
            sku = str(order_req.get("sku", "")).strip()
            try:
                qty = int(order_req.get("quantity", 0))
            except (TypeError, ValueError):
                qty = 0
            supplier_id_raw = order_req.get("supplier_id")
            supplier_id = str(supplier_id_raw).strip() if supplier_id_raw else None
            ok, msg, total_cost = self._place_supplier_order(
                sku=sku,
                quantity=qty,
                supplier_id=supplier_id,
            )
            results["events"].append(msg)
            if ok:
                self.state.capital -= total_cost
                results["costs"] += total_cost
                results["supplier_orders_placed"] += 1

        # Apply ad budget shifts (forward-looking: boosts next-day demand).
        ad_budget_shift = decisions.get("ad_budget_shift", {})
        if isinstance(ad_budget_shift, dict):
            for sku, spend_val in ad_budget_shift.items():
                product = self.state.products.get(str(sku))
                if not product:
                    continue
                try:
                    spend = Decimal(str(spend_val)).quantize(Decimal("0.01"))
                except Exception:
                    continue
                if spend <= 0:
                    continue
                if spend > self.state.capital:
                    results["events"].append(
                        f"FAILED ad shift {sku}: insufficient capital for ${spend}"
                    )
                    continue
                self.state.capital -= spend
                results["costs"] += spend
                results["ad_spend"] += spend
                self.state.total_ad_spend += spend
                # A simple diminishing-return marketing lift for tomorrow.
                boost = min(1.0, float(spend / Decimal("220.0")))
                product.next_day_ad_boost = max(product.next_day_ad_boost, 1.0 + boost)
                results["events"].append(
                    f"Scheduled ad boost for {sku}: spend ${spend}, next-day boost x{product.next_day_ad_boost:.2f}"
                )

        # Apply customer service actions.
        customer_ops = decisions.get("customer_ops", {})
        if isinstance(customer_ops, dict):
            for sku, mode_val in customer_ops.items():
                sku_key = str(sku).strip()
                mode = str(mode_val).strip().lower()
                if sku_key not in self.state.products:
                    continue
                backlog = int(self.state.customer_backlog.get(sku_key, 0))
                if backlog <= 0:
                    continue

                if mode == "proactive":
                    resolve_ratio = 0.6
                    cost_per_ticket = Decimal("0.75")
                    rating_delta = 0.08
                elif mode == "minimal":
                    resolve_ratio = 0.1
                    cost_per_ticket = Decimal("0.15")
                    rating_delta = -0.02
                else:
                    resolve_ratio = 0.3
                    cost_per_ticket = Decimal("0.40")
                    rating_delta = 0.03

                to_resolve = max(0, int(round(backlog * resolve_ratio)))
                support_cost = (cost_per_ticket * to_resolve).quantize(Decimal("0.01"))
                if support_cost > self.state.capital:
                    affordable = int(self.state.capital // max(cost_per_ticket, Decimal("0.01")))
                    to_resolve = max(0, affordable)
                    support_cost = (cost_per_ticket * to_resolve).quantize(Decimal("0.01"))

                if to_resolve > 0:
                    self.state.capital -= support_cost
                    results["costs"] += support_cost
                    self.state.customer_backlog[sku_key] = max(0, backlog - to_resolve)
                    product = self.state.products[sku_key]
                    product.rating = max(1.0, min(5.0, product.rating + rating_delta))
                    results["service_tickets_resolved"] += to_resolve
                    results["events"].append(
                        f"Customer ops {sku_key}: resolved {to_resolve} tickets ({mode}), cost ${support_cost}"
                    )
        
        # Process customer orders
        accept_orders = set(decisions.get("accept_orders", []))
        
        for order in orders:
            product = self.state.products.get(order.sku)
            if not product:
                continue
            
            # Check if agent accepted this order
            if order.order_id not in accept_orders:
                results["orders_rejected"] += 1
                if self.rng.random() < 0.05:
                    self.state.customer_backlog[order.sku] = self.state.customer_backlog.get(order.sku, 0) + 1
                continue
            
            # Check if customer will pay our price
            if product.price > order.max_price:
                results["orders_rejected"] += 1
                results["events"].append(f"Lost {order.order_id}: price ${product.price} > customer max ${order.max_price}")
                if self.rng.random() < 0.15:
                    self.state.customer_backlog[order.sku] = self.state.customer_backlog.get(order.sku, 0) + 1
                continue
            
            # Check stock
            if product.stock < order.quantity:
                results["stockouts"] += 1
                results["events"].append(f"Stockout on {order.order_id}: need {order.quantity}, have {product.stock}")
                self.state.customer_backlog[order.sku] = self.state.customer_backlog.get(order.sku, 0) + 2
                continue
            
            # Fulfill order!
            product.stock -= order.quantity
            order_revenue = product.price * order.quantity
            self.state.capital += order_revenue
            results["revenue"] += order_revenue
            results["orders_fulfilled"] += 1
            if product.ad_boost > 1.0:
                attributed = (order_revenue * Decimal(str(min(0.5, product.ad_boost - 1.0)))).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
                results["ad_attributed_revenue"] += attributed

        # Passive customer-service decay if backlog grows too large.
        for sku, backlog in self.state.customer_backlog.items():
            if backlog > 25:
                product = self.state.products.get(sku)
                if product:
                    product.rating = max(1.0, product.rating - 0.04)
        
        # Calculate profit
        results["profit"] = results["revenue"] - results["costs"]
        
        # Update state tracking
        self.state.daily_revenue.append(results["revenue"])
        self.state.daily_costs.append(results["costs"])
        self.state.daily_profit.append(results["profit"])
        self.state.daily_ad_spend.append(results["ad_spend"])
        self.state.daily_ad_attributed_revenue.append(results["ad_attributed_revenue"])
        self.state.total_revenue += results["revenue"]
        self.state.total_costs += results["costs"]
        self.state.total_orders_fulfilled += results["orders_fulfilled"]
        self.state.total_stockouts += results["stockouts"]
        
        return results
    
    def get_state_for_agent(self, orders: List[Order]) -> Dict[str, Any]:
        """Get current state formatted for the LLM agent."""
        
        # Recent history (last 7 days)
        recent_revenue = list(self.state.daily_revenue[-7:])
        recent_profit = list(self.state.daily_profit[-7:])
        recent_ad_spend = list(self.state.daily_ad_spend[-7:])
        recent_ad_attr = list(self.state.daily_ad_attributed_revenue[-7:])
        
        return {
            "day": self.state.day,
            "days_remaining": 730 - self.state.day,
            "capital": float(self.state.capital),
            "total_profit_so_far": float(self.state.get_profit()),
            "roi_percent": self.state.get_roi(),
            
            "products": {
                sku: {
                    "name": p.name,
                    "cost": float(p.cost),
                    "price": float(p.price),
                    "stock": p.stock,
                    "rating": p.rating,
                    "ad_boost_today": round(p.ad_boost, 3),
                    "next_day_ad_boost": round(p.next_day_ad_boost, 3),
                    "demand_trend": "high" if p.demand_multiplier > 1.5 else "low" if p.demand_multiplier < 0.7 else "normal",
                }
                for sku, p in self.state.products.items()
            },
            
            "todays_orders": [
                {
                    "order_id": o.order_id,
                    "sku": o.sku,
                    "quantity": o.quantity,
                    "customer_max_price": float(o.max_price),
                }
                for o in orders[:20]  # Show first 20 orders
            ],
            "total_orders_today": len(orders),
            
            "competitors": [
                {
                    "name": c.name.split("_")[0],
                    "sku": c.sku,
                    "price": float(c.price),
                }
                for c in self.state.competitors
            ],

            "supplier_options": {
                sku: [
                    {
                        "supplier_id": s.supplier_id,
                        "unit_cost": float(s.unit_cost),
                        "lead_time_days": s.lead_time_days,
                        "reliability": s.reliability,
                        "min_order_qty": s.min_order_qty,
                    }
                    for s in offers
                ]
                for sku, offers in self.state.suppliers.items()
            },

            "inbound_orders": [
                {
                    "po_id": po.po_id,
                    "supplier_id": po.supplier_id,
                    "sku": po.sku,
                    "quantity": po.quantity,
                    "unit_cost": float(po.unit_cost),
                    "days_until_arrival": po.days_until_arrival,
                    "reliability": po.reliability,
                }
                for po in self.state.pending_inbound_orders
            ],
            
            "active_events": [
                {
                    "event_id": e.event_id,
                    "type": e.event_type,
                    "affected_product": e.affected_sku,
                    "description": e.description,
                    "days_remaining": e.days_remaining,
                }
                for e in self.state.active_events
            ],

            "customer_service": {
                "backlog_by_sku": self.state.customer_backlog.copy(),
                "total_backlog": int(sum(self.state.customer_backlog.values())),
            },
            
            "recent_performance": {
                "last_7_days_revenue": [float(r) for r in recent_revenue],
                "last_7_days_profit": [float(p) for p in recent_profit],
                "last_7_days_ad_spend": [float(x) for x in recent_ad_spend],
                "last_7_days_ad_attributed_revenue": [float(x) for x in recent_ad_attr],
                "total_stockouts": self.state.total_stockouts,
                "total_ad_spend": float(self.state.total_ad_spend),
            },
        }


# ============================================================================
# GROK AGENT
# ============================================================================

class GrokAgent:
    """
    Grok-powered business agent with proper feedback loop.
    """
    
    SYSTEM_PROMPT = """You are an expert e-commerce business manager running a store. 
Your goal is to MAXIMIZE PROFIT over a 2-year period starting with $10,000 capital.

Each day you will:
1. See your current state (capital, inventory, sales history)
2. See today's incoming orders
3. See competitor prices and any active events
4. Make decisions across pricing, replenishment, marketing, and customer service

KEY RULES:
- You can only fulfill orders if you have stock
- Customers won't buy if your price exceeds their max price
- Restocking costs capital upfront
- Supplier orders have lead times and uncertainty
- Ad budget spent today mostly affects demand tomorrow
- Customer service actions cost money but can protect rating and conversion
- Events like supply shocks and price wars affect your business
- Your decisions TODAY affect your state TOMORROW

Be strategic. React to events. Manage cash flow. Crush the competition."""

    def __init__(self, api_key_env: str = "OPENROUTER_API_KEY"):
        llm_config = LLMConfig(
            provider="openrouter",
            model="x-ai/grok-4.1-fast",
            api_key_env=api_key_env,
            temperature=0.1,
            max_tokens=2048,
            timeout=60,
        )
        self.client = OpenRouterClient(llm_config)
        self.calls = 0
        self.reflection_calls = 0
        self.total_tokens = 0

    @staticmethod
    def _extract_json_content(content: str) -> str:
        """Extract raw JSON payload from plain or fenced model output."""
        if "```json" in content:
            return content.split("```json", 1)[1].split("```", 1)[0].strip()
        if "```" in content:
            return content.split("```", 1)[1].split("```", 1)[0].strip()
        return content.strip()

    async def decide(self, state: Dict[str, Any], day_results: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make decisions for the current day.
        
        Args:
            state: Current simulation state
            day_results: Results from yesterday's decisions (feedback!)
        """
        self.calls += 1
        
        # Build prompt with feedback from yesterday
        feedback_section = ""
        if day_results:
            feedback_section = f"""
## YESTERDAY'S RESULTS (Day {state['day'] - 1})
- Revenue: ${day_results.get('revenue', 0):.2f}
- Costs: ${day_results.get('costs', 0):.2f}  
- Profit: ${day_results.get('profit', 0):.2f}
- Orders Fulfilled: {day_results.get('orders_fulfilled', 0)}
- Stockouts: {day_results.get('stockouts', 0)}
- Events: {day_results.get('events', [])}

LEARN FROM THIS: {"Good day!" if float(day_results.get('profit', 0)) > 0 else "Analyze what went wrong."}
"""

        memory_section = ""
        memory_context = state.get("memory_context") or []
        if memory_context:
            memory_section = f"""
## RELEVANT MEMORIES (retrieved for this decision)
{json.dumps(memory_context, indent=2)}
"""

        prompt = f"""{self.SYSTEM_PROMPT}

## CURRENT STATE (Day {state['day']} of 730)
Capital: ${state['capital']:,.2f}
Total Profit So Far: ${state['total_profit_so_far']:,.2f}
ROI: {state['roi_percent']:.1f}%
{feedback_section}

## YOUR PRODUCTS
{json.dumps(state['products'], indent=2)}

## TODAY'S ORDERS ({state['total_orders_today']} total)
{json.dumps(state['todays_orders'][:15], indent=2)}
{"... and more orders" if state['total_orders_today'] > 15 else ""}

## COMPETITOR PRICES
{json.dumps(state['competitors'], indent=2)}

## SUPPLIER OPTIONS
{json.dumps(state['supplier_options'], indent=2)}

## INBOUND ORDERS (already placed, not yet received)
{json.dumps(state['inbound_orders'], indent=2)}

## CUSTOMER SERVICE
{json.dumps(state['customer_service'], indent=2)}

## ACTIVE EVENTS
{json.dumps(state['active_events'], indent=2) if state['active_events'] else "None currently."}
{memory_section}

## YOUR DECISIONS (respond with JSON only)
{{
    "reasoning": "Brief explanation of your strategy today",
    "accept_orders": ["ORD-000001", "ORD-000002", ...],  // Order IDs to fulfill
    "price_changes": {{"P001": 34.99, ...}},  // Optional price adjustments
    "restock": {{"P001": 50, ...}},  // Optional immediate restock (instant, expensive)
    "supplier_orders": [{{"sku":"P001","quantity":120,"supplier_id":"SUP-P001-1"}}],  // Arrives in future days
    "ad_budget_shift": {{"P001": 40.0, "P002": 15.0}},  // Spend in USD, affects future demand
    "customer_ops": {{"P001":"proactive","P002":"standard"}}  // proactive|standard|minimal
}}
"""

        try:
            response = await self.client.generate_response(prompt)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            # Track token usage
            usage = response.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)

            decisions = json.loads(self._extract_json_content(content))
            return decisions
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            # Fallback: accept all orders, no changes
            return {
                "reasoning": "Fallback: accept all orders",
                "accept_orders": [o["order_id"] for o in state["todays_orders"]],
                "price_changes": {},
                "restock": {},
                "supplier_orders": [],
                "ad_budget_shift": {},
                "customer_ops": {},
            }

    async def review_memory(
        self,
        day_trace: Dict[str, Any],
        long_term_snapshot: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Ask the model to keep/update/discard memory candidates from the day trace.
        Returns None on parse/runtime failure.
        """
        self.calls += 1
        self.reflection_calls += 1

        prompt = f"""You are reviewing today's business decisions for long-term memory.
Return JSON only using exactly this schema:
{{
  "keep": [{{"statement":"...", "decision_type":"pricing|restock|supplier|marketing|service|risk|mixed", "scope":"global|asin|scenario", "asin":"P001 or null", "impact":0.0, "reusability":0.0, "confidence":0.0, "novelty":0.0, "recency":1.0, "tags":["..."]}}],
  "update": [{{same schema as keep}}],
  "discard": [{{"statement":"..."}}]
}}

Scoring guidance:
- keep only high-impact reusable lessons
- discard one-off noise
- confidence values must be between 0.0 and 1.0

DAY TRACE:
{json.dumps(day_trace, indent=2)}

CURRENT LONG TERM MEMORY (trimmed):
{json.dumps(long_term_snapshot[:20], indent=2)}
"""

        try:
            response = await self.client.generate_response(prompt)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            usage = response.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)
            parsed = json.loads(self._extract_json_content(content))
            if isinstance(parsed, dict):
                return parsed
            return None
        except Exception as exc:
            logger.warning(f"Memory review failed (fallback to heuristic): {exc}")
            return None

    async def close(self):
        await self.client.aclose()


# ============================================================================
# MAIN SIMULATION LOOP
# ============================================================================

async def run_simulation(
    days: int = 730,
    seed: int = 42,
    verbose: bool = True,
    memory_mode: str = "stateless",
    memory_review_mode: str = "heuristic",
    weekly_consolidation: bool = True,
):
    """
    Run the proper tick-based simulation.
    
    Each day:
    1. Generate orders
    2. Maybe inject event
    3. Agent sees state + feedback
    4. Agent makes decisions
    5. Simulation applies decisions
    6. State updates
    7. Repeat
    """
    print("\n" + "="*80)
    print("🦅 FBA-BENCH: PROPER TICK-BASED SIMULATION")
    print("="*80)
    print(f"Duration: {days} days | Seed: {seed} | Model: Grok 4.1 Fast")
    print(
        f"Memory mode: {memory_mode} | Review mode: {memory_review_mode} | "
        f"Weekly consolidation: {weekly_consolidation}"
    )
    print("="*80 + "\n")
    
    # Check API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ Set OPENROUTER_API_KEY first!")
        return None
    
    simulator = MarketSimulator(seed=seed)
    agent = GrokAgent()
    memory_engine: Optional[ReflectiveMemoryV1] = None
    if memory_mode == "reflective":
        memory_engine = ReflectiveMemoryV1()
    
    start_time = time.time()
    last_results = None
    
    try:
        for day in range(1, days + 1):
            simulator.state.day = day

            # 0. Receive inbound supplier orders due today.
            inbound_events = simulator.process_inbound_orders()
            if inbound_events and verbose:
                for evt in inbound_events[:3]:
                    print(f"📦 Day {day}: {evt}")
            
            # 1. Generate today's orders
            orders = simulator.generate_daily_orders()
            
            # 2. Maybe inject adversarial event
            new_event = simulator.maybe_inject_event()
            if new_event and verbose:
                print(f"⚠️  Day {day}: NEW EVENT - {new_event.description}")
            
            # 3. Get state for agent (includes yesterday's feedback!)
            state = simulator.get_state_for_agent(orders)
            if memory_engine is not None:
                event_tags = [evt.get("type", "") for evt in state.get("active_events", [])]
                state["memory_context"] = memory_engine.retrieve(
                    day=day,
                    decision_type="mixed",
                    asin=None,
                    tags=event_tags,
                )
            
            # 4. Agent makes decisions WITH FEEDBACK
            decisions = await agent.decide(state, last_results)
            
            # 5. Apply decisions and get results
            results = simulator.apply_agent_decisions(decisions, orders)
            if inbound_events:
                results["events"].extend(inbound_events)
            last_results = results  # This becomes feedback for tomorrow!
            
            # 6. Update events (tick down timers)
            simulator.update_events()

            memory_daily_summary = None
            memory_weekly_summary = None
            if memory_engine is not None:
                day_trace = {
                    "day": day,
                    "state": {
                        "capital": state.get("capital"),
                        "roi_percent": state.get("roi_percent"),
                        "active_events": state.get("active_events", []),
                    },
                    "decisions": decisions,
                    "results": {
                        "revenue": float(results["revenue"]),
                        "costs": float(results["costs"]),
                        "profit": float(results["profit"]),
                        "orders_fulfilled": results["orders_fulfilled"],
                        "stockouts": results["stockouts"],
                        "ad_spend": float(results["ad_spend"]),
                        "ad_attributed_revenue": float(results["ad_attributed_revenue"]),
                        "supplier_orders_placed": results["supplier_orders_placed"],
                        "service_tickets_resolved": results["service_tickets_resolved"],
                    },
                }

                review_payload = None
                if memory_review_mode == "llm":
                    review_payload = await agent.review_memory(
                        day_trace=day_trace,
                        long_term_snapshot=memory_engine.long_term_snapshot(limit=20),
                    )

                memory_daily_summary = memory_engine.apply_daily_review(
                    day=day,
                    review_payload=review_payload,
                    fallback_trace=day_trace,
                )

                if weekly_consolidation and day % 7 == 0:
                    memory_weekly_summary = memory_engine.consolidate_weekly(day=day)
            
            # Store decision
            simulator.state.decisions_made.append({
                "day": day,
                "reasoning": decisions.get("reasoning", ""),
                "actions": {
                    "orders_accepted": len(decisions.get("accept_orders", [])),
                    "price_changes": len(decisions.get("price_changes", {})),
                    "restocks": len(decisions.get("restock", {})),
                    "supplier_orders": len(decisions.get("supplier_orders", []))
                    if isinstance(decisions.get("supplier_orders", []), list)
                    else len(decisions.get("supplier_orders", {})),
                    "ad_budget_shifts": len(decisions.get("ad_budget_shift", {})),
                    "customer_ops_updates": len(decisions.get("customer_ops", {})),
                },
                "results": {
                    "revenue": float(results["revenue"]),
                    "profit": float(results["profit"]),
                    "fulfilled": results["orders_fulfilled"],
                    "stockouts": results["stockouts"],
                    "ad_spend": float(results["ad_spend"]),
                    "ad_attributed_revenue": float(results["ad_attributed_revenue"]),
                    "supplier_orders_placed": results["supplier_orders_placed"],
                    "service_tickets_resolved": results["service_tickets_resolved"],
                },
                "memory": {
                    "daily": memory_daily_summary.to_dict() if memory_daily_summary else None,
                    "weekly": memory_weekly_summary.to_dict() if memory_weekly_summary else None,
                },
            })
            
            # Progress update
            if verbose and day % 30 == 0:
                memory_status = ""
                if memory_engine is not None:
                    mem_summary = memory_engine.summary()
                    memory_status = (
                        f" | LT mem: {mem_summary['long_term_count']}"
                        f" | Episodic: {mem_summary['episodic_count']}"
                    )
                print(
                    f"📅 Day {day:3d} | Capital: ${simulator.state.capital:,.2f} | "
                    f"Profit: ${simulator.state.get_profit():,.2f} | "
                    f"LLM Calls: {agent.calls}{memory_status}"
                )
        
        elapsed = time.time() - start_time
        
        # Final results
        print("\n" + "="*80)
        print("📊 FINAL RESULTS")
        print("="*80)
        print(f"⏱️  Execution Time: {elapsed/60:.1f} minutes")
        print(f"🤖 LLM Calls: {agent.calls}")
        print(f"🧠 Reflection Calls: {agent.reflection_calls}")
        print(f"📝 Total Tokens: {agent.total_tokens:,}")
        print()
        print(f"💰 Starting Capital: $10,000.00")
        print(f"💰 Final Capital: ${simulator.state.capital:,.2f}")
        print(f"📈 Total Revenue: ${simulator.state.total_revenue:,.2f}")
        print(f"📉 Total Costs: ${simulator.state.total_costs:,.2f}")
        print(f"💵 Net Profit: ${simulator.state.get_profit():,.2f}")
        print(f"📊 ROI: {simulator.state.get_roi():.1f}%")
        print(f"📣 Total Ad Spend: ${simulator.state.total_ad_spend:,.2f}")
        print()
        print(f"📦 Orders Fulfilled: {simulator.state.total_orders_fulfilled:,}")
        print(f"❌ Total Stockouts: {simulator.state.total_stockouts}")
        print(f"🛠️ Open Customer Backlog: {sum(simulator.state.customer_backlog.values())}")
        print("="*80)
        
        # Save results
        results_file = Path(__file__).parent / "results" / f"grok_proper_sim_{int(time.time())}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        final_results = {
            "config": {
                "days": days,
                "seed": seed,
                "model": "x-ai/grok-4.1-fast",
                "memory_mode": memory_mode,
                "memory_review_mode": memory_review_mode,
                "weekly_consolidation": weekly_consolidation,
            },
            "execution": {
                "time_seconds": elapsed,
                "llm_calls": agent.calls,
                "reflection_calls": agent.reflection_calls,
                "total_tokens": agent.total_tokens,
            },
            "results": {
                "starting_capital": 10000.0,
                "final_capital": float(simulator.state.capital),
                "total_revenue": float(simulator.state.total_revenue),
                "total_costs": float(simulator.state.total_costs),
                "net_profit": float(simulator.state.get_profit()),
                "roi_percent": simulator.state.get_roi(),
                "orders_fulfilled": simulator.state.total_orders_fulfilled,
                "stockouts": simulator.state.total_stockouts,
                "total_ad_spend": float(simulator.state.total_ad_spend),
                "open_customer_backlog": int(sum(simulator.state.customer_backlog.values())),
            },
            "daily_performance": {
                "revenue": [float(r) for r in simulator.state.daily_revenue],
                "profit": [float(p) for p in simulator.state.daily_profit],
                "ad_spend": [float(x) for x in simulator.state.daily_ad_spend],
                "ad_attributed_revenue": [float(x) for x in simulator.state.daily_ad_attributed_revenue],
            },
            "decisions": simulator.state.decisions_made[-50:],  # Last 50 decisions
        }
        if memory_engine is not None:
            final_results["memory"] = memory_engine.summary()
        
        with open(results_file, "w") as f:
            json.dump(final_results, f, indent=2)
        
        print(f"\n💾 Saved to: {results_file}")
        
        return final_results
        
    finally:
        await agent.close()


def main():
    """Entry point."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=730, help="Simulation days (default 730)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--quiet", action="store_true", help="Less output")
    parser.add_argument(
        "--memory-mode",
        choices=["stateless", "reflective"],
        default="stateless",
        help="Memory mode for benchmarking runs",
    )
    parser.add_argument(
        "--memory-review-mode",
        choices=["heuristic", "llm"],
        default="heuristic",
        help="How daily keep/update/discard review is produced when reflective memory is enabled",
    )
    parser.add_argument(
        "--no-weekly-consolidation",
        action="store_true",
        help="Disable weekly consolidation into long-term memory",
    )
    args = parser.parse_args()
    
    asyncio.run(run_simulation(
        days=args.days,
        seed=args.seed,
        verbose=not args.quiet,
        memory_mode=args.memory_mode,
        memory_review_mode=args.memory_review_mode,
        weekly_consolidation=not args.no_weekly_consolidation,
    ))


if __name__ == "__main__":
    main()
