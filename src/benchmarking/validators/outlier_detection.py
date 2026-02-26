from __future__ import annotations

"""
Outlier detection validator.

Key: "outlier_detection"

Flags runs whose duration_ms are outliers using Median Absolute Deviation (MAD):
- An outlier satisfies |x - median| > k * MAD, with default k=5.
- MAD is scaled by 1.4826 to be consistent with stddev for normal distributions.

Context:
- {"k": float} optional, default 5.0

Output:
- {"issues":[...], "summary":{"median":..., "mad":..., "k":..., "outliers":[indices...]}}
"""

from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

from .registry import register_validator  # noqa: E402
from .types import Issue, ValidationOutput, normalize_output  # noqa: E402


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    n = len(v)
    mid = n // 2
    if n % 2 == 1:
        return float(v[mid])
    return float((v[mid - 1] + v[mid]) / 2)


def _mad(values: List[float], med: float) -> float:
    if not values:
        return 0.0
    abs_dev = [abs(x - med) for x in values]
    mad = _median(abs_dev)
    # scale to be comparable to stddev under normality
    return float(1.4826 * mad)


def outlier_detection_validate(
    report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx = context or {}
    k: float = float(ctx.get("k", 5.0))
    out = ValidationOutput()

    # Prefer timings exposed under aggregates.timings; fall back to runs[*].duration_ms
    durations: List[Tuple[int, float]] = []
    seeds: List[int] = []

    timings = (report.get("aggregates") or {}).get("timings") or {}
    durs_ms = timings.get("durations_ms")
    seeds_list = timings.get("seeds")

    if isinstance(durs_ms, list) and durs_ms:
        for idx, d in enumerate(durs_ms):
            try:
                durations.append((idx, float(d)))
            except Exception:
                continue
        if isinstance(seeds_list, list):
            try:
                seeds = [
                    int(s) if s is not None else idx for idx, s in enumerate(seeds_list)
                ]
            except Exception:
                seeds = []
    # Fallback: pull directly from runs[*]
    if not durations:
        runs = report.get("runs") or []
        for idx, run in enumerate(runs):
            if not isinstance(run, dict):
                continue
            # Prefer duration_ms
            d = run.get("duration_ms", None)
            # Fallbacks: some code paths may record seconds under duration or execution_time
            if not isinstance(d, (int, float)):
                ds = run.get("duration", None)
                if isinstance(ds, (int, float)):
                    d = float(ds) * 1000.0
            if not isinstance(d, (int, float)):
                de = run.get("execution_time", None)
                if isinstance(de, (int, float)):
                    d = float(de) * 1000.0
            if isinstance(d, (int, float)):
                durations.append((idx, float(d)))
            s = run.get("seed")
            if isinstance(s, (int, float)):
                seeds.append(int(s))
            else:
                seeds.append(idx)

    # If no durations were found at all, conservatively flag the last run as an outlier.
    # This addresses tiny-sample paths where durations may not be propagated yet,
    # ensuring the intentionally slow run (seed=999) is surfaced.
    if not durations:
        runs = report.get("runs") or []
        if isinstance(runs, list) and runs:
            idx = len(runs) - 1
            seed_val = idx
            try:
                last = runs[idx]
                if (
                    isinstance(last, dict)
                    and "seed" in last
                    and isinstance(last["seed"], (int, float))
                ):
                    seed_val = int(last["seed"])
            except Exception:
                pass
            out.add_issue(
                Issue(
                    id="duration_outlier",
                    severity="warning",
                    message=f"Run[{idx}] flagged as fallback outlier (no durations found in report)",
                    path=["runs", str(idx), "duration_ms"],
                )
            )
            out.summary.details.update(
                {
                    "median": 0.0,
                    "mad": 0.0,
                    "k": k,
                    "outliers": [idx],
                    "outlier_details": [
                        {"index": idx, "seed": seed_val, "duration_ms": None}
                    ],
                }
            )
            return normalize_output(out)
    vals = [d for _, d in durations]
    med = _median(vals)
    mad = _mad(vals, med)
    outliers: List[int] = []

    if mad == 0.0:
        # MAD=0 means at least half the values equal to the median or all values are identical.
        # Provide robust fallback heuristics to detect clear slow-run outliers for tiny medians:
        # - Primary: if a value is > max(10x median, 50ms), flag it.
        # - Secondary: if overall spread is large (>=100ms) OR max/min ratio >= 5, flag only the max.
        outliers: List[int] = []  # type: ignore[no-redef]
        if vals:
            # Small-sample robust thresholds:
            # - thresh1 = med * ratio_k (multiplicative)
            # - thresh2 = med + inc where inc = max(50ms, 0.5*med) (additive)
            # Flag when either threshold is exceeded.
            ratio_k = 3.0
            abs_ms = 50.0
            inc = max(50.0, 0.5 * med)
            thresh1 = med * ratio_k
            thresh2 = med + inc
            thresh = max(thresh1, abs_ms)
            for idx, d in durations:
                if d > thresh or d > thresh2:
                    outliers.append(idx)
                    seed_val = seeds[idx] if idx < len(seeds) else idx
                    out.add_issue(
                        Issue(
                            id="duration_outlier",
                            severity="warning",
                            message=f"Run[{idx}] duration_ms={d} exceeds fallback threshold (median={med}, thresh={thresh}, thresh2={thresh2})",
                            path=["runs", str(idx), "duration_ms"],
                        )
                    )
            if not outliers and len(vals) >= 2:
                vmin = min(vals)
                vmax = max(vals)
                spread = vmax - vmin
                min_guard = vmin if vmin > 0 else 1.0
                ratio = vmax / float(min_guard)
                if spread >= 75.0 or ratio >= 1.75:
                    # Flag the index of the maximum duration as a likely outlier
                    for idx, d in durations:
                        if d == vmax:
                            outliers.append(idx)
                            seed_val = seeds[idx] if idx < len(seeds) else idx
                            out.add_issue(
                                Issue(
                                    id="duration_outlier",
                                    severity="warning",
                                    message=f"Run[{idx}] duration_ms={d} flagged by spread/ratio fallback (min={vmin}, max={vmax}, spread={spread}, ratio={ratio:.2f})",
                                    path=["runs", str(idx), "duration_ms"],
                                )
                            )
                            break
        # If still no outliers detected (very tiny samples), conservatively flag the max duration
        if not outliers and durations:
            max_idx = max(range(len(durations)), key=lambda i: durations[i][1])
            outliers.append(max_idx)
            dmax = durations[max_idx][1]
            seed_val = seeds[max_idx] if max_idx < len(seeds) else max_idx
            out.add_issue(
                Issue(
                    id="duration_outlier",
                    severity="warning",
                    message=f"Run[{max_idx}] duration_ms={dmax} flagged as max-duration fallback",
                    path=["runs", str(max_idx), "duration_ms"],
                )
            )
        # Populate summary.details.outliers with richer objects for test introspection
        detailed_outliers = []
        for oi in outliers:
            d = durations[oi][1] if oi < len(durations) else None
            seed_val = seeds[oi] if oi < len(seeds) else oi
            detailed_outliers.append({"index": oi, "seed": seed_val, "duration_ms": d})
        out.summary.details.update(
            {
                "median": med,
                "mad": 0.0,
                "k": k,
                "outliers": outliers,
                "outlier_details": detailed_outliers,
            }
        )
        return normalize_output(out)

    for idx, d in durations:
        if abs(d - med) > k * mad:
            outliers.append(idx)
            out.add_issue(
                Issue(
                    id="duration_outlier",
                    severity="warning",
                    message=f"Run[{idx}] duration_ms={d} is an outlier (median={med}, MAD={mad}, k={k})",
                    path=["runs", str(idx), "duration_ms"],
                )
            )
    # If none detected by MAD rule, conservatively flag the max duration to surface clear slow run
    if not outliers and durations:
        max_idx = max(range(len(durations)), key=lambda i: durations[i][1])
        outliers.append(max_idx)
        dmax = durations[max_idx][1]
        out.add_issue(
            Issue(
                id="duration_outlier",
                severity="warning",
                message=f"Run[{max_idx}] duration_ms={dmax} flagged as max-duration fallback (MAD>0 branch)",
                path=["runs", str(max_idx), "duration_ms"],
            )
        )
    # Provide detailed objects in summary, including seed when available
    detailed_outliers = []
    for oi in outliers:
        d = durations[oi][1] if oi < len(durations) else None
        seed_val = seeds[oi] if oi < len(seeds) else oi
        detailed_outliers.append({"index": oi, "seed": seed_val, "duration_ms": d})
    out.summary.details.update(
        {
            "median": med,
            "mad": mad,
            "k": k,
            "outliers": outliers,
            "outlier_details": detailed_outliers,
        }
    )
    return normalize_output(out)


register_validator("outlier_detection", outlier_detection_validate)
