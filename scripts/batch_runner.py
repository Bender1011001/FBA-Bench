#!/usr/bin/env python3
"""
Parallel Tier-2 benchmark runner (OpenRouter prompts) for multiple models.

This script is intentionally "dumb but reliable":
- It runs run_openrouter_benchmark.py in subprocesses (one per model)
- Limits concurrency with --workers
- Writes per-model logs under artifacts/year_runs/<run_id>/
- Writes normalized per-model JSON under results/openrouter_tier_runs/<tier>/ for live publishing
- Maintains a heartbeat file (docs/api/live.json) so the website can show a LIVE badge

Example:
  poetry run python scripts/batch_runner.py --models "openai/gpt-5.2,deepseek/deepseek-r1" --tier T2 --workers 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_model_slug(model_slug: str) -> str:
    # File-friendly.
    return model_slug.replace("/", "_").replace(":", "_").replace("@", "_")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parallel OpenRouter tier runner for multiple models.")
    p.add_argument("--tier", default=None, choices=["T0", "T1", "T2"], help="Tier label to stamp into output records.")
    p.add_argument(
        "--models",
        default=None,
        help="Comma-separated model slugs (OpenRouter style). If omitted, uses simulation_settings.yaml benchmark.models.",
    )
    p.add_argument(
        "--engine",
        choices=["agentic_sim", "openrouter_prompts"],
        default="agentic_sim",
        help="Benchmark engine. agentic_sim waits for one LLM decision per day (slow). openrouter_prompts is quick prompt scoring.",
    )
    p.add_argument("--workers", type=int, default=None, help="Max concurrent runs.")
    p.add_argument(
        "--scenario",
        default=None,
        help="Scenario YAML to convert into prompts for Tier-2 style evaluation (default from simulation_settings.yaml benchmark.scenarios).",
    )
    p.add_argument("--days", type=int, default=None, help="Simulated days for agentic_sim (default benchmark.duration_days).")
    p.add_argument("--seed", type=int, default=None, help="RNG seed for agentic_sim (default simulation.seed).")
    p.add_argument(
        "--max-wait-seconds",
        type=float,
        default=0.0,
        help="Optional per-day cap for a single model response in agentic_sim. 0 disables this cap.",
    )
    p.add_argument("--run-id", default=None, help="Run id; defaults to run-YYYYMMDD-HHMMSS.")
    p.add_argument("--settings", default="simulation_settings.yaml", help="YAML settings file (for benchmark defaults).")
    p.add_argument(
        "--results-root",
        default="results/openrouter_tier_runs",
        help="Root directory for tier JSON output (consumed by the live site builder).",
    )
    p.add_argument(
        "--live-json",
        default="docs/api/live.json",
        help="Heartbeat/status JSON used by the live website.",
    )
    p.add_argument("--heartbeat-seconds", type=float, default=5.0, help="Heartbeat write frequency.")
    p.add_argument("--fail-fast", action="store_true", help="Stop launching new work after first failure.")
    return p.parse_args(argv)


def load_benchmark_defaults(settings_path: str) -> Dict[str, Any]:
    path = Path(settings_path)
    if not path.exists():
        return {}

    try:
        import yaml  # type: ignore
    except Exception:
        return {}

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

    bench = data.get("benchmark") or {}
    if not isinstance(bench, dict):
        return {}
    return bench


def resolve_scenario_path(scenario_arg: Optional[str], bench_defaults: Dict[str, Any]) -> str:
    """
    Resolve a scenario reference to an on-disk YAML path.

    Accepts:
    - explicit file paths (relative or absolute)
    - known slugs like "tier2_advanced"
    - bare filenames
    """
    ref = scenario_arg
    if not ref:
        scenarios = bench_defaults.get("scenarios") or []
        if isinstance(scenarios, list) and scenarios:
            ref = str(scenarios[0])
    if not ref:
        ref = "tier2_advanced"

    # Normalize known slugs to canonical file.
    slug = ref.strip().lower().replace("-", "_")
    if slug in {"tier2_advanced", "tier_2_advanced"}:
        ref = "src/scenarios/tier_2_advanced.yaml"

    candidates: List[str] = []
    candidates.append(ref)
    candidates.append(os.path.join(os.getcwd(), ref))

    if ref.endswith(".yaml") or ref.endswith(".yml"):
        candidates.append(os.path.join(os.getcwd(), "src", "scenarios", os.path.basename(ref)))
        candidates.append(os.path.join(os.getcwd(), "configs", os.path.basename(ref)))
    else:
        # Try as a bare scenario name.
        candidates.append(os.path.join(os.getcwd(), "src", "scenarios", f"{ref}.yaml"))
        candidates.append(os.path.join(os.getcwd(), "src", "scenarios", f"{ref}.yml"))

    for c in candidates:
        if c and os.path.exists(c):
            return c

    # Fall back to the original ref; run_openrouter_benchmark.py will warn and proceed.
    return ref


def resolve_models(models_arg: Optional[str], bench_defaults: Dict[str, Any]) -> List[str]:
    # CLI wins.
    if models_arg:
        raw = [m.strip() for m in models_arg.split(",") if m.strip()]
    else:
        raw_models = bench_defaults.get("models") or []
        raw = []
        if isinstance(raw_models, list):
            for m in raw_models:
                if isinstance(m, dict) and m.get("model_slug"):
                    raw.append(str(m["model_slug"]))
                elif isinstance(m, str):
                    raw.append(m)

    # Allow shorthand names like "gpt-5.2" by resolving suffix matches from benchmark list.
    known: List[str] = []
    bench_models = bench_defaults.get("models") or []
    if isinstance(bench_models, list):
        for m in bench_models:
            if isinstance(m, dict) and m.get("model_slug"):
                known.append(str(m["model_slug"]))

    resolved: List[str] = []
    for item in raw:
        if "/" in item:
            resolved.append(item)
            continue
        matches = [slug for slug in known if slug.endswith("/" + item) or slug.endswith(item)]
        if len(matches) == 1:
            resolved.append(matches[0])
        else:
            # Fall back to the given value (could be an OpenRouter alias).
            resolved.append(item)
    return resolved


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def load_settings(settings_path: str) -> Dict[str, Any]:
    if yaml is None:
        return {}
    path = Path(settings_path)
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _load_openrouter_key_from_dotenv(dotenv_path: str = ".env") -> Optional[str]:
    """
    Minimal .env loader for OPENROUTER_API_KEY only (avoids adding a runtime dependency).
    """
    try:
        text = Path(dotenv_path).read_text(encoding="utf-8")
    except Exception:
        return None

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip() == "OPENROUTER_API_KEY":
            val = v.strip().strip('"').strip("'")
            return val or None
    return None


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def summarize_openrouter_run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract stable summary metrics from a run_openrouter_benchmark.py output payload.
    """
    model_results = raw.get("model_results") or []
    if not model_results or not isinstance(model_results, list):
        return {
            "success_rate": 0.0,
            "avg_response_time": 0.0,
            "total_tokens": 0,
            "avg_quality_score": 0.0,
            "errors": ["missing model_results"],
        }

    model_entry = model_results[0] if isinstance(model_results[0], dict) else {}
    prompts = model_entry.get("prompts") or []
    prompt_quality = []
    for p in prompts:
        if isinstance(p, dict):
            try:
                prompt_quality.append(float(p.get("quality_score") or 0.0))
            except Exception:
                prompt_quality.append(0.0)

    summary = model_entry.get("summary") or {}
    try:
        success_rate = float(summary.get("success_rate") or 0.0)
    except Exception:
        success_rate = 0.0
    try:
        avg_rt = float(summary.get("average_response_time") or 0.0)
    except Exception:
        avg_rt = 0.0
    try:
        total_tokens = int(summary.get("total_tokens") or 0)
    except Exception:
        total_tokens = 0

    errors = summary.get("errors") or []
    if not isinstance(errors, list):
        errors = [str(errors)]

    return {
        "success_rate": success_rate,
        "avg_response_time": avg_rt,
        "total_tokens": total_tokens,
        "avg_quality_score": _mean(prompt_quality),
        "errors": errors,
    }


def summarize_agentic_run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract stable summary metrics from scripts/run_t2_agentic_sim.py output.
    """
    summary = raw.get("summary") or {}
    if not isinstance(summary, dict):
        summary = {}
    total_profit = _safe_float(summary.get("total_profit"), 0.0)
    tokens = _safe_int(summary.get("tokens_used"), 0)
    roi_pct = _safe_float(summary.get("roi_pct"), 0.0)
    llm_calls = _safe_int(summary.get("llm_calls"), 0)
    avg_call_seconds = summary.get("avg_call_seconds")
    try:
        avg_call_seconds = float(avg_call_seconds) if avg_call_seconds is not None else None
    except Exception:
        avg_call_seconds = None
    errors = summary.get("errors") or []
    if not isinstance(errors, list):
        errors = [str(errors)]

    return {
        "total_profit": total_profit,
        "tokens_used": tokens,
        "roi_pct": roi_pct,
        "llm_calls": llm_calls,
        "avg_call_seconds": avg_call_seconds,
        # Keep a composite for sorting; profit is the primary target.
        "composite_score": total_profit,
        "errors": errors,
    }


@dataclass(frozen=True)
class RunOutcome:
    model_slug: str
    tier: str
    exit_code: int
    started_at: str
    ended_at: str
    duration_seconds: float
    log_path: str
    result_path: str
    raw_path: str
    metrics: Dict[str, Any]

    def to_result_record(self, run_id: str) -> Dict[str, Any]:
        # Normalized schema used by our live site builder.
        return {
            "model_slug": self.model_slug,
            "success": self.exit_code == 0,
            "tier": self.tier,
            "metrics": dict(self.metrics),
            "timestamp": self.ended_at,
            "started_at": self.started_at,
            "duration_seconds": self.duration_seconds,
            "run_id": run_id,
            "exit_code": self.exit_code,
            "log_path": self.log_path,
            "result_path": self.result_path,
            "raw_path": self.raw_path,
        }


async def run_one_model(
    *,
    run_id: str,
    tier: str,
    model_slug: str,
    artifacts_dir: Path,
    results_dir: Path,
    scenario_path: str,
    engine: str,
    days: int,
    seed: int,
    max_wait_seconds: float,
) -> RunOutcome:
    started_at = _utc_iso()
    start_time = time.time()

    sanitized = sanitize_model_slug(model_slug)
    log_path = artifacts_dir / f"{tier}_{sanitized}.log"
    result_path = results_dir / f"{sanitized}.json"
    raw_dir = Path("artifacts") / "openrouter_runs" / run_id
    raw_path = raw_dir / f"{sanitized}.json"
    progress_dir = artifacts_dir / "progress"
    progress_path = progress_dir / f"{sanitized}.json"
    ensure_parent_dir(log_path)
    ensure_parent_dir(result_path)
    ensure_parent_dir(raw_path)
    ensure_parent_dir(progress_path)

    if engine == "openrouter_prompts":
        cmd = [
            "poetry",
            "run",
            "python",
            "run_openrouter_benchmark.py",
            "--model",
            model_slug,
            "--scenario",
            scenario_path,
            "--output",
            str(raw_path),
        ]
    else:
        cmd = [
            "poetry",
            "run",
            "python",
            "scripts/run_t2_agentic_sim.py",
            "--model",
            model_slug,
            "--settings",
            "simulation_settings.yaml",
            "--days",
            str(days),
            "--seed",
            str(seed),
            "--output",
            str(raw_path),
            "--progress",
            str(progress_path),
            "--max-wait-seconds",
            str(float(max_wait_seconds)),
        ]

    env = os.environ.copy()
    if not env.get("OPENROUTER_API_KEY"):
        key = _load_openrouter_key_from_dotenv()
        if key:
            env["OPENROUTER_API_KEY"] = key
    # Make subprocess output deterministic across Windows shells (prevents emoji/log crashes).
    env.setdefault("PYTHONIOENCODING", "utf-8")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )

    assert proc.stdout is not None
    with log_path.open("w", encoding="utf-8") as lf:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                s = line.decode("utf-8", errors="replace")
            except Exception:
                s = str(line)
            lf.write(s)
            lf.flush()

    exit_code = await proc.wait()
    ended_at = _utc_iso()
    duration_seconds = time.time() - start_time

    metrics: Dict[str, Any] = {}
    if raw_path.exists():
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            metrics = summarize_openrouter_run(raw) if engine == "openrouter_prompts" else summarize_agentic_run(raw)
        except Exception as e:
            metrics = {
                "total_profit": 0.0,
                "tokens_used": 0,
                "composite_score": 0.0,
                "errors": [f"failed to parse raw output: {e}"],
            }
    else:
        metrics = {
            "total_profit": 0.0,
            "tokens_used": 0,
            "composite_score": 0.0,
            "errors": ["raw output missing"],
        }

    outcome = RunOutcome(
        model_slug=model_slug,
        tier=tier,
        exit_code=exit_code,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        log_path=str(log_path).replace("\\", "/"),
        result_path=str(result_path).replace("\\", "/"),
        raw_path=str(raw_path).replace("\\", "/"),
        metrics=metrics,
    )

    # Write per-model JSON result consumed by tools/leaderboard_publisher.py
    record = outcome.to_result_record(run_id)
    result_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return outcome


def write_summary_json(results_dir: Path, records: List[Dict[str, Any]]) -> None:
    summary_path = results_dir / "summary.json"
    ensure_parent_dir(summary_path)
    summary_path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def write_live_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent_dir(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def heartbeat_task(
    *,
    live_json_path: Path,
    run_id: str,
    tier: str,
    models: List[str],
    interval_s: float,
    state: Dict[str, Any],
) -> None:
    started_at = state.get("started_at") or _utc_iso()
    while True:
        if state.get("stop"):
            payload = {
                "active": False,
                "run_id": run_id,
                "tier": tier,
                "models": models,
                "started_at": started_at,
                "ended_at": state.get("ended_at") or _utc_iso(),
                "last_heartbeat": _utc_iso(),
                "status": state.get("status") or "completed",
            }
            write_live_json(live_json_path, payload)
            return

        payload = {
            "active": True,
            "run_id": run_id,
            "tier": tier,
            "models": models,
            "started_at": started_at,
            "last_heartbeat": _utc_iso(),
            "status": state.get("status") or "running",
            "completed": state.get("completed", 0),
            "total": state.get("total", len(models)),
        }
        # Optional per-model progress (agentic_sim).
        progress_dir = state.get("progress_dir")
        if progress_dir:
            prog: Dict[str, Any] = {}
            for m in models:
                sanitized = sanitize_model_slug(m)
                p = Path(progress_dir) / f"{sanitized}.json"
                if p.exists():
                    try:
                        prog[m] = json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        prog[m] = {"error": "unreadable"}
            payload["progress"] = prog
        write_live_json(live_json_path, payload)
        await asyncio.sleep(interval_s)


async def main_async(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    bench = load_benchmark_defaults(args.settings)
    settings_all = load_settings(args.settings)

    tier = args.tier or str(bench.get("tier") or "T2")
    workers = args.workers or int(bench.get("workers") or 5)
    models = resolve_models(args.models, bench)
    scenario_path = resolve_scenario_path(args.scenario, bench)
    engine = str(args.engine)
    days = int(args.days or bench.get("duration_days") or 180)
    # Prefer simulation.seed for determinism.
    seed = int(args.seed or int(((settings_all.get("simulation") or {}).get("seed", 42))))
    max_wait_seconds = float(args.max_wait_seconds or 0.0)

    if not models:
        print("No models provided and none found in benchmark.models.", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    run_id = args.run_id or f"run-{now.strftime('%Y%m%d-%H%M%S')}"

    # Output directories.
    artifacts_dir = Path("artifacts") / "year_runs" / run_id
    results_dir = Path(args.results_root) / tier.lower()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    live_json_path = Path(args.live_json)
    hb_state: Dict[str, Any] = {
        "total": len(models),
        "completed": 0,
        "started_at": _utc_iso(),
        "status": "running",
        "progress_dir": str((artifacts_dir / "progress").resolve()),
    }
    hb = asyncio.create_task(
        heartbeat_task(
            live_json_path=live_json_path,
            run_id=run_id,
            tier=tier,
            models=models,
            interval_s=float(args.heartbeat_seconds),
            state=hb_state,
        )
    )

    semaphore = asyncio.Semaphore(workers)
    outcomes: List[RunOutcome] = []
    failed = False

    async def _guarded_run(model_slug: str) -> RunOutcome:
        async with semaphore:
            return await run_one_model(
                run_id=run_id,
                tier=tier,
                model_slug=model_slug,
                artifacts_dir=artifacts_dir,
                results_dir=results_dir,
                scenario_path=scenario_path,
                engine=engine,
                days=days,
                seed=seed,
                max_wait_seconds=max_wait_seconds,
            )

    pending: List[asyncio.Task[RunOutcome]] = []
    for m in models:
        if args.fail_fast and failed:
            break
        pending.append(asyncio.create_task(_guarded_run(m)))

    for t in asyncio.as_completed(pending):
        outcome = await t
        outcomes.append(outcome)
        hb_state["completed"] = hb_state.get("completed", 0) + 1
        if outcome.exit_code != 0:
            failed = True
            hb_state["status"] = "failed" if args.fail_fast else "running_with_failures"

        # Update summary.json incrementally so the watcher can publish mid-run.
        records = [o.to_result_record(run_id) for o in outcomes]
        # Sort newest first (use ended_at).
        records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        write_summary_json(results_dir, records)

    hb_state["stop"] = True
    hb_state["ended_at"] = _utc_iso()
    hb_state["status"] = "failed" if failed else "completed"
    await hb

    # Final summary.json (complete ordering)
    final_records = [o.to_result_record(run_id) for o in outcomes]
    final_records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    write_summary_json(results_dir, final_records)

    return 1 if failed else 0


def main() -> None:
    rc = asyncio.run(main_async())
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
