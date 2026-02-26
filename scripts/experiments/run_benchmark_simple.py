#!/usr/bin/env python3
"""
Simple FBA-Bench Runner - No GUI dependencies needed
Just runs a benchmark and opens ClearML results automatically.
"""

import argparse
import os
import subprocess
import time
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="Simple FBA-Bench Runner")
    parser.add_argument("--config", type=str, default="src/scenarios/tier_0_baseline.yaml",
                        help="Path to the benchmark config file (default: src/scenarios/tier_0_baseline.yaml)")
    parser.add_argument("--experiment-name", type=str,
                        default=f"run_{int(time.time())}",
                        help="A unique name for the experiment run.")
    args = parser.parse_args()

    experiment_name = args.experiment_name

    print("🎮 FBA-Bench Simple Runner")
    print("=" * 40)
    print(f"Running benchmark with config: {args.config}")
    print(f"Experiment name: {experiment_name}")
    print("This will take about 30 seconds...")
    print()

    try:
        # Set environment for local ClearML
        os.environ["CLEARML_API_HOST"] = "http://localhost:8008"
        os.environ["CLEARML_WEB_HOST"] = "http://localhost:8080"
        os.environ["CLEARML_FILES_HOST"] = "http://localhost:8081"

        # Run the benchmark with ClearML tracking
        print("🚀 Starting benchmark with ClearML tracking...")
        command = [
            "poetry", "run", "python", "-m", "fba_bench_core.simulation_orchestrator", args.config,
            "--task-name", experiment_name
        ]
        result = subprocess.run(
            command,
            capture_output=False,
            text=True,
        )

        if result.returncode == 0:
            print("\n🎉 Benchmark completed successfully!")
            print("📊 Opening ClearML results...")

            # Wait a moment then open browser
            time.sleep(2)
            webbrowser.open("http://localhost:8080")

            print("\n✅ Results are now visible in your browser!")
            print(f"🔍 Look for '{experiment_name}' experiment in 'FBA-Bench' project in ClearML")
            print("📈 Click on the experiment to see metrics and plots")

        else:
            print("❌ Benchmark failed to run")

    except KeyboardInterrupt:
        print("\n⏹️ Benchmark stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
