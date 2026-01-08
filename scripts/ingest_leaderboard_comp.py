import json
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from leaderboard.leaderboard_manager import LeaderboardManager
from leaderboard.leaderboard_renderer import LeaderboardRenderer
from leaderboard.score_tracker import ScoreTracker

async def main():
    result_path = "results/leaderboard_comp_run.json"
    if not os.path.exists(result_path):
        print(f"Result file {result_path} not found.")
        return

    print(f"Loading results from {result_path}...")
    with open(result_path) as f:
        data = json.load(f)
    
    tracker = ScoreTracker(artifacts_dir="artifacts")
    renderer = LeaderboardRenderer(template_path="leaderboard/templates")
    # bot_configs_dir defaults to baseline_bots/configs. Make sure it exists or is handled.
    manager = LeaderboardManager(tracker, renderer, artifacts_dir="artifacts")
    
    results = data.get("results", {}).get("scenario_results", [])
    print(f"Found {len(results)} results to ingest.")

    for res in results:
        agent_id = res.get("agent_id")
        if not agent_id:
            continue
            
        tier = "T0" # Default tier for this comp
        metrics = res.get("metrics", {})
        score = metrics.get("score", 0.0)
        
        # Ensure score is present for manager
        ingest_metrics = {"score": score, "details": res}
        ingest_metrics.update(metrics)

        print(f"Ingesting result for {agent_id}: score={score}")
        await manager.update_leaderboard(agent_id, tier, ingest_metrics)

    print("Ingestion complete. Leaderboard artifacts updated in artifacts/ folder.")

if __name__ == "__main__":
    asyncio.run(main())
