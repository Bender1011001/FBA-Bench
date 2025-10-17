"""Run a Tier 2 FBA simulation for a full simulated year.

This is a lightweight, deterministic simulator that approximates
Tier 2 dynamics using seasonal demand curves, supply disruptions,
marketing pushes, and operational levers. It produces an artifact
bundle with a JSON summary, CSV daily metrics, and a console report.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fba_bench.money import Money


@dataclass
class Tier2Config:
    """Configuration parameters for the simulated Tier 2 run."""

    seed: int = 2025
    start_date: date = date(2024, 1, 1)
    days: int = 365
    base_daily_demand: int = 130
    base_price: Decimal = Decimal("48.75")
    base_unit_cost: Decimal = Decimal("25.40")
    expedite_unit_cost: Decimal = Decimal("6.15")
    daily_overhead: Decimal = Decimal("720")
    initial_inventory: int = 520
    weekly_restock: int = 180
    restock_day: int = 0  # Monday
    safety_stock_threshold: int = 220
    expedite_restock: int = 90


@dataclass
class DailySnapshot:
    day_index: int
    date: date
    demand: int
    fulfilled: int
    lost_sales: int
    revenue: Money
    cogs: Money
    expedite_cost: Money
    overhead: Money
    profit: Money
    ending_inventory: int
    stockout: bool
    events: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "day_index": self.day_index,
            "date": self.date.isoformat(),
            "demand": self.demand,
            "fulfilled": self.fulfilled,
            "lost_sales": self.lost_sales,
            "revenue": self.revenue.to_dict(),
            "cogs": self.cogs.to_dict(),
            "expedite_cost": self.expedite_cost.to_dict(),
            "overhead": self.overhead.to_dict(),
            "profit": self.profit.to_dict(),
            "ending_inventory": self.ending_inventory,
            "stockout": self.stockout,
            "events": self.events,
        }


class Tier2YearSimulation:
    def __init__(self, config: Tier2Config):
        self.config = config
        self.random = random.Random(config.seed)
        self.daily_records: List[DailySnapshot] = []
        self._inventory = config.initial_inventory
        self._cumulative_profit = Money.zero("USD")
        self._season_cache: Dict[int, float] = {}

    # Seasonal multipliers by month
    def _season_multiplier(self, current_date: date) -> float:
        month = current_date.month
        if month in self._season_cache:
            return self._season_cache[month]
        if month in {1, 2}:
            value = 0.88  # Post-holiday slump
        elif month in {3, 4, 5}:
            value = 1.05  # Spring refresh
        elif month in {6, 7, 8}:
            value = 1.12  # Summer travel + prime season
        elif month in {9, 10}:
            value = 1.03  # Back-to-business shoulder
        else:
            value = 1.35  # Q4 holiday peak
        self._season_cache[month] = value
        return value

    def _event_adjustments(self, day_idx: int, current_date: date) -> Dict[str, float]:
        adjustments: Dict[str, float] = {"demand": 1.0, "restock_modifier": 1.0, "overhead": 1.0}
        events: List[str] = []

        # Early spring influencer campaign (days 70-80)
        if 70 <= day_idx <= 80:
            adjustments["demand"] *= 1.18
            events.append("influencer_campaign")

        # Summer lightning deals (Prime week, around mid-July)
        if current_date.month == 7 and current_date.day in range(10, 18):
            adjustments["demand"] *= 1.25
            events.append("prime_flash_sale")

        # Late summer logistics backlog (days 220-235)
        if 220 <= day_idx <= 235:
            adjustments["restock_modifier"] *= 0.55
            events.append("port_congestion")

        # Q4 compliance audit raising overhead for a short window
        if current_date.month == 10 and current_date.day in range(15, 23):
            adjustments["overhead"] *= 1.15
            events.append("compliance_audit")

        # Holiday expedited shipping push (Nov Black Friday weekend)
        if current_date.month == 11 and current_date.day in range(24, 29):
            adjustments["demand"] *= 1.4
            adjustments["overhead"] *= 1.12
            events.append("holiday_spike")

        return adjustments, events

    def run(self) -> Dict[str, object]:
        config = self.config
        fulfilled_total = 0
        demand_total = 0
        lost_sales_total = 0
        expedite_units_total = 0
        expedite_cost_total = Money.zero("USD")
        revenue_total = Money.zero("USD")
        cogs_total = Money.zero("USD")
        overhead_total = Money.zero("USD")
        profitable_days = 0
        stockout_days = 0
        daily_profits: List[Decimal] = []

        current_date = config.start_date

        for day in range(config.days):
            season_multiplier = self._season_multiplier(current_date)
            adjustments, events = self._event_adjustments(day, current_date)

            demand_noise = self.random.normalvariate(0, 0.12)
            raw_demand = config.base_daily_demand * season_multiplier * adjustments["demand"] * (1 + demand_noise)
            demand = max(0, int(round(raw_demand)))

            # Determine restock quantity
            inbound_units = 0
            if current_date.weekday() == config.restock_day:
                inbound_units = int(config.weekly_restock * adjustments["restock_modifier"])
            # Expedite if below safety stock
            expedite_units = 0
            if self._inventory < config.safety_stock_threshold and inbound_units == 0:
                expedite_units = config.expedite_restock
                events.append("expedited_restock")

            # Apply restock
            self._inventory += inbound_units + expedite_units
            if expedite_units:
                expedite_units_total += expedite_units

            fulfilled = min(self._inventory, demand)
            lost_sales = demand - fulfilled
            stockout = fulfilled < demand

            revenue = Money.from_dollars(Decimal(fulfilled) * config.base_price)
            cogs = Money.from_dollars(Decimal(fulfilled) * config.base_unit_cost)
            expedite_cost = Money.from_dollars(Decimal(expedite_units) * config.expedite_unit_cost)
            overhead_multiplier = Decimal(str(adjustments["overhead"]))
            overhead = Money.from_dollars(config.daily_overhead * overhead_multiplier)
            profit = revenue - cogs - expedite_cost - overhead

            self._inventory -= fulfilled
            fulfilled_total += fulfilled
            demand_total += demand
            lost_sales_total += lost_sales
            revenue_total += revenue
            cogs_total += cogs
            expedite_cost_total += expedite_cost
            overhead_total += overhead
            self._cumulative_profit += profit
            daily_profits.append(profit.amount)
            if profit.amount > 0:
                profitable_days += 1
            if stockout:
                stockout_days += 1

            self.daily_records.append(
                DailySnapshot(
                    day_index=day,
                    date=current_date,
                    demand=demand,
                    fulfilled=fulfilled,
                    lost_sales=lost_sales,
                    revenue=revenue,
                    cogs=cogs,
                    expedite_cost=expedite_cost,
                    overhead=overhead,
                    profit=profit,
                    ending_inventory=self._inventory,
                    stockout=stockout,
                    events=events,
                )
            )

            current_date += timedelta(days=1)

        service_level = 0.0 if demand_total == 0 else fulfilled_total / demand_total
        stockout_rate = stockout_days / config.days
        avg_daily_profit = Decimal(0)
        if daily_profits:
            avg_daily_profit = mean(daily_profits)

        domain_scores = {
            "financial_health": float(min(1.0, max(0.0, (self._cumulative_profit.amount / Decimal("45000"))))),
            "customer_experience": round(service_level, 3),
            "supply_chain": float(max(0.0, 1.0 - stockout_rate)),
            "risk_management": float(max(0.0, 0.92 - stockout_rate * 0.5)),
            "operations": float(max(0.0, min(1.0, (profitable_days / config.days) + 0.1))),
            "governance": 0.97,
            "sustainability": 0.72,
        }

        config_payload = {**asdict(config)}
        config_payload["start_date"] = config.start_date.isoformat()
        for key, value in list(config_payload.items()):
            if isinstance(value, Decimal):
                config_payload[key] = str(value)

        summary = {
            "config": config_payload,
            "totals": {
                "demand": demand_total,
                "fulfilled": fulfilled_total,
                "lost_sales": lost_sales_total,
                "revenue": revenue_total.to_dict(),
                "cogs": cogs_total.to_dict(),
                "expedite_cost": expedite_cost_total.to_dict(),
                "overhead": overhead_total.to_dict(),
                "profit": self._cumulative_profit.to_dict(),
            },
            "performance": {
                "service_level": round(service_level, 4),
                "stockout_days": stockout_days,
                "stockout_rate": round(stockout_rate, 4),
                "profitable_days": profitable_days,
                "avg_daily_profit": str(avg_daily_profit.quantize(Decimal("0.01"))),
                "expedite_units": expedite_units_total,
            },
            "domain_scores": domain_scores,
            "daily_records": [record.to_dict() for record in self.daily_records],
        }

        return summary


def write_artifacts(summary: Dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    csv_path = output_dir / "daily_metrics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "day_index",
            "date",
            "demand",
            "fulfilled",
            "lost_sales",
            "revenue",
            "cogs",
            "expedite_cost",
            "overhead",
            "profit",
            "ending_inventory",
            "stockout",
            "events",
        ])
        for record in summary["daily_records"]:
            writer.writerow([
                record["day_index"],
                record["date"],
                record["demand"],
                record["fulfilled"],
                record["lost_sales"],
                record["revenue"]["amount"],
                record["cogs"]["amount"],
                record["expedite_cost"]["amount"],
                record["overhead"]["amount"],
                record["profit"]["amount"],
                record["ending_inventory"],
                record["stockout"],
                "|".join(record["events"]),
            ])


def print_report(summary: Dict[str, object], output_dir: Path) -> None:
    totals = summary["totals"]
    performance = summary["performance"]
    domain_scores = summary["domain_scores"]

    print("=== Tier 2 Full-Year Simulation Summary ===")
    print(f"Artifacts stored in: {output_dir}")
    print("Totals:")
    print(f"  Demand:     {totals['demand']:,}")
    print(f"  Fulfilled:  {totals['fulfilled']:,}")
    print(f"  Lost sales: {totals['lost_sales']:,}")
    print(
        f"  Revenue:    ${Decimal(totals['revenue']['amount']):,.2f}"
        f" | Profit: ${Decimal(totals['profit']['amount']):,.2f}"
    )
    print("Performance Metrics:")
    print(f"  Service level: {performance['service_level']*100:.2f}%")
    print(f"  Stockout days: {performance['stockout_days']} ({performance['stockout_rate']*100:.2f}% of year)")
    print(f"  Profitable days: {performance['profitable_days']} | Avg daily profit: ${performance['avg_daily_profit']}")
    print(f"  Expedite units: {performance['expedite_units']}")
    print("Domain Scores:")
    for domain, score in domain_scores.items():
        print(f"  {domain.replace('_', ' ').title()}: {score:.3f}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tier 2 simulation for a simulated year")
    parser.add_argument("--seed", type=int, default=Tier2Config.seed, help="Random seed")
    parser.add_argument("--days", type=int, default=Tier2Config.days, help="Number of days to simulate")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/tier2_full_year"),
        help="Directory for simulation artifacts",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    config = Tier2Config(seed=args.seed, days=args.days)
    sim = Tier2YearSimulation(config)
    summary = sim.run()

    timestamped = args.output_dir / date.today().isoformat()
    run_dir = timestamped
    index = 1
    while run_dir.exists():
        run_dir = timestamped.parent / f"{timestamped.name}-{index}"  # Avoid collisions
        index += 1

    write_artifacts(summary, run_dir)
    print_report(summary, run_dir)


if __name__ == "__main__":
    main()
