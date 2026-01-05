#!/usr/bin/env python3
"""
Medusa Trainer: Autonomous Agent Evolution Engine

This module implements the core trainer for Project Medusa, handling genome-based agent evolution.
It integrates with the FBA-Bench benchmarking system to evaluate agent performance and manage generational progress.
"""

import os
import shutil
import subprocess
from pathlib import Path


# Assuming a simple Budget class for completeness (replace with actual if defined elsewhere)
class Budget:
    def check_budget(self, operation: str):
        """Placeholder for budget check."""
        pass

    def add_benchmark_cost(self):
        """Placeholder for adding benchmark cost."""
        pass


# Global logger (replace with proper logging setup)
import logging

logger = logging.getLogger(__name__)


# Define RESULTS_DIR as a class attribute or in __init__
RESULTS_DIR = Path("medusa_results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# Logging setup
LOG_DIR = Path("medusa_experiments/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "medusa_trainer.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MedusaTrainer:
    """
    Main trainer class for Project Medusa.
    Manages the evolution process, benchmark execution, and result archiving.
    """

    def __init__(self):
        """
        Initialize the Medusa trainer with budget and logging.
        """
        self.budget = Budget()  # Initialize budget manager
        self._logger = logger  # Assuming logger is defined globally or imported

    def run_benchmark(self, genome_path: Path, generation_num: int, agent_type: str = "student_agent") -> Path:
        """Run benchmark on a genome and return the results summary path."""
        self.budget.check_budget("benchmark")
        experiment_name = f"medusa_{agent_type}_gen_{generation_num}"
        
        # Use the project's simple benchmark runner
        command = [
            "poetry", "run", "python", "run_benchmark_simple.py",
            "--config", str(genome_path),
            "--experiment-name", experiment_name,
        ]

        self._logger.info(f"Running benchmark command: {' '.join(command)}")
        try:
            # Execute the benchmark script. Set a generous timeout.
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
            self._logger.info(f"Benchmark for {experiment_name} completed successfully.")
            
            # The benchmark script creates a directory like 'results/experiment_name_TIMESTAMP'
            # We need to find the latest one for this experiment.
            results_root = Path("results")
            
            # Find the most recent directory for this experiment
            run_dirs = sorted(list(results_root.glob(f"{experiment_name}_*")), key=os.path.getmtime, reverse=True)
            if not run_dirs:
                raise FileNotFoundError(f"No results directory found for {experiment_name}")
                
            latest_run_dir = run_dirs[0]
            summary_path = latest_run_dir / "summary.json"

            if not summary_path.exists():
                raise FileNotFoundError(f"summary.json not found in {latest_run_dir}")

            # Archive the summary to our dedicated results location for Medusa
            archive_path = RESULTS_DIR / f"{experiment_name}_summary.json"
            shutil.copy2(summary_path, archive_path)
            
            self._logger.info(f"Archived benchmark results to {archive_path}")
            self.budget.add_benchmark_cost()
            return archive_path

        except subprocess.CalledProcessError as e:
            self._logger.error(f"Benchmark failed for {experiment_name} with exit code {e.returncode}:\n{e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            self._logger.error(f"Benchmark for {experiment_name} timed out after 600 seconds.")
            raise
        except FileNotFoundError as e:
            self._logger.error(f"Could not find benchmark results: {e}")
            raise


# Example usage (for testing)
if __name__ == "__main__":
    trainer = MedusaTrainer()
    # Example usage (for testing)
    genome_path = Path("medusa_experiments/genomes/student_agent_gen_0.yaml")
    trainer.run_benchmark(genome_path, 1)
