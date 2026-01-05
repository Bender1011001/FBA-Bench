#!/usr/bin/env python3
"""
Run Tier 0 and Tier 1 scenarios across 11 models with year-like pacing.
Stores logs and results in artifacts/year_runs/<timestamp>/
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

# List of 11 models from the task
MODELS = [
    "x-ai/grok-4-fast:free",
    "deepseek/deepseek-chat-v3.1:free",
    "deepseek/deepseek-r1-0528:free",
    "qwen/qwen3-coder:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "openai/gpt-oss-20b:free",
    "moonshotai/kimi-k2:free",
    "cognitivecomputations/dolphin3.0-mistral-24b:free",
    "openai/gpt-oss-120b:free",
]

# Common parameters for year-like pacing
YEAR_PARAMS = {
    "SIM_MAX_TICKS": "365",
    "SIM_TICK_INTERVAL_SECONDS": "0.01",
    "SIM_TIME_ACCELERATION": "200",
}

def run_single_run(model, tier, output_dir):
    """Run a single tier for a model and save output."""
    cmd = [
        "python", "integration_tests/run_integration_tests.py",
        "--tier", tier,
        "--model", model,
        "--max-ticks", YEAR_PARAMS["SIM_MAX_TICKS"],
        "--tick-interval-seconds", YEAR_PARAMS["SIM_TICK_INTERVAL_SECONDS"],
        "--time-acceleration", YEAR_PARAMS["SIM_TIME_ACCELERATION"],
        "--verbose"
    ]
    
    env = os.environ.copy()
    for key, value in YEAR_PARAMS.items():
        env[key] = value
    
    # CRITICAL: Ensure OPENROUTER_API_KEY is passed through
    if "OPENROUTER_API_KEY" not in env:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found in environment. "
            "Set it before running this script: set OPENROUTER_API_KEY=sk-..."
        )
    
    # Replace both '/' and ':' for valid Windows filenames
    safe_model = model.replace('/', '_').replace(':', '_')
    log_file = output_dir / f"{tier}_{safe_model}.log"
    
    print(f"Running {tier} for {model}...")
    with open(log_file, "w", encoding="utf-8") as f:
        result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    
    return result.returncode, log_file

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("artifacts") / "year_runs" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Running year-like Tier 0 and Tier 1 for 11 models. Logs in {output_dir}")
    
    results = {"T0": {}, "T1": {}}
    
    for model in MODELS:
        print(f"\n--- Model: {model} ---")
        
        # Run T0
        code, log = run_single_run(model, "T0", output_dir)
        results["T0"][model] = {"return_code": code, "log": log}
        print(f"T0 {model}: exit code {code}")
        
        # Run T1 (requirements validation, model may not affect it, but set anyway)
        code, log = run_single_run(model, "T1", output_dir)
        results["T1"][model] = {"return_code": code, "log": log}
        print(f"T1 {model}: exit code {code}")
    
    # Summary
    summary_file = output_dir / "summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# Year-Like Runs Summary\n\n")
        f.write(f"Timestamp: {timestamp}\n\n")
        
        for tier, model_results in results.items():
            f.write(f"## {tier} Results\n")
            successful = sum(1 for r in model_results.values() if r["return_code"] == 0)
            f.write(f"Successful: {successful}/{len(model_results)} ({successful/len(model_results):.1%})\n\n")
            
            for model, r in model_results.items():
                status = "PASS" if r["return_code"] == 0 else "FAIL"
                f.write(f"- {model}: {status} (log: {r['log'].name})\n")
            f.write("\n")
    
    print(f"\nAll runs completed. Summary: {summary_file}")
    print(f"Logs directory: {output_dir}")

if __name__ == "__main__":
    main()
