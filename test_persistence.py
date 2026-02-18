import asyncio
import os
import sys
import uuid

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from fba_bench_api.core.database_async import AsyncSessionLocal, create_db_tables_async
from fba_bench_api.core.persistence_async import AsyncPersistenceManager

async def test_persistence():
    print("Testing persistence...")
    await create_db_tables_async()
    
    async with AsyncSessionLocal() as session:
        persistence = AsyncPersistenceManager(session)
        
        run_id = str(uuid.uuid4())
        data = {
            "id": run_id,
            "experiment_id": "test-exp-001",
            "scenario_id": "test-scenario",
            "params": {"model": "test"},
            "status": "completed",
            "metrics": {"score": 100}
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
        run = await persistence.experiment_runs().get(run_id)
        if run:
            print(f"Found run: {run['id']}")
        else:
            print("Run NOT found!")

if __name__ == "__main__":
    asyncio.run(test_persistence())
