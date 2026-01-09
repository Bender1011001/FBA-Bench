#!/usr/bin/env python3
"""
FBA-Bench: LIVE VISUALIZATION Tick-Based Simulation

Watch Grok make business decisions in real-time with rich console output.

USAGE:
  1. Edit simulation_settings.yaml to configure
  2. Run: poetry run python run_grok_live.py

All settings are loaded from simulation_settings.yaml
"""

import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load settings from YAML
SETTINGS_FILE = Path(__file__).parent / "simulation_settings.yaml"

def load_settings() -> Dict:
    """Load settings from YAML file."""
    if not SETTINGS_FILE.exists():
        print(f"❌ Settings file not found: {SETTINGS_FILE}")
        print("   Create it or copy from simulation_settings.yaml.example")
        sys.exit(1)
    
    with open(SETTINGS_FILE) as f:
        return yaml.safe_load(f)

SETTINGS = load_settings()

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient


# ============================================================================
# RICH CONSOLE OUTPUT
# ============================================================================

class LiveDisplay:
    """Rich console output for visualization."""
    
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "gray": "\033[90m",
    }
    
    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_header(day: int, total_days: int, capital: float, profit: float):
        c = LiveDisplay.COLORS
        print(f"\n{c['bold']}{c['cyan']}{'='*70}{c['reset']}")
        print(f"{c['bold']}📅 DAY {day}/{total_days}  |  💰 Capital: ${capital:,.2f}  |  📈 Profit: ${profit:+,.2f}{c['reset']}")
        print(f"{c['cyan']}{'='*70}{c['reset']}\n")
    
    @staticmethod
    def print_state(products: Dict, events: List, competitors: List):
        c = LiveDisplay.COLORS
        
        print(f"{c['bold']}📦 INVENTORY:{c['reset']}")
        for sku, p in products.items():
            stock_color = c['green'] if p['stock'] > 20 else c['yellow'] if p['stock'] > 5 else c['red']
            print(f"   {sku}: {p['name'][:20]:<20} | "
                  f"${p['price']:<6.2f} | "
                  f"{stock_color}Stock: {p['stock']:>3}{c['reset']} | "
                  f"⭐ {p['rating']:.1f}")
        
        if events:
            print(f"\n{c['bold']}{c['yellow']}⚠️  ACTIVE EVENTS:{c['reset']}")
            for e in events:
                print(f"   {c['yellow']}• {e['type']}: {e['description']} ({e['days_remaining']} days left){c['reset']}")
    
    @staticmethod
    def print_orders(orders: List, total: int):
        c = LiveDisplay.COLORS
        print(f"\n{c['bold']}📋 TODAY'S ORDERS: {total} total{c['reset']}")
        for o in orders[:8]:  # Show first 8
            print(f"   {o['order_id']}: {o['sku']} x{o['quantity']} (max ${o['customer_max_price']:.2f})")
        if total > 8:
            print(f"   {c['gray']}... and {total - 8} more orders{c['reset']}")
    
    @staticmethod
    def print_thinking():
        c = LiveDisplay.COLORS
        print(f"\n{c['bold']}{c['magenta']}🧠 GROK IS THINKING...{c['reset']}")
    
    @staticmethod
    def print_decision(reasoning: str, actions: Dict):
        c = LiveDisplay.COLORS
        print(f"\n{c['bold']}{c['blue']}💭 GROK'S REASONING:{c['reset']}")
        # Word wrap reasoning
        words = reasoning.split()
        line = "   "
        for word in words:
            if len(line) + len(word) > 65:
                print(line)
                line = "   "
            line += word + " "
        if line.strip():
            print(line)
        
        print(f"\n{c['bold']}📝 DECISIONS:{c['reset']}")
        if actions.get('price_changes'):
            print(f"   {c['cyan']}Price Changes:{c['reset']}")
            for sku, price in actions['price_changes'].items():
                print(f"      {sku} → ${price:.2f}")
        
        if actions.get('restock'):
            print(f"   {c['cyan']}Restock Orders:{c['reset']}")
            for sku, qty in actions['restock'].items():
                print(f"      {sku}: +{qty} units")
        
        orders_accepted = actions.get('orders_accepted', 0)
        print(f"   {c['cyan']}Orders Accepted:{c['reset']} {orders_accepted}")
    
    @staticmethod
    def print_results(results: Dict):
        c = LiveDisplay.COLORS
        profit = results.get('profit', 0)
        profit_color = c['green'] if profit >= 0 else c['red']
        
        print(f"\n{c['bold']}📊 DAY RESULTS:{c['reset']}")
        print(f"   Revenue:  {c['green']}+${results.get('revenue', 0):,.2f}{c['reset']}")
        print(f"   Costs:    {c['red']}-${results.get('costs', 0):,.2f}{c['reset']}")
        print(f"   Profit:   {profit_color}${profit:+,.2f}{c['reset']}")
        print(f"   Fulfilled: {results.get('fulfilled', 0)} orders")
        
        if results.get('stockouts', 0) > 0:
            print(f"   {c['red']}❌ Stockouts: {results['stockouts']}{c['reset']}")
        
        if results.get('events'):
            print(f"\n{c['gray']}   Events:{c['reset']}")
            for evt in results['events'][:5]:
                print(f"   {c['gray']}• {evt}{c['reset']}")


# ============================================================================
# SIMULATION STATE (Same as before but simplified)
# ============================================================================

@dataclass
class Product:
    sku: str
    name: str
    cost: Decimal
    price: Decimal
    stock: int
    daily_demand: int
    demand_mult: float = 1.0
    rating: float = 4.5


@dataclass
class SimState:
    day: int = 0
    capital: Decimal = field(default_factory=lambda: Decimal(str(SETTINGS['simulation']['starting_capital'])))
    products: Dict[str, Product] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)
    competitors: List[Dict] = field(default_factory=list)
    history: List[Dict] = field(default_factory=list)
    total_profit: Decimal = Decimal("0.00")


class MarketSim:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.state = SimState()
        self._init_products()
        self._init_competitors()
    
    def _init_products(self):
        # Load products from settings file
        for p in SETTINGS.get('products', []):
            self.state.products[p['sku']] = Product(
                sku=p['sku'],
                name=p['name'],
                cost=Decimal(str(p['cost'])),
                price=Decimal(str(p['price'])),
                stock=p['stock'],
                daily_demand=p['daily_demand'],
            )
    
    def _init_competitors(self):
        for sku, p in self.state.products.items():
            comp_price = float(p.price) * self.rng.uniform(0.85, 1.1)
            self.state.competitors.append({
                "name": self.rng.choice(["ValueMart", "TechDeals", "BudgetKing"]),
                "sku": sku,
                "price": round(comp_price, 2),
            })
    
    def generate_orders(self) -> List[Dict]:
        orders = []
        for sku, p in self.state.products.items():
            demand = int(p.daily_demand * p.demand_mult * self.rng.uniform(0.7, 1.3))
            for i in range(demand):
                max_price = float(p.price) * self.rng.uniform(0.9, 1.1)
                orders.append({
                    "order_id": f"ORD-{self.state.day:03d}-{len(orders):03d}",
                    "sku": sku,
                    "quantity": self.rng.randint(1, 2),
                    "customer_max_price": round(max_price, 2),
                })
        self.rng.shuffle(orders)
        return orders
    
    def maybe_event(self) -> Optional[Dict]:
        if self.rng.random() > 0.08:
            return None
        
        events = [
            ("supply_shock", "Supplier delays shipment", 0.6),
            ("price_war", "Competitor slashed prices 20%", 0.5),
            ("demand_spike", "Product went viral!", 0.4),
            ("demand_crash", "Negative review impact", 0.5),
        ]
        etype, desc, sev = self.rng.choice(events)
        sku = self.rng.choice(list(self.state.products.keys()))
        duration = self.rng.randint(3, 10)
        
        event = {
            "type": etype,
            "sku": sku,
            "description": f"{desc} - {self.state.products[sku].name}",
            "days_remaining": duration,
            "severity": sev,
        }
        
        # Apply effect
        prod = self.state.products[sku]
        if etype == "demand_spike":
            prod.demand_mult = 2.5
        elif etype == "demand_crash":
            prod.demand_mult = 0.4
        elif etype == "price_war":
            for c in self.state.competitors:
                if c["sku"] == sku:
                    c["price"] *= 0.8
        
        self.state.events.append(event)
        return event
    
    def tick_events(self):
        active = []
        for e in self.state.events:
            e["days_remaining"] -= 1
            if e["days_remaining"] > 0:
                active.append(e)
            else:
                # Restore
                prod = self.state.products.get(e["sku"])
                if prod:
                    prod.demand_mult = 1.0
        self.state.events = active
    
    def apply_decisions(self, decisions: Dict, orders: List[Dict]) -> Dict:
        results = {"revenue": 0, "costs": 0, "profit": 0, "fulfilled": 0, "stockouts": 0, "events": []}
        
        # Price changes
        for sku, new_price in decisions.get("price_changes", {}).items():
            if sku in self.state.products:
                old = self.state.products[sku].price
                self.state.products[sku].price = Decimal(str(new_price))
                results["events"].append(f"Changed {sku}: ${old}→${new_price}")
        
        # Restock
        for sku, qty in decisions.get("restock", {}).items():
            if sku in self.state.products:
                cost = self.state.products[sku].cost * qty
                if cost <= self.state.capital:
                    self.state.capital -= cost
                    self.state.products[sku].stock += qty
                    results["costs"] += float(cost)
                    results["events"].append(f"Restocked {sku}: +{qty}")
        
        # Process orders
        accepted = set(decisions.get("accept_orders", []))
        for o in orders:
            if o["order_id"] not in accepted:
                continue
            
            prod = self.state.products.get(o["sku"])
            if not prod:
                continue
            
            if float(prod.price) > o["customer_max_price"]:
                continue
            
            if prod.stock < o["quantity"]:
                results["stockouts"] += 1
                continue
            
            # Fulfill
            prod.stock -= o["quantity"]
            rev = float(prod.price) * o["quantity"]
            self.state.capital += Decimal(str(rev))
            results["revenue"] += rev
            results["fulfilled"] += 1
        
        results["profit"] = results["revenue"] - results["costs"]
        self.state.total_profit += Decimal(str(results["profit"]))
        
        return results
    
    def get_state_dict(self, orders: List[Dict]) -> Dict:
        return {
            "day": self.state.day,
            "capital": float(self.state.capital),
            "profit_so_far": float(self.state.total_profit),
            "products": {
                sku: {"name": p.name, "cost": float(p.cost), "price": float(p.price), 
                      "stock": p.stock, "rating": p.rating}
                for sku, p in self.state.products.items()
            },
            "orders": orders,
            "total_orders": len(orders),
            "events": self.state.events,
            "competitors": self.state.competitors,
        }


# ============================================================================
# GROK AGENT
# ============================================================================

class GrokAgent:
    def __init__(self):
        model_cfg = SETTINGS['model']
        config = LLMConfig(
            provider=model_cfg['provider'],
            model=model_cfg['name'],
            api_key_env="OPENROUTER_API_KEY",
            temperature=model_cfg['temperature'],
            max_tokens=model_cfg['max_tokens'],
            timeout=model_cfg['timeout_seconds'],
        )
        self.client = OpenRouterClient(config)
        self.calls = 0
    
    async def decide(self, state: Dict, last_results: Optional[Dict] = None) -> Dict:
        self.calls += 1
        
        feedback = ""
        if last_results:
            feedback = f"""
YESTERDAY'S RESULTS:
- Revenue: ${last_results['revenue']:.2f}
- Costs: ${last_results['costs']:.2f}
- Profit: ${last_results['profit']:+.2f}
- Fulfilled: {last_results['fulfilled']} orders
- Stockouts: {last_results['stockouts']}
"""

        prompt = f"""You manage an e-commerce store. Goal: MAXIMIZE PROFIT.

CURRENT STATE (Day {state['day']}/365):
- Capital: ${state['capital']:,.2f}
- Profit so far: ${state['profit_so_far']:+,.2f}
{feedback}

PRODUCTS:
{json.dumps(state['products'], indent=2)}

TODAY'S ORDERS ({state['total_orders']} total, showing first 10):
{json.dumps(state['orders'][:10], indent=2)}

ACTIVE EVENTS: {json.dumps(state['events']) if state['events'] else 'None'}

COMPETITORS: {json.dumps(state['competitors'])}

RESPOND WITH JSON ONLY:
{{
  "reasoning": "One sentence explaining your strategy",
  "accept_orders": ["ORD-001-000", ...],
  "price_changes": {{"P001": 34.99}},
  "restock": {{"P002": 50}}
}}"""

        try:
            resp = await self.client.generate_response(prompt)
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            return json.loads(content)
        except Exception as e:
            return {
                "reasoning": f"Fallback: {e}",
                "accept_orders": [o["order_id"] for o in state["orders"]],
                "price_changes": {},
                "restock": {},
            }
    
    async def close(self):
        await self.client.aclose()


# ============================================================================
# MAIN LOOP WITH LIVE VISUALIZATION
# ============================================================================

async def run_live(days: int = 365, seed: int = 42, delay: float = 0.5):
    """Run simulation with live visualization."""
    
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ Set OPENROUTER_API_KEY!")
        return
    
    LiveDisplay.clear()
    print("\n🦅 FBA-BENCH LIVE SIMULATION")
    print(f"   Model: Grok 4.1 Fast | Days: {days} | Seed: {seed}\n")
    
    sim = MarketSim(seed)
    agent = GrokAgent()
    last_results = None
    
    try:
        for day in range(1, days + 1):
            sim.state.day = day
            
            # Generate orders & events
            orders = sim.generate_orders()
            new_event = sim.maybe_event()
            
            # Get state
            state = sim.get_state_dict(orders)
            
            # Display current state
            LiveDisplay.print_header(day, days, float(sim.state.capital), float(sim.state.total_profit))
            LiveDisplay.print_state(state["products"], state["events"], state["competitors"])
            LiveDisplay.print_orders(state["orders"], len(orders))
            
            if new_event:
                print(f"\n⚠️  NEW EVENT: {new_event['description']}")
            
            # Agent thinks
            LiveDisplay.print_thinking()
            decisions = await agent.decide(state, last_results)
            
            # Show decision
            LiveDisplay.print_decision(
                decisions.get("reasoning", "No reasoning provided"),
                {
                    "price_changes": decisions.get("price_changes", {}),
                    "restock": decisions.get("restock", {}),
                    "orders_accepted": len(decisions.get("accept_orders", [])),
                }
            )
            
            # Apply & get results
            results = sim.apply_decisions(decisions, orders)
            last_results = results
            
            # Show results
            LiveDisplay.print_results(results)
            
            # Update events
            sim.tick_events()
            
            # Pause for readability
            await asyncio.sleep(delay)
        
        # Final summary
        print(f"\n{'='*70}")
        print(f"🏆 FINAL RESULTS AFTER {days} DAYS")
        print(f"{'='*70}")
        print(f"   Starting Capital: $10,000.00")
        print(f"   Final Capital:    ${sim.state.capital:,.2f}")
        print(f"   Total Profit:     ${sim.state.total_profit:+,.2f}")
        print(f"   ROI:              {float((sim.state.capital - 10000) / 10000 * 100):+.1f}%")
        print(f"   LLM Calls:        {agent.calls}")
        print(f"{'='*70}\n")
        
    finally:
        await agent.close()


def main():
    # Load defaults from settings file, allow CLI overrides
    sim_cfg = SETTINGS['simulation']
    
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=sim_cfg['days'])
    p.add_argument("--seed", type=int, default=sim_cfg['seed'])
    p.add_argument("--delay", type=float, default=sim_cfg['display_delay'])
    args = p.parse_args()
    
    print(f"📁 Settings loaded from: {SETTINGS_FILE}")
    print(f"   Model: {SETTINGS['model']['name']}")
    print(f"   Days: {args.days} | Seed: {args.seed}")
    
    asyncio.run(run_live(args.days, args.seed, args.delay))


if __name__ == "__main__":
    main()
