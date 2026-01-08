#!/usr/bin/env python3
"""
Script to run the leaderboard competition between registered agents.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from benchmarking.config.manager import get_config_manager
from benchmarking.config.pydantic_config import BenchmarkConfig
from benchmarking.core.engine import BenchmarkEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("leaderboard_run.log")
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the benchmark."""
    config_path = "leaderboard_comp.yaml"
    
    try:
        logger.info(f"Starting Leaderboard Competition run using {config_path}...")

        # Register agents into benchmarking registry
        logger.info("Registering agents...")
        try:
            from benchmarking.agents.registry import agent_registry, AgentDescriptor
            from agents.advanced_agent import AdvancedAgent
            from agents.baseline.baseline_agent_v1 import BaselineAgentV1
            
            agent_registry.register_agent(AgentDescriptor(
                slug="advanced_agent",
                display_name="Advanced Agent",
                constructor=AdvancedAgent,
                provenance="core"
            ))
            agent_registry.register_agent(AgentDescriptor(
                slug="baseline_v1",
                display_name="Baseline Agent V1",
                constructor=BaselineAgentV1,
                provenance="core"
            ))
            logger.info("Agents registered successfully.")
            logger.info(f"Registry slugs: {agent_registry._by_slug.keys()}")
        except Exception as e:
            logger.error(f"Failed to register agents: {e}")
            raise

        # Load benchmark configuration from YAML file
        config_manager = get_config_manager()
        config_data = config_manager.load_config(config_path, "benchmark")
        
        # Convert dict to BenchmarkConfig object for the engine
        config = BenchmarkConfig.model_validate(config_data)
        
        with open("config_debug.txt", "w") as f:
            f.write(f"config_data keys: {list(config_data.keys())}\n")
            f.write(f"config object fields: {config.__dict__.keys()}\n")
            f.write(f"metrics in config_data: {'metrics' in config_data}\n")
            f.write(f"metrics type: {type(config_data.get('metrics'))}\n")
        
        logger.info(f"Benchmark configuration loaded and validated from {config_path}")

        # Create and initialize the benchmark engine
        engine = BenchmarkEngine(config=config)

        # Initialize the engine
        logger.info("Initializing engine...")
        await engine.initialize()

        logger.info("Running benchmark competition...")

        # Run the benchmark
        # We pass the dict here because BenchmarkEngine._validate_configuration 
        # expects a dict for 'in' operator checks in Classic mode.
        result = await engine.run_benchmark(config=config_data)

        logger.info("Benchmark completed successfully!")

        # Save results
        results_path = await engine.save_results()
        logger.info(f"Results saved to: {results_path}")

        # Print summary
        summary = engine.get_summary()
        logger.info("=== Benchmark Summary ===")
        logger.info(f"Total duration: {summary.get('total_duration_seconds', 0):.2f} seconds")
        
        agent_results = summary.get('agent_results', {})
        for agent_id, metrics in agent_results.items():
            logger.info(f"Agent: {agent_id}")
            for metric, value in metrics.items():
                logger.info(f"  - {metric}: {value}")

        # Clean up
        # await engine.cleanup() # Method does not exist

        logger.info("Leaderboard Competition run completed successfully!")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
