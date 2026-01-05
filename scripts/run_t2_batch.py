#!/usr/bin/env python3
"""
Run Tier-2 (T2) simulation sequentially for a list of models,
ensuring each run performs real LLM calls.

Usage:
    poetry run python scripts/run_t2_batch.py

Behavior:
- Runs each model in sequence using integration_tests/run_integration_tests.py
- Sets SIM_MAX_TICKS=365, SIM_TICK_INTERVAL_SECONDS=0.01, SIM_TIME_ACCELERATION=200
- Sets MODEL_SLUG per-run
- Writes per-run stdout/stderr to artifacts/year_runs/<timestamp>/<T2_<sanitized_model>_free.log>
- Exits on first non-zero exit code (so failures are visible)
"""
import os
import subprocess
import sys
from datetime import datetime

MODELS = [
    "anthropic/claude-sonnet-4",
    "google/gemini-2.5-flash",
    "anthropic/claude-sonnet-4.5",
    "google/gemini-2.5-pro",
    "openai/gpt-5",
    "openai/gpt-oss-120b",
    "openai/gpt-5-mini",
]

# Simulation pacing
SIM_ENV = {
    "SIM_MAX_TICKS": "365",
    "SIM_TICK_INTERVAL_SECONDS": "0.01",
    "SIM_TIME_ACCELERATION": "200",
}

# Create a timestamped folder for logs
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
out_root = os.path.join("artifacts", "year_runs", timestamp)
os.makedirs(out_root, exist_ok=True)

def sanitize_model(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")

def run_model(model: str) -> int:
    sanitized = sanitize_model(model)
    log_name = f"T2_{sanitized}_free.log"
    log_path = os.path.join(out_root, log_name)
    env = os.environ.copy()
    env.update(SIM_ENV)
    env["MODEL_SLUG"] = model

    cmd = [
        "poetry",
        "run",
        "python",
        "integration_tests/run_integration_tests.py",
        "--tier",
        "T2",
        "--model",
        model,
        "--verbose",
    ]

    print(f"\n=== Starting T2 run for: {model}")
    print(f"Writing logs to: {log_path}")
    with open(log_path, "w", encoding="utf-8") as lf:
        # Stream output to log file and also mirror to stdout for visibility
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            lf.write(line)
            lf.flush()
            sys.stdout.write(line)
            sys.stdout.flush()
        proc.wait()
        return proc.returncode

def main():
    for m in MODELS:
        rc = run_model(m)
        if rc != 0:
            print(f"*** Run for {m} exited with code {rc}. Stopping batch.")
            sys.exit(rc)
        else:
            print(f"=== Completed T2 run for: {m}")
    print("\nAll T2 runs completed successfully.")
    print(f"Logs and artifacts are in: {out_root}")

if __name__ == "__main__":
    main()
