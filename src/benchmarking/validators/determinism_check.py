from __future__ import annotations

"""
Determinism check validator.

Key: "determinism_check"

Checks that runs with the same (runner_key, seed) produce consistent outputs within tolerance.
- Numeric fields compared with absolute tolerance (context["tolerance"] default 0.0)
- Non-numeric fields compared for exact equality
- You can restrict comparison to specific output fields via context["fields"] = ["path.to.field", ...]
  where each path is dot-separated into nested dicts within run["output"].

Input: ScenarioReport-like dict with runs list.

Output schema: {"issues": [...], "summary": {...}}
"""

from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

from .registry import register_validator  # noqa: E402
from .types import Issue, ValidationOutput, normalize_output  # noqa: E402


def _get_nested(d: Dict[str, Any], path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _near_equal(a: Any, b: Any, tol: float) -> bool:
    try:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(float(a) - float(b)) <= tol
        return a == b
    except Exception:
        return False


def determinism_check_validate(
    report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx = context or {}
    tol: float = float(ctx.get("tolerance", 0.0))
    fields: Optional[List[str]] = ctx.get("fields")
    out = ValidationOutput()

    runs = report.get("runs") or []
    # group by (runner_key, seed)
    groups: Dict[Tuple[str, Any], List[Tuple[int, Dict[str, Any]]]] = {}
    for idx, run in enumerate(runs):
        if not isinstance(run, dict):
            continue
        key = (run.get("runner_key"), run.get("seed"))
        groups.setdefault(key, []).append((idx, run))  # type: ignore[arg-type]

    inconsistencies = 0
    checked_pairs = 0
    for key, items in groups.items():
        if key[1] is None:  # seed missing, warn
            for idx, _ in items:
                out.add_issue(
                    Issue(
                        id="missing_seed",
                        severity="warning",
                        message=f"Run[{idx}] missing seed for determinism check",
                        path=["runs", str(idx), "seed"],
                    )
                )
            continue
        if len(items) < 2:
            continue
        # build comparison baseline from first success run's output
        base_idx, base = items[0]
        base_out = base.get("output") if base.get("status") == "success" else None
        for idx, run in items[1:]:
            if run.get("status") != "success" or base_out is None:
                # Skip non-success comparisons but record info
                out.add_issue(
                    Issue(
                        id="non_success_skipped",
                        severity="info",
                        message=f"Run[{idx}] status={run.get('status')} skipped from determinism comparison",
                        path=["runs", str(idx), "status"],
                    )
                )
                continue
            cur_out = run.get("output")
            if not isinstance(cur_out, dict) or not isinstance(base_out, dict):
                continue
            checked_pairs += 1
            # Determine fields to check
            if fields:
                paths = fields
            else:
                # Compare all top-level keys present in both
                paths = sorted(set(base_out.keys()) & set(cur_out.keys()))
            local_mismatch = False
            for path in paths:
                if "." in path:
                    a = _get_nested(base_out, path)
                    b = _get_nested(cur_out, path)
                    comp_path = path.split(".")
                else:
                    a = base_out.get(path) if isinstance(path, str) else None
                    b = cur_out.get(path) if isinstance(path, str) else None
                    comp_path = [path] if isinstance(path, str) else []
                if not _near_equal(a, b, tol):
                    inconsistencies += 1
                    local_mismatch = True
                    out.add_issue(
                        Issue(
                            id="determinism_mismatch",
                            severity="error",
                            message=f"Inconsistent output for group runner={key[0]} seed={key[1]} at field '{path}': {a} != {b} (tol={tol})",
                            path=(
                                ["runs", str(idx), "output", *comp_path]
                                if comp_path
                                else ["runs", str(idx), "output"]
                            ),
                        )
                    )
            if not local_mismatch:
                # Record a positive info for visibility
                out.add_issue(
                    Issue(
                        id="determinism_ok",
                        severity="info",
                        message=f"Outputs match within tolerance for runner={key[0]} seed={key[1]}",
                        path=None,
                    )
                )

    out.summary.details.update(
        {
            "groups": len(groups),
            "checked_pairs": checked_pairs,
            "inconsistencies": inconsistencies,
            "tolerance": tol,
            "fields": fields or "all-common",
        }
    )
    return normalize_output(out)


register_validator("determinism_check", determinism_check_validate)
