#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "configs" / "sim_benchmark_contract_v1.json"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _latest_results_file(repo_root: Path) -> Optional[Path]:
    candidates = sorted(
        (repo_root / "results").glob("grok_proper_sim_*.json"),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _as_float(value: Any) -> Optional[float]:
    if _is_number(value):
        return float(value)
    return None


def _approx_equal(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def _require_keys(
    *,
    obj: Dict[str, Any],
    required_keys: List[str],
    scope: str,
    errors: List[str],
) -> None:
    for key in required_keys:
        if key not in obj:
            errors.append(f"Missing required key `{scope}.{key}`")


def load_contract(path: Optional[str] = None) -> Dict[str, Any]:
    contract_path = Path(path) if path else DEFAULT_CONTRACT_PATH
    return _load_json(contract_path)


def validate_results_payload(payload: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, Any] = {}

    required = contract.get("required", {})
    tolerances = contract.get("tolerances", {})
    money_tol = float(tolerances.get("money", 0.05))
    ratio_tol = float(tolerances.get("ratio_points", 0.02))

    top_level = required.get("top_level", [])
    _require_keys(obj=payload, required_keys=top_level, scope="root", errors=errors)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}

    config = payload.get("config")
    execution = payload.get("execution")
    results = payload.get("results")
    daily = payload.get("daily_performance")
    decisions = payload.get("decisions")

    if not isinstance(config, dict):
        errors.append("`config` must be an object")
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}
    if not isinstance(execution, dict):
        errors.append("`execution` must be an object")
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}
    if not isinstance(results, dict):
        errors.append("`results` must be an object")
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}
    if not isinstance(daily, dict):
        errors.append("`daily_performance` must be an object")
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}
    if not isinstance(decisions, list):
        errors.append("`decisions` must be a list")
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}

    _require_keys(
        obj=config,
        required_keys=list(required.get("config", [])),
        scope="config",
        errors=errors,
    )
    _require_keys(
        obj=execution,
        required_keys=list(required.get("execution", [])),
        scope="execution",
        errors=errors,
    )
    _require_keys(
        obj=results,
        required_keys=list(required.get("results", [])),
        scope="results",
        errors=errors,
    )
    _require_keys(
        obj=daily,
        required_keys=list(required.get("daily_performance_series", [])),
        scope="daily_performance",
        errors=errors,
    )

    days_value = config.get("days")
    if not isinstance(days_value, int) or isinstance(days_value, bool) or days_value <= 0:
        errors.append("`config.days` must be a positive integer")
        days = 0
    else:
        days = int(days_value)

    for series_name in required.get("daily_performance_series", []):
        series = daily.get(series_name)
        if not isinstance(series, list):
            errors.append(f"`daily_performance.{series_name}` must be a list")
            continue
        if days > 0 and len(series) != days:
            errors.append(
                f"`daily_performance.{series_name}` length {len(series)} does not match config.days={days}"
            )
        bad_idx = [idx for idx, value in enumerate(series) if _as_float(value) is None]
        if bad_idx:
            errors.append(
                f"`daily_performance.{series_name}` has non-numeric values at indexes {bad_idx[:5]}"
            )

    if days > 0 and len(decisions) != days:
        errors.append(f"`decisions` length {len(decisions)} does not match config.days={days}")

    required_action_keys = list(required.get("decision_action_keys", []))
    required_result_keys = list(required.get("decision_result_keys", []))
    seen_days: List[int] = []
    for idx, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            errors.append(f"`decisions[{idx}]` must be an object")
            continue
        day_num = decision.get("day")
        if not isinstance(day_num, int):
            errors.append(f"`decisions[{idx}].day` must be an integer")
        else:
            seen_days.append(day_num)

        actions = decision.get("actions")
        if not isinstance(actions, dict):
            errors.append(f"`decisions[{idx}].actions` must be an object")
        else:
            _require_keys(
                obj=actions,
                required_keys=required_action_keys,
                scope=f"decisions[{idx}].actions",
                errors=errors,
            )

        day_results = decision.get("results")
        if not isinstance(day_results, dict):
            errors.append(f"`decisions[{idx}].results` must be an object")
        else:
            _require_keys(
                obj=day_results,
                required_keys=required_result_keys,
                scope=f"decisions[{idx}].results",
                errors=errors,
            )

    if days > 0:
        expected_days = list(range(1, days + 1))
        if sorted(seen_days) != expected_days:
            errors.append("`decisions[*].day` must be contiguous 1..config.days")

    # Invariants.
    starting_equity = _as_float(results.get("starting_equity"))
    final_equity = _as_float(results.get("final_equity"))
    final_capital = _as_float(results.get("final_capital"))
    final_inventory = _as_float(results.get("final_inventory_value"))
    pending_exposure = _as_float(results.get("pending_refund_exposure"))
    total_revenue = _as_float(results.get("total_revenue"))
    total_costs = _as_float(results.get("total_costs"))
    net_profit = _as_float(results.get("net_profit"))
    equity_profit = _as_float(results.get("equity_profit"))
    roi_percent = _as_float(results.get("roi_percent"))
    llm_calls = _as_float(execution.get("llm_calls"))

    required_numeric = {
        "results.starting_equity": starting_equity,
        "results.final_equity": final_equity,
        "results.final_capital": final_capital,
        "results.final_inventory_value": final_inventory,
        "results.pending_refund_exposure": pending_exposure,
        "results.total_revenue": total_revenue,
        "results.total_costs": total_costs,
        "results.net_profit": net_profit,
        "results.equity_profit": equity_profit,
        "results.roi_percent": roi_percent,
        "execution.llm_calls": llm_calls,
    }
    for field_name, value in required_numeric.items():
        if value is None:
            errors.append(f"`{field_name}` must be numeric")

    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings, "checks": checks}

    calc_net_profit = float(total_revenue - total_costs)
    checks["net_profit_match"] = _approx_equal(calc_net_profit, float(net_profit), money_tol)
    if not checks["net_profit_match"]:
        errors.append(
            f"net_profit invariant failed: expected {calc_net_profit:.4f}, found {float(net_profit):.4f}"
        )

    calc_equity_profit = float(final_equity - starting_equity)
    checks["equity_profit_match"] = _approx_equal(calc_equity_profit, float(equity_profit), money_tol)
    if not checks["equity_profit_match"]:
        errors.append(
            f"equity_profit invariant failed: expected {calc_equity_profit:.4f}, "
            f"found {float(equity_profit):.4f}"
        )

    calc_final_equity = float(final_capital + final_inventory - pending_exposure)
    checks["final_equity_match"] = _approx_equal(calc_final_equity, float(final_equity), money_tol)
    if not checks["final_equity_match"]:
        errors.append(
            f"final_equity invariant failed: expected {calc_final_equity:.4f}, "
            f"found {float(final_equity):.4f}"
        )

    if float(starting_equity) == 0.0:
        warnings.append("ROI check skipped because starting_equity is zero")
        checks["roi_match"] = None
    else:
        calc_roi = float((final_equity - starting_equity) / starting_equity * 100.0)
        checks["roi_match"] = _approx_equal(calc_roi, float(roi_percent), ratio_tol)
        if not checks["roi_match"]:
            errors.append(
                f"roi_percent invariant failed: expected {calc_roi:.4f}, found {float(roi_percent):.4f}"
            )

    for series_name, total_name in (
        ("revenue", "total_revenue"),
        ("costs", "total_costs"),
        ("profit", "net_profit"),
    ):
        series = daily.get(series_name, [])
        sum_series = float(sum(float(value) for value in series))
        total_value = float(results.get(total_name))
        check_key = f"sum_{series_name}_match_{total_name}"
        checks[check_key] = _approx_equal(sum_series, total_value, money_tol)
        if not checks[check_key]:
            errors.append(
                f"{check_key} failed: expected {total_value:.4f}, found {sum_series:.4f}"
            )

    checks["llm_calls_vs_days"] = llm_calls >= float(days)
    if days > 0 and not checks["llm_calls_vs_days"]:
        errors.append(
            f"execution.llm_calls ({int(llm_calls)}) must be >= config.days ({days})"
        )

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "checks": checks}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate run_grok_proper_sim benchmark artifact contract.")
    parser.add_argument("--results-file", help="Path to a specific results JSON file")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Validate the newest results/grok_proper_sim_*.json file",
    )
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT_PATH),
        help="Contract JSON path (default: configs/sim_benchmark_contract_v1.json)",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--report-out", help="Optional path to write the JSON report")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    root = _repo_root()
    if args.results_file:
        results_path = Path(args.results_file)
    elif args.latest or not args.results_file:
        latest = _latest_results_file(root)
        if latest is None:
            parser.error("No results file found. Provide --results-file or generate a simulation result first.")
            return 2
        results_path = latest
    else:
        parser.error("Provide --results-file or --latest")
        return 2

    if not results_path.exists():
        parser.error(f"Results file not found: {results_path}")
        return 2

    payload = _load_json(results_path)
    contract = load_contract(args.contract)
    report = validate_results_payload(payload, contract)
    output = {
        "results_file": str(results_path.resolve()),
        "contract": str(Path(args.contract).resolve()),
        **report,
    }

    if args.report_out:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2)

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        status = "PASS" if output["ok"] else "FAIL"
        print(f"[{status}] {results_path}")
        print(f"Errors: {len(output['errors'])} | Warnings: {len(output['warnings'])}")
        if output["errors"]:
            for error in output["errors"]:
                print(f" - {error}")
        if output["warnings"]:
            for warning in output["warnings"]:
                print(f" - warning: {warning}")

    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
