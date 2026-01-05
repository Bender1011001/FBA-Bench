# FBA-Bench API Data Models Architecture

## Overview
The API data models support the benchmarking and simulation domain of FBA-Bench, focusing on agents, experiments, simulations, and runs. These models interface with the core simulation logic in [src/fba_bench_core/](src/fba_bench_core) by persisting experiment configurations, agent states, and results. The boundary emphasizes API-facing persistence for orchestration and tracking, while core simulations handle transient state. Models use SQLAlchemy ORM for relational storage and Pydantic for request/response validation, enabling async/sync operations in FastAPI endpoints.

## Entities and Relationships
Core entities are defined primarily in [src/fba_bench_api/models/](src/fba_bench_api/models), with additional persistence models in [src/fba_bench_api/core/database.py](src/fba_bench_api/core/database.py). Key fields include identifiers (UUID strings), timestamps (created/updated), status enums, and JSON-encoded configurations/metrics.

- **Agent**: Represents AI agents for benchmarks. Key fields: name, framework (enum: baseline, langchain, crewai, custom), config (JSON). Used in experiments for participant roles.
- **Experiment**: Orchestrates benchmark runs. Key fields: name, description, agent reference, scenario ID, params (JSON), status (enum: draft, running, completed, failed). Links to agents and simulations.
- **Simulation**: Tracks individual simulation instances. Key fields: experiment reference, status (enum: pending, running, stopped, completed, failed), metadata (JSON). Associated with experiments for execution tracking.
- **ExperimentRun**: Manages specific runs within experiments. Key fields: experiment reference, scenario ID, params (JSON), status (enum: pending, starting, running, completed, failed, stopped), progress (tick counts, percentage), timing (start/complete), metrics/results (JSON), error message.
- **ExperimentRunParticipant**: Links agents to runs. Key fields: run reference, agent reference, role, config override (JSON). Ensures unique agent per run.
- **Scenario**: Configuration for benchmark environments (file-based YAML, loaded dynamically). Key fields: ID (from filename), name, description, difficulty tier (0-3), duration, tags, params/success criteria/market conditions/external events/agent constraints (all dicts/lists). Not persisted relationally; managed via service in [src/fba_bench_api/models/scenarios.py](src/fba_bench_api/models/scenarios.py).
- **Template**: Stores reusable configs. Key fields: name, description, config data (JSON). Supports experiment setup.
- **Supporting Entities** (in [src/fba_bench_api/core/database.py](src/fba_bench_api/core/database.py)): ExperimentConfig (tracks experiment progress/metrics), SimulationConfig (holds sim params/agent/LLM settings), Template (as above).

**Relationships** (high-level, from models/migrations):
- One-to-many: Experiment to Simulations (optional FK, SET NULL on delete).
- One-to-many: Experiment to ExperimentRuns (FK, CASCADE on delete).
- Many-to-one: Experiment to Agent (RESTRICT on delete).
- Many-to-many (via junction): ExperimentRun to Agent via ExperimentRunParticipant (unique per run-agent, CASCADE/RESTRICT).
- No direct relationships for Scenarios (file-driven) or Templates (standalone).

**API Usage** (cross-references from [src/fba_bench_api/api/routers/](src/fba_bench_api/api/routers)):
- [experiments.py](src/fba_bench_api/api/routers/experiments.py): Read/write Experiments, ExperimentRuns, Participants (create/status/progress/results endpoints).
- [medusa.py](src/fba_bench_api/api/routers/medusa.py): Interacts with Experiments/Simulations for ML training workflows.
- [templates.py](src/fba_bench_api/api/routers/templates.py): Manages Templates for config reuse.
- [stats.py](src/fba_bench_api/api/routers/stats.py), [leaderboard.py](src/fba_bench_api/api/routers/leaderboard.py): Query ExperimentRuns/metrics for aggregation.

**ER Overview** (text-based):
- Agents ←[one-to-many]→ Experiments ←[one-to-many]→ Simulations
- Experiments ←[one-to-many]→ ExperimentRuns ←[one-to-many]→ ExperimentRunParticipants ←[many-to-one]→ Agents
- Scenarios/Templates: Standalone, referenced by Experiments/Configs

## Persistence and Migrations
Database connections use PostgreSQL/SQLite (configurable via [src/fba_bench_core/config.py](src/fba_bench_core/config.py)), with engines in [src/fba_bench_api/core/database.py](src/fba_bench_api/core/database.py) (sync: SessionLocal, one-per-request, commit/rollback) and [src/fba_bench_api/core/database_async.py](src/fba_bench_api/core/database_async.py) (async: AsyncSession, pool=20, pre-ping/recycle). Schema auto-creates via Base.metadata.create_all (sync/async). Sessions manage transactions explicitly; async supports non-blocking I/O for API scalability. JSON fields use custom TypeDecorators for serialization.

**Migration Mapping** ([alembic/versions/](alembic/versions)):
- 0001_initial_baseline.py: Empty baseline (no-op).
- 0002_models_baseline.py: Introduces Agents (framework enum), Experiments (status enum, agent FK), Simulations (status enum, experiment FK). Adds indexes on names/status/created_at.
- 0003_experiment_runs.py: Adds ExperimentRuns (status enum, experiment/scenario FKs, progress/timing/metrics JSON), ExperimentRunParticipants (run/agent FKs, unique constraint). CASCADE/RESTRICT deletes.

No tenant/billing tables yet; schema evolves from baseline to run tracking.

**Async vs Sync Differences**: Sync for simple ops/simple DB (SQLite); async for high-concurrency (Postgres via asyncpg). Both use same models/metadata; async engine resolves dialects automatically.

## Validation and Constraints
Validation layers: Pydantic BaseModels in [src/fba_bench_api/models/](src/fba_bench_api/models) (e.g., ExperimentRunCreate: field validators for non-empty IDs/unique participants, ge=0 for progress); SQLAlchemy ORM enforces types/enums/FKs in models (e.g., [src/fba_bench_api/models/experiment.py](src/fba_bench_api/models/experiment.py)). Constraints: Unique keys (e.g., run-agent in participants), non-nullable IDs/names/status, indexes (status/created_at/agent_id), enums (status/frameworks), ondelete (RESTRICT/CASCADE/SET NULL). Invariants: Timestamps auto-update (mixin/event listener); JSON fields default to empty dict; progress bounded (0-100%).

## Gaps and Risks
- **Missing Tenancy/Billing**: No tenant_id FKs or billing entities; risks data leakage in multi-user SaaS. Scenarios/templates lack DB persistence (file-based, no versioning/ACLs).
- **Denormalization/Duplication**: JSON params/metrics may duplicate core sim state; no dedicated metrics table for querying.
- **Constraints Gaps**: Nullable scenario_id in Experiments (unsafe if required); missing indexes on FKs (e.g., experiment_id in runs) for join perf; no unique on agent names.
- **Coverage Issues**: [src/fba_bench_api/core/database.py](src/fba_bench_api/core/database.py) models (e.g., ExperimentConfigDB) not in main models/ or migrations; potential sync. Routers like [clearml.py](src/fba_bench_api/api/routers/clearml.py) may reference unmodeled entities.
- **Async/Sync Drift**: Dual setups risk inconsistency; no explicit tenant context in sessions.
- **Validation Limits**: Pydantic forbids extra fields but lacks deep JSON schema validation for configs.

## Next Steps
- Audit/align [src/fba_bench_api/core/database.py](src/fba_bench_api/core/database.py) models to [src/fba_bench_api/models/](src/fba_bench_api/models); autogenerate migration for integration (target: 100% model-migration sync).
- Add tenant_id to all entities (FK to new Tenants table); implement RLS policies; write integration tests for isolation (coverage >80% on new auth/tenant deps).
- Migrate scenarios to DB (add ScenarioORM); add missing indexes/constraints via Alembic (e.g., composite on experiment_id+status).
- Enhance validation: Deep Pydantic for JSON configs; unit tests for enums/invariants (aim: 90% coverage on models/routers).
- Stabilize CI: Add make targets for migration linting (alembic check), DB schema diffs; run full suite post-changes.
