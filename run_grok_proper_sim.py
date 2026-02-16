#!/usr/bin/env python3
"""
FBA-Bench: PROPER Tick-Based Simulation with Feedback Loop

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
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

try:
    import yaml
except Exception:  # pragma: no cover - dependency is present in runtime env
    yaml = None


DEFAULT_REALISM_CONFIG: Dict[str, Any] = {
    "cost_model": {
        "fulfillment_fee_per_unit": 3.20,
        "payment_processing_rate": 0.03,
        "daily_platform_overhead": 8.0,
        "max_order_qty_per_decision": 2000,
    },
    "seasonality": {
        "enabled": True,
        "default_multiplier": 1.0,
        "weekend_multiplier": 1.05,
        "windows": [
            {
                "name": "q4_holiday_spike",
                "start_day": 320,
                "end_day": 360,
                "multiplier": 1.18,
                "categories": ["audio", "camera", "charging", "connectivity"],
            },
            {
                "name": "post_holiday_softness",
                "start_day": 1,
                "end_day": 35,
                "multiplier": 0.92,
                "categories": ["audio", "camera", "workstation"],
            },
            {
                "name": "back_to_school",
                "start_day": 220,
                "end_day": 255,
                "multiplier": 1.10,
                "categories": ["workstation", "camera", "accessories", "connectivity"],
            },
        ],
        "return_windows": [
            {
                "name": "post_holiday_return_wave",
                "start_day": 1,
                "end_day": 45,
                "multiplier": 1.35,
                "categories": ["audio", "camera", "workstation"],
            }
        ],
    },
    "supplier_lanes": {
        "profiles": {
            "domestic": {"lead_min": 2, "lead_max": 5, "rel_min": 0.90, "rel_max": 0.99},
            "nearshore": {"lead_min": 4, "lead_max": 8, "rel_min": 0.86, "rel_max": 0.97},
            "overseas_air": {"lead_min": 5, "lead_max": 10, "rel_min": 0.82, "rel_max": 0.95},
            "overseas_ocean": {"lead_min": 9, "lead_max": 18, "rel_min": 0.78, "rel_max": 0.93},
        },
        "mix": ["domestic", "nearshore", "overseas_air", "overseas_ocean"],
        "delay_risk_by_lane": {
            "domestic": 0.018,
            "nearshore": 0.038,
            "overseas_air": 0.062,
            "overseas_ocean": 0.095,
        },
        "supply_shock_extra_delay_risk": 0.18,
        "max_delay_risk": 0.45,
        "delay_days_min": 1,
        "delay_days_max": 3,
        "max_cumulative_delay_days": 14,
    },
    "returns": {
        "profiles_by_category": {
            "audio": {"base": 0.046, "restock_prob": 0.58, "recovery_low": 0.42, "recovery_high": 0.86, "salvage": 0.24},
            "charging": {"base": 0.024, "restock_prob": 0.76, "recovery_low": 0.65, "recovery_high": 0.97, "salvage": 0.15},
            "connectivity": {"base": 0.026, "restock_prob": 0.79, "recovery_low": 0.68, "recovery_high": 0.98, "salvage": 0.14},
            "workstation": {"base": 0.038, "restock_prob": 0.66, "recovery_low": 0.50, "recovery_high": 0.90, "salvage": 0.19},
            "camera": {"base": 0.042, "restock_prob": 0.60, "recovery_low": 0.46, "recovery_high": 0.87, "salvage": 0.22},
            "accessories": {"base": 0.020, "restock_prob": 0.82, "recovery_low": 0.72, "recovery_high": 0.99, "salvage": 0.12},
        },
        "default_profile": {"base": 0.03, "restock_prob": 0.7, "recovery_low": 0.55, "recovery_high": 0.92, "salvage": 0.18},
    },
}


def _deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_realism_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = deepcopy(DEFAULT_REALISM_CONFIG)
    if not path:
        return cfg
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Realism config file not found: {cfg_path}")
    if yaml is None:
        raise RuntimeError("pyyaml is required for --realism-config but is not available")
    with open(cfg_path, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Realism config root must be a mapping/object")
    return _deep_merge_dicts(cfg, loaded)


# ============================================================================
# VISUALIZATION TRACE HELPERS
# ============================================================================

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp_path.replace(path)

def _sanitize_decisions_for_replay(decisions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persist only the actionable decision fields needed to replay a run deterministically.
    Keep this stable: it becomes part of the reproducibility story.
    """
    if not isinstance(decisions, dict):
        return {}
    return {
        "accept_all_orders": bool(decisions.get("accept_all_orders", False)),
        "accept_skus": list(decisions.get("accept_skus", []) or []),
        "reject_skus": list(decisions.get("reject_skus", []) or []),
        "accept_orders": list(decisions.get("accept_orders", []) or []),
        "price_changes": dict(decisions.get("price_changes", {}) or {}),
        "restock": dict(decisions.get("restock", {}) or {}),
        "supplier_orders": decisions.get("supplier_orders", []) or [],
        "ad_budget_shift": dict(decisions.get("ad_budget_shift", {}) or {}),
        "customer_ops": dict(decisions.get("customer_ops", {}) or {}),
    }


def _load_replay_decisions(results_file: str) -> List[Dict[str, Any]]:
    """
    Load a previous results JSON and extract day-indexed decisions for replay.
    Uses `decisions_raw` when available; falls back to parsing `decisions` entries.
    """
    results_path = Path(results_file)
    if not results_path.exists():
        raise FileNotFoundError(f"Replay results file not found: {results_path}")
    with open(results_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    decisions_list = payload.get("decisions", [])
    if not isinstance(decisions_list, list) or not decisions_list:
        raise ValueError("Replay source missing `decisions` list")

    by_day: Dict[int, Dict[str, Any]] = {}
    for entry in decisions_list:
        if not isinstance(entry, dict):
            continue
        day_val = entry.get("day")
        if not isinstance(day_val, int) or day_val <= 0:
            continue
        raw = entry.get("decisions_raw")
        if isinstance(raw, dict) and raw:
            by_day[day_val] = raw
            continue
        fallback = entry.get("decisions")
        if isinstance(fallback, dict) and fallback:
            by_day[day_val] = _sanitize_decisions_for_replay(fallback)

    if not by_day:
        raise ValueError("Replay source has no usable decisions (missing `decisions_raw` fields)")

    max_day = max(by_day.keys())
    out: List[Dict[str, Any]] = []
    for day in range(1, max_day + 1):
        if day not in by_day:
            raise ValueError(f"Replay source missing decisions for day {day}")
        out.append(by_day[day])
    return out


def _action_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0


def _build_theater_frame(
    *,
    simulator: "MarketSimulator",
    day: int,
    decisions: Dict[str, Any],
    results: Dict[str, Any],
    decision_latency_seconds: float,
) -> Dict[str, Any]:
    product_rows: List[Dict[str, Any]] = []
    for sku, product in simulator.state.products.items():
        product_rows.append(
            {
                "sku": sku,
                "name": product.name,
                "category": product.category,
                "price": float(product.price),
                "stock": int(product.stock),
                "rating": round(float(product.rating), 2),
                "ad_boost_today": round(float(product.ad_boost), 3),
                "next_day_ad_boost": round(float(product.next_day_ad_boost), 3),
                "backlog": int(simulator.state.customer_backlog.get(sku, 0)),
            }
        )
    product_rows.sort(key=lambda item: (item["stock"], -item["backlog"], item["price"]))

    events = [str(evt) for evt in results.get("events", []) if str(evt).strip()]
    reasoning = str(decisions.get("reasoning", "")).strip()
    reasoning_preview = reasoning[:280] + ("..." if len(reasoning) > 280 else "")

    return {
        "timestamp_utc": _utc_now_iso(),
        "day": day,
        "capital": float(simulator.state.capital),
        "equity_value": float(simulator.state.get_equity()),
        "pending_refund_exposure": float(simulator.state.get_pending_refund_exposure()),
        "equity_profit": float(simulator.state.get_equity_profit()),
        "total_profit": float(simulator.state.get_profit()),
        "roi_percent": float(simulator.state.get_roi()),
        "decision_latency_seconds": round(decision_latency_seconds, 3),
        "orders": {
            "received": int(results.get("orders_received", 0)),
            "fulfilled": int(results.get("orders_fulfilled", 0)),
            "rejected": int(results.get("orders_rejected", 0)),
            "stockouts": int(results.get("stockouts", 0)),
        },
        "daily_results": {
            "revenue": float(results.get("revenue", 0.0)),
            "costs": float(results.get("costs", 0.0)),
            "profit": float(results.get("profit", 0.0)),
            "ad_spend": float(results.get("ad_spend", 0.0)),
            "ad_attributed_revenue": float(results.get("ad_attributed_revenue", 0.0)),
            "supplier_orders_placed": int(results.get("supplier_orders_placed", 0)),
            "service_tickets_resolved": int(results.get("service_tickets_resolved", 0)),
            "returns_processed": int(results.get("returns_processed", 0)),
            "refunds_paid": float(results.get("refunds_paid", 0.0)),
            "salvage_recovered": float(results.get("salvage_recovered", 0.0)),
        },
        "actions": {
            "accept_all_orders": bool(decisions.get("accept_all_orders", False)),
            "accept_skus": _action_count(decisions.get("accept_skus", [])),
            "reject_skus": _action_count(decisions.get("reject_skus", [])),
            "orders_accepted": _action_count(decisions.get("accept_orders", [])),
            "price_changes": _action_count(decisions.get("price_changes", {})),
            "restocks": _action_count(decisions.get("restock", {})),
            "supplier_orders": _action_count(decisions.get("supplier_orders", [])),
            "ad_budget_shifts": _action_count(decisions.get("ad_budget_shift", {})),
            "customer_ops_updates": _action_count(decisions.get("customer_ops", {})),
        },
        "reasoning_preview": reasoning_preview,
        "events": events[:8],
        "products": product_rows[:8],
        "active_events": [event.description for event in simulator.state.active_events[:5]],
        "open_customer_backlog": int(sum(simulator.state.customer_backlog.values())),
        "supply_chain": {
            "pending_inbound": len(simulator.state.pending_inbound_orders),
            "total_delay_events": simulator.state.total_supplier_delay_events,
            "total_delay_days": simulator.state.total_supplier_delay_days,
        },
    }


def _build_storyline(
    frame: Dict[str, Any],
    previous_frame: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    daily = frame.get("daily_results", {})
    orders = frame.get("orders", {})

    profit = float(daily.get("profit", 0.0))
    stockouts = int(orders.get("stockouts", 0))
    supplier_orders = int(daily.get("supplier_orders_placed", 0))
    ad_spend = float(daily.get("ad_spend", 0.0))
    ad_attr = float(daily.get("ad_attributed_revenue", 0.0))
    returns_processed = int(daily.get("returns_processed", 0))
    refunds_paid = float(daily.get("refunds_paid", 0.0))
    supply_chain = frame.get("supply_chain", {})
    total_delay_events = int(supply_chain.get("total_delay_events", 0))
    fulfilled = int(orders.get("fulfilled", 0))

    tone = "neutral"
    headline = "Steady operations with mixed signals."
    detail = "No single driver dominated outcomes today."

    if stockouts >= 6:
        tone = "negative"
        headline = "Demand outran inventory; stockouts are now a primary risk."
        detail = f"Stockouts reached {stockouts} while only {fulfilled} orders were fulfilled."
    elif profit < 0:
        tone = "negative"
        headline = "Day closed in the red; cost discipline needs correction."
        detail = f"Daily profit was ${profit:,.2f} with {fulfilled} fulfilled orders."
    elif profit > 0 and fulfilled >= 12:
        tone = "positive"
        headline = "Healthy execution day with profitable throughput."
        detail = f"Profit ${profit:,.2f} on {fulfilled} fulfilled orders."
    elif supplier_orders > 0:
        tone = "neutral"
        headline = "Cash deployed into inbound inventory for forward coverage."
        detail = f"Placed {supplier_orders} supplier orders to protect future fulfillment."
    elif ad_spend > 0 and ad_attr >= ad_spend:
        tone = "positive"
        headline = "Marketing spend is converting into attributable revenue."
        detail = f"Ad spend ${ad_spend:,.2f}, attributed revenue ${ad_attr:,.2f}."
    elif returns_processed > 0 and refunds_paid > 0:
        tone = "neutral"
        headline = "Return wave hit cash flow; watch quality and fulfillment consistency."
        detail = f"Processed {returns_processed} returns with ${refunds_paid:,.2f} refunded."
    elif total_delay_events > 0:
        tone = "neutral"
        headline = "Supply chain volatility is building in inbound lanes."
        detail = f"Observed {total_delay_events} cumulative supplier delay events."

    if previous_frame is not None:
        prev_profit = float(previous_frame.get("daily_results", {}).get("profit", 0.0))
        delta = profit - prev_profit
        if delta > 150:
            detail = f"{detail} Profit accelerated by ${delta:,.2f} vs prior day."
        elif delta < -150:
            detail = f"{detail} Profit fell by ${abs(delta):,.2f} vs prior day."

    return {"tone": tone, "headline": headline, "detail": detail}


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
    category: str
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
    lane: str


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
    lane: str
    cumulative_delay_days: int = 0


@dataclass
class PendingReturn:
    """Customer return awaiting refund resolution."""
    return_id: str
    order_id: str
    sku: str
    quantity: int
    refund_amount: Decimal
    days_until_resolution: int
    restockable: bool
    recovery_rate: float
    inventory_reconciled: bool = False
    

@dataclass
class SimulationState:
    """Full state of the simulation."""
    day: int = 0
    total_days: int = 730
    capital: Decimal = Decimal("10000.00")
    starting_capital: Decimal = Decimal("10000.00")
    starting_inventory_value: Decimal = Decimal("0.00")
    starting_equity: Decimal = Decimal("10000.00")
    products: Dict[str, Product] = field(default_factory=dict)
    competitors: List[Competitor] = field(default_factory=list)
    active_events: List[AdversarialEvent] = field(default_factory=list)
    suppliers: Dict[str, List[SupplierOffer]] = field(default_factory=dict)
    pending_inbound_orders: List[PendingInboundOrder] = field(default_factory=list)
    pending_returns: List[PendingReturn] = field(default_factory=list)
    customer_backlog: Dict[str, int] = field(default_factory=dict)
    next_order_sequence: int = 0
    
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
    total_returns_processed: int = 0
    total_refunds_paid: Decimal = Decimal("0.00")
    total_salvage_recovered: Decimal = Decimal("0.00")
    total_supplier_delay_events: int = 0
    total_supplier_delay_days: int = 0
    
    def get_profit(self) -> Decimal:
        return self.total_revenue - self.total_costs

    def get_inventory_value(self) -> Decimal:
        inventory_value = Decimal("0.00")
        for product in self.products.values():
            inventory_value += (product.cost * product.stock).quantize(Decimal("0.01"))
        return inventory_value

    def get_pending_refund_exposure(self) -> Decimal:
        exposure = Decimal("0.00")
        for pending in self.pending_returns:
            exposure += pending.refund_amount.quantize(Decimal("0.01"))
        return exposure

    def get_equity(self) -> Decimal:
        # Equity should include known refund liabilities from unresolved returns.
        return self.capital + self.get_inventory_value() - self.get_pending_refund_exposure()

    def get_equity_profit(self) -> Decimal:
        return self.get_equity() - self.starting_equity
    
    def get_roi(self) -> float:
        baseline = self.starting_equity if self.starting_equity > 0 else Decimal("1.00")
        return float((self.get_equity() - baseline) / baseline * 100)


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
    
    def __init__(self, seed: int = 42, realism_config: Optional[Dict[str, Any]] = None):
        self.rng = random.Random(seed)
        self.state = SimulationState()
        self.realism_config = realism_config or deepcopy(DEFAULT_REALISM_CONFIG)
        # Lightweight cost model for improved realism.
        cost_cfg = self.realism_config.get("cost_model", {})
        self.fulfillment_fee_per_unit = Decimal(str(cost_cfg.get("fulfillment_fee_per_unit", 3.20)))
        self.payment_processing_rate = Decimal(str(cost_cfg.get("payment_processing_rate", 0.03)))
        self.daily_platform_overhead = Decimal(str(cost_cfg.get("daily_platform_overhead", 8.0)))
        self.max_order_qty_per_decision = int(cost_cfg.get("max_order_qty_per_decision", 2000))
        self._initialize_products()
        self._initialize_competitors()
        self._initialize_suppliers()
        self._initialize_backlog()
        self._initialize_opening_equity()
        
    def _initialize_products(self):
        """Create initial product catalog."""
        products = [
            ("P001", "Wireless Earbuds", "audio", 15.00, 39.99, 100, 8),
            ("P002", "Phone Charger", "charging", 5.00, 14.99, 200, 15),
            ("P003", "Laptop Stand", "workstation", 22.00, 59.99, 50, 3),
            ("P004", "USB Hub", "connectivity", 12.00, 29.99, 80, 5),
            ("P005", "Bluetooth Speaker", "audio", 25.00, 69.99, 60, 4),
            ("P006", "Webcam HD", "camera", 18.00, 49.99, 70, 6),
            ("P007", "Mouse Pad XL", "accessories", 4.00, 12.99, 150, 10),
            ("P008", "HDMI Cable", "connectivity", 3.00, 9.99, 300, 20),
        ]
        
        for sku, name, category, cost, price, stock, demand in products:
            self.state.products[sku] = Product(
                sku=sku,
                name=name,
                category=category,
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
        lane_cfg = self.realism_config.get("supplier_lanes", {})
        lane_profiles = lane_cfg.get("profiles", {})
        lane_mix = lane_cfg.get("mix", list(lane_profiles.keys()))
        if not lane_profiles:
            lane_profiles = deepcopy(DEFAULT_REALISM_CONFIG["supplier_lanes"]["profiles"])
            lane_mix = list(lane_profiles.keys())
        for sku, product in self.state.products.items():
            offers: List[SupplierOffer] = []
            for idx in range(2):
                lane = self.rng.choice(lane_mix)
                profile = lane_profiles[lane]
                unit_cost = product.cost * Decimal(str(self.rng.uniform(0.9, 1.2)))
                offers.append(
                    SupplierOffer(
                        supplier_id=f"SUP-{sku}-{idx + 1}",
                        sku=sku,
                        unit_cost=unit_cost.quantize(Decimal("0.01")),
                        lead_time_days=self.rng.randint(profile["lead_min"], profile["lead_max"]),
                        reliability=round(
                            self.rng.uniform(profile["rel_min"], profile["rel_max"]),
                            2,
                        ),
                        min_order_qty=self.rng.choice([20, 25, 30, 40]),
                        lane=lane,
                    )
                )
            self.state.suppliers[sku] = offers

    def _initialize_backlog(self):
        """Initialize customer-service backlog counters."""
        self.state.customer_backlog = {sku: 0 for sku in self.state.products}

    def _initialize_opening_equity(self):
        """Set equity baseline from opening cash + opening inventory value."""
        self.state.starting_capital = self.state.capital
        opening_inventory = self.state.get_inventory_value()
        self.state.starting_inventory_value = opening_inventory
        self.state.starting_equity = self.state.capital + opening_inventory

    def evolve_competitor_prices(self):
        """
        Move competitor prices each day with slight drift and occasional undercutting.
        Keeps market context dynamic instead of static.
        """
        for competitor in self.state.competitors:
            product = self.state.products.get(competitor.sku)
            if product is None:
                continue

            if self.rng.random() < competitor.aggression * 0.12:
                target = product.price * Decimal(str(self.rng.uniform(0.90, 0.98)))
            else:
                target = competitor.price * Decimal(str(self.rng.uniform(0.97, 1.03)))

            # Active price-war events apply sustained downward pressure by severity.
            pressure = self._active_price_war_pressure(competitor.sku)
            if pressure < 1.0:
                target = target * Decimal(str(pressure))

            floor_price = (product.cost * Decimal("1.02")).quantize(Decimal("0.01"))
            cap_price = (product.price * Decimal("1.35")).quantize(Decimal("0.01"))
            clamped = min(max(target, floor_price), cap_price)
            competitor.price = clamped.quantize(Decimal("0.01"))

    def _competitor_price_factor(self, sku: str, own_price: Decimal) -> float:
        """
        Estimate demand lift/drag from relative pricing vs competitors.
        """
        sku_prices = [float(c.price) for c in self.state.competitors if c.sku == sku]
        if not sku_prices or own_price <= 0:
            return 1.0
        avg_comp_price = sum(sku_prices) / len(sku_prices)
        ratio = avg_comp_price / float(own_price)
        return max(0.65, min(1.35, ratio))

    def _lane_delay_risk(self, lane: str, sku: str) -> float:
        """
        Baseline lane delay risk, increased when SKU is under active supply-shock event.
        """
        lane_cfg = self.realism_config.get("supplier_lanes", {})
        base_risk_by_lane = lane_cfg.get("delay_risk_by_lane", {})
        risk = float(base_risk_by_lane.get(lane, 0.04))
        if any(
            event.event_type == "supply_shock" and event.affected_sku == sku
            for event in self.state.active_events
        ):
            risk += float(lane_cfg.get("supply_shock_extra_delay_risk", 0.18))
        max_risk = float(lane_cfg.get("max_delay_risk", 0.45))
        return min(max_risk, max(0.0, risk))

    def _return_profile(self, category: str) -> Dict[str, float]:
        """
        Category-level return characteristics.
        """
        ret_cfg = self.realism_config.get("returns", {})
        profiles = ret_cfg.get("profiles_by_category", {})
        default_profile = ret_cfg.get(
            "default_profile",
            {"base": 0.03, "restock_prob": 0.7, "recovery_low": 0.55, "recovery_high": 0.92, "salvage": 0.18},
        )
        chosen = profiles.get(category, default_profile)
        return {
            "base": float(chosen.get("base", 0.03)),
            "restock_prob": float(chosen.get("restock_prob", 0.7)),
            "recovery_low": float(chosen.get("recovery_low", 0.55)),
            "recovery_high": float(chosen.get("recovery_high", 0.92)),
            "salvage": float(chosen.get("salvage", 0.18)),
        }

    @staticmethod
    def _day_of_year(day: int) -> int:
        return ((max(1, int(day)) - 1) % 365) + 1

    @staticmethod
    def _window_applies(day_of_year: int, start_day: int, end_day: int) -> bool:
        if start_day <= end_day:
            return start_day <= day_of_year <= end_day
        # Wrap-around window (e.g., 350..20).
        return day_of_year >= start_day or day_of_year <= end_day

    def _seasonal_demand_factor(self, *, day: int, product: Product) -> float:
        season_cfg = self.realism_config.get("seasonality", {})
        if not bool(season_cfg.get("enabled", True)):
            return 1.0

        factor = float(season_cfg.get("default_multiplier", 1.0))
        day_of_week = (max(1, int(day)) - 1) % 7
        if day_of_week in (5, 6):
            factor *= float(season_cfg.get("weekend_multiplier", 1.0))

        day_of_year = self._day_of_year(day)
        for window in season_cfg.get("windows", []) or []:
            try:
                start_day = int(window.get("start_day", 1))
                end_day = int(window.get("end_day", 365))
                multiplier = float(window.get("multiplier", 1.0))
            except Exception:
                continue
            categories = window.get("categories")
            if categories and product.category not in set(map(str, categories)):
                continue
            if self._window_applies(day_of_year, start_day, end_day):
                factor *= multiplier

        return max(0.5, min(2.5, factor))

    def _seasonal_return_factor(self, *, day: int, product: Product) -> float:
        season_cfg = self.realism_config.get("seasonality", {})
        if not bool(season_cfg.get("enabled", True)):
            return 1.0

        factor = 1.0
        day_of_year = self._day_of_year(day)
        for window in season_cfg.get("return_windows", []) or []:
            try:
                start_day = int(window.get("start_day", 1))
                end_day = int(window.get("end_day", 365))
                multiplier = float(window.get("multiplier", 1.0))
            except Exception:
                continue
            categories = window.get("categories")
            if categories and product.category not in set(map(str, categories)):
                continue
            if self._window_applies(day_of_year, start_day, end_day):
                factor *= multiplier

        return max(0.6, min(2.5, factor))

    @staticmethod
    def _normalize_sku_set(raw_values: Any) -> set[str]:
        if not isinstance(raw_values, list):
            return set()
        cleaned = set()
        for value in raw_values:
            sku = str(value).strip()
            if sku:
                cleaned.add(sku)
        return cleaned

    @staticmethod
    def _build_order_summary(orders: List[Order]) -> Dict[str, Dict[str, float]]:
        summary: Dict[str, Dict[str, float]] = {}
        for order in orders:
            item = summary.setdefault(
                order.sku,
                {
                    "orders": 0.0,
                    "units": 0.0,
                    "max_price_sum": 0.0,
                    "min_customer_max_price": float(order.max_price),
                    "max_customer_max_price": float(order.max_price),
                },
            )
            item["orders"] += 1
            item["units"] += float(order.quantity)
            customer_cap = float(order.max_price)
            item["max_price_sum"] += customer_cap
            item["min_customer_max_price"] = min(item["min_customer_max_price"], customer_cap)
            item["max_customer_max_price"] = max(item["max_customer_max_price"], customer_cap)

        final: Dict[str, Dict[str, float]] = {}
        for sku, item in summary.items():
            orders_count = max(item["orders"], 1.0)
            final[sku] = {
                "orders": item["orders"],
                "units": item["units"],
                "avg_customer_max_price": round(item["max_price_sum"] / orders_count, 2),
                "min_customer_max_price": round(item["min_customer_max_price"], 2),
                "max_customer_max_price": round(item["max_customer_max_price"], 2),
            }
        return final

    def _estimate_return_probability(
        self,
        product: Product,
        order: Order,
        day: Optional[int] = None,
    ) -> float:
        """
        Simple return model influenced by rating and quantity.
        """
        profile = self._return_profile(product.category)
        base = float(profile["base"])
        rating_penalty = max(0.0, 4.4 - product.rating) * 0.018
        qty_penalty = max(0, order.quantity - 1) * 0.012
        seasonal_return = self._seasonal_return_factor(
            day=self.state.day if day is None else day,
            product=product,
        )
        return max(0.008, min(0.30, (base + rating_penalty + qty_penalty) * seasonal_return))

    def _estimate_base_return_rate(self, product: Product) -> float:
        profile = self._return_profile(product.category)
        base = float(profile["base"])
        rating_penalty = max(0.0, 4.4 - product.rating) * 0.018
        return max(0.008, min(0.22, base + rating_penalty))

    def process_inbound_orders(self) -> List[str]:
        """
        Process pending supplier deliveries at start of each day.
        Returns textual events for observability.
        """
        events: List[str] = []
        remaining: List[PendingInboundOrder] = []

        for po in self.state.pending_inbound_orders:
            delay_risk = self._lane_delay_risk(lane=po.lane, sku=po.sku)
            lane_cfg = self.realism_config.get("supplier_lanes", {})
            max_cumulative_delay = int(lane_cfg.get("max_cumulative_delay_days", 14))
            if max_cumulative_delay < 0:
                max_cumulative_delay = 0
            can_delay_more = po.cumulative_delay_days < max_cumulative_delay

            if po.days_until_arrival > 1 and can_delay_more and self.rng.random() < delay_risk:
                min_delay = int(lane_cfg.get("delay_days_min", 1))
                max_delay = int(lane_cfg.get("delay_days_max", 3))
                if max_delay < min_delay:
                    max_delay = min_delay
                delay_days = self.rng.randint(min_delay, max_delay)
                remaining_delay_budget = max_cumulative_delay - po.cumulative_delay_days
                delay_days = min(delay_days, max(0, remaining_delay_budget))
                if delay_days <= 0:
                    delay_days = 0
                else:
                    po.days_until_arrival += delay_days
                    po.cumulative_delay_days += delay_days
                    self.state.total_supplier_delay_events += 1
                    self.state.total_supplier_delay_days += delay_days
                    events.append(
                        f"Supplier delay on {po.po_id} ({po.lane}): +{delay_days}d for {po.sku}"
                    )

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

    def process_pending_returns(self) -> Dict[str, Any]:
        """
        Process delayed customer returns and refunds.
        Returns adjustment payload consumed by apply_agent_decisions.
        """
        adjustments = {
            "returns_processed": 0,
            "refunds_paid": Decimal("0.00"),
            "salvage_recovered": Decimal("0.00"),
            "events": [],
        }
        remaining: List[PendingReturn] = []

        for pending in self.state.pending_returns:
            pending.days_until_resolution -= 1
            if pending.days_until_resolution > 0:
                remaining.append(pending)
                continue

            refund_due = pending.refund_amount.quantize(Decimal("0.01"))
            refund_paid = min(refund_due, max(self.state.capital, Decimal("0.00")))
            if refund_paid > 0:
                self.state.capital -= refund_paid
                adjustments["refunds_paid"] += refund_paid
                self.state.total_refunds_paid += refund_paid
            refund_remaining = (refund_due - refund_paid).quantize(Decimal("0.01"))
            if refund_paid < refund_due:
                adjustments["events"].append(
                    f"Return {pending.return_id} partial refund: paid ${refund_paid} "
                    f"of ${refund_due}, ${refund_remaining} outstanding"
                )
            else:
                adjustments["events"].append(
                    f"Return {pending.return_id} refunded ${refund_paid} for {pending.sku}"
                )

            if not pending.inventory_reconciled:
                adjustments["returns_processed"] += 1
                product = self.state.products.get(pending.sku)
                if product is not None:
                    recovered_units = 0
                    if pending.restockable:
                        recovered_units = max(0, int(round(pending.quantity * pending.recovery_rate)))
                        if recovered_units > 0:
                            product.stock += recovered_units
                            adjustments["events"].append(
                                f"Return {pending.return_id}: restocked "
                                f"{recovered_units}/{pending.quantity} units"
                            )

                    damaged_units = max(0, pending.quantity - recovered_units)
                    if damaged_units > 0:
                        profile = self._return_profile(product.category)
                        salvage_rate = Decimal(str(profile["salvage"]))
                        salvage = (product.cost * damaged_units * salvage_rate).quantize(
                            Decimal("0.01"),
                            rounding=ROUND_HALF_UP,
                        )
                        if salvage > 0:
                            self.state.capital += salvage
                            adjustments["salvage_recovered"] += salvage
                            self.state.total_salvage_recovered += salvage
                            adjustments["events"].append(
                                f"Return {pending.return_id}: salvage recovery ${salvage} "
                                f"from {damaged_units} damaged units"
                            )
                pending.inventory_reconciled = True
                self.state.total_returns_processed += 1

            if refund_remaining > 0:
                pending.refund_amount = refund_remaining
                pending.days_until_resolution = 1
                remaining.append(pending)

        self.state.pending_returns = remaining
        return adjustments

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
        
        for sku, product in self.state.products.items():
            raw_demand = product.calculate_daily_demand(self.rng)
            price_factor = self._competitor_price_factor(sku=sku, own_price=product.price)
            seasonal_factor = self._seasonal_demand_factor(day=self.state.day, product=product)
            demand = max(0, int(round(raw_demand * price_factor * seasonal_factor)))
            
            for i in range(demand):
                self.state.next_order_sequence += 1
                # Customer max price = our price ± 10%
                max_price = product.price * Decimal(str(self.rng.uniform(0.9, 1.1)))
                
                orders.append(Order(
                    order_id=f"ORD-{self.state.next_order_sequence:07d}",
                    sku=sku,
                    quantity=self.rng.randint(1, 3),
                    max_price=max_price.quantize(Decimal("0.01")),
                ))
        
        self.rng.shuffle(orders)
        return orders

    @staticmethod
    def _demand_event_multiplier(event_type: str, severity: float) -> float:
        sev = max(0.0, float(severity))
        if event_type == "demand_spike":
            return min(3.5, 1.0 + (2.0 * sev))
        if event_type == "demand_crash":
            return max(0.25, 1.0 - (0.75 * sev))
        return 1.0

    @staticmethod
    def _price_war_shock_multiplier(severity: float) -> float:
        sev = max(0.0, float(severity))
        return max(0.55, min(0.95, 1.0 - (0.35 * sev)))

    @staticmethod
    def _price_war_drift_multiplier(severity: float) -> float:
        sev = max(0.0, float(severity))
        return max(0.70, min(0.98, 1.0 - (0.18 * sev)))

    @staticmethod
    def _review_bomb_drop(severity: float) -> float:
        sev = max(0.0, float(severity))
        return max(0.25, min(2.20, 1.20 * sev))

    @staticmethod
    def _review_bomb_recovery(severity: float) -> float:
        sev = max(0.0, float(severity))
        return max(0.10, min(0.75, 0.45 * sev))

    def _active_price_war_pressure(self, sku: str) -> float:
        pressure = 1.0
        for event in self.state.active_events:
            if event.event_type != "price_war" or event.affected_sku != sku:
                continue
            pressure *= self._price_war_drift_multiplier(event.severity)
        return max(0.55, min(1.0, pressure))

    def _apply_event_initial_effects(self, event: AdversarialEvent) -> None:
        product = self.state.products.get(event.affected_sku)
        if product is None:
            return
        if event.event_type == "review_bomb":
            drop = self._review_bomb_drop(event.severity)
            product.rating = max(1.0, product.rating - drop)
            return
        if event.event_type == "price_war":
            shock = self._price_war_shock_multiplier(event.severity)
            for comp in self.state.competitors:
                if comp.sku != event.affected_sku:
                    continue
                comp.price = (comp.price * Decimal(str(shock))).quantize(Decimal("0.01"))
            return

    def _recalculate_demand_multipliers(self) -> None:
        """
        Recompute SKU demand multipliers from active demand events.
        Avoids event-stack bugs where one expiring event can overwrite another.
        """
        for product in self.state.products.values():
            product.demand_multiplier = 1.0

        for event in self.state.active_events:
            factor = self._demand_event_multiplier(event.event_type, event.severity)
            if factor == 1.0:
                continue
            product = self.state.products.get(event.affected_sku)
            if product is None:
                continue
            product.demand_multiplier = max(0.2, min(4.0, product.demand_multiplier * factor))
    
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
        event_severity = severity * self.rng.uniform(0.8, 1.2)
        
        event = AdversarialEvent(
            event_id=f"EVT-{self.state.day}-{event_type}",
            event_type=event_type,
            affected_sku=affected_sku,
            severity=event_severity,
            days_remaining=duration,
            description=f"{desc} for {self.state.products[affected_sku].name}",
        )

        self.state.active_events.append(event)
        self._apply_event_initial_effects(event)
        self._recalculate_demand_multipliers()
        return event
    
    def update_events(self):
        """Tick down active events and remove expired ones."""
        still_active = []
        
        for event in self.state.active_events:
            event.days_remaining -= 1
            
            if event.days_remaining <= 0:
                # Event ended - restore normal state
                product = self.state.products[event.affected_sku]
                if event.event_type == "review_bomb":
                    recovery = self._review_bomb_recovery(event.severity)
                    product.rating = min(5.0, product.rating + recovery)
            else:
                still_active.append(event)
        
        self.state.active_events = still_active
        self._recalculate_demand_multipliers()

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
                lane=offer.lane,
            )
        )
        msg = (
            f"Placed {po_id}: {sku} x{final_qty} from {offer.supplier_id} "
            f"(ETA {offer.lead_time_days}d via {offer.lane} @ ${offer.unit_cost})"
        )
        return True, msg, total_cost
    
    def apply_agent_decisions(
        self, 
        decisions: Dict[str, Any],
        orders: List[Order],
        pre_day_adjustments: Optional[Dict[str, Any]] = None,
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
            "fulfillment_fees": Decimal("0.00"),
            "payment_processing_fees": Decimal("0.00"),
            "fixed_operating_cost": Decimal("0.00"),
            "returns_processed": 0,
            "refunds_paid": Decimal("0.00"),
            "salvage_recovered": Decimal("0.00"),
            "events": [],
        }

        # Baseline daily operating overhead.
        if self.daily_platform_overhead > 0:
            overhead = min(self.daily_platform_overhead, max(self.state.capital, Decimal("0.00")))
            if overhead > 0:
                self.state.capital -= overhead
                results["costs"] += overhead
                results["fixed_operating_cost"] += overhead
                results["events"].append(f"Daily platform overhead charged: ${overhead}")

        if pre_day_adjustments:
            returns_processed = int(pre_day_adjustments.get("returns_processed", 0))
            refunds_paid = Decimal(str(pre_day_adjustments.get("refunds_paid", 0.0))).quantize(
                Decimal("0.01")
            )
            salvage_recovered = Decimal(
                str(pre_day_adjustments.get("salvage_recovered", 0.0))
            ).quantize(Decimal("0.01"))
            results["returns_processed"] += returns_processed
            results["refunds_paid"] += refunds_paid
            results["salvage_recovered"] += salvage_recovered
            # Refunds and salvage affect the day's P&L.
            results["revenue"] -= refunds_paid
            results["revenue"] += salvage_recovered
            for event in pre_day_adjustments.get("events", []) or []:
                msg = str(event).strip()
                if msg:
                    results["events"].append(msg)
        
        # Apply price changes
        price_changes = decisions.get("price_changes", {})
        for sku, new_price in price_changes.items():
            if sku in self.state.products:
                old_price = self.state.products[sku].price
                try:
                    candidate = Decimal(str(new_price)).quantize(Decimal("0.01"))
                except Exception:
                    continue
                if candidate <= 0:
                    results["events"].append(f"FAILED price change {sku}: price must be > 0")
                    continue
                self.state.products[sku].price = candidate
                results["events"].append(f"Changed {sku} price: ${old_price} → ${candidate}")
        
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
                qty_i = min(qty_i, self.max_order_qty_per_decision)
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
            qty = min(qty, self.max_order_qty_per_decision)
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
        accept_all_orders = bool(decisions.get("accept_all_orders", False))
        accept_orders_raw = decisions.get("accept_orders", [])
        accept_orders = set()
        if isinstance(accept_orders_raw, list):
            for order_id in accept_orders_raw:
                oid = str(order_id).strip()
                if oid:
                    accept_orders.add(oid)
        accept_skus = self._normalize_sku_set(decisions.get("accept_skus", []))
        reject_skus = self._normalize_sku_set(decisions.get("reject_skus", []))
        
        for order in orders:
            product = self.state.products.get(order.sku)
            if not product:
                continue
            
            # Check if agent accepted this order
            should_accept = accept_all_orders or (order.order_id in accept_orders)
            if order.sku in accept_skus:
                should_accept = True
            if order.sku in reject_skus:
                should_accept = False

            if not should_accept:
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

            # Realism pass: account for per-order fulfillment + processing fees.
            fulfillment_fee = (self.fulfillment_fee_per_unit * order.quantity).quantize(Decimal("0.01"))
            payment_fee = (order_revenue * self.payment_processing_rate).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            order_fees = fulfillment_fee + payment_fee
            if order_fees > 0:
                self.state.capital -= order_fees
                results["costs"] += order_fees
                results["fulfillment_fees"] += fulfillment_fee
                results["payment_processing_fees"] += payment_fee

            if product.ad_boost > 1.0:
                attributed = (order_revenue * Decimal(str(min(0.5, product.ad_boost - 1.0)))).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
                results["ad_attributed_revenue"] += attributed

            # Delayed returns/refunds pipeline for realism.
            return_probability = self._estimate_return_probability(
                product=product,
                order=order,
                day=self.state.day,
            )
            if self.rng.random() < return_probability:
                return_id = f"RET-{self.state.day:03d}-{len(self.state.pending_returns) + 1:03d}"
                profile = self._return_profile(product.category)
                restockable = self.rng.random() < float(profile["restock_prob"])
                recovery_rate = (
                    self.rng.uniform(float(profile["recovery_low"]), float(profile["recovery_high"]))
                    if restockable
                    else 0.0
                )
                self.state.pending_returns.append(
                    PendingReturn(
                        return_id=return_id,
                        order_id=order.order_id,
                        sku=order.sku,
                        quantity=order.quantity,
                        refund_amount=order_revenue.quantize(Decimal("0.01")),
                        days_until_resolution=self.rng.randint(2, 10),
                        restockable=restockable,
                        recovery_rate=recovery_rate,
                    )
                )
                results["events"].append(
                    f"Potential return flagged for {order.order_id} ({order.sku}); pending resolution"
                )

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
        order_book_by_sku = self._build_order_summary(orders)
        pending_refund_exposure = self.state.get_pending_refund_exposure()
        
        return {
            "day": self.state.day,
            "total_days": self.state.total_days,
            "days_remaining": max(0, self.state.total_days - self.state.day),
            "capital": float(self.state.capital),
            "total_profit_so_far": float(self.state.get_profit()),
            "equity_value": float(self.state.get_equity()),
            "equity_profit_so_far": float(self.state.get_equity_profit()),
            "roi_percent": self.state.get_roi(),
            
            "products": {
                sku: {
                    "name": p.name,
                    "category": p.category,
                    "cost": float(p.cost),
                    "price": float(p.price),
                    "stock": p.stock,
                    "rating": p.rating,
                    "ad_boost_today": round(p.ad_boost, 3),
                    "next_day_ad_boost": round(p.next_day_ad_boost, 3),
                    "seasonality_factor_today": round(
                        self._seasonal_demand_factor(day=self.state.day, product=p),
                        3,
                    ),
                    "base_return_rate_estimate": round(self._estimate_base_return_rate(p), 4),
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
            "order_book_by_sku": order_book_by_sku,
            
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
                        "lane": s.lane,
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
                    "lane": po.lane,
                    "cumulative_delay_days": po.cumulative_delay_days,
                }
                for po in self.state.pending_inbound_orders
            ],

            "pending_returns": [
                {
                    "return_id": ret.return_id,
                    "sku": ret.sku,
                    "quantity": ret.quantity,
                    "refund_amount": float(ret.refund_amount),
                    "days_until_resolution": ret.days_until_resolution,
                    "restockable": ret.restockable,
                }
                for ret in self.state.pending_returns[:20]
            ],
            "returns_overview": {
                "pending_count": len(self.state.pending_returns),
                "pending_refund_exposure": float(pending_refund_exposure.quantize(Decimal("0.01"))),
                "total_returns_processed": self.state.total_returns_processed,
                "total_refunds_paid": float(self.state.total_refunds_paid),
                "total_salvage_recovered": float(self.state.total_salvage_recovered),
            },
            "supply_chain_overview": {
                "pending_inbound_count": len(self.state.pending_inbound_orders),
                "total_supplier_delay_events": self.state.total_supplier_delay_events,
                "total_supplier_delay_days": self.state.total_supplier_delay_days,
            },
            
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
            "calendar_context": {
                "day_of_year": self._day_of_year(self.state.day),
                "is_weekend": ((self.state.day - 1) % 7) in (5, 6),
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
Your goal is to MAXIMIZE PROFIT over the configured simulation horizon starting with $10,000 capital.

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
- Supplier lanes (domestic/nearshore/overseas) carry different delay risk
- Ad budget spent today mostly affects demand tomorrow
- Customer service actions cost money but can protect rating and conversion
- Fulfilled orders incur fulfillment and payment processing fees
- Customer returns vary by product category and can trigger delayed refunds/salvage recovery
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

## CURRENT STATE (Day {state['day']} of {state['total_days']})
Capital: ${state['capital']:,.2f}
Total Profit So Far: ${state['total_profit_so_far']:,.2f}
Equity Value: ${state['equity_value']:,.2f}
Equity Profit So Far: ${state['equity_profit_so_far']:,.2f}
ROI: {state['roi_percent']:.1f}%
{feedback_section}

## YOUR PRODUCTS
{json.dumps(state['products'], indent=2)}

## CALENDAR CONTEXT
{json.dumps(state['calendar_context'], indent=2)}

## TODAY'S ORDERS ({state['total_orders_today']} total)
Order summary by SKU:
{json.dumps(state['order_book_by_sku'], indent=2)}

Sample of individual orders:
{json.dumps(state['todays_orders'][:15], indent=2)}
{"... and more orders" if state['total_orders_today'] > 15 else ""}

## COMPETITOR PRICES
{json.dumps(state['competitors'], indent=2)}

## SUPPLIER OPTIONS
{json.dumps(state['supplier_options'], indent=2)}

## INBOUND ORDERS (already placed, not yet received)
{json.dumps(state['inbound_orders'], indent=2)}
Supply chain overview:
{json.dumps(state['supply_chain_overview'], indent=2)}

## RETURNS PIPELINE
{json.dumps(state['returns_overview'], indent=2)}
Pending return queue (sample):
{json.dumps(state['pending_returns'], indent=2)}

## CUSTOMER SERVICE
{json.dumps(state['customer_service'], indent=2)}

## ACTIVE EVENTS
{json.dumps(state['active_events'], indent=2) if state['active_events'] else "None currently."}
{memory_section}

## YOUR DECISIONS (respond with JSON only)
{{
    "reasoning": "Brief explanation of your strategy today",
    "accept_all_orders": false,  // true = all orders are eligible unless blocked by reject_skus
    "accept_skus": ["P001", "P002"],  // Optional SKU allowlist
    "reject_skus": ["P008"],  // Optional SKU blocklist (highest priority)
    "accept_orders": ["ORD-000001", "ORD-000002", ...],  // Optional specific order IDs
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
                "accept_all_orders": True,
                "accept_skus": [],
                "reject_skus": [],
                "accept_orders": [],
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
    live_trace_enabled: bool = True,
    live_trace_file: Optional[str] = None,
    realism_config_path: Optional[str] = None,
    replay_results_file: Optional[str] = None,
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
    if realism_config_path:
        print(f"Realism config: {realism_config_path}")
    if replay_results_file:
        print(f"Replay source: {replay_results_file}")
    if live_trace_enabled:
        print(f"Live theater trace: {live_trace_file or 'docs/api/sim_theater_live.json'}")
    print("="*80 + "\n")

    replay_decisions: Optional[List[Dict[str, Any]]] = None
    if replay_results_file:
        replay_decisions = _load_replay_decisions(replay_results_file)
        if days != len(replay_decisions):
            print(
                f"⚠️  Overriding --days={days} to replay length={len(replay_decisions)} "
                f"from {replay_results_file}"
            )
            days = len(replay_decisions)
    else:
        # Check API key only for live LLM runs.
        if not os.getenv("OPENROUTER_API_KEY"):
            print("❌ Set OPENROUTER_API_KEY first!")
            return None
    
    realism_config = _load_realism_config(realism_config_path)
    simulator = MarketSimulator(seed=seed, realism_config=realism_config)
    simulator.state.total_days = days
    agent: Optional[GrokAgent] = None
    if replay_decisions is None:
        agent = GrokAgent()
    memory_engine: Optional[ReflectiveMemoryV1] = None
    if memory_mode == "reflective":
        memory_engine = ReflectiveMemoryV1()

    live_trace_path = Path(live_trace_file) if live_trace_file else (
        Path(__file__).parent / "docs" / "api" / "sim_theater_live.json"
    )
    live_trace_payload: Optional[Dict[str, Any]] = None
    run_id = f"grok_proper_sim_{int(time.time())}"
    if live_trace_enabled:
        live_trace_payload = {
            "run_id": run_id,
            "status": "running",
            "phase": "initializing",
            "started_at_utc": _utc_now_iso(),
            "updated_at_utc": _utc_now_iso(),
            "config": {
                "days": days,
                "seed": seed,
                "memory_mode": memory_mode,
                "memory_review_mode": memory_review_mode,
                "weekly_consolidation": weekly_consolidation,
                "realism_config_path": realism_config_path,
            },
            "progress": {"day": 0, "days_total": days, "percent": 0.0},
            "current_frame": None,
            "recent_frames": [],
            "frames": [],
            "series": {
                "day": [],
                "capital": [],
                "daily_profit": [],
                "roi_percent": [],
                "orders_fulfilled": [],
                "stockouts": [],
            },
            "execution": {
                "llm_calls": 0,
                "reflection_calls": 0,
                "total_tokens": 0,
                "elapsed_seconds": 0.0,
            },
        }
        _write_json_atomic(live_trace_path, live_trace_payload)
    
    start_time = time.time()
    last_results = None
    previous_theater_frame: Optional[Dict[str, Any]] = None
    
    try:
        for day in range(1, days + 1):
            simulator.state.day = day
            if live_trace_enabled and live_trace_payload is not None:
                live_trace_payload["phase"] = f"day_{day}: model_deciding"
                live_trace_payload["progress"] = {
                    "day": day,
                    "days_total": days,
                    "percent": round((day - 1) / max(days, 1) * 100, 2),
                }
                live_trace_payload["updated_at_utc"] = _utc_now_iso()
                _write_json_atomic(live_trace_path, live_trace_payload)

            # 0. Receive inbound supplier orders due today.
            inbound_events = simulator.process_inbound_orders()
            if inbound_events and verbose:
                for evt in inbound_events[:3]:
                    print(f"📦 Day {day}: {evt}")

            return_adjustments = simulator.process_pending_returns()
            if return_adjustments.get("returns_processed", 0) and verbose:
                print(
                    f"↩️ Day {day}: processed {return_adjustments['returns_processed']} returns "
                    f"(refunds ${return_adjustments['refunds_paid']}, "
                    f"salvage ${return_adjustments['salvage_recovered']})"
                )
            
            # 1. Generate today's orders
            simulator.evolve_competitor_prices()
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
            decision_latency_seconds = 0.0
            if replay_decisions is not None:
                decisions = replay_decisions[day - 1]
            else:
                assert agent is not None
                decision_started_at = time.time()
                decisions = await agent.decide(state, last_results)
                decision_latency_seconds = time.time() - decision_started_at
            
            # 5. Apply decisions and get results
            results = simulator.apply_agent_decisions(
                decisions,
                orders,
                pre_day_adjustments=return_adjustments,
            )
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
                        "equity_value": state.get("equity_value"),
                        "roi_percent": state.get("roi_percent"),
                        "supply_chain_overview": state.get("supply_chain_overview"),
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
                        "fulfillment_fees": float(results["fulfillment_fees"]),
                        "payment_processing_fees": float(results["payment_processing_fees"]),
                        "fixed_operating_cost": float(results["fixed_operating_cost"]),
                        "returns_processed": results["returns_processed"],
                        "refunds_paid": float(results["refunds_paid"]),
                        "salvage_recovered": float(results["salvage_recovered"]),
                    },
                }

                review_payload = None
                if memory_review_mode == "llm":
                    assert agent is not None
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
            
            theater_frame = _build_theater_frame(
                simulator=simulator,
                day=day,
                decisions=decisions,
                results=results,
                decision_latency_seconds=decision_latency_seconds,
            )
            theater_frame["story"] = _build_storyline(
                frame=theater_frame,
                previous_frame=previous_theater_frame,
            )
            previous_theater_frame = theater_frame

            # Store decision
            simulator.state.decisions_made.append({
                "day": day,
                "reasoning": decisions.get("reasoning", ""),
                "story_headline": theater_frame.get("story", {}).get("headline", ""),
                "decisions_raw": _sanitize_decisions_for_replay(decisions),
                "actions": {
                    "accept_all_orders": bool(decisions.get("accept_all_orders", False)),
                    "accept_skus": _action_count(decisions.get("accept_skus", [])),
                    "reject_skus": _action_count(decisions.get("reject_skus", [])),
                    "orders_accepted": _action_count(decisions.get("accept_orders", [])),
                    "price_changes": _action_count(decisions.get("price_changes", {})),
                    "restocks": _action_count(decisions.get("restock", {})),
                    "supplier_orders": _action_count(decisions.get("supplier_orders", [])),
                    "ad_budget_shifts": _action_count(decisions.get("ad_budget_shift", {})),
                    "customer_ops_updates": _action_count(decisions.get("customer_ops", {})),
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
                    "fulfillment_fees": float(results["fulfillment_fees"]),
                    "payment_processing_fees": float(results["payment_processing_fees"]),
                    "fixed_operating_cost": float(results["fixed_operating_cost"]),
                    "returns_processed": results["returns_processed"],
                    "refunds_paid": float(results["refunds_paid"]),
                    "salvage_recovered": float(results["salvage_recovered"]),
                },
                "memory": {
                    "daily": memory_daily_summary.to_dict() if memory_daily_summary else None,
                    "weekly": memory_weekly_summary.to_dict() if memory_weekly_summary else None,
                },
            })

            if live_trace_enabled and live_trace_payload is not None:
                recent_frames = list(live_trace_payload.get("recent_frames", []))
                recent_frames.append(theater_frame)
                live_trace_payload["recent_frames"] = recent_frames[-3:]
                live_trace_payload["current_frame"] = theater_frame
                all_frames = list(live_trace_payload.get("frames", []))
                all_frames.append(theater_frame)
                live_trace_payload["frames"] = all_frames
                series = live_trace_payload.get("series", {})
                series["day"] = [*series.get("day", []), day]
                series["capital"] = [*series.get("capital", []), float(simulator.state.capital)]
                series["daily_profit"] = [*series.get("daily_profit", []), float(results["profit"])]
                series["roi_percent"] = [*series.get("roi_percent", []), float(simulator.state.get_roi())]
                series["orders_fulfilled"] = [
                    *series.get("orders_fulfilled", []),
                    int(results["orders_fulfilled"]),
                ]
                series["stockouts"] = [*series.get("stockouts", []), int(results["stockouts"])]
                live_trace_payload["series"] = series
                live_trace_payload["progress"] = {
                    "day": day,
                    "days_total": days,
                    "percent": round(day / max(days, 1) * 100, 2),
                }
                live_trace_payload["updated_at_utc"] = _utc_now_iso()
                live_trace_payload["execution"] = {
                    "llm_calls": agent.calls if agent is not None else 0,
                    "reflection_calls": agent.reflection_calls if agent is not None else 0,
                    "total_tokens": agent.total_tokens if agent is not None else 0,
                    "elapsed_seconds": round(time.time() - start_time, 2),
                }
                live_trace_payload["phase"] = f"day_{day}: results_applied"
                _write_json_atomic(live_trace_path, live_trace_payload)
            
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
        print(f"🤖 LLM Calls: {agent.calls if agent is not None else 0}")
        print(f"🧠 Reflection Calls: {agent.reflection_calls if agent is not None else 0}")
        print(f"📝 Total Tokens: {(agent.total_tokens if agent is not None else 0):,}")
        print()
        print("💰 Starting Capital: $10,000.00")
        print(f"💰 Final Capital: ${simulator.state.capital:,.2f}")
        print(f"🏦 Final Equity: ${simulator.state.get_equity():,.2f}")
        print(f"📈 Total Revenue: ${simulator.state.total_revenue:,.2f}")
        print(f"📉 Total Costs: ${simulator.state.total_costs:,.2f}")
        print(f"💵 Net Profit: ${simulator.state.get_profit():,.2f}")
        print(f"💵 Equity Profit: ${simulator.state.get_equity_profit():,.2f}")
        print(f"📊 ROI: {simulator.state.get_roi():.1f}%")
        print(f"📣 Total Ad Spend: ${simulator.state.total_ad_spend:,.2f}")
        print()
        print(f"📦 Orders Fulfilled: {simulator.state.total_orders_fulfilled:,}")
        print(f"❌ Total Stockouts: {simulator.state.total_stockouts}")
        print(f"↩️ Returns Processed: {simulator.state.total_returns_processed}")
        print(f"💸 Refunds Paid: ${simulator.state.total_refunds_paid:,.2f}")
        print(f"♻️ Salvage Recovered: ${simulator.state.total_salvage_recovered:,.2f}")
        print(f"🚚 Supplier Delay Events: {simulator.state.total_supplier_delay_events}")
        print(f"⏳ Supplier Delay Days: {simulator.state.total_supplier_delay_days}")
        print(f"🛠️ Open Customer Backlog: {sum(simulator.state.customer_backlog.values())}")
        print("="*80)
        
        # Save results
        file_prefix = "grok_proper_sim_replay" if replay_decisions is not None else "grok_proper_sim"
        results_file = Path(__file__).parent / "results" / f"{file_prefix}_{int(time.time())}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        final_results = {
            "config": {
                "days": days,
                "seed": seed,
                "model": "x-ai/grok-4.1-fast",
                "memory_mode": memory_mode,
                "memory_review_mode": memory_review_mode,
                "weekly_consolidation": weekly_consolidation,
                "realism_config_path": realism_config_path,
                "run_mode": "replay" if replay_decisions is not None else "live",
                "replay_source": replay_results_file,
            },
            "execution": {
                "time_seconds": elapsed,
                "llm_calls": agent.calls if agent is not None else 0,
                "reflection_calls": agent.reflection_calls if agent is not None else 0,
                "total_tokens": agent.total_tokens if agent is not None else 0,
            },
            "results": {
                "starting_capital": float(simulator.state.starting_capital),
                "starting_inventory_value": float(simulator.state.starting_inventory_value),
                "starting_equity": float(simulator.state.starting_equity),
                "final_capital": float(simulator.state.capital),
                "final_inventory_value": float(simulator.state.get_inventory_value()),
                "final_equity": float(simulator.state.get_equity()),
                "total_revenue": float(simulator.state.total_revenue),
                "total_costs": float(simulator.state.total_costs),
                "net_profit": float(simulator.state.get_profit()),
                "equity_profit": float(simulator.state.get_equity_profit()),
                "roi_percent": simulator.state.get_roi(),
                "orders_fulfilled": simulator.state.total_orders_fulfilled,
                "stockouts": simulator.state.total_stockouts,
                "total_ad_spend": float(simulator.state.total_ad_spend),
                "returns_processed": simulator.state.total_returns_processed,
                "refunds_paid": float(simulator.state.total_refunds_paid),
                "salvage_recovered": float(simulator.state.total_salvage_recovered),
                "supplier_delay_events": simulator.state.total_supplier_delay_events,
                "supplier_delay_days": simulator.state.total_supplier_delay_days,
                "open_customer_backlog": int(sum(simulator.state.customer_backlog.values())),
                "pending_refund_exposure": float(simulator.state.get_pending_refund_exposure()),
                "pending_returns_open": len(simulator.state.pending_returns),
            },
            "daily_performance": {
                "revenue": [float(r) for r in simulator.state.daily_revenue],
                "costs": [float(c) for c in simulator.state.daily_costs],
                "profit": [float(p) for p in simulator.state.daily_profit],
                "ad_spend": [float(x) for x in simulator.state.daily_ad_spend],
                "ad_attributed_revenue": [float(x) for x in simulator.state.daily_ad_attributed_revenue],
            },
            "decisions": simulator.state.decisions_made,
        }
        if memory_engine is not None:
            final_results["memory"] = memory_engine.summary()
        
        with open(results_file, "w") as f:
            json.dump(final_results, f, indent=2)

        if live_trace_enabled and live_trace_payload is not None:
            live_trace_payload["status"] = "completed"
            live_trace_payload["phase"] = "finished"
            live_trace_payload["updated_at_utc"] = _utc_now_iso()
            live_trace_payload["results_file"] = str(results_file)
            live_trace_payload["final_results"] = {
                "final_capital": float(simulator.state.capital),
                "net_profit": float(simulator.state.get_profit()),
                "final_equity": float(simulator.state.get_equity()),
                "equity_profit": float(simulator.state.get_equity_profit()),
                "roi_percent": float(simulator.state.get_roi()),
                "orders_fulfilled": simulator.state.total_orders_fulfilled,
                "stockouts": simulator.state.total_stockouts,
                "returns_processed": simulator.state.total_returns_processed,
                "supplier_delay_events": simulator.state.total_supplier_delay_events,
                "supplier_delay_days": simulator.state.total_supplier_delay_days,
                "pending_refund_exposure": float(simulator.state.get_pending_refund_exposure()),
                "pending_returns_open": len(simulator.state.pending_returns),
            }
            _write_json_atomic(live_trace_path, live_trace_payload)
        
        print(f"\n💾 Saved to: {results_file}")
        
        return final_results
        
    except Exception:
        if live_trace_enabled and live_trace_payload is not None:
            live_trace_payload["status"] = "failed"
            live_trace_payload["phase"] = "error"
            live_trace_payload["updated_at_utc"] = _utc_now_iso()
            live_trace_payload["execution"] = {
                "llm_calls": agent.calls if agent is not None else 0,
                "reflection_calls": agent.reflection_calls if agent is not None else 0,
                "total_tokens": agent.total_tokens if agent is not None else 0,
                "elapsed_seconds": round(time.time() - start_time, 2),
            }
            _write_json_atomic(live_trace_path, live_trace_payload)
        raise
    finally:
        if agent is not None:
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
    parser.add_argument(
        "--no-live-trace",
        action="store_true",
        help="Disable live theater trace JSON output",
    )
    parser.add_argument(
        "--live-trace-file",
        default=str(Path(__file__).parent / "docs" / "api" / "sim_theater_live.json"),
        help="Path for live theater trace JSON",
    )
    parser.add_argument(
        "--realism-config",
        default=None,
        help="Optional YAML file to tune seasonality/returns/supplier-lane realism",
    )
    parser.add_argument(
        "--replay-results-file",
        default=None,
        help="Offline replay: load decisions from a prior results JSON (writes grok_proper_sim_replay_*.json)",
    )
    args = parser.parse_args()
    
    asyncio.run(run_simulation(
        days=args.days,
        seed=args.seed,
        verbose=not args.quiet,
        memory_mode=args.memory_mode,
        memory_review_mode=args.memory_review_mode,
        weekly_consolidation=not args.no_weekly_consolidation,
        live_trace_enabled=not args.no_live_trace,
        live_trace_file=args.live_trace_file,
        realism_config_path=args.realism_config,
        replay_results_file=args.replay_results_file,
    ))


if __name__ == "__main__":
    main()
