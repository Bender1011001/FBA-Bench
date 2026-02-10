#!/usr/bin/env python3
"""
Watch results/openrouter_tier_runs/**.json and rebuild docs/api leaderboard JSON on changes.

This is a simple polling watcher (stdlib-only). It's designed to run as a background
process while scripts/batch_runner.py is executing.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Tuple


def iter_json_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("*.json")


def snapshot_mtimes(root: Path) -> Dict[str, Tuple[int, int]]:
    """
    Return a stable snapshot keyed by path string with (size, mtime_ns).
    """
    out: Dict[str, Tuple[int, int]] = {}
    for p in iter_json_files(root):
        try:
            st = p.stat()
        except OSError:
            continue
        out[str(p)] = (int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))))
    return out


def run_build(results_root: str, tier: str, live_json: str, out_lb: str, out_top10: str) -> int:
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "build_live_leaderboard.py"),
        "--tier",
        tier,
        "--results-root",
        results_root,
        "--output-leaderboard",
        out_lb,
        "--output-top10",
        out_top10,
        "--live-json",
        live_json,
    ]
    # Keep output quiet; watcher logs should be minimal.
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch results JSON and rebuild docs/api leaderboard JSON.")
    ap.add_argument("--results-root", default="results/openrouter_tier_runs", help="Results root directory to watch.")
    ap.add_argument("--tier", default="T2", help="Tier to build (T0/T1/T2).")
    ap.add_argument("--interval-seconds", type=float, default=2.0, help="Polling interval.")
    ap.add_argument("--live-json", default="docs/api/live.json", help="Live status/heartbeat JSON path.")
    ap.add_argument("--output-leaderboard", default="docs/api/leaderboard.json", help="Output leaderboard.json path.")
    ap.add_argument("--output-top10", default="docs/api/top10.json", help="Output top10.json path.")
    args = ap.parse_args()

    results_root = Path(args.results_root)
    tier_dir = results_root / args.tier.lower()

    last = snapshot_mtimes(tier_dir)
    # Initial build (useful when starting watcher mid-run)
    run_build(args.results_root, args.tier, args.live_json, args.output_leaderboard, args.output_top10)

    while True:
        time.sleep(float(args.interval_seconds))
        cur = snapshot_mtimes(tier_dir)
        if cur != last:
            last = cur
            run_build(args.results_root, args.tier, args.live_json, args.output_leaderboard, args.output_top10)


if __name__ == "__main__":
    raise SystemExit(main())

