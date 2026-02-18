import asyncio
import os
import sys
import uuid

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

# Target src DB
os.environ["FBA_BENCH_DB_URL"] = "sqlite:///src/fba_bench.db"

from fba_bench_api.core.database_async import AsyncSessionLocal, create_db_tables_async
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

async def test_src_persistence():
    print(f"Testing persistence (Env: {os.environ.get('FBA_BENCH_DB_URL')})...")
    
    # Init schema
    await create_db_tables_async()
    
    async with AsyncSessionLocal() as session:
        persistence = AsyncPersistenceManager(session)
        
        run_id = str(uuid.uuid4())
        data = {
            "id": run_id,
            "experiment_id": "test-src-001",
            "scenario_id": "test-scenario",
            "params": {"model": "test-src"},
            "status": "completed",
            "metrics": {"score": 999}
        }
        
        print(f"Creating run {run_id}...")
        try:
            await persistence.experiment_runs().create(data)
            await session.commit()
            print("Commit successful.")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            return

    # Verify
    async with AsyncSessionLocal() as session:
        persistence = AsyncPersistenceManager(session)
        print("Reading back...")
        runs = await persistence.experiment_runs().list_all()
        print(f"Found {len(runs)} runs.")
        for r in runs:
            print(f" - {r['id']} (Metrics: {r.get('metrics')})")

if __name__ == "__main__":
    asyncio.run(test_src_persistence())
