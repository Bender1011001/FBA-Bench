from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # Fallback if yaml isn't available; we can proceed without it  # type: ignore[assignment]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/golden", tags=["GoldenRun"])

# Configuration: allow overriding base dir via environment
GOLDEN_BASE_DIR = Path(
    os.getenv("GOLDEN_BASE_DIR", "golden_masters/golden_run_baseline")
).resolve()
RUN_DIR_PREFIX = "golden_run_baseline_"
RUN_TS_REGEX = re.compile(r"^golden_run_baseline_(\d{8}-\d{6})$")
RUN_FILE_PATTERN = re.compile(r"^run_(\d+)\.json$", re.IGNORECASE)


@dataclass(frozen=True)
class RunInfo:
    dir_path: Path
    dir_name: str
    created_at: datetime


def _parse_dir_ts(dir_name: str) -> Optional[datetime]:
    """
    Parse the timestamp from a golden run directory name e.g.:
      golden_run_baseline_20250831-033251
    Returns timezone-aware UTC datetime if successful, else None.
    """
    m = RUN_TS_REGEX.match(dir_name)
    if not m:
        return None
    ts_str = m.group(1)
    try:
        dt = datetime.strptime(ts_str, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _list_run_dirs(base: Path) -> List[RunInfo]:
    items: List[RunInfo] = []
    if not base.exists():
        return items
    for child in base.iterdir():
        if not child.is_dir():
            continue
        if not child.name.startswith(RUN_DIR_PREFIX):
            continue
        dt = _parse_dir_ts(child.name)
        if dt is None:
            continue
        items.append(RunInfo(dir_path=child, dir_name=child.name, created_at=dt))
    return items


def _find_latest_run_dir() -> RunInfo:
    """
    Return the latest RunInfo by timestamp embedded in directory name.
    Raises 404 if none found.
    """
    runs = _list_run_dirs(GOLDEN_BASE_DIR)
    if not runs:
        raise HTTPException(status_code=404, detail="No golden run directories found")
    # Sort by created_at, descending
    runs.sort(key=lambda r: r.created_at, reverse=True)
    return runs[0]


def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to read JSON file %s: %s", path, e)
        return None


def _safe_read_yaml(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists() or yaml is None:
            return None
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to read YAML file %s: %s", path, e)
        return None


def _discover_first_run_file(run_dir: Path) -> Optional[Path]:
    """
    Prefer run_1.json; if not present, choose the lexicographically smallest run_*.json.
    """
    preferred = run_dir / "run_1.json"
    if preferred.exists():
        return preferred
    candidates = sorted(
        [p for p in run_dir.iterdir() if p.is_file() and RUN_FILE_PATTERN.match(p.name)]
    )
    return candidates[0] if candidates else None


def _default_summary() -> Dict[str, Any]:
    return {
        "total_runs": 0,
        "successful_runs": 0,
        "average_profit": None,
        "overall_profit": 0.0,
    }


def _build_golden_payload(latest: RunInfo) -> Dict[str, Any]:
    run_dir = latest.dir_path

    # Summary
    summary = _safe_read_json(run_dir / "summary.json") or _default_summary()

    # Experiment name from experiment_config.yaml if available
    exp_cfg = _safe_read_yaml(run_dir / "experiment_config.yaml") or {}
    experiment_name = exp_cfg.get("experiment_name") or "golden_run_baseline"

    # First run metrics (from first available run file)
    first_run_metrics: Optional[Dict[str, Any]] = None
    first_run_path = _discover_first_run_file(run_dir)
    if first_run_path:
        first_run = _safe_read_json(first_run_path) or {}
        # Flatten to metrics field if present; otherwise drop-in whole document
        if isinstance(first_run, dict) and isinstance(first_run.get("metrics"), dict):
            first_run_metrics = first_run["metrics"]
        elif isinstance(first_run, dict):
            # Fallback: best-effort extract common keys
            keys = (
                "profit_target",
                "inventory_turnover_rate",
                "customer_satisfaction",
                "on_time_delivery_rate",
            )
            first_run_metrics = {k: first_run.get(k) for k in keys if k in first_run}

    payload: Dict[str, Any] = {
        "run_id": latest.dir_name,
        "experiment_name": experiment_name,
        "created_at": latest.created_at.isoformat(),
        "path": str(run_dir.as_posix()),
        "summary": summary,
    }
    if first_run_metrics is not None:
        payload["first_run_metrics"] = first_run_metrics
    return payload


@router.get("/latest")
async def get_golden_latest() -> Dict[str, Any]:
    """
    Return latest Golden Run baseline information.

    Response envelope:
    {
      "data": {
        "run_id": "golden_run_baseline_YYYYMMDD-HHMMSS",
        "experiment_name": "golden_run_baseline",
        "created_at": "ISO-8601",
        "path": "golden_masters/golden_run_baseline/golden_run_baseline_YYYYMMDD-HHMMSS",
        "summary": {
          "total_runs": int,
          "successful_runs": int,
          "average_profit": float|null,
          "overall_profit": float
        },
        "first_run_metrics": {
          "profit_target": number,
          "inventory_turnover_rate": number,
          "customer_satisfaction": number,
          "on_time_delivery_rate": number
        }
      }
    }
    """
    if not GOLDEN_BASE_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Golden base directory not found: {GOLDEN_BASE_DIR}",
        )

    latest = _find_latest_run_dir()
    payload = _build_golden_payload(latest)
    # Return with "data" envelope to align with frontend ApiService usage
    return {"data": payload}
