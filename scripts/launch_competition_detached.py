#!/usr/bin/env python3
"""
Detached Competition Launcher
==============================
Spawns run_competition_benchmark.py as a fully independent Windows process
using DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP so it survives even after
this launcher (and any parent session) exits.

All output is written to competition_run.log in the repo root.
Progress can be monitored by reading that log file or the incremental
results/competition/run_<timestamp>/recording.json that is updated after
every completed simulation day.

Usage:
    python launch_competition_detached.py
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PYTHON     = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPT     = REPO_ROOT / "scripts" / "run_competition_benchmark.py"
LOG_FILE   = REPO_ROOT / "competition_run.log"
ERR_FILE   = REPO_ROOT / "competition_run_err.log"

# Windows process-creation flags
DETACHED_PROCESS       = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

cmd = [
    str(PYTHON),
    str(SCRIPT),
    "--days", "365",
    "--seed", "42",
    "--new-baseline",
    "--budget-usd", "50",
    "--log-file", str(LOG_FILE),
]

print(f"Launching: {' '.join(cmd)}")
print(f"Log file:  {LOG_FILE}")

with open(LOG_FILE, "w", encoding="utf-8") as log_out, \
     open(ERR_FILE, "w", encoding="utf-8") as log_err:
    proc = subprocess.Popen(
        cmd,
        stdout=log_out,
        stderr=log_err,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

print(f"Launched PID {proc.pid} — fully detached from this session.")
print(f"Monitor: tail -f {LOG_FILE}")
print(f"Results: {REPO_ROOT / 'results' / 'competition'}")
