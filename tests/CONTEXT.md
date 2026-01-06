# Tests - Context

> **Last Updated**: 2026-01-05

## Purpose

Comprehensive test suite for FBA-Bench Enterprise, following a testing pyramid approach (Unit, Integration, E2E, Performance, Validation).

## Testing Architecture

- **Framework**: `pytest` with `pytest-asyncio` and `pytest-mock`.
- **Database**: Uses a shared SQLite database (`test_shared.db`) for all tests, managed via fixtures in `conftest.py`.
- **Environment**: `TESTING=true` environment variable is set during test sessions to trigger mock behaviors in services.

## Key Files

| File | Description |
|------|-------------|
| `conftest.py` | Central fixture management (DB setup, FastAPI client, Auth tokens). |
| `TESTING_STRATEGY.md` | Detailed documentation on overall testing philosophy and organization. |
| `pytest.ini` | Test configuration, markers (asyncio), and logging settings. |
| `test_missing_features.py`| Verification of previously missing logic (Multi-agent negotiation, Agent learning). |

## Core Subdirectories

| Directory | Type | Description |
|-----------|------|-------------|
| `unit/` | Unit | Isolated tests for core components. |
| `integration/` | Integration | Cross-service interaction tests. |
| `api/` | Integration | FastAPI endpoint testing using `TestClient`. |
| `curriculum/` | Validation | Tests for agent progression through difficulty tiers. |
| `performance/` | Performance | Load testing and resource utilization monitoring. |
| `regression/` | Regression | Ensuring old bugs don't return. |
| `contracts/` | Contract | Verifying API schema consistency. |

## Mocking Strategy

- **External APIs**: Mocked using `responses` or `pytest-mock`.
- **LLMs**: Mocked in unit tests; integration tests may use small local models or mocks via `BaseAgentRunner`.
- **Time**: Simulation time is controlled via `TickEvent` injection rather than real-world sleeps.

## Running Tests

```bash
# Run all tests
pytest

# Run a specific category
pytest tests/unit/

# Run with coverage
pytest --cov=src
```

## ⚠️ Known Issues

| Location | Issue | Severity |
|----------|-------|----------|
| `test_missing_features.py` | Uses heavy mocking for core logic; tests may pass even if real implementation drifts. | Medium |
| `conftest.py` | Database management (unlink/link) can be brittle on Windows due to file locks. | Low |
| `tests/` root | Contains many disparate test files that could be better organized into subdirectories. | Low (Organization) |

## Related

- [TESTING_STRATEGY.md](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/tests/TESTING_STRATEGY.md) - Full strategy document.
- [CONTRIBUTING.md](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/CONTRIBUTING.md) - Coding standards.
