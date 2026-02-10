#!/usr/bin/env python3
"""
Agentic Tier-2 style simulation runner.

This is the "slow" benchmark the way you described it: the model makes (at least)
one decision per simulated day, sequentially, and we wait for the LLM response.

Output is written as JSON so scripts/batch_runner.py can aggregate and publish.
"""

from __future__ import annotations

import sys
import argparse
import json
import os
import random
import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Allow running this script without installing the package into the environment.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _maybe_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(x)
    except Exception:
        return None


def _maybe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _extract_json(content: str) -> str:
    s = content.strip()
    if "```" in s:
        parts = s.split("```")
        # Prefer fenced JSON block if present.
        for p in parts:
            p2 = p.strip()
            if p2.lower().startswith("json"):
                p2 = p2[4:].strip()
            if p2.startswith("{") and p2.endswith("}"):
                return p2
        # Fallback: take the largest brace block.
    # Heuristic: find first '{' and last '}'.
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        return s[i : j + 1]
    return s


@dataclass
class Product:
    sku: str
    name: str
    cost: Decimal
    price: Decimal
    stock: int
    daily_demand: int
    demand_mult: float = 1.0
    restock_cost_mult: float = 1.0
    rating: float = 4.5


@dataclass
class SimState:
    day: int = 0
    capital: Decimal = Decimal("10000.0")
    products: Dict[str, Product] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    total_profit: Decimal = Decimal("0.0")


class MarketSim:
    def __init__(self, *, settings: Dict[str, Any], seed: int, days: int) -> None:
        self.settings = settings
        self.days = days
        self.rng = random.Random(seed)
        self.state = SimState()

        sim_cfg = (settings.get("simulation") or {}) if isinstance(settings, dict) else {}
        self.state.capital = Decimal(str(sim_cfg.get("starting_capital", 10000.0)))

        self._init_products()
        self._init_competitors()

        # Global recession multiplier: Tier-2 "recession" baseline.
        bench = settings.get("benchmark") or {}
        self._global_demand_mult = float(bench.get("recession_demand_multiplier", 0.70))

    def _init_products(self) -> None:
        for p in self.settings.get("products", []):
            prod = Product(
                sku=p["sku"],
                name=p["name"],
                cost=Decimal(str(p["cost"])),
                price=Decimal(str(p["price"])),
                stock=int(p["stock"]),
                daily_demand=int(p["daily_demand"]),
            )
            self.state.products[prod.sku] = prod

    def _init_competitors(self) -> None:
        market = self.settings.get("market") or {}
        variance = float(market.get("competitor_price_variance", 0.15))
        comps_per = int(market.get("competitors_per_product", 2))
        names = ["ValueMart", "TechDeals", "BudgetKing", "PrimePanda", "EchoCart"]

        for sku, p in self.state.products.items():
            for _ in range(comps_per):
                comp_price = float(p.price) * self.rng.uniform(1.0 - variance, 1.0 + variance)
                self.state.competitors.append(
                    {"name": self.rng.choice(names), "sku": sku, "price": round(comp_price, 2)}
                )

    def _update_competitors_daily(self) -> None:
        market = self.settings.get("market") or {}
        variance = float(market.get("competitor_price_variance", 0.15))
        for c in self.state.competitors:
            sku = c.get("sku")
            prod = self.state.products.get(sku)
            if not prod:
                continue
            # Daily reprice around your current price.
            c["price"] = round(float(prod.price) * self.rng.uniform(1.0 - variance, 1.0 + variance), 2)

    def generate_orders(self) -> List[Dict[str, Any]]:
        orders: List[Dict[str, Any]] = []
        for sku, p in self.state.products.items():
            demand = int(p.daily_demand * self._global_demand_mult * p.demand_mult * self.rng.uniform(0.7, 1.3))
            for _ in range(max(0, demand)):
                max_price = float(p.price) * self.rng.uniform(0.9, 1.1)
                orders.append(
                    {
                        "order_id": f"ORD-{self.state.day:03d}-{len(orders):04d}",
                        "sku": sku,
                        "quantity": self.rng.randint(1, 2),
                        "customer_max_price": round(max_price, 2),
                    }
                )
        self.rng.shuffle(orders)
        return orders

    def maybe_event(self) -> Optional[Dict[str, Any]]:
        market = self.settings.get("market") or {}
        p_evt = float(market.get("event_probability", 0.08))
        if self.rng.random() > p_evt:
            return None

        event_types = market.get("event_types") or []
        if not isinstance(event_types, list) or not event_types:
            return None

        raw = self.rng.choice(event_types)
        if not isinstance(raw, dict) or "type" not in raw:
            return None

        sku = self.rng.choice(list(self.state.products.keys()))
        duration = self.rng.randint(int(raw.get("duration_min", 3)), int(raw.get("duration_max", 10)))
        severity = float(raw.get("severity", 0.5))

        event = {
            "type": str(raw.get("type")),
            "sku": sku,
            "description": f"{raw.get('description', 'Event')} - {self.state.products[sku].name}",
            "days_remaining": duration,
            "severity": severity,
            "effect_multiplier": raw.get("effect_multiplier"),
        }

        # Apply effects.
        prod = self.state.products[sku]
        etype = event["type"]
        if etype == "demand_spike":
            mult = float(event.get("effect_multiplier") or 2.5)
            prod.demand_mult = mult
        elif etype == "demand_crash":
            mult = float(event.get("effect_multiplier") or 0.4)
            prod.demand_mult = mult
        elif etype == "price_war":
            # Slash competitor prices on this SKU.
            for c in self.state.competitors:
                if c.get("sku") == sku:
                    c["price"] = round(float(c["price"]) * 0.8, 2)
        elif etype == "supply_shock":
            # Make restocking more expensive for this SKU.
            prod.restock_cost_mult = 1.0 + (severity * 0.75)

        self.state.events.append(event)
        return event

    def tick_events(self) -> None:
        active: List[Dict[str, Any]] = []
        for e in self.state.events:
            e["days_remaining"] = int(e.get("days_remaining", 0)) - 1
            if e["days_remaining"] > 0:
                active.append(e)
                continue

            # Restore effects when an event expires.
            sku = e.get("sku")
            prod = self.state.products.get(sku)
            if prod:
                etype = e.get("type")
                if etype in {"demand_spike", "demand_crash"}:
                    prod.demand_mult = 1.0
                if etype == "supply_shock":
                    prod.restock_cost_mult = 1.0
        self.state.events = active

    def apply_decisions(self, decisions: Dict[str, Any], orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = {"revenue": 0.0, "costs": 0.0, "profit": 0.0, "fulfilled": 0, "stockouts": 0, "events": []}

        # Price changes.
        pc = decisions.get("price_changes") or {}
        if isinstance(pc, dict):
            for sku, new_price in pc.items():
                if sku not in self.state.products:
                    continue
                try:
                    np = Decimal(str(new_price))
                except Exception:
                    continue
                prod = self.state.products[sku]
                # Permissive guard rails: prevent negative prices / absurd typos, but allow
                # aggressive discounting or premium pricing (we're testing the model).
                floor = Decimal("0.01")
                ceil = prod.cost * Decimal("25.0")
                if np < floor:
                    np = floor
                if np > ceil:
                    np = ceil
                prod.price = np

        # Restock (instant purchase; Tier-2 pressure = expensive during supply shock).
        rest = decisions.get("restock") or {}
        if isinstance(rest, dict):
            for sku, qty in rest.items():
                if sku not in self.state.products:
                    continue
                q = _safe_int(qty, 0)
                if q <= 0:
                    continue
                if q > 10000:
                    q = 10000
                prod = self.state.products[sku]
                unit_cost = prod.cost * Decimal(str(prod.restock_cost_mult))
                cost = unit_cost * Decimal(q)
                if cost <= self.state.capital:
                    self.state.capital -= cost
                    prod.stock += q
                    results["costs"] += float(cost)

        # Process orders.
        accepted = decisions.get("accept_orders") or []
        if not isinstance(accepted, list):
            accepted = []
        accepted_set = set(str(x) for x in accepted)
        for o in orders:
            if o["order_id"] not in accepted_set:
                continue
            prod = self.state.products.get(o["sku"])
            if not prod:
                continue
            if float(prod.price) > float(o["customer_max_price"]):
                continue
            if prod.stock < int(o["quantity"]):
                results["stockouts"] += 1
                continue

            prod.stock -= int(o["quantity"])
            rev = float(prod.price) * int(o["quantity"])
            self.state.capital += Decimal(str(rev))
            results["revenue"] += rev
            results["fulfilled"] += 1

        results["profit"] = results["revenue"] - results["costs"]
        self.state.total_profit += Decimal(str(results["profit"]))
        return results

    def get_state_dict(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "day": self.state.day,
            "days_total": self.days,
            "capital": float(self.state.capital),
            "profit_so_far": float(self.state.total_profit),
            "products": {
                sku: {
                    "name": p.name,
                    "cost": float(p.cost),
                    "price": float(p.price),
                    "stock": p.stock,
                    "rating": p.rating,
                }
                for sku, p in self.state.products.items()
            },
            "orders": orders,
            "total_orders": len(orders),
            "events": self.state.events,
            "competitors": self.state.competitors,
        }


class ModelAgent:
    def __init__(self, *, model_slug: str, settings: Dict[str, Any], max_wait_seconds: float = 0.0) -> None:
        model_cfg = settings.get("model") or {}
        max_tokens = _maybe_int(model_cfg.get("max_tokens"))
        timeout_seconds = _maybe_float(model_cfg.get("timeout_seconds"))
        config = LLMConfig(
            provider=str(model_cfg.get("provider", "openrouter")),
            model=model_slug,
            api_key_env="OPENROUTER_API_KEY",
            temperature=_safe_float(model_cfg.get("temperature", 0.1), 0.1),
            max_tokens=max_tokens,
            timeout=timeout_seconds,
        )
        self.client = OpenRouterClient(config)
        self.calls = 0
        self.tokens_used = 0
        self.call_seconds: List[float] = []
        self.errors: List[str] = []
        self.max_wait_seconds = float(max_wait_seconds)

        prompts = settings.get("prompts") or {}
        self.system = str(prompts.get("system") or "You manage an e-commerce store. Your goal is to MAXIMIZE PROFIT.")
        self.decision_format = str(
            prompts.get("decision_format")
            or """Respond with JSON only:
{
  "reasoning": "One sentence explaining your strategy",
  "accept_orders": ["ORD-001-000", "..."],
  "price_changes": {"P001": 34.99},
  "restock": {"P002": 50}
}"""
        )

    async def decide(
        self, *, state: Dict[str, Any], last_results: Optional[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.calls += 1
        feedback = ""
        if last_results:
            feedback = (
                "\nYESTERDAY'S RESULTS:\n"
                f"- Revenue: ${last_results['revenue']:.2f}\n"
                f"- Costs: ${last_results['costs']:.2f}\n"
                f"- Profit: ${last_results['profit']:+.2f}\n"
                f"- Fulfilled: {last_results['fulfilled']} orders\n"
                f"- Stockouts: {last_results['stockouts']}\n"
            )

        prompt = (
            f"{self.system}\n\n"
            f"CURRENT STATE (Day {state['day']}/{state.get('days_total','?')}):\n"
            f"- Capital: ${state['capital']:,.2f}\n"
            f"- Profit so far: ${state['profit_so_far']:+,.2f}\n"
            f"{feedback}\n\n"
            "PRODUCTS:\n"
            f"{json.dumps(state['products'], indent=2)}\n\n"
            f"TODAY'S ORDERS ({state['total_orders']} total):\n"
            f"{json.dumps(state['orders'], indent=2)}\n\n"
            f"ACTIVE EVENTS: {json.dumps(state['events']) if state['events'] else 'None'}\n\n"
            f"COMPETITORS: {json.dumps(state['competitors'])}\n\n"
            "RESPOND WITH JSON ONLY:\n"
            f"{self.decision_format}\n"
        )

        t0 = time.perf_counter()
        resp: Dict[str, Any] = {}
        # Some models support response_format; if it errors, retry without it.
        try:
            call = self.client.generate_response(prompt, response_format={"type": "json_object"})
            resp = (
                await asyncio.wait_for(call, timeout=self.max_wait_seconds)
                if (self.max_wait_seconds and self.max_wait_seconds > 0)
                else await call
            )
        except Exception as e1:
            try:
                call2 = self.client.generate_response(prompt)
                resp = (
                    await asyncio.wait_for(call2, timeout=self.max_wait_seconds)
                    if (self.max_wait_seconds and self.max_wait_seconds > 0)
                    else await call2
                )
            except Exception as e2:
                # Hard failure: skip the day with a safe fallback.
                self.errors.append(f"llm_call_failed: {e1} | retry_failed: {e2}")
                t1 = time.perf_counter()
                self.call_seconds.append(t1 - t0)
                return (
                    {
                        "reasoning": "fallback: LLM call failed",
                        "accept_orders": [o["order_id"] for o in state.get("orders", [])],
                        "price_changes": {},
                        "restock": {},
                    },
                    {"usage": {}},
                )
        t1 = time.perf_counter()
        self.call_seconds.append(t1 - t0)

        usage = resp.get("usage") or {}
        self.tokens_used += _safe_int(usage.get("total_tokens") or 0, 0)

        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        try:
            payload = json.loads(_extract_json(str(content)))
            if not isinstance(payload, dict):
                raise ValueError("response was not a JSON object")
            return payload, {"usage": usage}
        except Exception as e:
            self.errors.append(str(e))
            # Fallback: accept all orders, no price changes/restock.
            return (
                {
                    "reasoning": f"fallback: {e}",
                    "accept_orders": [o["order_id"] for o in state.get("orders", [])],
                    "price_changes": {},
                    "restock": {},
                },
                {"usage": usage},
            )

    async def close(self) -> None:
        await self.client.aclose()


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run an agentic Tier-2 simulation for a single model.")
    ap.add_argument("--model", required=True, help="OpenRouter model slug (e.g., openai/gpt-5.2).")
    ap.add_argument("--settings", default="simulation_settings.yaml", help="Settings YAML path.")
    ap.add_argument("--days", type=int, default=180, help="Simulated days (one LLM decision per day).")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed.")
    ap.add_argument("--output", required=True, help="Output JSON path for raw run details.")
    ap.add_argument("--progress", default=None, help="Optional progress JSON path updated each day.")
    ap.add_argument(
        "--max-wait-seconds",
        type=float,
        default=0.0,
        help="Optional per-day cap for a single model response. 0 disables this cap.",
    )
    return ap.parse_args()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def main_async() -> int:
    args = parse_args()
    settings = yaml.safe_load(Path(args.settings).read_text(encoding="utf-8")) or {}

    if not os.getenv("OPENROUTER_API_KEY"):
        # OpenRouterClient also loads .env if python-dotenv is available, but fail early here.
        raise SystemExit("OPENROUTER_API_KEY is not set in the environment.")

    sim = MarketSim(settings=settings, seed=int(args.seed), days=int(args.days))
    agent = ModelAgent(
        model_slug=str(args.model), settings=settings, max_wait_seconds=float(args.max_wait_seconds)
    )

    started_at = utc_iso()
    last_results: Optional[Dict[str, Any]] = None

    daily_profit: List[float] = []
    try:
        for day in range(1, int(args.days) + 1):
            sim.state.day = day

            sim._update_competitors_daily()
            orders = sim.generate_orders()
            sim.maybe_event()
            state = sim.get_state_dict(orders)

            try:
                decisions, meta = await agent.decide(state=state, last_results=last_results)
            except asyncio.TimeoutError:
                agent.errors.append(
                    f"day {day}: model response exceeded max_wait_seconds={float(args.max_wait_seconds)}"
                )
                decisions, meta = (
                    {
                        "reasoning": "skipped: response timeout",
                        "accept_orders": [],
                        "price_changes": {},
                        "restock": {},
                    },
                    {"usage": {}},
                )
            except Exception as e:
                agent.errors.append(f"day {day}: decide_failed: {e}")
                decisions, meta = (
                    {
                        "reasoning": "fallback: decide failed",
                        "accept_orders": [],
                        "price_changes": {},
                        "restock": {},
                    },
                    {"usage": {}},
                )
            # Constrain accept_orders to existing ids (prevents hallucinated order ids).
            order_ids = {o["order_id"] for o in orders}
            ao = decisions.get("accept_orders") or []
            if isinstance(ao, list):
                decisions["accept_orders"] = [x for x in ao if str(x) in order_ids]
            else:
                decisions["accept_orders"] = []

            results = sim.apply_decisions(decisions, orders)
            last_results = results
            daily_profit.append(float(results["profit"]))
            sim.tick_events()

            if args.progress:
                write_json(
                    Path(args.progress),
                    {
                        "model": str(args.model),
                        "day": day,
                        "days_total": int(args.days),
                        "capital": float(sim.state.capital),
                        "profit_so_far": float(sim.state.total_profit),
                        "tokens_used": int(agent.tokens_used),
                        "llm_calls": int(agent.calls),
                        "last_call_seconds": float(agent.call_seconds[-1]) if agent.call_seconds else None,
                        "timestamp": utc_iso(),
                    },
                )

        ended_at = utc_iso()
        starting_capital = Decimal(str((settings.get("simulation") or {}).get("starting_capital", 10000.0)))
        final_capital = sim.state.capital
        total_profit = sim.state.total_profit
        roi_pct = float(((final_capital - starting_capital) / starting_capital) * Decimal("100.0"))

        payload = {
            "benchmark_info": {
                "timestamp": ended_at,
                "started_at": started_at,
                "ended_at": ended_at,
                "model": str(args.model),
                "days": int(args.days),
                "seed": int(args.seed),
            },
            "summary": {
                "success": True,
                "starting_capital": float(starting_capital),
                "final_capital": float(final_capital),
                "total_profit": float(total_profit),
                "roi_pct": roi_pct,
                "tokens_used": int(agent.tokens_used),
                "llm_calls": int(agent.calls),
                "avg_call_seconds": (sum(agent.call_seconds) / len(agent.call_seconds)) if agent.call_seconds else None,
                "errors": list(agent.errors),
            },
        }

        write_json(Path(args.output), payload)
        return 0
    finally:
        await agent.close()


def main() -> None:
    import asyncio

    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
