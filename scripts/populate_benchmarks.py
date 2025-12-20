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
    async with AsyncSessionLocal() as db:
        pm = AsyncPersistenceManager(db)
        
        results_files = [
            ("openrouter_benchmark_results.json", "Grok-4 Fast"),
            ("results_grok41.json", "Grok-4.1 Fast"),
            ("results_deepseek.json", "DeepSeek-v3.2")
        ]
        
        count = 0
        for filename, display_name in results_files:
            path = ROOT_DIR / filename
            if not path.exists():
                print(f"  [SKIPPED] {display_name} - File {filename} not found.")
                continue
                
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"  [ERROR] Failed to read {filename}: {e}")
                continue
                
            if not data.get("model_results") or len(data["model_results"]) == 0:
                print(f"  [SKIPPED] {display_name} - No results in file.")
                continue
                
            res = data["model_results"][0]
            summary = res.get("summary", {})
            successful = summary.get("successful_responses", 0)
            total = summary.get("total_prompts", 3)
            
            # Calculate average quality score
            prompts = res.get("prompts", [])
            quality_scores = [p.get("quality_score", 0) for p in prompts]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            # Create experiment record
            exp_id = str(uuid4())
            model_id = res.get("model", "unknown")
            
            experiment = {
                "id": exp_id,
                "name": f"Benchmark: {display_name}",
                "description": f"Automated benchmark run for {model_id} via OpenRouter.",
                "agent_id": model_id,
                "scenario_id": "openrouter_business_v1",
                "params": {
                    "quality_score": avg_quality,
                    "success_rate": successful / total if total > 0 else 0,
                    "avg_response_time": summary.get("average_response_time", 0),
                    "total_tokens": summary.get("total_tokens", 0),
                    "successful_responses": successful,
                    "total_prompts": total
                },
                "status": "completed",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            try:
                await pm.experiments().create(experiment)
                print(f"  [SUCCESS] {display_name} ({model_id}) - Score: {avg_quality*100:.2f}%")
                count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to save {display_name} to database: {e}")

        print(f"✅ Finished! Added {count} results to the leaderboard.")

if __name__ == "__main__":
    asyncio.run(populate())
