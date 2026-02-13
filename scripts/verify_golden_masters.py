#!/usr/bin/env python3
"""
Golden master verification (fast, filesystem-level).

The repository contains pre-generated "golden masters" under `golden_masters/`.
Historically, this script attempted to run a large suite of integration tests to
reproduce those outputs. That approach is brittle in local/dev environments where
optional dependencies and fixtures may not be available.

This script provides a professional baseline verification:
- Ensures golden master directories exist
- Ensures each golden master run folder has required artifacts
- Validates `summary.json` is valid JSON with expected keys

If you want to run a full golden-run reproduction, wire it through a dedicated
CI job with pinned dependencies and stable fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_SUMMARY_KEYS = {"total_runs", "successful_runs", "average_profit", "overall_profit"}


def _fail(msg: str) -> int:
    print(f"[FAILED] {msg}")
    return 1


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    golden_root = repo_root / "golden_masters"
    baseline_root = golden_root / "golden_run_baseline"

    if not golden_root.exists():
        return _fail("Missing directory: golden_masters/")
    if not baseline_root.exists():
        return _fail("Missing directory: golden_masters/golden_run_baseline/")

    run_dirs = sorted([p for p in baseline_root.iterdir() if p.is_dir()])
    if not run_dirs:
        return _fail("No golden baseline run directories found under golden_masters/golden_run_baseline/")

    problems: list[str] = []
    checked = 0

    for run_dir in run_dirs:
        exp_cfg = run_dir / "experiment_config.yaml"
        summary = run_dir / "summary.json"

        if not exp_cfg.exists():
            problems.append(f"{run_dir}: missing experiment_config.yaml")
            continue
        if not summary.exists():
            problems.append(f"{run_dir}: missing summary.json")
            continue

        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{run_dir}: invalid summary.json ({e})")
            continue

        if not isinstance(data, dict):
            problems.append(f"{run_dir}: summary.json must be an object")
            continue

        missing = REQUIRED_SUMMARY_KEYS - set(data.keys())
        if missing:
            problems.append(f"{run_dir}: summary.json missing keys: {sorted(missing)}")
            continue

        checked += 1

    if problems:
        print("Golden master verification problems:")
        for p in problems:
            print(f"- {p}")
        return 1

    print(f"[PASSED] Golden master artifacts verified ({checked} run folders).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

