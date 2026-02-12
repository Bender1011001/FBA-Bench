from __future__ import annotations

from scripts.sim_theater_demo import _latest_results_file, build_replay_payload


def test_build_replay_payload_from_results_shape() -> None:
    results_payload = {
        "config": {"days": 3},
        "execution": {"llm_calls": 3, "time_seconds": 90.0, "total_tokens": 1000},
        "results": {"starting_capital": 10000.0, "final_capital": 10120.0, "net_profit": 120.0},
        "daily_performance": {"revenue": [100.0, 120.0, 140.0], "profit": [20.0, 40.0, 60.0]},
        "decisions": [
            {
                "day": 1,
                "reasoning": "Day 1 plan",
                "actions": {"price_changes": 1},
                "results": {"fulfilled": 3, "stockouts": 0, "revenue": 100.0, "profit": 20.0},
            },
            {
                "day": 2,
                "reasoning": "Day 2 plan",
                "actions": {"restocks": 1},
                "results": {"fulfilled": 4, "stockouts": 1, "revenue": 120.0, "profit": 40.0},
            },
            {
                "day": 3,
                "reasoning": "Day 3 plan",
                "actions": {"supplier_orders": 1},
                "results": {"fulfilled": 5, "stockouts": 0, "revenue": 140.0, "profit": 60.0},
            },
        ],
    }

    payload = build_replay_payload(results_payload=results_payload, run_id="replay_test")

    assert payload["run_id"] == "replay_test"
    assert payload["status"] == "completed"
    assert len(payload["frames"]) == 3
    assert payload["current_frame"]["day"] == 3
    assert payload["series"]["day"] == [1, 2, 3]


def test_latest_results_file_picks_newest(tmp_path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    older = results_dir / "grok_proper_sim_1.json"
    newer = results_dir / "grok_proper_sim_2.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    newer.touch()

    picked = _latest_results_file(tmp_path)
    assert picked == newer
