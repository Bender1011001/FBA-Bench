from __future__ import annotations

"""
Structural consistency validator.

Key: "structural_consistency"

- Validates that each run in a ScenarioReport-like dict contains required fields with correct types.
- Safe defaults: returns issues and summary; never raises.
- Deterministic.

Input:
- report: {
    "scenario_key": str,
    "runs": [RunResult-like dicts],
    "aggregates": dict
  }

Context (optional): not used.

Output:
- {"issues": [issue...], "summary": {...}}
"""

from typing import Any, Dict, Optional  # noqa: E402

from .registry import register_validator  # noqa: E402
from .types import Issue, ValidationOutput, normalize_output  # noqa: E402

REQUIRED_BASE_FIELDS = {
    "scenario_key": str,
    "runs": list,
    "aggregates": dict,
}

REQUIRED_RUN_FIELDS = {
    "scenario_key": str,
    "runner_key": str,
    "status": str,  # "success"|"failed"|"timeout"|"error"
    "duration_ms": int,
    "metrics": dict,
}

# When status == "success", require output be a dict (may be empty)
SUCCESS_OUTPUT_FIELD = ("output", dict)


def _type_name(t) -> str:
    try:
        return t.__name__
    except Exception:
        return str(t)


def _validate_run(idx: int, run: Dict[str, Any], out: ValidationOutput) -> None:
    # Base required fields
    for key, tp in REQUIRED_RUN_FIELDS.items():
        if key not in run:
            out.add_issue(
                Issue(
                    id="missing_field",
                    severity="error",
                    message=f"Run[{idx}] missing required field '{key}'",
                    path=["runs", str(idx), key],
                )
            )
            continue
        if not isinstance(run[key], tp):
            out.add_issue(
                Issue(
                    id="invalid_type",
                    severity="error",
                    message=f"Run[{idx}].{key} expected {_type_name(tp)}, got {type(run[key]).__name__}",
                    path=["runs", str(idx), key],
                )
            )

    # Seed is optional but if present must be int or None
    if "seed" in run and run["seed"] is not None and not isinstance(run["seed"], int):
        out.add_issue(
            Issue(
                id="invalid_type",
                severity="warning",
                message=f"Run[{idx}].seed expected int or None, got {type(run['seed']).__name__}",
                path=["runs", str(idx), "seed"],
            )
        )

    # Output when success
    status = run.get("status")
    if status == "success":
        key, tp = SUCCESS_OUTPUT_FIELD
        if key not in run or run[key] is None:
            out.add_issue(
                Issue(
                    id="missing_output_on_success",
                    severity="error",
                    message=f"Run[{idx}] status=success but 'output' missing/None",
                    path=["runs", str(idx), "output"],
                )
            )
        elif not isinstance(run[key], tp):
            out.add_issue(
                Issue(
                    id="invalid_output_type",
                    severity="error",
                    message=f"Run[{idx}].output expected dict, got {type(run[key]).__name__}",
                    path=["runs", str(idx), "output"],
                )
            )
    else:
        # On non-success, output must be None
        if run.get("output") not in (None,):
            out.add_issue(
                Issue(
                    id="unexpected_output_on_failure",
                    severity="warning",
                    message=f"Run[{idx}] status={status} should not include 'output'",
                    path=["runs", str(idx), "output"],
                )
            )

    # Duration sanity
    dur = run.get("duration_ms")
    if isinstance(dur, int) and dur < 0:
        out.add_issue(
            Issue(
                id="negative_duration",
                severity="warning",
                message=f"Run[{idx}].duration_ms is negative ({dur})",
                path=["runs", str(idx), "duration_ms"],
            )
        )


def structural_consistency_validate(
    report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    out = ValidationOutput()
    # Scenario-level required fields
    if not isinstance(report, dict):
        out.add_issue(
            Issue(
                id="invalid_report_type",
                severity="error",
                message=f"report expected dict, got {type(report).__name__}",
                path=None,
            )
        )
        return normalize_output(out)

    for key, tp in REQUIRED_BASE_FIELDS.items():
        if key not in report:
            out.add_issue(
                Issue(
                    id="missing_field",
                    severity="error",
                    message=f"ScenarioReport missing '{key}'",
                    path=[key],
                )
            )
        elif not isinstance(report[key], tp):
            out.add_issue(
                Issue(
                    id="invalid_type",
                    severity="error",
                    message=f"ScenarioReport.{key} expected {_type_name(tp)}, got {type(report[key]).__name__}",
                    path=[key],
                )
            )

    runs = report.get("runs") or []
    if not isinstance(runs, list):
        runs = []
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            out.add_issue(
                Issue(
                    id="invalid_run_type",
                    severity="error",
                    message=f"Run[{i}] expected dict, got {type(run).__name__}",
                    path=["runs", str(i)],
                )
            )
            continue
        _validate_run(i, run, out)

    # Summary details
    success = sum(
        1 for r in runs if isinstance(r, dict) and r.get("status") == "success"
    )
    errors = sum(1 for r in runs if isinstance(r, dict) and r.get("status") == "error")
    timeouts = sum(
        1 for r in runs if isinstance(r, dict) and r.get("status") == "timeout"
    )
    out.summary.details.update(
        {
            "runs": len(runs),
            "success": success,
            "errors": errors,
            "timeouts": timeouts,
        }
    )
    return normalize_output(out)


# Auto-register on import
register_validator("structural_consistency", structural_consistency_validate)
