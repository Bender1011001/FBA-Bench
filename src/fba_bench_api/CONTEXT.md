# FBA-Bench API - Context

> **Last Updated**: 2026-01-08

## Purpose

FastAPI-based REST API and WebSocket server for FBA-Bench. Provides HTTP endpoints for simulations, experiments, leaderboards, and real-time streaming for the Godot GUI.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | Entry point - factory pattern for ASGI servers (`uvicorn --factory`) |
| `api/routes/realtime.py` | **Core** - WebSocket handlers for real-time simulation streaming to Godot GUI |
| `api/routes/leaderboard.py` | Leaderboard CRUD and ranking endpoints |
| `api/routes/public_leaderboard.py` | Public-facing leaderboard for fbabench.com |
| `api/routes/experiments.py` | Experiment management, execution, results |
| `api/routes/benchmarks.py` | Benchmark run endpoints |
| `api/routes/simulation.py` | Simulation control (start, stop, run) - now uses real simulation engine |
| `api/routes/scenarios.py` | Scenario configuration and listing |
| `api/routes/golden.py` | Golden master comparison endpoints |
| `api/routes/demo.py` | Demo/sandbox mode endpoints |
| `api/routes/metrics.py` | Prometheus metrics endpoints |
| `core/simulation_runner.py` | **NEW** - Production simulation runner integrating real business logic |

## Directory Structure

```
fba_bench_api/
├── main.py              # Entry point
├── api/
│   ├── routes/          # All FastAPI routers (20 files)
│   └── deps/            # Dependency injection
├── core/                # App configuration, middleware
│   └── simulation_runner.py  # Real simulation runner (new)
├── models/              # Pydantic request/response models
└── server/              # App factory, ASGI config
```

## Real Simulation Engine (2026-01-08)

The `/api/v1/simulation/{id}/run` endpoint now uses the **real simulation engine**:

- **SimulationOrchestrator**: Generates deterministic TickEvents
- **WorldStore**: Canonical state management with command arbitration
- **MarketSimulationService**: Demand calculation using elasticity models AND agent-based customer pools
- **EventBus**: Typed event pub/sub for decoupled architecture

Configuration via simulation metadata:
```json
{
  "max_ticks": 100,
  "seed": 42,
  "use_agent_mode": true,
  "customers_per_tick": 200,
  "elasticity": 1.5,
  "asins": ["ASIN001", "ASIN002"]
}
```

## Dependencies

- **Internal**: `src/services/` (all business logic), `fba_events/` (event types), `fba_bench_core/` (orchestrator)
- **External**: `fastapi`, `uvicorn`, `pydantic`, `websockets`

## Running the Server

```bash
# Development (with hot reload)
python api_server.py
# or
python -m fba_bench_api.main

# Production
uvicorn fba_bench_api.main:get_app --factory --host 0.0.0.0 --port 8000
```

## Architecture Notes

1. **Factory Pattern**: Uses `create_app()` factory to avoid module-level side effects
2. **WebSocket Streaming**: `realtime.py` streams simulation state to Godot GUI via Redis pub/sub
3. **Real Simulation**: `simulation.py` integrates with `RealSimulationRunner` for actual business logic
4. **API Versioning**: Routes are under `/api/v1/`
5. **OpenAPI Docs**: Available at `/docs` (Swagger) and `/redoc`

## ⚠️ Known Issues

*No critical issues identified during audit.*

## Related

- [services](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/services/CONTEXT.md) - Business logic layer
- [godot_gui](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/godot_gui/CONTEXT.md) - WebSocket client
- [fba_bench_core](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_bench_core/CONTEXT.md) - Simulation orchestrator

