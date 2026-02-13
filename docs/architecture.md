# Architecture Overview

FBA-Bench Enterprise is a Python monorepo built around a tick-based business simulation and two evaluation modes:
- LLM Benchmark: evaluates raw model capability (no hidden scaffolding)
- Agent Benchmark: evaluates an agent system (tools, memory, orchestration allowed)

## Repository Layout (Developer-Oriented)

Core code lives under `src/` and is packaged via Poetry (see `pyproject.toml`).

Key domains:
- `src/fba_bench_core/`: simulation core, models, orchestration, deterministic run behavior
- `src/fba_bench_api/`: FastAPI app factory and HTTP/WebSocket routes
- `src/agents/`: reference agents (baseline + advanced)
- `src/agent_runners/`: adapters for agent frameworks and model providers
- `src/benchmarking/`: benchmark engine, registries, validators
- `src/scenarios/`: scenario definitions and generation
- `src/plugins/`: extension points
- `src/fba_events/`: event bus primitives and event types

## Runtime Components

Local demo stack (one-click):
- Nginx front door: serves `docs/` static site and proxies API/WebSocket to the API container
- API: FastAPI application
- Redis: pub/sub and realtime support

Production stack (typical):
- API container behind a reverse proxy / ingress
- Postgres (or compatible DB)
- Redis
- OpenTelemetry collector and metrics backend (optional but recommended)

## High-Level Data Flow

1. A simulation run is configured (scenario, seed, agent runner, constraints).
2. Each tick:
   - agent runner constructs context
   - model/agent decides actions
   - simulation core applies actions to state and emits events
3. API exposes:
   - control surfaces for starting/stopping/running simulations
   - realtime event streaming via WebSocket
   - leaderboard views and exports

## Entry Points

- API app factory (recommended):
  - `uvicorn fba_bench_api.main:get_app --factory ...`
- Compatibility module (used by Dockerfiles/compose):
  - `api_server.py` exposes `app` for `uvicorn api_server:app ...`

## Related Docs

- Configuration: `docs/configuration.md`
- API: `docs/api/README.md`
- Testing: `docs/testing.md`
- Deployment: `docs/deployment/README.md`

