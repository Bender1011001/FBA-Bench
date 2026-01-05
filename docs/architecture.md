# Architecture Overview

FBA-Bench Enterprise is a modular, scalable framework for benchmarking AI agents in simulated e-commerce environments. It follows a clean `src/`-based package structure managed by Poetry, enabling isolated development, testing, and deployment. The architecture emphasizes separation of concerns, extensibility via plugins, and observability for production use.

## High-Level Components

The system is organized into core packages under `src/`, each handling specific domains. Key relationships include:

- **fba_bench_core**: Foundational services for simulation management.
  - **World Store**: Persistent state management for simulations (`src/fba_bench_core/services/world_store/`).
  - **Event Bus**: Asynchronous event handling (`src/fba_bench_core/services/event_bus/`).
  - **Cost Tracking**: Monitors token usage and expenses (`src/fba_bench_core/services/cost_tracking/`).
  - Relationships: Provides shared utilities to all other modules; depends on `fba_events` for pub/sub.

- **fba_bench_api**: FastAPI-based web services for external interactions.
  - **Main App**: Entry point at `src/fba_bench_api/main.py`, serving endpoints for simulations, experiments, and metrics.
  - **Routers**: Modular endpoints (e.g., `/simulations`, `/experiments`, `/metrics`) in `src/fba_bench_api/routers/`.
  - **Dependencies**: Uses `dependency_injector` for DI (`src/dependency_injector/`).
  - Relationships: Integrates with `fba_bench_core` for business logic; exposes `agents` and `benchmarking` via API. Database interactions via Alembic-migrated schemas.

- **agents**: AI agent implementations and personas.
  - **Baseline Bots**: Simple rule-based agents (`src/agents/baseline_bots/`).
  - **Learning Agents**: Adaptive agents with memory (`src/agents/learning/`).
  - Relationships: Consumes `scenarios` for execution; interacts with `agent_runners` for orchestration.

- **agent_runners**: Framework-agnostic runners for executing agents.
  - **Unified Factory**: Abstracts runners like CrewAI and LangChain (`src/agent_runners/unified_runner_factory.py`).
  - **Runners**: Specific implementations (`src/agent_runners/runners/`).
  - Relationships: Bridges `agents` and `scenarios`; reports metrics to `benchmarking`.

- **benchmarking**: Evaluation engine for agent performance.
  - **Validators**: Custom validators for success criteria (`src/benchmarking/validators/`).
  - **Metrics**: Scoring and reporting (`src/benchmarking/metrics/`).
  - **Engine**: Orchestrates runs (`src/benchmarking/engine/`).
  - Relationships: Depends on `scenarios` for test cases; integrates with `fba_events` for real-time updates.

- **scenarios**: Simulation blueprints and business logic.
  - **Core Scenarios**: E-commerce flows like sourcing and fulfillment (`src/scenarios/core/`).
  - **Advanced**: Multi-agent and adversarial scenarios (`src/scenarios/advanced/`).
  - Relationships: Defines environments for `agents`; validated by `benchmarking`.

- **plugins**: Extensible components for tools and integrations.
  - **Skills**: Reusable agent capabilities (e.g., calculator, summarizer) in `src/plugins/skills/`.
  - **Constraints**: Budget and token limits (`src/plugins/constraints/`).
  - Relationships: Pluggable into `agents` and `scenarios`; configurable via `configs/`.

- **fba_events**: Event-driven communication layer.
  - **Models and Handlers**: Event schemas and processing (`src/fba_events/models/` and `src/fba_events/handlers/`).
  - Relationships: Used across modules for loose coupling; integrates with WebSockets in `fba_bench_api`.

## Data Flow

1. **Simulation Initiation**: API request to `fba_bench_api` triggers a scenario from `scenarios`.
2. **Agent Execution**: `agent_runners` selects and runs an agent from `agents`, injecting plugins.
3. **State Management**: `fba_bench_core` (World Store) persists simulation state; events flow via `fba_events`.
4. **Evaluation**: `benchmarking` validators assess outcomes, generating metrics.
5. **Persistence and Observability**: Results stored in DB (via Alembic); tracked in ClearML/Prometheus.

Example flow for a benchmark run:
- API: POST `/experiments/run` → Loads config from `configs/`.
- Core: Initializes World Store.
- Runner: Executes agent in scenario.
- Benchmarking: Validates and scores.
- Events: Streams updates to dashboard.

## Infrastructure and Dependencies

- **Database**: SQLite for local dev (default); PostgreSQL for production. Migrations in `alembic/` via `make be-migrate`.
- **Caching and Queues**: Redis for session state and event queuing (configured in `config/`).
- **Observability**:
  - ClearML: Experiment tracking (`src/instrumentation/clearml_tracking.py`).
  - Prometheus/Grafana: Metrics collection (`config/prometheus/` and `config/grafana/`).
  - OpenTelemetry: Tracing (`config/observability/`).
- **LLM Interface**: Unified client in `src/llm_interface/` supporting OpenAI, OpenRouter, etc., via env vars.
- **Deployment**: Docker Compose setups in `docker-compose.*.yml` for dev/full/prod. Nginx for routing.

## API Entry Points

- **Base URL**: `/` (e.g., http://localhost:8000).
- **Key Endpoints**:
  - `/simulations/{id}`: Manage simulations (GET/POST/PUT).
  - `/experiments`: Run and monitor benchmarks (POST `/run`, GET `/results`).
  - `/agents`: Register and list agents (POST `/register`, GET `/list`).
  - `/metrics`: Retrieve performance data (GET `/dashboard`).
  - `/auth`: User authentication (POST `/login`, GET `/me`).
  - WebSockets: `/ws/events` for real-time updates.
- OpenAPI docs: `/docs` (Swagger UI).

All endpoints use Pydantic for validation; auth via JWT (configurable expiry in `.env`).

## Relationships and Dependencies

- **Core Dependencies**: `fba_bench_core` → `fba_events` (events), `llm_interface` (AI calls).
- **API Layer**: Depends on all packages; injects via `dependency_injector`.
- **Modularity**: Absolute imports from `src/` (e.g., `from services import ...`). Avoid cycles via layered design (core → api).
- **Configs**: YAML in `config/` and `configs/` loaded via Pydantic Settings; overrides via `.env`.
- **Testing**: Pytest in `tests/` with markers (`unit`, `integration`); fixtures in `tests/fixtures/`.

This architecture supports scaling via Docker/Kubernetes, with plugins enabling custom extensions without core changes.

For deployment details, see [deployment.md](deployment.md). For API specifics, see [api.md](api.md).
