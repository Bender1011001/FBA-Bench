#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp.replace(path)


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _latest_results_file(repo_root: Path) -> Optional[Path]:
    candidates = sorted(
        (repo_root / "results").glob("grok_proper_sim_*.json"),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _story_from_values(
    *,
    profit: float,
    stockouts: int,
    fulfilled: int,
    supplier_orders: int,
    ad_spend: float,
    ad_attr: float,
    prior_profit: Optional[float],
) -> Dict[str, str]:
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

    if prior_profit is not None:
        delta = profit - prior_profit
        if delta > 150:
            detail = f"{detail} Profit accelerated by ${delta:,.2f} vs prior day."
        elif delta < -150:
            detail = f"{detail} Profit fell by ${abs(delta):,.2f} vs prior day."

    return {"tone": tone, "headline": headline, "detail": detail}


def build_replay_payload(results_payload: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    config = results_payload.get("config", {})
    execution = results_payload.get("execution", {})
    top_results = results_payload.get("results", {})
    daily = results_payload.get("daily_performance", {})
    decisions = results_payload.get("decisions", [])

    starting_capital = float(top_results.get("starting_capital", 10000.0))
    total_days = int(config.get("days", 0))
    revenue_series = [float(x) for x in daily.get("revenue", [])]
    profit_series = [float(x) for x in daily.get("profit", [])]
    if total_days <= 0:
        total_days = max(len(revenue_series), len(profit_series), len(decisions))
    if total_days <= 0:
        total_days = 1

    decision_by_day: Dict[int, Dict[str, Any]] = {}
    for decision in decisions:
        day = int(decision.get("day", 0))
        if day > 0:
            decision_by_day[day] = decision

    llm_calls = int(execution.get("llm_calls", 0))
    time_seconds = float(execution.get("time_seconds", 0.0))
    est_latency = round(time_seconds / llm_calls, 3) if llm_calls > 0 else 0.0

    frames: List[Dict[str, Any]] = []
    capital = starting_capital
    prior_profit: Optional[float] = None
    roi_series: List[float] = []
    capital_series: List[float] = []
    filled_series: List[int] = []
    stockout_series: List[int] = []

    for day in range(1, total_days + 1):
        decision = decision_by_day.get(day, {})
        action_map = decision.get("actions", {}) or {}
        decision_results = decision.get("results", {}) or {}

        revenue = revenue_series[day - 1] if day - 1 < len(revenue_series) else float(
            decision_results.get("revenue", 0.0)
        )
        profit = profit_series[day - 1] if day - 1 < len(profit_series) else float(
            decision_results.get("profit", 0.0)
        )
        costs = revenue - profit
        fulfilled = int(decision_results.get("fulfilled", 0))
        stockouts = int(decision_results.get("stockouts", 0))
        supplier_orders = int(decision_results.get("supplier_orders_placed", 0))
        ad_spend = float(decision_results.get("ad_spend", 0.0))
        ad_attr = float(decision_results.get("ad_attributed_revenue", 0.0))

        capital += profit
        roi = ((capital - starting_capital) / starting_capital) * 100.0
        story = _story_from_values(
            profit=profit,
            stockouts=stockouts,
            fulfilled=fulfilled,
            supplier_orders=supplier_orders,
            ad_spend=ad_spend,
            ad_attr=ad_attr,
            prior_profit=prior_profit,
        )
        if decision.get("story_headline"):
            story["headline"] = str(decision["story_headline"])

        frame = {
            "timestamp_utc": _utc_now_iso(),
            "day": day,
            "capital": round(capital, 2),
            "total_profit": round(capital - starting_capital, 2),
            "roi_percent": round(roi, 3),
            "decision_latency_seconds": est_latency,
            "orders": {
                "received": 0,
                "fulfilled": fulfilled,
                "rejected": 0,
                "stockouts": stockouts,
            },
            "daily_results": {
                "revenue": revenue,
                "costs": costs,
                "profit": profit,
                "ad_spend": ad_spend,
                "ad_attributed_revenue": ad_attr,
                "supplier_orders_placed": supplier_orders,
                "service_tickets_resolved": int(
                    decision_results.get("service_tickets_resolved", 0)
                ),
            },
            "actions": {
                "orders_accepted": int(action_map.get("orders_accepted", 0)),
                "price_changes": int(action_map.get("price_changes", 0)),
                "restocks": int(action_map.get("restocks", 0)),
                "supplier_orders": int(action_map.get("supplier_orders", 0)),
                "ad_budget_shifts": int(action_map.get("ad_budget_shifts", 0)),
                "customer_ops_updates": int(action_map.get("customer_ops_updates", 0)),
            },
            "reasoning_preview": str(decision.get("reasoning", ""))[:280],
            "events": [],
            "products": [],
            "active_events": [],
            "open_customer_backlog": 0,
            "story": story,
        }
        frames.append(frame)
        prior_profit = profit
        roi_series.append(round(roi, 3))
        capital_series.append(round(capital, 2))
        filled_series.append(fulfilled)
        stockout_series.append(stockouts)

    return {
        "run_id": run_id,
        "status": "completed",
        "phase": "replay_loaded",
        "started_at_utc": _utc_now_iso(),
        "updated_at_utc": _utc_now_iso(),
        "config": config,
        "progress": {"day": total_days, "days_total": total_days, "percent": 100.0},
        "current_frame": frames[-1] if frames else None,
        "recent_frames": frames[-3:] if frames else [],
        "frames": frames,
        "series": {
            "day": list(range(1, total_days + 1)),
            "capital": capital_series,
            "daily_profit": profit_series if profit_series else [f["daily_results"]["profit"] for f in frames],
            "roi_percent": roi_series,
            "orders_fulfilled": filled_series,
            "stockouts": stockout_series,
        },
        "execution": {
            "llm_calls": llm_calls,
            "reflection_calls": int(execution.get("reflection_calls", 0)),
            "total_tokens": int(execution.get("total_tokens", 0)),
            "elapsed_seconds": round(time_seconds, 2),
        },
        "results_file": str(results_payload.get("results_file", "")),
        "final_results": {
            "final_capital": float(top_results.get("final_capital", capital)),
            "net_profit": float(top_results.get("net_profit", capital - starting_capital)),
            "roi_percent": float(top_results.get("roi_percent", roi_series[-1] if roi_series else 0.0)),
            "orders_fulfilled": int(top_results.get("orders_fulfilled", sum(filled_series))),
            "stockouts": int(top_results.get("stockouts", sum(stockout_series))),
        },
    }


def _start_docs_server(docs_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(docs_dir))
    server = ThreadingHTTPServer((host, port), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def run_live_mode(args: argparse.Namespace, repo_root: Path, trace_file: Path) -> None:
    command = [
        sys.executable,
        str(repo_root / "run_grok_proper_sim.py"),
        "--days",
        str(args.days),
        "--seed",
        str(args.seed),
        "--memory-mode",
        args.memory_mode,
        "--memory-review-mode",
        args.memory_review_mode,
        "--live-trace-file",
        str(trace_file),
    ]
    if args.realism_config:
        command.extend(["--realism-config", args.realism_config])
    if args.quiet:
        command.append("--quiet")
    if args.no_weekly_consolidation:
        command.append("--no-weekly-consolidation")

    print("Launching live simulation:", flush=True)
    print("  " + " ".join(command), flush=True)
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(command, cwd=repo_root, env=child_env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def run_replay_mode(args: argparse.Namespace, repo_root: Path, trace_file: Path) -> None:
    results_path: Optional[Path] = None
    if args.results_file:
        results_path = Path(args.results_file)
    elif args.latest_results:
        results_path = _latest_results_file(repo_root)
        if results_path is None:
            raise SystemExit("No grok_proper_sim_*.json files found under results/")
    else:
        raise SystemExit("--results-file or --latest-results is required for --mode replay")

    if results_path is None:
        raise SystemExit("Could not resolve results file for replay mode")

    if not results_path.exists():
        raise SystemExit(f"Results file not found: {results_path}")

    payload = _load_json(results_path)
    replay = build_replay_payload(payload, run_id=f"replay_{results_path.stem}")
    replay["results_file"] = str(results_path.resolve())
    _write_json_atomic(trace_file, replay)
    print(f"Replay trace written: {trace_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-command live/replay launcher for Simulation Theater."
    )
    parser.add_argument("--mode", choices=["live", "replay"], default="live")
    parser.add_argument("--results-file", help="Saved results JSON (required in replay mode)")
    parser.add_argument(
        "--latest-results",
        action="store_true",
        help="Use newest results/grok_proper_sim_*.json for replay mode",
    )
    parser.add_argument(
        "--trace-file",
        default="docs/api/sim_theater_live.json",
        help="Trace JSON consumed by docs/sim-theater.html",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-serve", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--keep-serving", action="store_true")

    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--memory-mode", choices=["stateless", "reflective"], default="stateless")
    parser.add_argument(
        "--memory-review-mode",
        choices=["heuristic", "llm"],
        default="heuristic",
    )
    parser.add_argument("--no-weekly-consolidation", action="store_true")
    parser.add_argument(
        "--realism-config",
        default=None,
        help="Optional realism YAML passed through to run_grok_proper_sim.py",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = _repo_root()
    docs_dir = repo_root / "docs"
    trace_file = (repo_root / args.trace_file).resolve()

    server: Optional[ThreadingHTTPServer] = None
    if not args.no_serve:
        server = _start_docs_server(docs_dir=docs_dir, host=args.host, port=args.port)
        page_url = f"http://{args.host}:{args.port}/sim-theater.html"
        print(f"Docs server: {page_url}?source=api/sim_theater_live.json")
        if args.open_browser:
            webbrowser.open(page_url)

    try:
        if args.mode == "live":
            run_live_mode(args=args, repo_root=repo_root, trace_file=trace_file)
        else:
            run_replay_mode(args=args, repo_root=repo_root, trace_file=trace_file)

        should_wait = args.keep_serving or args.mode == "replay"
        if server is not None and should_wait:
            print("Press Ctrl+C to stop the docs server.")
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
