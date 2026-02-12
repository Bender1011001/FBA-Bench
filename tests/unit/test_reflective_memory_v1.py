from __future__ import annotations

from memory_experiments.reflective_memory_v1 import ReflectiveMemoryV1, score_memory


def test_score_memory_prefers_high_signal() -> None:
    low = score_memory(
        impact=0.2,
        reusability=0.2,
        confidence=0.3,
        novelty=0.2,
        recency=0.4,
        penalty=0.0,
    )
    high = score_memory(
        impact=0.9,
        reusability=0.8,
        confidence=0.9,
        novelty=0.6,
        recency=1.0,
        penalty=0.0,
    )
    assert high > low


def test_apply_daily_review_keeps_high_scoring_entries() -> None:
    mem = ReflectiveMemoryV1(keep_threshold=0.45)
    summary = mem.apply_daily_review(
        day=1,
        review_payload={
            "keep": [
                {
                    "statement": "Always maintain margin guardrails before cutting price.",
                    "decision_type": "pricing",
                    "scope": "global",
                    "impact": 0.8,
                    "reusability": 0.9,
                    "confidence": 0.8,
                    "novelty": 0.4,
                    "recency": 1.0,
                    "tags": ["pricing", "margin"],
                }
            ],
            "discard": [{"statement": "A noisy one-off event happened."}],
        },
        fallback_trace={},
    )

    assert summary.kept == 1
    assert summary.discarded == 1
    assert len(mem.episodic) == 1
    assert mem.episodic[0].decision_type == "pricing"


def test_heuristic_fallback_generates_inventory_memory_from_stockout() -> None:
    mem = ReflectiveMemoryV1(keep_threshold=0.30)
    summary = mem.apply_daily_review(
        day=3,
        review_payload=None,
        fallback_trace={
            "state": {"active_events": []},
            "decisions": {"price_changes": {}, "restock": {}},
            "results": {
                "revenue": 100.0,
                "costs": 30.0,
                "profit": 70.0,
                "orders_fulfilled": 20,
                "stockouts": 5,
            },
        },
    )

    assert summary.kept >= 1
    retrieved = mem.retrieve(day=3, decision_type="restock", asin=None, tags=["inventory"])
    assert retrieved
    assert any("stockout" in item["statement"].lower() for item in retrieved)


def test_weekly_consolidation_promotes_episodic_memories() -> None:
    mem = ReflectiveMemoryV1(keep_threshold=0.35, long_term_limit=5)

    for day in range(1, 8):
        mem.apply_daily_review(
            day=day,
            review_payload={
                "keep": [
                    {
                        "statement": "Price tests should preserve contribution margin floor.",
                        "decision_type": "pricing",
                        "scope": "global",
                        "impact": 0.7,
                        "reusability": 0.8,
                        "confidence": 0.75,
                        "novelty": 0.3,
                        "recency": 1.0,
                        "tags": ["pricing"],
                    }
                ]
            },
            fallback_trace={},
        )

    weekly = mem.consolidate_weekly(day=7)
    assert weekly.promoted_to_long_term >= 1
    assert weekly.long_term_total >= 1
    assert len(mem.long_term_snapshot(limit=5)) >= 1
