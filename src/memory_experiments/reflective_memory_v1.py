from __future__ import annotations

"""
Reflective memory v1 for long-horizon simulation runs.

This module provides a practical memory loop:
- daily review (keep/update/discard)
- weekly consolidation into long-term memory
- relevance-based retrieval for next decisions

Design goals:
- deterministic by default (reproducible benchmark behavior)
- optional model-authored review payload support
- bounded memory sizes for stable prompt injection
"""

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_memory(
    *,
    impact: float,
    reusability: float,
    confidence: float,
    novelty: float,
    recency: float,
    penalty: float = 0.0,
) -> float:
    """
    Score a memory candidate for retention.

    score = 0.35*impact + 0.25*reusability + 0.15*confidence +
            0.15*novelty + 0.10*recency - penalty
    """
    weighted = (
        0.35 * _clamp_01(impact)
        + 0.25 * _clamp_01(reusability)
        + 0.15 * _clamp_01(confidence)
        + 0.15 * _clamp_01(novelty)
        + 0.10 * _clamp_01(recency)
        - _clamp_01(penalty)
    )
    return _clamp_01(weighted)


@dataclass
class MemoryRecord:
    memory_id: str
    statement: str
    decision_type: str
    scope: str
    asin: Optional[str]
    tags: List[str]
    source: str
    created_day: int
    last_seen_day: int
    impact: float
    reusability: float
    confidence: float
    novelty: float
    recency: float
    penalty: float = 0.0
    score: float = 0.0
    evidence_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DailyReviewSummary:
    day: int
    kept: int
    discarded: int
    promoted: int
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeeklyConsolidationSummary:
    day: int
    consolidated_candidates: int
    promoted_to_long_term: int
    long_term_total: int
    episodic_total: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReflectiveMemoryV1:
    def __init__(
        self,
        *,
        episodic_limit: int = 200,
        long_term_limit: int = 80,
        retrieval_limit: int = 7,
        keep_threshold: float = 0.45,
        episodic_ttl_days: int = 14,
    ) -> None:
        self.episodic_limit = max(1, int(episodic_limit))
        self.long_term_limit = max(1, int(long_term_limit))
        self.retrieval_limit = max(1, int(retrieval_limit))
        self.keep_threshold = _clamp_01(keep_threshold)
        self.episodic_ttl_days = max(1, int(episodic_ttl_days))

        self.episodic: List[MemoryRecord] = []
        self.long_term: List[MemoryRecord] = []
        self.daily_reviews: List[DailyReviewSummary] = []

    def _make_id(
        self, day: int, statement: str, decision_type: str, asin: Optional[str]
    ) -> str:
        raw = f"{day}|{decision_type}|{asin or 'none'}|{statement.strip().lower()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def _build_record(
        self, day: int, candidate: Dict[str, Any], source: str
    ) -> Optional[MemoryRecord]:
        statement = str(candidate.get("statement", "")).strip()
        if not statement:
            return None
        decision_type = (
            str(candidate.get("decision_type", "mixed")).strip().lower() or "mixed"
        )
        scope = str(candidate.get("scope", "global")).strip().lower() or "global"
        asin = candidate.get("asin")
        asin_val = str(asin).strip() if asin is not None else None
        if asin_val == "":
            asin_val = None

        impact = float(candidate.get("impact", 0.5))
        reusability = float(candidate.get("reusability", 0.5))
        confidence = float(candidate.get("confidence", 0.5))
        novelty = float(candidate.get("novelty", 0.4))
        recency = float(candidate.get("recency", 1.0))
        penalty = float(candidate.get("penalty", 0.0))
        tags = [
            str(x).strip().lower() for x in candidate.get("tags", []) if str(x).strip()
        ]

        mem_id = self._make_id(day, statement, decision_type, asin_val)
        score = score_memory(
            impact=impact,
            reusability=reusability,
            confidence=confidence,
            novelty=novelty,
            recency=recency,
            penalty=penalty,
        )
        return MemoryRecord(
            memory_id=mem_id,
            statement=statement,
            decision_type=decision_type,
            scope=scope,
            asin=asin_val,
            tags=tags,
            source=source,
            created_day=day,
            last_seen_day=day,
            impact=_clamp_01(impact),
            reusability=_clamp_01(reusability),
            confidence=_clamp_01(confidence),
            novelty=_clamp_01(novelty),
            recency=_clamp_01(recency),
            penalty=_clamp_01(penalty),
            score=score,
        )

    def _heuristic_candidates(self, day_trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        decisions = day_trace.get("decisions", {}) or {}
        results = day_trace.get("results", {}) or {}
        state = day_trace.get("state", {}) or {}

        price_changes = decisions.get("price_changes", {}) or {}
        restock = decisions.get("restock", {}) or {}
        stockouts = int(results.get("stockouts", 0) or 0)
        revenue = float(results.get("revenue", 0.0) or 0.0)
        costs = float(results.get("costs", 0.0) or 0.0)
        profit = float(results.get("profit", 0.0) or 0.0)
        events = state.get("active_events", []) or []

        candidates: List[Dict[str, Any]] = []

        if stockouts > 0:
            candidates.append(
                {
                    "statement": (
                        "Stockout losses occurred. Increase safety stock and trigger earlier replenishment."
                    ),
                    "decision_type": "restock",
                    "scope": "global",
                    "impact": min(1.0, 0.45 + stockouts / 20.0),
                    "reusability": 0.9,
                    "confidence": 0.85,
                    "novelty": 0.5,
                    "recency": 1.0,
                    "tags": ["stockout", "inventory", "risk"],
                }
            )

        if price_changes and profit > 0:
            candidates.append(
                {
                    "statement": "Pricing adjustments correlated with positive daily profit. Keep controlled tests.",
                    "decision_type": "pricing",
                    "scope": "global",
                    "impact": min(1.0, 0.4 + min(len(price_changes), 5) / 10.0),
                    "reusability": 0.75,
                    "confidence": 0.7,
                    "novelty": 0.45,
                    "recency": 1.0,
                    "tags": ["pricing", "profit"],
                }
            )

        if price_changes and profit < 0:
            candidates.append(
                {
                    "statement": "Price changes preceded negative day profit. Tighten margin guardrails before cuts.",
                    "decision_type": "pricing",
                    "scope": "global",
                    "impact": min(1.0, 0.35 + abs(profit) / 500.0),
                    "reusability": 0.8,
                    "confidence": 0.75,
                    "novelty": 0.4,
                    "recency": 1.0,
                    "tags": ["pricing", "margin", "risk"],
                }
            )

        if restock and costs > revenue:
            candidates.append(
                {
                    "statement": "Restock spend exceeded daily revenue. Add stricter cash discipline on purchases.",
                    "decision_type": "restock",
                    "scope": "global",
                    "impact": min(1.0, 0.35 + (costs - revenue) / 600.0),
                    "reusability": 0.9,
                    "confidence": 0.85,
                    "novelty": 0.35,
                    "recency": 1.0,
                    "tags": ["cash", "restock", "budget"],
                }
            )

        if events and profit >= 0:
            candidates.append(
                {
                    "statement": "Operations remained profitable under adverse events. Preserve resilience tactics.",
                    "decision_type": "risk",
                    "scope": "scenario",
                    "impact": 0.55,
                    "reusability": 0.65,
                    "confidence": 0.65,
                    "novelty": 0.5,
                    "recency": 1.0,
                    "tags": ["resilience", "events"],
                }
            )

        return candidates

    def apply_daily_review(
        self,
        *,
        day: int,
        review_payload: Optional[Dict[str, Any]],
        fallback_trace: Dict[str, Any],
    ) -> DailyReviewSummary:
        """
        Apply daily keep/update/discard decisions.

        review_payload format:
        {
          "keep": [candidate, ...],
          "update": [candidate, ...],
          "discard": [candidate, ...]
        }
        """
        kept_records: List[MemoryRecord] = []
        discarded = 0
        source = "heuristic"

        keep_candidates: List[Dict[str, Any]] = []
        update_candidates: List[Dict[str, Any]] = []
        discard_candidates: List[Dict[str, Any]] = []

        if isinstance(review_payload, dict):
            keep_candidates = list(review_payload.get("keep", []) or [])
            update_candidates = list(review_payload.get("update", []) or [])
            discard_candidates = list(review_payload.get("discard", []) or [])
            if keep_candidates or update_candidates or discard_candidates:
                source = "llm_review"

        if source == "heuristic":
            keep_candidates = self._heuristic_candidates(fallback_trace)

        for item in discard_candidates:
            record = self._build_record(day, item, source)
            if record is not None:
                discarded += 1

        for item in keep_candidates + update_candidates:
            record = self._build_record(day, item, source)
            if record is None:
                continue
            if record.score >= self.keep_threshold:
                kept_records.append(record)
            else:
                discarded += 1

        # Update episodic memory (dedupe by id)
        by_id: Dict[str, MemoryRecord] = {m.memory_id: m for m in self.episodic}
        promoted = 0
        for record in kept_records:
            existing = by_id.get(record.memory_id)
            if existing is None:
                by_id[record.memory_id] = record
                promoted += 1
            else:
                existing.last_seen_day = day
                existing.evidence_count += 1
                # Smooth update for confidence and score
                existing.confidence = _clamp_01(
                    (existing.confidence + record.confidence) / 2.0
                )
                existing.score = _clamp_01((existing.score + record.score) / 2.0)

        episodic_sorted = sorted(
            by_id.values(),
            key=lambda m: (m.score, m.last_seen_day),
            reverse=True,
        )
        self.episodic = episodic_sorted[: self.episodic_limit]

        summary = DailyReviewSummary(
            day=day,
            kept=len(kept_records),
            discarded=discarded,
            promoted=promoted,
            source=source,
        )
        self.daily_reviews.append(summary)
        return summary

    def consolidate_weekly(self, *, day: int) -> WeeklyConsolidationSummary:
        """Promote strong episodic memories into long-term memory."""
        # Expire old episodic memories first
        min_day = day - self.episodic_ttl_days
        self.episodic = [m for m in self.episodic if m.last_seen_day >= min_day]

        long_term_by_id: Dict[str, MemoryRecord] = {
            m.memory_id: m for m in self.long_term
        }
        promoted = 0
        for candidate in self.episodic:
            if candidate.score < self.keep_threshold:
                continue
            existing = long_term_by_id.get(candidate.memory_id)
            if existing is None:
                long_term_by_id[candidate.memory_id] = candidate
                promoted += 1
            else:
                existing.last_seen_day = day
                existing.evidence_count += 1
                existing.confidence = _clamp_01(
                    (existing.confidence + candidate.confidence) / 2.0
                )
                existing.score = _clamp_01((existing.score + candidate.score) / 2.0)

        self.long_term = sorted(
            long_term_by_id.values(),
            key=lambda m: (m.score, m.evidence_count, m.last_seen_day),
            reverse=True,
        )[: self.long_term_limit]

        return WeeklyConsolidationSummary(
            day=day,
            consolidated_candidates=len(self.episodic),
            promoted_to_long_term=promoted,
            long_term_total=len(self.long_term),
            episodic_total=len(self.episodic),
        )

    def retrieve(
        self,
        *,
        day: int,
        decision_type: str,
        asin: Optional[str],
        tags: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve memory context for next decision."""
        limit_value = self.retrieval_limit if limit is None else max(1, int(limit))
        tag_set = {str(t).strip().lower() for t in (tags or []) if str(t).strip()}
        decision = decision_type.strip().lower() if decision_type else "mixed"
        asin_norm = asin.strip() if asin else None

        pool = self.long_term + self.episodic
        ranked: List[tuple[float, MemoryRecord]] = []

        for mem in pool:
            score = mem.score
            if mem.decision_type == decision or mem.decision_type == "mixed":
                score += 0.2
            if asin_norm:
                if mem.asin == asin_norm:
                    score += 0.3
                elif mem.asin and mem.asin != asin_norm:
                    score -= 0.15
            overlap = len(set(mem.tags) & tag_set)
            score += min(0.2, overlap * 0.05)

            age_days = max(0, day - mem.last_seen_day)
            freshness = 1.0 - min(1.0, age_days / 60.0)
            score += 0.1 * freshness

            ranked.append((score, mem))

        ranked.sort(key=lambda x: x[0], reverse=True)
        selected = [x[1] for x in ranked[:limit_value]]
        return [
            {
                "memory_id": m.memory_id,
                "statement": m.statement,
                "decision_type": m.decision_type,
                "scope": m.scope,
                "asin": m.asin,
                "tags": m.tags,
                "confidence": round(m.confidence, 3),
                "score": round(m.score, 3),
                "last_seen_day": m.last_seen_day,
                "evidence_count": m.evidence_count,
            }
            for m in selected
        ]

    def long_term_snapshot(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.long_term[: max(1, int(limit))]]

    def summary(self) -> Dict[str, Any]:
        avg_score = (
            sum(m.score for m in self.long_term) / len(self.long_term)
            if self.long_term
            else 0.0
        )
        return {
            "episodic_count": len(self.episodic),
            "long_term_count": len(self.long_term),
            "daily_reviews": [r.to_dict() for r in self.daily_reviews[-30:]],
            "long_term_avg_score": round(avg_score, 4),
        }
