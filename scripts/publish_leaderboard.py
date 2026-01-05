#!/usr/bin/env python3
"""
Publish year-run results to the leaderboard artifacts using the project's leaderboard tools.

This script:
- Finds the latest artifacts/year_runs/<timestamp> folder
- Parses its summary.md to discover per-model, per-tier run status and log filenames
- Attempts to extract numeric scores from per-run logs (if present)
- Falls back to PASS=100.0 / FAIL=0.0 when no numeric score is found
- Uses leaderboard.ScoreTracker and LeaderboardManager to record the runs and generate
  artifacts (artifacts/leaderboard.json and artifacts/leaderboard.html)

Usage:
    python scripts/publish_leaderboard.py
"""
import asyncio
import os
import re
from typing import Any, Dict, List, Optional

from leaderboard.leaderboard_manager import LeaderboardManager
from leaderboard.leaderboard_renderer import LeaderboardRenderer
from leaderboard.score_tracker import ScoreTracker

ARTIFACTS_ROOT = "artifacts/year_runs"
SCORE_FALLBACK_PASS = 100.0
SCORE_FALLBACK_FAIL = 0.0


def find_latest_run_dir(root: str = ARTIFACTS_ROOT) -> Optional[str]:
    if not os.path.isdir(root):
        return None
    candidates = [
        os.path.join(root, d)
        for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d))
    ]
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1]


def parse_summary_md(summary_path: str) -> List[Dict[str, Any]]:
    """
    Parse summary.md to extract per-run entries.
    Returns list of dicts: {tier, model, status, logfile}
    Expected summary.md format (examples):
      ## T0 Results
      - x-ai/grok-4-fast:free: FAIL (log: T0_x-ai_grok-4-fast:free.log)
    """
    entries: List[Dict[str, Any]] = []
    if not os.path.exists(summary_path):
        return entries
    with open(summary_path, encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines()]

    current_tier = None
    for line in lines:
        if line.startswith("## T0"):
            current_tier = "T0"
            continue
        if line.startswith("## T1"):
            current_tier = "T1"
            continue
        if line.startswith("- ") and current_tier:
            # Try full form: - model: FAIL (log: filename)
            m = re.match(r"-\s+([^\:]+:[^\:]+):\s+(\w+)\s*\(log:\s*([^\)]+)\)", line)
            if m:
                model = m.group(1).strip()
                status = m.group(2).strip()
                logfile = m.group(3).strip()
                entries.append({"tier": current_tier, "model": model, "status": status, "logfile": logfile})
                continue
            # Try simpler form: - model: FAIL
            m2 = re.match(r"-\s+([^\:]+:[^\:]+):\s+(\w+)", line)
            if m2:
                model = m2.group(1).strip()
                status = m2.group(2).strip()
                entries.append({"tier": current_tier, "model": model, "status": status, "logfile": None})
    return entries


def extract_score_from_log(log_path: str) -> Optional[float]:
    """
    Try multiple heuristics/regexes to extract a numeric score from a run log.
    Returns float if found, otherwise None.
    """
    if not log_path or not os.path.exists(log_path):
        return None

    patterns = [
        r"final_score[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"final score[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"Final score[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"score[:=]\s*([0-9]+(?:\.[0-9]+)?)",
        r"Score[:=]\s*([0-9]+(?:\.[0-9]+)?)",
    ]
    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        return None

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                continue
    return None


async def publish_entries(entries: List[Dict[str, Any]], run_dir: str):
    # Use artifacts folder at repository root for ScoreTracker persistence (artifacts/scores.json)
    tracker = ScoreTracker(artifacts_dir="artifacts")
    renderer = LeaderboardRenderer(template_path="leaderboard/templates")
    manager = LeaderboardManager(tracker, renderer, artifacts_dir="artifacts")

    for e in entries:
        tier = e["tier"]
        model = e["model"]
        logfile = e["logfile"]
        status = e["status"]
        log_path = os.path.join(run_dir, logfile) if logfile else None

        score = None
        if log_path and os.path.exists(log_path):
            score = extract_score_from_log(log_path)

        if score is None:
            # Fallback mapping
            score = SCORE_FALLBACK_PASS if status.upper() == "PASS" else SCORE_FALLBACK_FAIL

        run_details = {"status": status, "logfile": logfile, "log_path": log_path}
        print(f"[publish] model={model} tier={tier} score={score} logfile={logfile}")
        # Use manager.update_leaderboard which will write artifacts after each add
        await manager.update_leaderboard(agent_id=model, tier=tier, metric_results={"score": score, "details": run_details})


def main():
    latest = find_latest_run_dir()
    if not latest:
        print("No year_runs artifacts found under artifacts/year_runs")
        return
    print(f"Latest run dir: {latest}")
    summary_path = os.path.join(latest, "summary.md")
    entries = parse_summary_md(summary_path)
    if not entries:
        print("No entries parsed from summary.md; aborting")
        return
    asyncio.run(publish_entries(entries, latest))
    print("Leaderboard publish completed. Artifacts saved to artifacts/leaderboard.json and artifacts/leaderboard.html")


if __name__ == "__main__":
    main()
