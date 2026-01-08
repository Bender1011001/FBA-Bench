#!/usr/bin/env python3
"""Regenerate leaderboard from scores.json."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leaderboard.score_tracker import ScoreTracker
from leaderboard.leaderboard_manager import LeaderboardManager
from leaderboard.leaderboard_renderer import LeaderboardRenderer


async def main():
    print("=== Leaderboard Regeneration ===")
    
    tracker = ScoreTracker()
    scores = tracker.get_all_tracked_scores()
    
    print(f"Found {len(scores)} bots in scores.json:")
    for bot_name, tiers in scores.items():
        for tier, runs in tiers.items():
            verified = any(r.get("verified") for r in runs)
            print(f"  - {bot_name} ({tier}): {len(runs)} runs, verified={verified}")
    
    renderer = LeaderboardRenderer()
    manager = LeaderboardManager(tracker, renderer)
    await manager.generate_leaderboard_artifacts()
    
    print("\n✅ Leaderboard artifacts regenerated!")
    
    # Show the JSON summary
    with open("artifacts/leaderboard.json") as f:
        data = json.load(f)
    
    print(f"\nLeaderboard Rankings:")
    for r in data.get("rankings", []):
        badge = "🔒 VERIFIED" if r.get("verified") else ""
        print(f"  #{r['rank']} {r['bot_name']}: Score={r['score']} {badge}")
    
    print(f"\nSummary: {data.get('summary', {})}")


if __name__ == "__main__":
    asyncio.run(main())
