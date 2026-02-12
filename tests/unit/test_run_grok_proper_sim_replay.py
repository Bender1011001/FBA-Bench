from __future__ import annotations

import json

import pytest

from run_grok_proper_sim import _load_replay_decisions, _sanitize_decisions_for_replay


def test_sanitize_decisions_for_replay_keeps_action_fields_only() -> None:
    raw = {
        "reasoning": "ignore",
        "accept_all_orders": True,
        "accept_skus": ["P001"],
        "reject_skus": [],
        "accept_orders": ["ORD-1"],
        "price_changes": {"P001": 12.34},
        "restock": {"P001": 50},
        "supplier_orders": [{"sku": "P001", "quantity": 100}],
        "ad_budget_shift": {"P001": 10.0},
        "customer_ops": {"P001": "proactive"},
        "extra": {"should": "not persist"},
    }
    sanitized = _sanitize_decisions_for_replay(raw)
    assert "reasoning" not in sanitized
    assert "extra" not in sanitized
    assert sanitized["accept_all_orders"] is True
    assert sanitized["price_changes"]["P001"] == 12.34


def test_load_replay_decisions_reads_decisions_raw(tmp_path) -> None:
    payload = {
        "decisions": [
            {"day": 1, "decisions_raw": {"accept_all_orders": True}},
            {"day": 2, "decisions_raw": {"accept_all_orders": False}},
        ]
    }
    p = tmp_path / "results.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    decisions = _load_replay_decisions(str(p))
    assert decisions == [{"accept_all_orders": True}, {"accept_all_orders": False}]


def test_load_replay_decisions_errors_on_missing_day(tmp_path) -> None:
    payload = {"decisions": [{"day": 2, "decisions_raw": {"accept_all_orders": True}}]}
    p = tmp_path / "results.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="missing decisions for day 1"):
        _load_replay_decisions(str(p))
