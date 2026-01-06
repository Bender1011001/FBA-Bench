# FBA-Bench API - Context

> **Last Updated**: 2026-01-05

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
| `api/routes/simulation.py` | Simulation control (start, stop, step) |
| `api/routes/scenarios.py` | Scenario configuration and listing |
| `api/routes/golden.py` | Golden master comparison endpoints |
| `api/routes/demo.py` | Demo/sandbox mode endpoints |
| `api/routes/metrics.py` | Prometheus metrics endpoints |

## Directory Structure

```
fba_bench_api/
├── main.py              # Entry point
├── api/
│   ├── routes/          # All FastAPI routers (20 files)
│   └── deps/            # Dependency injection
├── core/                # App configuration, middleware
├── models/              # Pydantic request/response models
└── server/              # App factory, ASGI config
```

## Dependencies

- **Internal**: `src/services/` (all business logic), `fba_events/` (event types)
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
3. **API Versioning**: Routes are under `/api/v1/`
4. **OpenAPI Docs**: Available at `/docs` (Swagger) and `/redoc`

## ⚠️ Known Issues

*No critical issues identified during audit.*

## Related

- [services](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/services/CONTEXT.md) - Business logic layer
- [godot_gui](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/godot_gui/CONTEXT.md) - WebSocket client
