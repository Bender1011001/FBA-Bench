# FBA-Bench Root

## Status

- **Working**: Core simulation engine, FastAPI backend, Godot GUI, comprehensive test suite, Docker orchestration.
- **Broken**: None currently reported; focus is on code quality hardening.

## Tech Stack

- Python 3.10–3.13
- Poetry (Package Management)
- FastAPI (API Server)
- Pydantic (Data Models/Settings)
- Alembic (PostgreSQL Migrations)
- Godot 4.5+ (GUI)
- Docker & Docker Compose

## Key Files

- `pyproject.toml` — Dependency and tool configuration (Ruff, Black, Mypy).
- `Makefile` — Core development workflow automation.
- `config/simulation_settings.yaml` — Centralized simulation behavior configuration.
- `src/fba_bench_api/main.py` — Entry point for the API server.
- `src/services/production_service.py` — External service integrations (rate limiting, caching, auth).

## Architecture Quirks

- The benchmark uses "Tick-Based Simulation" where each day is a separate LLM call. This is intentional to simulate compounding effects over time.
- Imports must be absolute from `src/` packages to ensure parity between local development and CI (which uses `importlib` mode).
- Testing uses `golden_masters/` for regression testing of simulation outputs. Do not modify these without explicit re-validation.
- Experiment scripts live in `scripts/experiments/` — these are self-contained one-off runners, not part of the core architecture.
- Infrastructure configs live in `config/` (env files, prometheus, grafana, nginx, otel, clearml).
- Scenario/agent YAML configs live in `configs/` (separate from infra config).

## Trap Diary

| Issue                           | Cause                                                                                                | Fix                                                                                                        |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Mypy failures on `src/`         | Cyclic imports in event bus                                                                          | Refactored `fba_events` into separate package.                                                             |
| Slow CI runs                    | Too many integration tests                                                                           | Added `@pytest.mark.integration` and skip by default.                                                      |
| Repo bloat (~610 MB)            | Committed `.exe`, `.mp4`, stray test/log/debug files at root                                         | Purged all junk; updated `.gitignore` with `*.exe`, `*.mp4`, `*debug*.log`, `/test_*.py`, etc.             |
| Legacy import shims             | Old `src/event_bus.py` and `src/simulation_orchestrator.py` files                                    | All consumers updated to canonical `fba_bench_core.*` imports; shims deleted.                              |
| `mock_service.py` naming        | File held real production code despite "mock" name                                                   | Renamed to `production_service.py`, updated all imports.                                                   |
| Quality gates were cosmetic     | Makefile overrode pyproject.toml with blanket lint suppressions; mypy used `follow_imports = "skip"` | Makefile defers to pyproject.toml; mypy uses `follow_imports = "silent"` with `check_untyped_defs = true`. |
| Root script sprawl              | 23 `.py` files at project root                                                                       | Moved experiment scripts to `scripts/experiments/`, utilities to `scripts/`.                               |
| `.env.prod` in Git              | Prod env file with JWT/Stripe secrets committed                                                      | `git rm --cached`; added `.env.prod` to `.gitignore`.                                                      |
| Root file sprawl (Round 2)      | `audit.py`, `api_server.py`, batch launchers, `dashboard.html`, infra configs at root                | Moved to `scripts/`, `docs/`, `config/` respectively.                                                      |
| Empty placeholder dirs          | 11 empty dirs committed (`agents/`, `deploy/`, `ssl/`, `temp/`, etc.)                                | Removed; `.gitignore` blocks recreation.                                                                   |
| Stale `.db` files               | 4 SQLite databases committed to repo                                                                 | Deleted; `*.db` pattern in `.gitignore`.                                                                   |
| `simulation_settings.yaml` path | Scripts referenced root path after move to `config/`                                                 | Updated 3 script defaults to `config/simulation_settings.yaml`.                                            |

## Anti-Patterns (DO NOT)

- **NO Mocks/Simulated Logic:** Never use placeholders. Every function must be fully implemented.
- **NO Relative Imports:** Always use absolute imports from `src`.
- **NO Committed Secrets:** Use `.env` and `pydantic-settings`. Never commit `.env.prod` or `.env.staging`.
- **NO Binaries/Logs in Git:** Never commit `.exe`, `.log`, `.mp4`, `.db`, or large binaries. Use `.gitignore`.
- **NO Stray Test Files at Root:** All tests go in `tests/` or `integration_tests/`.
- **NO Compatibility Shims:** Do not create re-export shims. Fix the consumers to use canonical imports.
- **NO Makefile Lint Overrides:** Lint rules live in `pyproject.toml`, not as `--ignore` flags in the Makefile.
- **NO Root Scripts:** Python scripts go in `scripts/`. Infra configs go in `config/`. Nothing at root except standard files (README, pyproject, Makefile, Dockerfile, conftest).
- **NO Empty Dirs:** If a dir is needed at runtime, code should create it. Don't commit empty placeholder dirs.

## Build / Verify

`make ci-local`
