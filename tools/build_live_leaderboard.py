#!/usr/bin/env python3
"""
Build public-facing docs/api/leaderboard.json and docs/api/top10.json from
results/openrouter_tier_runs/<tier>/summary.json (emitted by scripts/batch_runner.py).

This is used by tools/watch_and_build.py for local live updates and can also be
run manually.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_human(ts: Optional[str] = None) -> str:
    try:
        dt = datetime.fromisoformat((ts or _utc_now_iso()).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    except Exception:
        return ts or "Unknown"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _provider_from_slug(model_slug: str) -> str:
    if "/" in model_slug:
        return model_slug.split("/", 1)[0]
    return "unknown"


def _provider_display(provider: str) -> str:
    p = provider.strip().lower()
    if p in {"x-ai", "xai", "x_ai"}:
        return "X.AI"
    if p == "openai":
        return "OpenAI"
    if p == "anthropic":
        return "Anthropic"
    if p in {"google", "gemini"}:
        return "Google"
    if p == "deepseek":
        return "DeepSeek"
    if p in {"meta", "meta-llama", "meta_llama"}:
        return "Meta"
    return provider[:1].upper() + provider[1:]


def _model_name_from_slug(model_slug: str) -> str:
    # Prefer last path segment and strip variant.
    s = model_slug.split("/")[-1]
    s = s.split(":")[0]
    return s


def _tier_bucket(model_slug: str) -> str:
    return "free" if ":free" in model_slug else "flagship"


@dataclass(frozen=True)
class Record:
    model_slug: str
    tier: str
    run_id: str
    timestamp: str
    metrics: Dict[str, Any]
    success: bool

    @property
    def provider(self) -> str:
        return _provider_from_slug(self.model_slug)

    @property
    def quality_score(self) -> float:
        try:
            return float(self.metrics.get("avg_quality_score") or 0.0)
        except Exception:
            return 0.0

    @property
    def success_rate(self) -> float:
        try:
            return float(self.metrics.get("success_rate") or 0.0)
        except Exception:
            return 0.0

    @property
    def avg_response_time(self) -> float:
        try:
            return float(self.metrics.get("avg_response_time") or 0.0)
        except Exception:
            return 0.0

    @property
    def total_tokens(self) -> int:
        try:
            return int(self.metrics.get("total_tokens") or 0)
        except Exception:
            return 0


def load_records(summary_path: Path) -> List[Record]:
    if not summary_path.exists():
        return []
    data = _read_json(summary_path)
    if not isinstance(data, list):
        return []

    out: List[Record] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_slug = str(item.get("model_slug") or "")
        if not model_slug:
            continue
        out.append(
            Record(
                model_slug=model_slug,
                tier=str(item.get("tier") or "T2"),
                run_id=str(item.get("run_id") or "unknown"),
                timestamp=str(item.get("timestamp") or _utc_now_iso()),
                metrics=dict(item.get("metrics") or {}),
                success=bool(item.get("success")),
            )
        )
    return out


def select_current_run(records: List[Record], live_json_path: Path) -> Tuple[Optional[str], bool]:
    if live_json_path.exists():
        try:
            live = _read_json(live_json_path)
            run_id = live.get("run_id")
            active = bool(live.get("active"))
            if isinstance(run_id, str) and run_id:
                return run_id, active
        except Exception:
            pass

    # Fall back to most recent run_id by timestamp.
    if not records:
        return None, False
    recs_sorted = sorted(records, key=lambda r: r.timestamp, reverse=True)
    return recs_sorted[0].run_id, False


def build_leaderboard(records: List[Record], *, run_id: Optional[str], tier: str, active: bool) -> Dict[str, Any]:
    filtered = [r for r in records if r.tier.upper() == tier.upper()]
    if run_id:
        filtered = [r for r in filtered if r.run_id == run_id]

    # Keep last record per model (should be 1 per model per run anyway).
    by_model: Dict[str, Record] = {}
    for r in sorted(filtered, key=lambda rr: rr.timestamp, reverse=True):
        by_model.setdefault(r.model_slug, r)

    ranked = sorted(by_model.values(), key=lambda r: (r.quality_score, r.success_rate), reverse=True)

    rankings: List[Dict[str, Any]] = []
    total_tokens = 0
    for i, r in enumerate(ranked, start=1):
        total_tokens += r.total_tokens
        badge = "stable"
        if i == 1:
            badge = "gold"
        elif i == 2:
            badge = "silver"
        elif i == 3:
            badge = "bronze"

        rankings.append(
            {
                "rank": i,
                "model_name": _model_name_from_slug(r.model_slug),
                "model_slug": r.model_slug,
                "provider": _provider_display(r.provider),
                "tier": _tier_bucket(r.model_slug),
                "quality_score": round(r.quality_score, 3),
                "success_rate": round(r.success_rate, 3),
                "avg_response_time": round(r.avg_response_time, 2),
                "total_tokens": r.total_tokens,
                "total_runs": 1,
                "badge": badge,
                "timestamp": r.timestamp,
                "run_id": r.run_id,
                "success": r.success,
            }
        )

    avg_quality = 0.0
    avg_success = 0.0
    if rankings:
        avg_quality = sum(r["quality_score"] for r in rankings) / len(rankings)
        avg_success = sum(r["success_rate"] for r in rankings) / len(rankings)

    payload: Dict[str, Any] = {
        "generated_at": _utc_human(_utc_now_iso()),
        "benchmark_version": "2026.02-live",
        "active_run": {
            "active": active,
            "run_id": run_id,
            "tier": tier,
        },
        "total_models": len(rankings),
        "summary": {
            "avg_quality_score": round(avg_quality, 3),
            "avg_success_rate": round(avg_success, 3),
            "total_tokens": int(total_tokens),
            "total_runs": int(len(rankings)),
            "top_performer": rankings[0]["model_name"] if rankings else None,
        },
        "rankings": rankings,
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Build docs/api leaderboard JSON from batch_runner results.")
    ap.add_argument("--tier", default="T2", help="Tier to build (T0/T1/T2).")
    ap.add_argument("--results-root", default="results/openrouter_tier_runs", help="Results root directory.")
    ap.add_argument("--output-leaderboard", default="docs/api/leaderboard.json", help="Output leaderboard.json path.")
    ap.add_argument("--output-top10", default="docs/api/top10.json", help="Output top10.json path.")
    ap.add_argument("--live-json", default="docs/api/live.json", help="Live status/heartbeat JSON path.")
    args = ap.parse_args()

    summary_path = Path(args.results_root) / args.tier.lower() / "summary.json"
    records = load_records(summary_path)
    run_id, active = select_current_run(records, Path(args.live_json))
    lb = build_leaderboard(records, run_id=run_id, tier=args.tier, active=active)

    _write_json(Path(args.output_leaderboard), lb)
    _write_json(Path(args.output_top10), {"generated_at": lb["generated_at"], "rankings": lb.get("rankings", [])[:10]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

