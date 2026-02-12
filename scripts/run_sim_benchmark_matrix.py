#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from scripts.verify_sim_benchmark_contract import load_contract, validate_results_payload
except ModuleNotFoundError:
    from verify_sim_benchmark_contract import load_contract, validate_results_payload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_seeds(raw: str) -> List[int]:
    values: List[int] = []
    for token in raw.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        values.append(int(stripped))
    if not values:
        raise ValueError("At least one seed is required")
    return values


def parse_profile_specs(profile_specs: List[str], repo_root: Path) -> Dict[str, Optional[Path]]:
    """
    Parse --profile values in `name=path` format.
    If not provided, default to baseline + stress profile.
    """
    if not profile_specs:
        baseline = repo_root / "configs" / "sim_realism.yaml"
        stress = repo_root / "configs" / "sim_realism_stress_returns.yaml"
        defaults: Dict[str, Optional[Path]] = {"baseline": baseline if baseline.exists() else None}
        if stress.exists():
            defaults["stress_returns"] = stress
        return defaults

    parsed: Dict[str, Optional[Path]] = {}
    for spec in profile_specs:
        if "=" not in spec:
            raise ValueError(f"Invalid --profile `{spec}`. Expected `name=path`.")
        name, path_value = spec.split("=", 1)
        profile_name = name.strip()
        profile_path = path_value.strip()
        if not profile_name:
            raise ValueError(f"Invalid --profile `{spec}`: missing profile name")
        if not profile_path:
            parsed[profile_name] = None
            continue
        resolved = Path(profile_path)
        if not resolved.is_absolute():
            resolved = repo_root / resolved
        if not resolved.exists():
            raise FileNotFoundError(f"Profile config not found: {resolved}")
        parsed[profile_name] = resolved
    return parsed


def summarize_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_profile: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        profile = str(record.get("profile", "unknown"))
        by_profile.setdefault(profile, []).append(record)

    profile_summary: Dict[str, Any] = {}
    metrics = [
        "roi_percent",
        "equity_profit",
        "net_profit",
        "orders_fulfilled",
        "stockouts",
        "pending_refund_exposure",
    ]

    for profile, items in by_profile.items():
        ok_items = [item for item in items if item.get("status") == "ok"]
        stats: Dict[str, Any] = {
            "runs_total": len(items),
            "runs_ok": len(ok_items),
            "runs_failed": len(items) - len(ok_items),
        }
        for metric in metrics:
            values = [
                float(item.get(metric))
                for item in ok_items
                if isinstance(item.get(metric), (int, float))
            ]
            if not values:
                stats[metric] = {"count": 0}
                continue
            stats[metric] = {
                "count": len(values),
                "mean": round(statistics.fmean(values), 4),
                "stddev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
                "min": round(min(values), 4),
                "max": round(max(values), 4),
            }
        profile_summary[profile] = stats

    return {
        "profiles": profile_summary,
        "runs_total": len(records),
        "runs_ok": sum(1 for r in records if r.get("status") == "ok"),
        "runs_failed": sum(1 for r in records if r.get("status") != "ok"),
    }


def _extract_results_path(stdout_text: str) -> Optional[Path]:
    match = re.search(r"Saved to:\s*(.+)", stdout_text)
    if not match:
        return None
    raw_path = match.group(1).strip()
    return Path(raw_path)

def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _approx_equal(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def compare_live_and_replay(
    *,
    live_payload: Dict[str, Any],
    replay_payload: Dict[str, Any],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Determinism check: compare environment outputs across live vs replay.
    Ignores execution counters and free-text fields.
    """
    tolerances = contract.get("tolerances", {})
    money_tol = float(tolerances.get("money", 0.05))
    ratio_tol = float(tolerances.get("ratio_points", 0.02))
    required = contract.get("required", {})

    mismatches: List[Dict[str, Any]] = []

    live_results = live_payload.get("results", {})
    replay_results = replay_payload.get("results", {})
    if not isinstance(live_results, dict) or not isinstance(replay_results, dict):
        return {"ok": False, "mismatches": [{"key": "results", "type": "missing_object"}]}

    for key in required.get("results", []):
        if key not in live_results or key not in replay_results:
            mismatches.append(
                {
                    "key": f"results.{key}",
                    "type": "missing_key",
                    "a": key in live_results,
                    "b": key in replay_results,
                }
            )
            continue
        a = live_results.get(key)
        b = replay_results.get(key)
        if _is_number(a) and _is_number(b):
            tol = ratio_tol if key == "roi_percent" else money_tol
            if isinstance(a, int) and isinstance(b, int):
                if a != b:
                    mismatches.append({"key": f"results.{key}", "a": a, "b": b, "type": "int"})
            else:
                aa = float(a)
                bb = float(b)
                if not _approx_equal(aa, bb, tol):
                    mismatches.append(
                        {"key": f"results.{key}", "a": aa, "b": bb, "tol": tol, "type": "float"}
                    )
        else:
            if a != b:
                mismatches.append({"key": f"results.{key}", "a": a, "b": b, "type": "value"})

    live_daily = live_payload.get("daily_performance", {})
    replay_daily = replay_payload.get("daily_performance", {})
    if not isinstance(live_daily, dict) or not isinstance(replay_daily, dict):
        mismatches.append({"key": "daily_performance", "type": "missing_object"})
    else:
        for series_name in required.get("daily_performance_series", []):
            la = live_daily.get(series_name)
            rb = replay_daily.get(series_name)
            if not isinstance(la, list) or not isinstance(rb, list):
                mismatches.append({"key": f"daily_performance.{series_name}", "type": "missing_series"})
                continue
            if len(la) != len(rb):
                mismatches.append(
                    {
                        "key": f"daily_performance.{series_name}.len",
                        "a": len(la),
                        "b": len(rb),
                        "type": "len",
                    }
                )
                continue
            for idx, (a, b) in enumerate(zip(la, rb)):
                if _is_number(a) and _is_number(b):
                    tol = ratio_tol if series_name == "roi_percent" else money_tol
                    if not _approx_equal(float(a), float(b), tol):
                        mismatches.append(
                            {
                                "key": f"daily_performance.{series_name}[{idx}]",
                                "a": float(a),
                                "b": float(b),
                                "tol": tol,
                                "type": "float",
                            }
                        )
                else:
                    if a != b:
                        mismatches.append(
                            {
                                "key": f"daily_performance.{series_name}[{idx}]",
                                "a": a,
                                "b": b,
                                "type": "value",
                            }
                        )

    live_decisions = live_payload.get("decisions", [])
    replay_decisions = replay_payload.get("decisions", [])
    if not isinstance(live_decisions, list) or not isinstance(replay_decisions, list):
        mismatches.append({"key": "decisions", "type": "missing_list"})
    else:
        if len(live_decisions) != len(replay_decisions):
            mismatches.append({"key": "decisions.len", "a": len(live_decisions), "b": len(replay_decisions)})
        else:
            day_keys = required.get("decision_result_keys", [])
            for idx, (ld, rd) in enumerate(zip(live_decisions, replay_decisions)):
                if not isinstance(ld, dict) or not isinstance(rd, dict):
                    mismatches.append({"key": f"decisions[{idx}]", "type": "non_object"})
                    continue
                if ld.get("decisions_raw") != rd.get("decisions_raw"):
                    mismatches.append({"key": f"decisions[{idx}].decisions_raw", "type": "value"})

                lr = ld.get("results", {})
                rr = rd.get("results", {})
                if not isinstance(lr, dict) or not isinstance(rr, dict):
                    mismatches.append({"key": f"decisions[{idx}].results", "type": "missing_object"})
                    continue
                for key in day_keys:
                    if key not in lr or key not in rr:
                        mismatches.append({"key": f"decisions[{idx}].results.{key}", "type": "missing_key"})
                        continue
                    a = lr.get(key)
                    b = rr.get(key)
                    if _is_number(a) and _is_number(b):
                        if isinstance(a, int) and isinstance(b, int):
                            if a != b:
                                mismatches.append(
                                    {"key": f"decisions[{idx}].results.{key}", "a": a, "b": b, "type": "int"}
                                )
                        else:
                            tol = ratio_tol if key == "roi_percent" else money_tol
                            if not _approx_equal(float(a), float(b), tol):
                                mismatches.append(
                                    {
                                        "key": f"decisions[{idx}].results.{key}",
                                        "a": float(a),
                                        "b": float(b),
                                        "tol": tol,
                                        "type": "float",
                                    }
                                )
                    else:
                        if a != b:
                            mismatches.append(
                                {"key": f"decisions[{idx}].results.{key}", "a": a, "b": b, "type": "value"}
                            )

    return {"ok": len(mismatches) == 0, "mismatches": mismatches}


def _run_single(
    *,
    repo_root: Path,
    days: int,
    seed: int,
    profile_name: str,
    profile_path: Optional[Path],
    memory_mode: str,
    memory_review_mode: str,
) -> Tuple[int, str, str]:
    command = [
        sys.executable,
        str(repo_root / "run_grok_proper_sim.py"),
        "--days",
        str(days),
        "--seed",
        str(seed),
        "--quiet",
        "--no-live-trace",
        "--memory-mode",
        memory_mode,
        "--memory-review-mode",
        memory_review_mode,
    ]
    if profile_path is not None:
        command.extend(["--realism-config", str(profile_path)])

    print(f"Running profile={profile_name} seed={seed}")
    print("  " + " ".join(command))
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _run_replay(
    *,
    repo_root: Path,
    seed: int,
    profile_path: Optional[Path],
    source_results_file: Path,
) -> Tuple[int, str, str]:
    command = [
        sys.executable,
        str(repo_root / "run_grok_proper_sim.py"),
        "--replay-results-file",
        str(source_results_file),
        "--seed",
        str(seed),
        "--quiet",
        "--no-live-trace",
    ]
    if profile_path is not None:
        command.extend(["--realism-config", str(profile_path)])

    print(f"Replaying profile seed={seed} source={source_results_file.name}")
    print("  " + " ".join(command))
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a reproducible simulation benchmark matrix.")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        help="Profile spec as name=path_to_realism_yaml (repeatable)",
    )
    parser.add_argument("--memory-mode", choices=["stateless", "reflective"], default="stateless")
    parser.add_argument(
        "--memory-review-mode",
        choices=["heuristic", "llm"],
        default="heuristic",
    )
    parser.add_argument(
        "--contract",
        default=str(_repo_root() / "configs" / "sim_benchmark_contract_v1.json"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(_repo_root() / "results" / "sim_benchmark_matrix"),
    )
    parser.add_argument("--print-only", action="store_true", help="Print planned runs only")
    parser.add_argument(
        "--strict-contract",
        action="store_true",
        help="Mark run as failed when contract validation fails",
    )
    parser.add_argument(
        "--no-verify-replay",
        action="store_true",
        help="Disable live->replay->diff determinism verification (enabled by default).",
    )
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()
    repo_root = _repo_root()
    seeds = _parse_seeds(args.seeds)
    profiles = parse_profile_specs(args.profile, repo_root)
    contract = load_contract(args.contract)
    verify_replay = not bool(args.no_verify_replay)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = Path(args.output_dir)
    run_dir = out_root / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = run_dir / "contract_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    plan = []
    for profile_name, profile_path in profiles.items():
        for seed in seeds:
            plan.append(
                {
                    "profile": profile_name,
                    "profile_path": str(profile_path) if profile_path is not None else None,
                    "seed": seed,
                    "days": args.days,
                }
            )

    if args.print_only:
        print(json.dumps({"generated_at_utc": _utc_now_iso(), "plan": plan}, indent=2))
        return 0

    records: List[Dict[str, Any]] = []
    for profile_name, profile_path in profiles.items():
        for seed in seeds:
            record: Dict[str, Any] = {
                "profile": profile_name,
                "profile_path": str(profile_path) if profile_path is not None else None,
                "seed": seed,
                "days": args.days,
                "status": "failed",
            }
            rc, stdout_text, stderr_text = _run_single(
                repo_root=repo_root,
                days=args.days,
                seed=seed,
                profile_name=profile_name,
                profile_path=profile_path,
                memory_mode=args.memory_mode,
                memory_review_mode=args.memory_review_mode,
            )
            record["return_code"] = rc

            log_base = f"{profile_name}_seed_{seed}"
            (run_dir / f"{log_base}.stdout.log").write_text(stdout_text, encoding="utf-8")
            (run_dir / f"{log_base}.stderr.log").write_text(stderr_text, encoding="utf-8")

            if rc != 0:
                record["error"] = "simulation_run_failed"
                records.append(record)
                continue

            results_path = _extract_results_path(stdout_text)
            if results_path is None:
                record["error"] = "could_not_parse_results_path"
                records.append(record)
                continue
            if not results_path.is_absolute():
                results_path = (repo_root / results_path).resolve()
            record["results_file"] = str(results_path)
            if not results_path.exists():
                record["error"] = "results_file_missing"
                records.append(record)
                continue

            with open(results_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            validation = validate_results_payload(payload, contract)
            report_path = reports_dir / f"{profile_name}_seed_{seed}.json"
            with open(report_path, "w", encoding="utf-8") as handle:
                json.dump(validation, handle, indent=2)
            record["contract_report"] = str(report_path)
            record["contract_ok"] = bool(validation.get("ok"))
            record["contract_error_count"] = len(validation.get("errors", []))

            run_results = payload.get("results", {})
            if isinstance(run_results, dict):
                for key in (
                    "roi_percent",
                    "equity_profit",
                    "net_profit",
                    "orders_fulfilled",
                    "stockouts",
                    "pending_refund_exposure",
                ):
                    if key in run_results:
                        record[key] = run_results.get(key)

            if verify_replay:
                rep_rc, rep_stdout_text, rep_stderr_text = _run_replay(
                    repo_root=repo_root,
                    seed=seed,
                    profile_path=profile_path,
                    source_results_file=results_path,
                )
                record["replay_return_code"] = rep_rc
                rep_log_base = f"{profile_name}_seed_{seed}.replay"
                (run_dir / f"{rep_log_base}.stdout.log").write_text(
                    rep_stdout_text, encoding="utf-8"
                )
                (run_dir / f"{rep_log_base}.stderr.log").write_text(
                    rep_stderr_text, encoding="utf-8"
                )
                if rep_rc != 0:
                    record["replay_ok"] = False
                    record["status"] = "failed"
                    record["error"] = "replay_run_failed"
                    records.append(record)
                    continue

                rep_results_path = _extract_results_path(rep_stdout_text)
                if rep_results_path is None:
                    record["replay_ok"] = False
                    record["status"] = "failed"
                    record["error"] = "replay_results_path_missing"
                    records.append(record)
                    continue
                if not rep_results_path.is_absolute():
                    rep_results_path = (repo_root / rep_results_path).resolve()
                record["replay_results_file"] = str(rep_results_path)
                if not rep_results_path.exists():
                    record["replay_ok"] = False
                    record["status"] = "failed"
                    record["error"] = "replay_results_file_missing"
                    records.append(record)
                    continue

                with open(rep_results_path, "r", encoding="utf-8") as handle:
                    rep_payload = json.load(handle)

                replay_diff = compare_live_and_replay(
                    live_payload=payload,
                    replay_payload=rep_payload,
                    contract=contract,
                )
                record["replay_ok"] = bool(replay_diff.get("ok"))
                record["replay_mismatch_count"] = len(replay_diff.get("mismatches", []))
                record["replay_mismatches_sample"] = replay_diff.get("mismatches", [])[:5]
                if not record["replay_ok"]:
                    record["status"] = "failed"
                    record["error"] = "replay_diff_failed"
                    records.append(record)
                    continue

            if args.strict_contract and not validation.get("ok", False):
                record["status"] = "failed"
                record["error"] = "contract_validation_failed"
            else:
                record["status"] = "ok"

            records.append(record)

    summary = summarize_records(records)
    output_payload = {
        "generated_at_utc": _utc_now_iso(),
        "config": {
            "days": args.days,
            "seeds": seeds,
            "profiles": {name: str(path) if path is not None else None for name, path in profiles.items()},
            "memory_mode": args.memory_mode,
            "memory_review_mode": args.memory_review_mode,
            "contract": str(Path(args.contract).resolve()),
            "strict_contract": bool(args.strict_contract),
            "verify_replay": bool(verify_replay),
        },
        "summary": summary,
        "records": records,
    }

    summary_path = run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(output_payload, handle, indent=2)
    print(f"Matrix summary written: {summary_path}")

    return 0 if summary["runs_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
