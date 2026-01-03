import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import sys

# Ensure we can import from src
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "src"))

# Load environment variables from .env if possible
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

from fba_bench_api.core.database_async import AsyncSessionLocal
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

async def populate():
    print("🚀 Populating benchmark results to database...")
    
    # Load the merged benchmark results
    results_path = ROOT_DIR / "openrouter_benchmark_results.json"
    if not results_path.exists():
        print(f"  [ERROR] Benchmark results not found at {results_path}")
        print("  Run merge_benchmark_results.py first.")
        return
    
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    rankings = data.get("rankings", [])
    if not rankings:
        print("  [ERROR] No rankings found in benchmark results.")
        return
    
    async with AsyncSessionLocal() as db:
        pm = AsyncPersistenceManager(db)
        
        count = 0
        for entry in rankings:
            model_id = entry["model"]
            display_name = entry["display_name"]
            
            # Create experiment record
            exp_id = str(uuid4())
            
            experiment = {
                "id": exp_id,
                "name": f"Benchmark: {display_name}",
                "description": f"Automated benchmark run for {model_id} via OpenRouter. Tested on business reasoning, problem solving, and creative strategy prompts.",
                "agent_id": model_id,
                "scenario_id": "openrouter_business_v1",
                "params": {
                    "score": entry["score"],
                    "quality_score": entry["quality_score"],
                    "success_rate": entry["success_rate"],
                    "avg_response_time": entry["avg_response_time"],
                    "total_tokens": entry["total_tokens"],
                    "tier": entry["tier"],
                    "cost": entry["cost"],
                    "rank": entry["rank"]
                },
                "status": "completed",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            try:
                # Create as draft (default)
                await pm.experiments().create(experiment)
                
                # Update to completed
                await pm.experiments().update(exp_id, {"status": "completed"})
                
                rank_badge = "🥇" if entry["rank"] == 1 else "🥈" if entry["rank"] == 2 else "🥉" if entry["rank"] == 3 else f"#{entry['rank']}"
                print(f"  {rank_badge} {display_name} ({entry['tier']}) - Score: {entry['score']:.1f}%")
                count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to save {display_name} to database: {e}")

        await db.commit()
        print(f"\n✅ Finished! Added {count} results to the leaderboard database.")
        print(f"\n📊 Leaderboard Summary:")
        print(f"   Best Overall: {data['summary']['best_overall']}")
        print(f"   Fastest: {data['summary']['fastest']}")
        print(f"   Best Quality: {data['summary']['best_quality']}")
        print(f"   Best Value: {data['summary']['best_value']}")

if __name__ == "__main__":
    asyncio.run(populate())
