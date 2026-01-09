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
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient

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
    
    def calculate_daily_demand(self, rng: random.Random) -> int:
        """Calculate actual demand for today with randomness."""
        base = self.daily_demand_base * self.demand_multiplier
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
class SimulationState:
    """Full state of the simulation."""
    day: int = 0
    capital: Decimal = Decimal("10000.00")
    products: Dict[str, Product] = field(default_factory=dict)
    competitors: List[Competitor] = field(default_factory=list)
    active_events: List[AdversarialEvent] = field(default_factory=list)
    
    # Historical tracking
    daily_revenue: List[Decimal] = field(default_factory=list)
    daily_costs: List[Decimal] = field(default_factory=list)
    daily_profit: List[Decimal] = field(default_factory=list)
    decisions_made: List[Dict] = field(default_factory=list)
    
    # Cumulative stats
    total_revenue: Decimal = Decimal("0.00")
    total_costs: Decimal = Decimal("0.00") 
    total_orders_fulfilled: int = 0
    total_stockouts: int = 0
    
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
    
    def generate_daily_orders(self) -> List[Order]:
        """Generate customer orders for today based on demand."""
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
                cost = product.cost * quantity
                if cost <= self.state.capital:
                    self.state.capital -= cost
                    product.stock += quantity
                    results["costs"] += cost
                    results["events"].append(f"Restocked {sku}: +{quantity} units (cost ${cost})")
                else:
                    results["events"].append(f"FAILED restock {sku}: insufficient capital")
        
        # Process customer orders
        accept_orders = set(decisions.get("accept_orders", []))
        
        for order in orders:
            product = self.state.products.get(order.sku)
            if not product:
                continue
            
            # Check if agent accepted this order
            if order.order_id not in accept_orders:
                results["orders_rejected"] += 1
                continue
            
            # Check if customer will pay our price
            if product.price > order.max_price:
                results["orders_rejected"] += 1
                results["events"].append(f"Lost {order.order_id}: price ${product.price} > customer max ${order.max_price}")
                continue
            
            # Check stock
            if product.stock < order.quantity:
                results["stockouts"] += 1
                results["events"].append(f"Stockout on {order.order_id}: need {order.quantity}, have {product.stock}")
                continue
            
            # Fulfill order!
            product.stock -= order.quantity
            order_revenue = product.price * order.quantity
            self.state.capital += order_revenue
            results["revenue"] += order_revenue
            results["orders_fulfilled"] += 1
        
        # Calculate profit
        results["profit"] = results["revenue"] - results["costs"]
        
        # Update state tracking
        self.state.daily_revenue.append(results["revenue"])
        self.state.daily_costs.append(results["costs"])
        self.state.daily_profit.append(results["profit"])
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
            
            "recent_performance": {
                "last_7_days_revenue": [float(r) for r in recent_revenue],
                "last_7_days_profit": [float(p) for p in recent_profit],
                "total_stockouts": self.state.total_stockouts,
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
4. Make decisions: accept orders, adjust prices, restock inventory

KEY RULES:
- You can only fulfill orders if you have stock
- Customers won't buy if your price exceeds their max price
- Restocking costs capital upfront
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
        self.total_tokens = 0
        
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

## ACTIVE EVENTS
{json.dumps(state['active_events'], indent=2) if state['active_events'] else "None currently."}

## YOUR DECISIONS (respond with JSON only)
{{
    "reasoning": "Brief explanation of your strategy today",
    "accept_orders": ["ORD-000001", "ORD-000002", ...],  // Order IDs to fulfill
    "price_changes": {{"P001": 34.99, ...}},  // Optional price adjustments
    "restock": {{"P001": 50, ...}}  // Optional restock orders (costs capital!)
}}
"""

        try:
            response = await self.client.generate_response(prompt)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            # Track token usage
            usage = response.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)
            
            # Parse JSON from response
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            decisions = json.loads(content.strip())
            return decisions
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            # Fallback: accept all orders, no changes
            return {
                "reasoning": "Fallback: accept all orders",
                "accept_orders": [o["order_id"] for o in state["todays_orders"]],
                "price_changes": {},
                "restock": {},
            }
    
    async def close(self):
        await self.client.aclose()


# ============================================================================
# MAIN SIMULATION LOOP
# ============================================================================

async def run_simulation(
    days: int = 730,
    seed: int = 42,
    verbose: bool = True,
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
    print("="*80 + "\n")
    
    # Check API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ Set OPENROUTER_API_KEY first!")
        return None
    
    simulator = MarketSimulator(seed=seed)
    agent = GrokAgent()
    
    start_time = time.time()
    last_results = None
    
    try:
        for day in range(1, days + 1):
            simulator.state.day = day
            
            # 1. Generate today's orders
            orders = simulator.generate_daily_orders()
            
            # 2. Maybe inject adversarial event
            new_event = simulator.maybe_inject_event()
            if new_event and verbose:
                print(f"⚠️  Day {day}: NEW EVENT - {new_event.description}")
            
            # 3. Get state for agent (includes yesterday's feedback!)
            state = simulator.get_state_for_agent(orders)
            
            # 4. Agent makes decisions WITH FEEDBACK
            decisions = await agent.decide(state, last_results)
            
            # 5. Apply decisions and get results
            results = simulator.apply_agent_decisions(decisions, orders)
            last_results = results  # This becomes feedback for tomorrow!
            
            # 6. Update events (tick down timers)
            simulator.update_events()
            
            # Store decision
            simulator.state.decisions_made.append({
                "day": day,
                "reasoning": decisions.get("reasoning", ""),
                "actions": {
                    "orders_accepted": len(decisions.get("accept_orders", [])),
                    "price_changes": len(decisions.get("price_changes", {})),
                    "restocks": len(decisions.get("restock", {})),
                },
                "results": {
                    "revenue": float(results["revenue"]),
                    "profit": float(results["profit"]),
                    "fulfilled": results["orders_fulfilled"],
                    "stockouts": results["stockouts"],
                },
            })
            
            # Progress update
            if verbose and day % 30 == 0:
                print(f"📅 Day {day:3d} | Capital: ${simulator.state.capital:,.2f} | "
                      f"Profit: ${simulator.state.get_profit():,.2f} | "
                      f"LLM Calls: {agent.calls}")
        
        elapsed = time.time() - start_time
        
        # Final results
        print("\n" + "="*80)
        print("📊 FINAL RESULTS")
        print("="*80)
        print(f"⏱️  Execution Time: {elapsed/60:.1f} minutes")
        print(f"🤖 LLM Calls: {agent.calls}")
        print(f"📝 Total Tokens: {agent.total_tokens:,}")
        print()
        print(f"💰 Starting Capital: $10,000.00")
        print(f"💰 Final Capital: ${simulator.state.capital:,.2f}")
        print(f"📈 Total Revenue: ${simulator.state.total_revenue:,.2f}")
        print(f"📉 Total Costs: ${simulator.state.total_costs:,.2f}")
        print(f"💵 Net Profit: ${simulator.state.get_profit():,.2f}")
        print(f"📊 ROI: {simulator.state.get_roi():.1f}%")
        print()
        print(f"📦 Orders Fulfilled: {simulator.state.total_orders_fulfilled:,}")
        print(f"❌ Total Stockouts: {simulator.state.total_stockouts}")
        print("="*80)
        
        # Save results
        results_file = Path(__file__).parent / "results" / f"grok_proper_sim_{int(time.time())}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        final_results = {
            "config": {
                "days": days,
                "seed": seed,
                "model": "x-ai/grok-4.1-fast",
            },
            "execution": {
                "time_seconds": elapsed,
                "llm_calls": agent.calls,
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
            },
            "daily_performance": {
                "revenue": [float(r) for r in simulator.state.daily_revenue],
                "profit": [float(p) for p in simulator.state.daily_profit],
            },
            "decisions": simulator.state.decisions_made[-50:],  # Last 50 decisions
        }
        
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
    args = parser.parse_args()
    
    asyncio.run(run_simulation(
        days=args.days,
        seed=args.seed,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    main()
