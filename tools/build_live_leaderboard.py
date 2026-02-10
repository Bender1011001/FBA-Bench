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
    def is_agentic(self) -> bool:
        # Agentic sim emits profit/ROI metrics; prompt-scoring emits quality metrics.
        m = self.metrics
        return any(k in m for k in ("total_profit", "roi_pct", "llm_calls", "avg_call_seconds"))

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

    @property
    def total_profit(self) -> float:
        try:
            return float(self.metrics.get("total_profit") or 0.0)
        except Exception:
            return 0.0

    @property
    def roi_pct(self) -> float:
        try:
            return float(self.metrics.get("roi_pct") or 0.0)
        except Exception:
            return 0.0

    @property
    def tokens_used(self) -> int:
        # Agentic sim uses tokens_used; prompt scoring uses total_tokens.
        if "tokens_used" in self.metrics:
            try:
                return int(self.metrics.get("tokens_used") or 0)
            except Exception:
                return 0
        return self.total_tokens

    @property
    def llm_calls(self) -> int:
        try:
            return int(self.metrics.get("llm_calls") or 0)
        except Exception:
            return 0

    @property
    def avg_call_seconds(self) -> Optional[float]:
        v = self.metrics.get("avg_call_seconds")
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None


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


def _records_from_live_progress(
    *, live: Dict[str, Any], tier: str, run_id: str
) -> List[Record]:
    """
    Create synthetic in-progress records from docs/api/live.json so the leaderboard
    can update while long agentic simulations are running.
    """
    progress = live.get("progress") or {}
    if not isinstance(progress, dict):
        return []

    out: List[Record] = []
    for model_slug, p in progress.items():
        if not isinstance(model_slug, str) or not model_slug:
            continue
        if not isinstance(p, dict):
            continue

        profit_so_far = p.get("profit_so_far")
        capital = p.get("capital")
        roi_pct = None
        try:
            pf = float(profit_so_far) if profit_so_far is not None else None
            cap = float(capital) if capital is not None else None
            if pf is not None and cap is not None:
                start_cap = cap - pf  # capital = starting_capital + profit_so_far in this sim
                if start_cap != 0:
                    roi_pct = (pf / start_cap) * 100.0
        except Exception:
            roi_pct = None

        # Map progress into the same metric keys as summarize_agentic_run() emits.
        metrics = {
            "total_profit": profit_so_far,
            "tokens_used": p.get("tokens_used"),
            "llm_calls": p.get("llm_calls"),
            # live.json has last_call_seconds; use it as a best-effort proxy until completion.
            "avg_call_seconds": p.get("last_call_seconds"),
            "roi_pct": roi_pct,
            "errors": [],
        }
        ts = str(p.get("timestamp") or _utc_now_iso())
        out.append(
            Record(
                model_slug=model_slug,
                tier=tier,
                run_id=run_id,
                timestamp=ts,
                metrics=metrics,
                success=True,
            )
        )
    return out


def build_leaderboard(
    records: List[Record], *, run_id: Optional[str], tier: str, active: bool, live: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    filtered = [r for r in records if r.tier.upper() == tier.upper()]
    if run_id:
        filtered = [r for r in filtered if r.run_id == run_id]

    if active and run_id and live:
        filtered.extend(_records_from_live_progress(live=live, tier=tier, run_id=run_id))

    # Keep last record per model (should be 1 per model per run anyway).
    by_model: Dict[str, Record] = {}
    for r in sorted(filtered, key=lambda rr: rr.timestamp, reverse=True):
        by_model.setdefault(r.model_slug, r)

    values = list(by_model.values())
    metric_mode = "agentic" if any(r.is_agentic for r in values) else "prompt"
    if metric_mode == "agentic":
        ranked = sorted(values, key=lambda r: (r.total_profit, r.roi_pct, r.tokens_used), reverse=True)
    else:
        ranked = sorted(values, key=lambda r: (r.quality_score, r.success_rate), reverse=True)

    rankings: List[Dict[str, Any]] = []
    total_tokens = 0
    total_profit_sum = 0.0
    roi_sum = 0.0
    roi_count = 0
    llm_calls_sum = 0
    for i, r in enumerate(ranked, start=1):
        total_tokens += r.tokens_used
        if metric_mode == "agentic":
            total_profit_sum += r.total_profit
            roi_sum += r.roi_pct
            roi_count += 1
            llm_calls_sum += r.llm_calls
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
                # Prompt-scoring metrics (may be absent in agentic mode).
                "quality_score": round(r.quality_score, 3) if metric_mode == "prompt" else None,
                "success_rate": round(r.success_rate, 3) if metric_mode == "prompt" else None,
                "avg_response_time": round(r.avg_response_time, 2) if metric_mode == "prompt" else None,
                "total_tokens": int(r.tokens_used),
                # Agentic metrics (may be absent in prompt mode).
                "total_profit": round(r.total_profit, 2) if metric_mode == "agentic" else None,
                "roi_pct": round(r.roi_pct, 3) if metric_mode == "agentic" else None,
                "llm_calls": int(r.llm_calls) if metric_mode == "agentic" else None,
                "avg_call_seconds": round(r.avg_call_seconds, 2) if (metric_mode == "agentic" and r.avg_call_seconds is not None) else None,
                "total_runs": 1,
                "badge": badge,
                "timestamp": r.timestamp,
                "run_id": r.run_id,
                "success": r.success,
            }
        )

    avg_quality = 0.0
    avg_success = 0.0
    avg_profit = 0.0
    avg_roi = 0.0
    if rankings:
        if metric_mode == "prompt":
            avg_quality = sum(float(r["quality_score"] or 0.0) for r in rankings) / len(rankings)
            avg_success = sum(float(r["success_rate"] or 0.0) for r in rankings) / len(rankings)
        else:
            avg_profit = total_profit_sum / float(len(rankings))
            avg_roi = (roi_sum / float(roi_count)) if roi_count else 0.0

    payload: Dict[str, Any] = {
        "generated_at": _utc_human(_utc_now_iso()),
        "benchmark_version": "2026.02-live",
        "metric_mode": metric_mode,
        "active_run": {
            "active": active,
            "run_id": run_id,
            "tier": tier,
        },
        "total_models": len(rankings),
        "summary": {
            # Prompt-scoring summary.
            "avg_quality_score": round(avg_quality, 3) if metric_mode == "prompt" else None,
            "avg_success_rate": round(avg_success, 3) if metric_mode == "prompt" else None,
            # Agentic summary.
            "avg_total_profit": round(avg_profit, 2) if metric_mode == "agentic" else None,
            "avg_roi_pct": round(avg_roi, 3) if metric_mode == "agentic" else None,
            "total_profit_sum": round(total_profit_sum, 2) if metric_mode == "agentic" else None,
            "total_llm_calls": int(llm_calls_sum) if metric_mode == "agentic" else None,
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
    live_payload: Optional[Dict[str, Any]] = None
    live_path = Path(args.live_json)
    if live_path.exists():
        try:
            live_payload = _read_json(live_path)
        except Exception:
            live_payload = None

    run_id, active = select_current_run(records, live_path)
    lb = build_leaderboard(records, run_id=run_id, tier=args.tier, active=active, live=live_payload)

    _write_json(Path(args.output_leaderboard), lb)
    _write_json(Path(args.output_top10), {"generated_at": lb["generated_at"], "rankings": lb.get("rankings", [])[:10]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
