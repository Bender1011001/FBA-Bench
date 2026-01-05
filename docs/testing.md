# Testing Strategy

FBA-Bench Enterprise employs a comprehensive testing strategy using pytest to ensure code quality, reliability, and maintainability. Tests are organized under `tests/`, mirroring the `src/` structure for easy navigation. The approach covers unit, integration, contract, validation, and performance testing, with CI parity via Makefile targets.

## Testing Philosophy

- **Test Pyramid**: Emphasize unit tests (fast, isolated) at the base, fewer integration tests, and end-to-end sparingly.
- **Markers**: Use pytest markers for categorization (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.).
- **Coverage**: Target >80% for `src/`; collected via `make test-all` (generates `.coverage` and `coverage.xml`).
- **Fixtures**: Shared setup in `tests/fixtures/` and `tests/conftest.py` (e.g., DB sessions, mock LLMs).
- **Isolation**: Tests use in-memory SQLite; mocks for external services (e.g., OpenAI, Stripe, ClearML).
- **Idempotency**: Tests are repeatable; no side effects on real data.
- **Parallelism**: Pytest runs in parallel where possible; disable for flaky tests.

Run all unit/contract tests before commits: `poetry run pytest -q && make test-contracts`.

## Test Types

### 1. Unit Tests (`tests/unit/`)
- **Scope**: Individual functions/classes in isolation (e.g., validator logic in `src/benchmarking/validators/`).
- **Characteristics**: Fast (<1s total), no DB/external calls, mocks for dependencies.
- **Examples**:
  - `tests/benchmarking/test_validators_unit.py`: Test `Validator` methods.
  - `tests/agent_runners/test_unified_runner_factory.py`: Factory instantiation.
- **Run**: `poetry run pytest tests/unit/ -v` (default; skips integration).

### 2. Integration Tests (`tests/integration/`)
- **Scope**: Interactions between modules (e.g., agent runner + scenario execution).
- **Characteristics**: Use test DB (SQLite), real configs from `configs/`, but mock LLMs/APIs. Marked `@pytest.mark.integration`.
- **Examples**:
  - `tests/integration/test_agent_integration.py`: End-to-end agent run.
  - `tests/integration/api/test_simulation_api.py`: API endpoint flows.
  - `tests/integration/runners/test_crewai_runner.py`: Framework-specific integration.
- **Run**: `poetry run pytest -m integration -v` (explicit; ~30s).

### 3. Contract Tests (`tests/contracts/`)
- **Scope**: API schema validation, Pydantic models, and response contracts (e.g., OpenAPI compliance).
- **Characteristics**: No business logic; focus on inputs/outputs. Uses `pytest` with `responses` for HTTP mocks.
- **Examples**:
  - `tests/contracts/test_api_schemas.py`: Request/response validation.
  - `tests/contracts/test_event_schemas.py`: `fba_events` models.
- **Run**: `make test-contracts` (fast, CI-critical).

### 4. Validation Tests (`tests/validation/`)
- **Scope**: Data integrity, invariants, and edge cases (e.g., invalid configs, constraint enforcement).
- **Characteristics**: Overlaps with unit; ensures assumptions hold (e.g., token counting accuracy).
- **Examples**:
  - `tests/validation/test_config_validation.py`: YAML/Pydantic parsing.
  - `tests/validation/test_scenario_invariants.py`: Simulation rules.
- **Run**: Included in `make test-all`.

### 5. Performance Tests (`tests/performance/`)
- **Scope**: Benchmark timings, memory usage, scalability (e.g., multi-agent runs).
- **Characteristics**: Use `pytest-benchmark` or custom timers; run on CI with thresholds.
- **Examples**:
  - `tests/performance/test_simulation_scalability.py`: Load testing scenarios.
  - `tests/performance/test_llm_latency.py`: API response times.
- **Run**: `poetry run pytest tests/performance/ --benchmark-only` (manual; resource-intensive).

### 6. Real-time & WebSocket Stress Tests
- **Scope**: Validate the stability and performance of the real-time WebSocket infrastructure (`/ws/realtime`).
- **Characteristics**: Uses `scripts/smoke/ws_smoke.py` to flood channels with high-frequency updates (e.g., verifying Godot GUI responsiveness).
- **Run**:
  ```bash
  # Flood simulation-progress topic at 20Hz for 30s
  python scripts/smoke/ws_smoke.py --url "ws://localhost:8000/ws/realtime" --jwt "test" --rate 20 --topic "simulation-progress" --duration 30
  ```

## Running Tests

### Basic Commands
- **All Fast Tests**: `poetry run pytest -q` (unit/contracts; skips integration).
- **Full Suite**: `make test-all` (all + coverage; ~2min).
- **Specific Marker**: `poetry run pytest -m unit -v`.
- **With Coverage**: `poetry run pytest --cov=src --cov-report=html tests/` (opens `htmlcov/index.html`).
- **Local CI**: `make ci-local` (lint + format + types + tests).

### Advanced
- **Parallel**: `poetry run pytest -n auto` (requires `pytest-xdist`).
- **Debug**: `poetry run pytest --pdb tests/my_test.py::test_func` (breakpoint on fail).
- **Integration with DB**: Tests auto-use `test.db`; override via `TEST_DATABASE_URL` in `.env`.
- **Mock External**: Patched in fixtures (e.g., `monkeypatch.setattr(llm_client, 'call', mock_response)`).

### CI Integration
- GitHub Actions (`.github/workflows/ci.yml`): Runs `make ci-local` on push/PR.
- Pre-commit hooks: `make pre-commit-install`; enforces on commit (lint, types, tests).
- Coverage upload: To Codecov or artifact in CI.

## Best Practices

- **One Assertion per Test**: Clear, focused tests.
- **Parametrize**: Use `@pytest.mark.parametrize` for variants (e.g., multiple models).
- **Fixtures**: Scope appropriately (`function` default; `session` for DB setup).
- **Mocks**: Use `pytest-mock` or `unittest.mock`; avoid over-mocking.
- **Flakiness**: Seed randoms; retry on network (rare, since mocked).
- **New Tests**: Add for new features; place in corresponding dir (e.g., `tests/src/fba_bench_api/`).
- **Coverage Gaps**: Run `make test-all`; address in PRs.

## Tools and Configuration

- **Framework**: Pytest 7+ with plugins: `pytest-cov`, `pytest-mock`, `pytest-asyncio` (for async).
- **Config**: `pytest.ini` in `tests/` (add markers, change dirs).
- **DB Fixtures**: `conftest.py` creates/teardown test DB per session.
- **Async Tests**: Mark `@pytest.mark.asyncio` for coroutines.
- **Benchmarking**: `pytest-benchmark` for perf; compare runs.

For troubleshooting flaky tests, see [troubleshooting/tests.md](troubleshooting/tests.md) if available.

This strategy ensures robust coverage, with `make ci-local` as the gatekeeper for contributions.
