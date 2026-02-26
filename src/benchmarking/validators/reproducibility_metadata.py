from __future__ import annotations

"""
Reproducibility metadata validator.

Key: "reproducibility_metadata"

Checks presence/consistency of seeds and config digests across runs.
- Warns when seeds are missing.
- If context provides expected_seeds (list[int]) for the scenario, verifies observed seeds ⊆ expected_seeds.
- If context provides config_digest (from EngineReport), adds info if present in context and warns if per-run/config
  metadata is missing or inconsistent (best-effort check; RunResult schema doesn't include digest by default).

Deterministic; never raises.

Context:
- {
    "scenario_key": str,
    "expected_seeds": list[int] | None,
    "config_digest": str | None
  }

Output schema: {"issues": [...], "summary": {...}}
"""

from typing import Any, Dict, List, Optional, Set  # noqa: E402

from .registry import register_validator  # noqa: E402
from .types import Issue, ValidationOutput, normalize_output  # noqa: E402


def reproducibility_metadata_validate(
    report: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    ctx = context or {}
    expected_seeds: Optional[List[int]] = ctx.get("expected_seeds")
    cfg_digest: Optional[str] = ctx.get("config_digest")

    out = ValidationOutput()

    runs = report.get("runs") or []
    seen_seeds: Set[int] = set()
    missing_seed_count = 0

    for idx, run in enumerate(runs):
        if not isinstance(run, dict):
            continue
        seed = run.get("seed")
        if seed is None:
            missing_seed_count += 1
            out.add_issue(
                Issue(
                    id="missing_seed",
                    severity="warning",
                    message=f"Run[{idx}] missing 'seed' metadata; reproducibility reduced",
                    path=["runs", str(idx), "seed"],
                )
            )
        elif isinstance(seed, int):
            seen_seeds.add(seed)
        else:
            out.add_issue(
                Issue(
                    id="invalid_seed_type",
                    severity="error",
                    message=f"Run[{idx}].seed expected int or None, got {type(seed).__name__}",
                    path=["runs", str(idx), "seed"],
                )
            )

        # Best-effort digest: RunResult does not define config digest; if present, check matches context
        run_digest = run.get("config_digest")
        if cfg_digest:
            if run_digest is None:
                # Only warn once globally in summary; avoid per-run spam
                pass
            elif run_digest != cfg_digest:
                out.add_issue(
                    Issue(
                        id="config_digest_mismatch",
                        severity="error",
                        message=f"Run[{idx}] config_digest mismatch with EngineReport digest",
                        path=["runs", str(idx), "config_digest"],
                    )
                )

    # Expected seeds consistency, if provided
    if expected_seeds is not None:
        exp_set = set(int(s) for s in expected_seeds)
        unexpected = sorted(list(seen_seeds - exp_set))
        if unexpected:
            out.add_issue(
                Issue(
                    id="unexpected_seed",
                    severity="error",
                    message=f"Observed seeds not in EngineConfig: {unexpected}",
                    path=["runs"],
                )
            )
        missing_expected = sorted(list(exp_set - seen_seeds))
        if missing_expected:
            out.add_issue(
                Issue(
                    id="missing_expected_seed",
                    severity="warning",
                    message=f"Some expected seeds not observed in runs: {missing_expected}",
                    path=["runs"],
                )
            )

    # Summarize
    out.summary.details.update(
        {
            "observed_seeds": sorted(list(seen_seeds)),
            "missing_seed_count": int(missing_seed_count),
            "expected_seeds": expected_seeds if expected_seeds is not None else None,
            "engine_config_digest": cfg_digest if cfg_digest else None,
        }
    )

    # If engine digest is provided but not present per-run, add an info-level note
    if cfg_digest:
        any_run_digest = any(
            isinstance(r, dict) and r.get("config_digest") for r in runs
        )
        if not any_run_digest:
            out.add_issue(
                Issue(
                    id="per_run_digest_missing",
                    severity="info",
                    message="Engine config_digest provided in context; per-run digest metadata not present (informational)",
                    path=None,
                )
            )

    return normalize_output(out)


register_validator("reproducibility_metadata", reproducibility_metadata_validate)
