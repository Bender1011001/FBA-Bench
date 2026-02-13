from __future__ import annotations

import json

from run_grok_proper_sim import (
    MarketSimulator,
    _build_storyline,
    _build_theater_frame,
    _write_json_atomic,
)


def test_build_theater_frame_contains_expected_fields() -> None:
    sim = MarketSimulator(seed=13)
    sim.state.day = 1
    decisions = {
        "reasoning": "Protect margin while keeping stock healthy.",
        "accept_orders": [],
        "price_changes": {"P001": 41.99},
        "restock": {"P002": 30},
        "supplier_orders": [{"sku": "P003", "quantity": 80}],
        "ad_budget_shift": {"P001": 15.0},
        "customer_ops": {"P001": "standard"},
    }
    results = sim.apply_agent_decisions(decisions, orders=[])

    frame = _build_theater_frame(
        simulator=sim,
        day=1,
        decisions=decisions,
        results=results,
        decision_latency_seconds=32.4,
    )

    assert frame["day"] == 1
    assert frame["actions"]["price_changes"] == 1
    assert frame["actions"]["restocks"] == 1
    assert frame["orders"]["received"] == 0
    assert "daily_results" in frame
    assert len(frame["products"]) <= 8


def test_write_json_atomic_persists_payload(tmp_path) -> None:
    out = tmp_path / "sim_trace.json"
    payload = {"status": "running", "progress": {"day": 2}}

    _write_json_atomic(out, payload)

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["status"] == "running"
    assert loaded["progress"]["day"] == 2


def test_storyline_flags_stockout_risk() -> None:
    frame = {
        "daily_results": {
            "profit": -30.0,
            "supplier_orders_placed": 0,
            "ad_spend": 0.0,
        },
        "orders": {"stockouts": 9, "fulfilled": 2},
        "actions": {},
    }
    story = _build_storyline(frame)

    assert story["tone"] == "negative"
    assert "stockouts" in story["headline"].lower()


def test_storyline_recognizes_marketing_efficiency() -> None:
    frame = {
        "daily_results": {
            "profit": 80.0,
            "supplier_orders_placed": 0,
            "ad_spend": 20.0,
            "ad_attributed_revenue": 26.0,
        },
        "orders": {"stockouts": 0, "fulfilled": 5},
        "actions": {},
    }
    story = _build_storyline(frame)

    assert story["tone"] in {"positive", "neutral"}
    assert (
        "marketing" in story["headline"].lower()
        or "healthy execution" in story["headline"].lower()
    )
