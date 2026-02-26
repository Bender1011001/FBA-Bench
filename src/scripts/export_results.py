"""
Script to export benchmark results from the database to a JSON file for the static documentation site.
"""
import asyncio
import json
import os
import sys

# Add src to path to allow imports
sys.path.append(os.path.join(os.getcwd(), "src"))

# Set DB URL to match backend (running in src)
# FORCE ABSOLUTE PATH for debugging
os.environ["FBA_BENCH_DB_URL"] = "sqlite:///e:/code.projects/fba/FBA-Bench-Enterprise/src/fba_bench.db"

from fba_bench_api.core.database_async import AsyncSessionLocal, create_db_tables_async
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

OUTPUT_FILE = "docs/data/benchmark_results.json"

async def export_results():
    print(f"Exporting benchmark results to {OUTPUT_FILE}...")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Initialize tables
    await create_db_tables_async()
    
    async with AsyncSessionLocal() as session:
        persistence = AsyncPersistenceManager(session)
        # List all runs
        runs = await persistence.experiment_runs().list_all(limit=1000)
        
        # Filter for completed runs with results or metrics
        export_data = []
        for run in runs:
            if run.get("status") == "completed" or run.get("results") or run.get("metrics"):
                # Parse metrics if string
                metrics = run.get("metrics") or run.get("results") or {}
                if isinstance(metrics, str):
                    try:
                        metrics = json.loads(metrics)
                    except Exception:
                        pass
                
                export_data.append({
                    "id": run["id"],
                    "agent_id": "unknown", # TODO: fetch participants
                    "scenario_id": run["scenario_id"],
                    "created_at": str(run["created_at"]),
                    "metrics": metrics,
                    "params": run.get("params") or {}
                })
        
        # Sort by date desc
        export_data.sort(key=lambda x: x["created_at"], reverse=True)
        
        with open(OUTPUT_FILE, "w") as f:
            json.dump(export_data, f, indent=2)
            
        print(f"Exported {len(export_data)} records.")

if __name__ == "__main__":
    asyncio.run(export_results())
