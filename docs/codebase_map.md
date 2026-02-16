# Codebase Map

This is a high-level map of the repository for readers who want to understand where major systems live.

## Core Packages (`src/`)

- `src/fba_bench_core/`: simulation core (tick orchestration, domain models, canonical Money shim).
- `src/fba_bench_api/`: FastAPI backend (routes, DI container, persistence, Redis/WebSocket realtime).
- `src/fba_events/`: typed event definitions used across services and runners.
- `src/services/`: simulation services (WorldStore, market simulator, supply chain, competitors, fees, dashboards).
- `src/agent_runners/`: runner adapters (LangChain, CrewAI, DIY) + per-day long-term memory consolidation.
- `src/agents/`: reference agents and skill modules (where present/used).
- `src/benchmarking/`: benchmark engine, configs, validators, registries, integration adapters.
- `src/metrics/`: legacy simulation KPI suite (finance/ops/trust/stress/adversarial/cost).
- `src/redteam/`: adversarial event injector + gauntlet runner + resistance scoring.
- `src/reproducibility/`: deterministic RNG, LLM response caching, golden masters, mode controller.
- `src/constraints/`: token/cost/call budget enforcement and gateways.
- `src/plugins/`: plugin framework for scenarios/agents/tools/metrics.
- `src/scenarios/`: scenario definitions and scenario-generation utilities (see `docs/scenarios_system.md`).
- `src/llm_interface/`: provider clients + deterministic wrapper + interfaces/contracts.
- `src/instrumentation/` and `src/observability/`: tracing/metrics/export helpers and analysis tooling.

## UI / Visualization

- `godot_gui/`: Godot 4 Simulation Theater (observer mode). Used for demos, recording, and explainability.

## Docs / Runbooks / Press

- `docs/`: documentation pages for setup, architecture, API, and feature deep-dives.
- `docs/press/`: pre-written posts, outreach, and video runbooks.

## Operations / Orchestration

- `scripts/`: orchestration, smoke tests, batch runners, publishing utilities.
- `docker-compose.*.yml`: dev/prod/one-click stacks.
- `Makefile`: lint/test/typecheck and automation targets.

