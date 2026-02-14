# FBA-Bench Enterprise Root

## Status

- **Working**: Core simulation engine, FastAPI backend, Godot GUI, comprehensive test suite, Docker orchestration.
- **Broken**: None currently reported; focus is on documentation standardization.

## Tech Stack

- Python 3.9–3.12
- Poetry (Package Management)
- FastAPI (API Server)
- Pydantic (Data Models/Settings)
- Alembic (PostgreSQL Migrations)
- Godot 4.5+ (GUI)
- Docker & Docker Compose

## Key Files

- `AGENTS.md` — Agent rules and project context (following standardized template).
- `pyproject.toml` — Dependency and tool configuration (Ruff, Black, Mypy).
- `Makefile` — Core development workflow automation.
- `simulation_settings.yaml` — Centralized simulation behavior configuration.
- `src/fba_bench_api/main.py` — Entry point for the API server.

## Architecture Quirks

- The benchmark uses "Tick-Based Simulation" where each day is a separate LLM call. This is intentional to simulate compounding effects over time.
- Imports must be absolute from `src/` packages to ensure parity between local development and CI (which uses `importlib` mode).
- Testing uses `golden_masters/` for regression testing of simulation outputs. Do not modify these without explicit re-validation.

## Trap Diary

| Issue | Cause | Fix |
|-------|-------|-----|
| Mypy failures on `src/` | Cyclic imports in event bus | Refactored `fba_events` into separate package. |
| Slow CI runs | Too many integration tests | Added `@pytest.mark.integration` and skip by default. |

## Anti-Patterns (DO NOT)

- **NO Mocks/Simulated Logic:** Never use placeholders. Every function must be fully implemented.
- **NO Relative Imports:** Always use absolute imports from `src`.
- **NO Committed Secrets:** Use `.env` and `pydantic-settings`.

## Build / Verify

`make ci-local`
