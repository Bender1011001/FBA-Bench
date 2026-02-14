# Project Context (for coding agent)

## What this is

FBA-Bench Enterprise is a high-fidelity business simulation benchmark for evaluating AI in complex e-commerce scenarios. It simulates market dynamics, inventory management, and adversarial events over extended timelines.

## Current goal

- Standardize project documentation and agent rules across all repos.
- Fix any remaining documentation drift between `AGENTS.md`, `README.md`, and `CONTRIBUTING.md`.
- Ensure all "How to run" commands are 100% copy/pasteable and verified.

## Repo map

- `src/` — Core application logic (`fba_bench_core`, `fba_bench_api`, `agents`, `agent_runners`, etc.)
- `tests/` — Comprehensive test suite (unit, integration, contracts, performance)
- `alembic/` — Database migrations for the FastAPI backend
- `config/` & `configs/` — YAML configurations for simulations and models
- `scripts/` — Utility scripts for orchestration and validation
- `docs/` — Deeper technical documentation and guides
- `godot_gui/` — Immersive GUI for simulation visualization

## How to run

- **Install:**
  ```powershell
  poetry install
  ```

- **Dev:**
  ```powershell
  # Start the API server
  poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 127.0.0.1 --port 8000
  ```

- **Test:**
  ```powershell
  # Run all unit/contract tests
  make test-contracts
  # Run full suite with coverage
  make test-all
  ```

- **Lint/format:**
  ```powershell
  make lint
  make format-fix
  ```

- **Build:**
  ```powershell
  docker compose -f docker-compose.yml build
  ```

- **Deploy:**
  ```powershell
  # Dev deployment
  docker compose -f docker-compose.dev.yml up -d
  ```

## Environment

- **Required tools/versions:**
  - Python 3.9–3.12
  - Poetry
  - Make
  - Godot 4.5+ (optional, for GUI)

- **Secrets/env vars:**
  - See `.env.example` for required keys. Never commit real secrets.

## Conventions (hard rules)

- **Language/framework patterns:** Python 3.9+; Pydantic for data models/settings; FastAPI for API.
- **Formatting/lint rules:** Ruff for linting, Black for formatting, Mypy for strict typing on `src/`.
- **Error handling/logging expectations:** Use structured logging; keep public APIs typed; avoid cyclic imports.
- **API/client conventions:** Use Conventional Commits (`feat(scope): ...`). PRs require rationale and validation results.

## Known landmines

- **Slow commands:** `make test-all` and `make ci-local` can take several minutes due to simulation length.
- **OS-specific issues:** Windows requires `pwsh` for some `Makefile` targets or Git Bash.
- **"Don't touch" areas:** `golden_masters/` contains reference data for regression testing.

## Decision log (optional)

- **2026-02-13:** Switch to standardized `AGENTS.md` template for cross-repo consistency.
