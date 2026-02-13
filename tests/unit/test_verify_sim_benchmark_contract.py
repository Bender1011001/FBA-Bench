from __future__ import annotations

from copy import deepcopy

from scripts.verify_sim_benchmark_contract import (
    load_contract,
    validate_results_payload,
)


def _valid_payload() -> dict:
    return {
        "config": {
            "days": 2,
            "seed": 42,
            "model": "x-ai/grok-4.1-fast",
            "memory_mode": "stateless",
            "memory_review_mode": "heuristic",
            "weekly_consolidation": True,
        },
        "execution": {
            "time_seconds": 12.3,
            "llm_calls": 2,
            "reflection_calls": 0,
            "total_tokens": 1234,
        },
        "results": {
            "starting_capital": 10000.0,
            "starting_inventory_value": 1000.0,
            "starting_equity": 11000.0,
            "final_capital": 10500.0,
            "final_inventory_value": 900.0,
            "final_equity": 11300.0,
            "total_revenue": 500.0,
            "total_costs": 200.0,
            "net_profit": 300.0,
            "equity_profit": 300.0,
            "roi_percent": ((11300.0 - 11000.0) / 11000.0) * 100.0,
            "orders_fulfilled": 12,
            "stockouts": 1,
            "total_ad_spend": 25.0,
            "returns_processed": 2,
            "refunds_paid": 10.0,
            "salvage_recovered": 1.0,
            "supplier_delay_events": 1,
            "supplier_delay_days": 2,
            "open_customer_backlog": 3,
            "pending_refund_exposure": 100.0,
            "pending_returns_open": 2,
        },
        "daily_performance": {
            "revenue": [250.0, 250.0],
            "costs": [100.0, 100.0],
            "profit": [150.0, 150.0],
            "ad_spend": [10.0, 15.0],
            "ad_attributed_revenue": [30.0, 40.0],
        },
        "decisions": [
            {
                "day": 1,
                "reasoning": "day 1",
                "story_headline": "headline",
                "actions": {
                    "accept_all_orders": True,
                    "accept_skus": 0,
                    "reject_skus": 0,
                    "orders_accepted": 12,
                    "price_changes": 0,
                    "restocks": 0,
                    "supplier_orders": 0,
                    "ad_budget_shifts": 1,
                    "customer_ops_updates": 0,
                },
                "results": {
                    "revenue": 250.0,
                    "profit": 150.0,
                    "fulfilled": 6,
                    "stockouts": 1,
                    "ad_spend": 10.0,
                    "ad_attributed_revenue": 30.0,
                    "supplier_orders_placed": 0,
                    "service_tickets_resolved": 0,
                    "fulfillment_fees": 8.0,
                    "payment_processing_fees": 7.0,
                    "fixed_operating_cost": 4.0,
                    "returns_processed": 1,
                    "refunds_paid": 5.0,
                    "salvage_recovered": 0.5,
                },
                "memory": {"daily": None, "weekly": None},
            },
            {
                "day": 2,
                "reasoning": "day 2",
                "story_headline": "headline",
                "actions": {
                    "accept_all_orders": True,
                    "accept_skus": 0,
                    "reject_skus": 0,
                    "orders_accepted": 12,
                    "price_changes": 0,
                    "restocks": 0,
                    "supplier_orders": 0,
                    "ad_budget_shifts": 1,
                    "customer_ops_updates": 0,
                },
                "results": {
                    "revenue": 250.0,
                    "profit": 150.0,
                    "fulfilled": 6,
                    "stockouts": 0,
                    "ad_spend": 15.0,
                    "ad_attributed_revenue": 40.0,
                    "supplier_orders_placed": 0,
                    "service_tickets_resolved": 0,
                    "fulfillment_fees": 8.0,
                    "payment_processing_fees": 7.0,
                    "fixed_operating_cost": 4.0,
                    "returns_processed": 1,
                    "refunds_paid": 5.0,
                    "salvage_recovered": 0.5,
                },
                "memory": {"daily": None, "weekly": None},
            },
        ],
    }


def test_validate_results_payload_accepts_valid_shape() -> None:
    contract = load_contract()
    report = validate_results_payload(_valid_payload(), contract)
    assert report["ok"] is True
    assert not report["errors"]


def test_validate_results_payload_catches_profit_invariant() -> None:
    payload = _valid_payload()
    payload["results"]["net_profit"] = 999.0

    contract = load_contract()
    report = validate_results_payload(payload, contract)
    assert report["ok"] is False
    assert any("net_profit invariant failed" in error for error in report["errors"])


def test_validate_results_payload_catches_missing_decision_fields() -> None:
    payload = _valid_payload()
    broken = deepcopy(payload)
    del broken["decisions"][0]["actions"]["restocks"]

    contract = load_contract()
    report = validate_results_payload(broken, contract)
    assert report["ok"] is False
    assert any("decisions[0].actions.restocks" in error for error in report["errors"])
