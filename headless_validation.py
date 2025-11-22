import asyncio
import logging
import sys
import json
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("HeadlessValidation")

# Mock Redis Client if real one is not available
class MockRedisClient:
    def __init__(self):
        self.published_messages = []
        self.pushed_events = []
        logger.info("Initialized MockRedisClient")

    async def connect(self):
        logger.info("MockRedisClient connected")

    async def close(self):
        logger.info("MockRedisClient closed")

    async def publish(self, channel: str, message: Any):
        logger.info(f"Redis PUBLISH to {channel}: {message}")
        self.published_messages.append((channel, message))

    async def lpush(self, key: str, value: Any):
        logger.info(f"Redis LPUSH to {key}: {value}")
        self.pushed_events.append((key, value))

async def main():
    logger.info("Starting Headless Validation for FBA-Bench Enterprise Integration")

    try:
        # Import Enterprise Adapter
        # Note: We need to make sure the python path is correct. 
        # Assuming this script is run from FBA-Bench-Enterprise root.
        sys.path.append("src")
        
        from fba_bench_api.core.simulation_adapter import EnterpriseSimulationAdapter
        from fba_bench_api.core.redis_client import RedisClient
        from fba_bench_core.benchmarking.scenarios.registry import scenario_registry
        # from fba_bench_core.agent_runners.registry import register_runner # agent_runners not found in core
        
        # Mocking register_runner since it's not available in core yet or path is different
        # Based on file list, it seems agent_runners is not in fba_bench_core root but maybe in agents?
        # Actually, I saw FBA-Bench-core/agent_runners/registry.py in the initial file list but it seems it's not installed as a package or I missed it.
        # Let's try to import from fba_bench_core.agents.registry if it exists or just mock the runner creation in Engine if possible.
        # But Engine imports from agent_runners.registry.
        
        # Wait, I see FBA-Bench-core/agent_runners/registry.py in the initial file list.
        # But when I listed FBA-Bench-core/src/fba_bench_core, I didn't see agent_runners.
        # This means agent_runners is a top level package in the repo but maybe not in the src/fba_bench_core package?
        # Let's check setup.py to see package layout.
        
        # For now, let's patch the Engine's import or the function it uses.
        from unittest.mock import patch
        
        # Register a dummy scenario and runner for validation
        async def dummy_scenario(runner, payload):
            logger.info(f"Running dummy scenario with payload: {payload}")
            return {"result": "success"}

        scenario_registry.register("basic_scenario", dummy_scenario)
        
        # Register a dummy runner
        class DummyRunner:
            def __init__(self, config):
                pass
        
        # register_runner("default_runner", DummyRunner)

        # Mock Redis for this headless run to avoid dependency on external service
        redis_mock = MockRedisClient()
        
        # Patch create_runner in fba_bench_core.benchmarking.engine.core
        with patch('fba_bench_core.benchmarking.engine.core.create_runner', return_value=DummyRunner({})):
            
            sim_config_dict = {
                "scenarios": [
                    {
                        "key": "basic_scenario",
                        "timeout_seconds": 10.0,
                        "repetitions": 1,
                        "seeds": [123]
                    }
                ],
                "runners": [
                    {
                        "key": "default_runner",
                        "config": {}
                    }
                ],
                "metrics": [],
                "validators": [],
                "parallelism": 1,
                "retries": 0
            }

            # Instantiate the adapter
            run_id = "validation_run_001"
            logger.info(f"Instantiating EnterpriseSimulationAdapter with run_id={run_id}")
            
            # We need to handle the case where SimulationOrchestrator or SimulationConfig are not actually available
            # or have different signatures than expected since I couldn't verify them with read_file.
            # But let's try to run it.
            
            try:
                adapter = EnterpriseSimulationAdapter(run_id=run_id, config=sim_config_dict, redis=redis_mock)
            except ImportError as e:
                logger.error(f"ImportError during adapter instantiation: {e}")
                logger.info("This might be due to missing core dependencies or incorrect paths.")
                return
            except Exception as e:
                logger.error(f"Error during adapter instantiation: {e}")
                # If it fails due to config validation, we'll know.
                return

            # Run the simulation loop
            # The start() method creates a background task. For validation, we might want to run it directly or wait for it.
            logger.info("Starting simulation loop...")
            
            # We can use _run_loop directly to await it, but start() is the public API.
            # Let's use start() and then wait a bit.
            await adapter.start()
            
            # Wait for a few seconds to let the loop run
            logger.info("Waiting for simulation ticks...")
            await asyncio.sleep(5)
            
            # Check if we got any updates in Redis
            if len(redis_mock.published_messages) > 0:
                logger.info(f"SUCCESS: Received {len(redis_mock.published_messages)} state updates in Redis.")
                logger.info(f"Last update: {redis_mock.published_messages[-1]}")
            else:
                logger.warning("WARNING: No state updates received in Redis. Simulation might not be ticking.")

            # Check for events
            if len(redis_mock.pushed_events) > 0:
                logger.info(f"SUCCESS: Received {len(redis_mock.pushed_events)} events in Redis.")
            else:
                logger.info("No events received (this might be normal if no events occurred).")

            logger.info("Headless validation complete.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred during validation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())