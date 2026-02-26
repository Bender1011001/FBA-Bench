#!/usr/bin/env python3
"""
Simple script to run a benchmark test with Gemini Flash agent.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from benchmarking.config.manager import get_config_manager
from benchmarking.core.engine import BenchmarkEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to run the benchmark."""
    parser = argparse.ArgumentParser(description="Run a Gemini Flash benchmark test.")
    parser.add_argument(
        "--config",
        type=str,
        default="benchmark_gemini_flash.yaml",
        help="Path to the benchmark configuration YAML file.",
    )
    args = parser.parse_args()

    try:
        logger.info("Starting Gemini Flash benchmark test...")

        # Load benchmark configuration from YAML file
        config_manager = get_config_manager()
        config = config_manager.load_config(args.config, "benchmark")

        logger.info(f"Benchmark configuration loaded successfully from {args.config}")

        # Create and initialize the benchmark engine
        engine = BenchmarkEngine(config)

        # Initialize the engine
        await engine.initialize()

        logger.info("Running benchmark...")

        # Run the benchmark
        result = await engine.run_benchmark()

        logger.info("Benchmark completed successfully!")

        # Save results
        results_path = await engine.save_results()
        logger.info(f"Results saved to: {results_path}")

        # Print summary
        summary = engine.get_summary()
        logger.info("Benchmark Summary:")
        logger.info(f"  - Total duration: {summary.get('total_duration_seconds', 0):.2f} seconds")
        logger.info(f"  - Scenarios completed: {len(summary.get('scenario_results', []))}")
        logger.info(f"  - Agents tested: {len(summary.get('agents_tested', []))}")
        logger.info(f"  - Success rate: {summary.get('success_rate', 0):.2f}%")

        # Clean up
        await engine.cleanup()

        logger.info("Gemini Flash benchmark test completed successfully!")

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.exception("Configuration file not found")
        sys.exit(1)
    except (ValueError, KeyError) as e:
        logger.error(f"Invalid configuration or arguments: {e}")
        logger.exception("Invalid configuration or arguments")
        sys.exit(1)
    except Exception as e:
        # General fallback for any other unexpected errors
        logger.error(f"An unexpected error occurred during benchmark execution: {e}")
        logger.exception("Unexpected error during benchmark execution")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
