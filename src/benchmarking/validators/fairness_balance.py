from __future__ import annotations

"""
Fairness/balance validator.

Key: "fairness_balance"

Checks that a metric does not differ across groups beyond a threshold.

Context:
- {
    "group": "runner_key" | "seed" | "output.details.group" | ... (dot path supported; default "runner_key"),
    "metric_path": "metrics.accuracy" | "output.score" | ... (dot path to numeric; required),
    "threshold": float (absolute difference threshold across group means; default 0.1),
    "min_group_size": int (optional, default 1; groups with size < this are ignored)
  }

Behavior:
- Computes per-group mean of the metric for runs with status == "success" and available numeric metric.
- If max(mean) - min(mean) > threshold => error issue with groups and values.
- Otherwise emits info-level summary.

Deterministic and non-fatal.
"""

from typing import Any, Dict, List, Optional  # noqa: E402

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


def fairness_balance_validate(
    report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx = context or {}
    group_path: str = str(ctx.get("group", "runner_key"))
    metric_path: Optional[str] = ctx.get("metric_path")
    threshold: float = float(ctx.get("threshold", 0.1))
    min_group_size: int = int(ctx.get("min_group_size", 1))

    out = ValidationOutput()

    if not metric_path:
        out.add_issue(
            Issue(
                id="missing_metric_path",
                severity="error",
                message="fairness_balance requires context['metric_path'] to be set",
                path=None,
            )
        )
        return normalize_output(out)

    runs = report.get("runs") or []
    groups: Dict[str, List[float]] = {}

    for idx, run in enumerate(runs):
        if not isinstance(run, dict) or run.get("status") != "success":
            continue
        grp_val = (
            run.get(group_path)
            if "." not in group_path
            else _get_nested(run, group_path)
        )
        if grp_val is None:
            grp_val = "unknown"
        met_val = (
            _get_nested(run, metric_path)
            if "." in metric_path
            else run.get(metric_path)
        )
        if isinstance(met_val, (int, float)):
            groups.setdefault(str(grp_val), []).append(float(met_val))
        else:
            # Non-numeric metric is ignored but reported
            out.add_issue(
                Issue(
                    id="non_numeric_metric",
                    severity="info",
                    message=f"Run[{idx}] metric at '{metric_path}' is non-numeric or missing; skipped",
                    path=["runs", str(idx), *metric_path.split(".")],
                )
            )

    # Filter by min group size
    filtered = {g: vals for g, vals in groups.items() if len(vals) >= min_group_size}

    if not filtered:
        out.add_issue(
            Issue(
                id="no_groups_evaluable",
                severity="info",
                message="No groups with sufficient data to evaluate fairness balance",
                path=None,
            )
        )
        out.summary.details.update(
            {
                "groups": {},
                "threshold": threshold,
                "group_path": group_path,
                "metric_path": metric_path,
            }
        )
        return normalize_output(out)

    means: Dict[str, float] = {
        g: (sum(vals) / len(vals)) for g, vals in filtered.items()
    }
    if means:
        max_mean = max(means.values())
        min_mean = min(means.values())
        diff = max_mean - min_mean
    else:
        max_mean = min_mean = diff = 0.0

    if diff > threshold:
        out.add_issue(
            Issue(
                id="fairness_imbalance",
                severity="error",
                message=f"Group mean difference {diff:.6f} exceeds threshold {threshold:.6f}",
                path=None,
            )
        )
    else:
        out.add_issue(
            Issue(
                id="fairness_within_threshold",
                severity="info",
                message=f"Group mean difference {diff:.6f} within threshold {threshold:.6f}",
                path=None,
            )
        )

    out.summary.details.update(
        {
            "group_path": group_path,
            "metric_path": metric_path,
            "threshold": threshold,
            "group_sizes": {g: len(v) for g, v in filtered.items()},
            "group_means": means,
            "difference": diff if means else 0.0,
        }
    )
    return normalize_output(out)


register_validator("fairness_balance", fairness_balance_validate)
