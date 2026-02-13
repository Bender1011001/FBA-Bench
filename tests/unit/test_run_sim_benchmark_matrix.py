from __future__ import annotations

from pathlib import Path

from scripts.run_sim_benchmark_matrix import (
    compare_live_and_replay,
    parse_profile_specs,
    summarize_records,
)


def test_parse_profile_specs_parses_named_paths(tmp_path: Path) -> None:
    profile_a = tmp_path / "a.yaml"
    profile_b = tmp_path / "b.yaml"
    profile_a.write_text("x: 1\n", encoding="utf-8")
    profile_b.write_text("y: 2\n", encoding="utf-8")

    parsed = parse_profile_specs(
        [f"baseline={profile_a}", f"stress={profile_b}"],
        repo_root=tmp_path,
    )

    assert parsed["baseline"] == profile_a
    assert parsed["stress"] == profile_b


def test_summarize_records_groups_by_profile() -> None:
    records = [
        {
            "profile": "baseline",
            "status": "ok",
            "roi_percent": 10.0,
            "equity_profit": 100.0,
            "net_profit": 70.0,
            "orders_fulfilled": 20,
            "stockouts": 2,
            "pending_refund_exposure": 30.0,
        },
        {
            "profile": "baseline",
            "status": "ok",
            "roi_percent": 14.0,
            "equity_profit": 140.0,
            "net_profit": 90.0,
            "orders_fulfilled": 24,
            "stockouts": 1,
            "pending_refund_exposure": 20.0,
        },
        {
            "profile": "stress_returns",
            "status": "failed",
            "roi_percent": 2.0,
        },
    ]

    summary = summarize_records(records)

    assert summary["runs_total"] == 3
    assert summary["runs_ok"] == 2
    assert summary["runs_failed"] == 1
    assert summary["profiles"]["baseline"]["runs_ok"] == 2
    assert summary["profiles"]["baseline"]["roi_percent"]["mean"] == 12.0
    assert summary["profiles"]["baseline"]["stockouts"]["max"] == 2.0
    assert summary["profiles"]["stress_returns"]["runs_ok"] == 0


def test_compare_live_and_replay_ok_on_identical_payloads() -> None:
    contract = {
        "required": {
            "results": ["net_profit", "roi_percent", "orders_fulfilled"],
            "daily_performance_series": ["profit"],
            "decision_result_keys": ["profit"],
        },
        "tolerances": {"money": 0.01, "ratio_points": 0.01},
    }
    payload = {
        "results": {"net_profit": 10.0, "roi_percent": 1.0, "orders_fulfilled": 3},
        "daily_performance": {"profit": [5.0, 5.0]},
        "decisions": [
            {"decisions_raw": {"accept_all_orders": True}, "results": {"profit": 5.0}},
            {"decisions_raw": {"accept_all_orders": True}, "results": {"profit": 5.0}},
        ],
    }
    report = compare_live_and_replay(
        live_payload=payload, replay_payload=payload, contract=contract
    )
    assert report["ok"] is True
    assert report["mismatches"] == []


def test_compare_live_and_replay_flags_mismatch() -> None:
    contract = {
        "required": {
            "results": ["net_profit"],
            "daily_performance_series": ["profit"],
            "decision_result_keys": ["profit"],
        },
        "tolerances": {"money": 0.01, "ratio_points": 0.01},
    }
    live = {
        "results": {"net_profit": 10.0},
        "daily_performance": {"profit": [10.0]},
        "decisions": [
            {"decisions_raw": {"accept_all_orders": True}, "results": {"profit": 10.0}}
        ],
    }
    replay = {
        "results": {"net_profit": 9.0},
        "daily_performance": {"profit": [9.0]},
        "decisions": [
            {"decisions_raw": {"accept_all_orders": True}, "results": {"profit": 9.0}}
        ],
    }
    report = compare_live_and_replay(
        live_payload=live, replay_payload=replay, contract=contract
    )
    assert report["ok"] is False
    assert report["mismatches"]
