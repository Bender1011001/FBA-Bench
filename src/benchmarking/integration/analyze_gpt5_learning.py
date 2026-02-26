#!/usr/bin/env python3
"""
Analyze GPT-5 Learning Benchmark results.

- Reads a results directory produced by either:
  - scripts/run_gpt5_learning_benchmark.py
  - experiment_cli.py run config_storage/simulations/gpt5_learning_full.yaml --parallel 1

- Produces:
  - analysis_report.json (key stats and learning deltas)
  - metrics_enhanced.csv (metrics.csv + derived columns)
  - Prints a concise console summary

Usage:
  python benchmarking/integration/analyze_gpt5_learning.py --results-dir results/gpt5_learning_full/gpt5_learning_full_YYYYmmdd-HHMMSS
  python benchmarking/integration/analyze_gpt5_learning.py  # auto-detects latest under results/gpt5_learning_full/
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _find_latest_results(
    base_root: Path = Path("results/gpt5_learning_full"),
) -> Optional[Path]:
    if not base_root.exists():
        return None
    dirs = [p for p in base_root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs[0]


def _read_summary(results_dir: Path) -> Dict[str, Any]:
    summary_path = results_dir / "summary.json"
    if summary_path.exists():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _read_metrics_csv(results_dir: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    csv_path = results_dir / "metrics.csv"
    if not csv_path.exists():
        return [], []
    rows: List[Dict[str, Any]] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for r in reader:
            rows.append(r)
    return header, rows  # type: ignore[return-value]


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _compute_slope(y: List[float]) -> float:
    """
    Compute a simple slope via least squares: slope of y over x (episodes 1..n).
    Return 0.0 if insufficient data.
    """
    n = len(y)
    if n < 2:
        return 0.0
    x = list(range(1, n + 1))
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den = sum((xi - mean_x) ** 2 for xi in x)
    return num / den if den != 0 else 0.0


def _monotonicity_score(series: List[float]) -> float:
    """
    Returns ratio in [0,1] measuring how often series is non-decreasing step-to-step.
    """
    if len(series) < 2:
        return 1.0
    ups = 0
    total = 0
    for a, b in zip(series[:-1], series[1:]):
        if b >= a:
            ups += 1
        total += 1
    return ups / total if total > 0 else 1.0


def _success_rate(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    success_count = 0
    for r in rows:
        v = r.get("success")
        try:
            # success column is 1/0 in writer
            success_count += 1 if int(v) == 1 else 0  # type: ignore[arg-type]
        except Exception:
            pass
    return success_count / len(rows)


def _enhance_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enhanced: List[Dict[str, Any]] = []
    for r in rows:
        e = dict(r)
        e["profit"] = _to_float(r.get("profit"))
        e["market_share"] = _to_float(r.get("market_share"))
        e["inventory_turnover_rate"] = _to_float(r.get("inventory_turnover_rate"))
        e["stock_out_rate"] = _to_float(r.get("stock_out_rate"))
        e["customer_satisfaction"] = _to_float(r.get("customer_satisfaction"))
        e["on_time_delivery_rate"] = _to_float(r.get("on_time_delivery_rate"))
        e["simulation_duration"] = int(_to_float(r.get("simulation_duration")))
        try:
            e["episode"] = int(r.get("episode", "0"))
        except Exception:
            e["episode"] = 0
        enhanced.append(e)
    enhanced.sort(key=lambda r: r.get("episode", 0))
    return enhanced


def _write_enhanced_csv(
    results_dir: Path, header: List[str], rows: List[Dict[str, Any]]
) -> None:
    out_path = results_dir / "metrics_enhanced.csv"
    # Merge existing header with normalized fields
    base = [
        "episode",
        "profit",
        "market_share",
        "inventory_turnover_rate",
        "stock_out_rate",
        "customer_satisfaction",
        "on_time_delivery_rate",
        "success",
        "composite_score",
        "bonus_score",
        "simulation_duration",
    ]
    # Preserve any additional columns not in base
    extra = [h for h in (header or []) if h not in base]
    final_header = base + extra
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=final_header)
        w.writeheader()
        for r in rows:
            row = {h: r.get(h, "") for h in final_header}
            w.writerow(row)


def analyze(results_dir: Path) -> Dict[str, Any]:
    summary = _read_summary(results_dir)
    header, raw_rows = _read_metrics_csv(results_dir)
    rows = _enhance_rows(raw_rows)

    series_profit = [r["profit"] for r in rows]
    series_market_share = [r["market_share"] for r in rows]
    series_csat = [r["customer_satisfaction"] for r in rows]

    slope_profit = _compute_slope(series_profit)
    slope_market_share = _compute_slope(series_market_share)
    slope_csat = _compute_slope(series_csat)

    mono_profit = _monotonicity_score(series_profit)
    succ_rate = _success_rate(rows)

    start_profit = series_profit[0] if series_profit else 0.0
    end_profit = series_profit[-1] if series_profit else 0.0
    delta_profit = end_profit - start_profit
    pct_profit = (
        (delta_profit / start_profit * 100.0) if abs(start_profit) > 1e-9 else 0.0
    )

    # Compute basic stats
    mean_profit = statistics.mean(series_profit) if series_profit else 0.0
    median_profit = statistics.median(series_profit) if series_profit else 0.0
    best_ep = max(rows, key=lambda r: r["profit"])["episode"] if rows else None
    worst_ep = min(rows, key=lambda r: r["profit"])["episode"] if rows else None

    report = {
        "results_dir": str(results_dir),
        "episodes": len(rows),
        "success_rate": succ_rate,
        "profit": {
            "start": start_profit,
            "end": end_profit,
            "delta": delta_profit,
            "pct_change": pct_profit,
            "mean": mean_profit,
            "median": median_profit,
            "slope": slope_profit,
            "monotonicity": mono_profit,
            "best_episode": best_ep,
            "worst_episode": worst_ep,
            "series": series_profit,
        },
        "market_share": {
            "slope": slope_market_share,
            "end": series_market_share[-1] if series_market_share else 0.0,
        },
        "customer_satisfaction": {
            "slope": slope_csat,
            "end": series_csat[-1] if series_csat else 0.0,
        },
        "summary_present": bool(summary),
    }

    # Write enhanced CSV
    _write_enhanced_csv(results_dir, header, rows)

    # Write JSON report
    out_json = results_dir / "analysis_report.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze GPT-5 Learning Benchmark results")
    ap.add_argument(
        "--results-dir", type=str, default=None, help="Path to a results directory"
    )
    args = ap.parse_args()

    if args.results_dir:
        rdir = Path(args.results_dir)
        if not rdir.exists():
            print(f"[ERROR] Results directory not found: {rdir}")
            return 2
    else:
        latest = _find_latest_results()
        if not latest:
            print("[ERROR] No results found under results/gpt5_learning_full/")
            return 2
        rdir = latest

    report = analyze(rdir)

    # Console summary
    print("=== GPT-5 Learning Benchmark Analysis ===")
    print(f"Results Dir        : {report['results_dir']}")
    print(f"Episodes           : {report['episodes']}")
    print(f"Success Rate       : {report['success_rate']:.2%}")
    print(
        f"Profit Start/End   : {report['profit']['start']:.2f} -> {report['profit']['end']:.2f}"
    )
    print(
        f"Profit Δ / %       : {report['profit']['delta']:.2f} / {report['profit']['pct_change']:.2f}%"
    )
    print(f"Profit Slope       : {report['profit']['slope']:.4f}")
    print(f"Profit Monotonic   : {report['profit']['monotonicity']:.2f}")
    print(
        f"Best/Worst Episode : {report['profit']['best_episode']} / {report['profit']['worst_episode']}"
    )
    print("Artifacts:")
    print(" - analysis_report.json")
    print(" - metrics_enhanced.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
