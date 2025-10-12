"""Tests for the benchmark execution endpoint."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from fba_bench_core.benchmarking.engine import EngineConfig, EngineReport


@pytest.fixture()
def benchmark_payload() -> dict[str, Any]:
    """Sample benchmark configuration payload."""

    return {
        "scenarios": [
            {
                "key": "enterprise.default",
                "params": {"region": "us-east-1"},
                "repetitions": 2,
            }
        ],
        "runners": [
            {
                "key": "async-runner",
                "config": {"timeout_seconds": 120},
            }
        ],
        "metrics": ["throughput", "success_rate"],
        "validators": ["result_consistency"],
        "parallelism": 2,
    }


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {
                "scenarios": [{"key": "enterprise.default"}],
                "runners": [{"key": "async-runner"}],
            },
            id="minimal",
        ),
    ],
)
def test_run_benchmark_requires_auth(client: TestClient, payload: dict[str, Any]):
    response = client.post("/protected/run-benchmark", json=payload)
    assert response.status_code == 401


def test_run_benchmark_executes_core_engine(
    client: TestClient,
    auth_token: str,
    benchmark_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
):
    observed: dict[str, EngineConfig] = {}

    async def fake_run(config: EngineConfig) -> EngineReport:
        observed["config"] = config
        return EngineReport(
            status="ok",
            totals={"runs": 2, "success": 2, "failed": 0},
            details={"received": config.model_dump()},
        )

    monkeypatch.setattr("api.routers.protected.run_benchmark", fake_run, raising=True)

    response = client.post(
        "/protected/run-benchmark",
        json=benchmark_payload,
        headers=_auth_headers(auth_token),
    )

    assert response.status_code == 200
    assert "config" in observed
    assert isinstance(observed["config"], EngineConfig)
    body = response.json()
    assert body["status"] == "ok"
    assert body["details"]["received"]["scenarios"][0]["key"] == "enterprise.default"
    assert body["details"]["received"]["scenarios"][0]["repetitions"] == 2
    assert body["totals"]["runs"] == 2
