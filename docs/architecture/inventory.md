# FBA-Bench — Phase 0 Inventory

## Repository Overview
- **[src/fba_bench_core/](src/fba_bench_core)**: Core business logic package for FBA simulation framework. Includes models (e.g., product.py, sales_result.py), services (e.g., sales_service.py, trust_score_service.py), and utilities like event_bus.py (compatibility shim for event handling), money.py (financial calculations), and simulation_orchestrator.py (orchestrates simulation flows).
- **[src/fba_bench_core/event_bus.py](src/fba_bench_core/event_bus.py)**: Legacy compatibility module bridging to fba_events.bus. Provides EventBus singleton, subscribe/publish APIs, and backends (InMemoryEventBus, AsyncioQueueBackend shim) for typed event dispatching in simulations and services.
- **[src/fba_bench_api/](src/fba_bench_api)**: FastAPI-based API layer for the benchmark system. Contains routes (e.g., experiments.py, medusa.py), models (e.g., experiment.py, simulation.py), core persistence (database.py, redis_client.py), and server setup (app_factory.py). Handles endpoints for simulations, leaderboards, and metrics.
- **[godot_gui/](godot_gui)**: Godot 4 GUI application for immersive simulation visualization. Includes autoload singletons (ApiClient.gd, WebSocketClient.gd, SimulationState.gd), scenes (SimulationViewer, Leaderboard, Sandbox), and real-time data streaming via WebSocket. Replaces the deprecated React frontend.
- **[Makefile](Makefile)**: Build and development orchestration. Defines targets for linting (ruff/black), testing (pytest contracts/all), type-checking (mypy), migrations (alembic), and CI parity (ci-local). Includes legacy shims (be-migrate) and deployment (deploy-prod).
- **[.github/workflows/ci.yml](.github/workflows/ci.yml)**: GitHub Actions workflow for CI/CD. Runs on push/PR to main/master; tests Python 3.9/3.10 with Poetry, pre-commit, lint/format/type checks, pytest (contracts/coverage), pip-audit, and uploads artifacts (coverage.xml, quality-gate-results.json). Enforces 80% coverage threshold.
- **[golden_masters/](golden_masters)**: Directory for baseline benchmark outputs. Contains golden_run_baseline/ subdir with timestamped runs (e.g., golden_run_baseline_20250831-032708/), each holding experiment_config.yaml, summary.json, and run_*.json for regression testing against expected simulation results.

## Directory Tree (abridged)
```
src/
├── fba_bench_core/
│   ├── core/ (fba_types.py, logging.py)
│   ├── models/ (product.py, sales_result.py)
│   └── services/ (sales_service.py, trust_score_service.py, world_store/)
├── fba_bench_api/
│   ├── api/routes/ (experiments.py, medusa.py)
│   ├── core/ (database.py, redis_client.py)
│   └── models/ (experiment.py, simulation.py)
godot_gui/
├── autoload/ (ApiClient.gd, WebSocketClient.gd, SimulationState.gd)
├── scenes/
│   ├── main/ (Main.tscn, Main.gd)
│   ├── simulation/ (SimulationViewer.tscn, SimulationViewer.gd)
│   ├── leaderboard/ (Leaderboard.tscn, Leaderboard.gd)
│   └── sandbox/ (Sandbox.tscn, Sandbox.gd)
└── project.godot
golden_masters/
└── golden_run_baseline/ (timestamped runs with config.yaml, summary.json)
```

## Key Manifests Summary
- **pyproject.toml**:
  - Packages: 21 installable from src/ (e.g., fba_bench_core, fba_bench_api, agents, benchmarking, fba_events, scenarios, plugins).
  - Dependencies: Core (fastapi^0.104.1, uvicorn^0.24.0, pydantic^2.5.0, sqlalchemy^2.0.23, alembic^1.12.0, redis^5.0.0, celery^5.3.0); LLM/ML (openai^1.3.0, anthropic^0.3.0, torch^2.1.0, transformers^4.35.0); Tools (pytest^7.4.0, black^23.10.0, ruff^0.1.0, mypy^1.6.0); Extras: opentelemetry for observability.
  - Scripts: fba = "scripts.cli:cli".
  - Tooling: ruff (line-length=100), black (line-length=100), isort (profile=black), mypy (strict=true), pytest (markers: unit/integration/contract/validation/performance/asyncio).
- **Godot GUI (godot_gui/project.godot)**:
  - Built with Godot 4.3+
  - Autoloads: ApiClient, WebSocketClient, SimulationState
  - Main scene: scenes/main/Main.tscn
  - Communication: REST API (HTTPRequest), WebSocket (WebSocketPeer)

## Gaps and Risks
- Incomplete routes in src/fba_bench_api/api/routes/ (e.g., benchmarks.py has commented services per audit notes): Potential legacy/WIP code. Risk: Unstable API endpoints during Phase 0 testing; may cause integration failures. Follow-up: Audit and stub/complete for stabilization.
- No explicit tests/performance/ subdir (perf tests scattered, e.g., tests/benchmarks/performance_benchmarks.py): Violates AGENTS.md guidelines. Risk: Harder to isolate load/stress tests; impacts benchmarking reliability. Follow-up: Restructure tests/ for dedicated performance/.
- No duplicates for event_bus.py (single legacy shim in fba_bench_core/); fba_events/ handles modern events. Risk: Low, but migration to fba_events.bus needed for full deprecation. Follow-up: Verify no hidden duplicates via full search.
- golden_masters/ lacks recent runs (last 2025-08-31); may not cover latest features. Risk: Regression testing gaps for new simulations. Follow-up: Generate fresh baselines post-stabilization.

## Next Actions
- Run make ci-local to baseline current quality gates and identify immediate test failures.
- Audit src/fba_bench_api/ for completeness (e.g., uncomment/stub routes, migrate legacy shims).
- Restructure tests/ to include performance/ subdir and update pytest markers.
- Generate updated golden_masters/ runs for regression validation.
- Proceed to Phase 0 deeper audits: event system integration, API persistence, and Godot-backend alignment.
