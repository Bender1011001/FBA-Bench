# FBA-Bench Data Model Inventory

This document inventories the current database models and entities in FBA-Bench, identifying potential tenant-owned entities for multi-tenancy in the SaaS migration. Based on codebase analysis, the project uses SQLAlchemy for ORM, with models primarily in test/integration files (likely mirroring production) and service layers. The schema focuses on benchmarking, simulations, agents, events, and metrics. No central models.py was found in src/fba_bench_api/models, suggesting models are distributed or Pydantic-heavy with SQLAlchemy in specific services.

## Current Models and Tables (from Codebase Search)

### 1. Benchmark-Related Models (from tests/integration/test_database_api_integration.py)
These represent core benchmarking entities. Likely production models are similar or in src/services or src/fba_bench_api/models.

- **BenchmarkModel** (`__tablename__ = "benchmarks"`)
  - Fields: id (String, PK), scenario_name (String), agent_ids (Text, JSON), metric_names (Text, JSON), start_time (DateTime), end_time (DateTime), duration_seconds (Float), success (Boolean), errors (Text, JSON), results (Text, JSON), created_at (DateTime), updated_at (DateTime)
  - Relationships: metrics (BenchmarkMetricModel), validations (BenchmarkValidationModel)
  - Purpose: Stores benchmark run metadata.

- **BenchmarkMetricModel** (`__tablename__ = "benchmark_metrics"`)
  - Fields: id (String, PK), benchmark_id (String, FK to benchmarks.id), name (String), value (Float), unit (String), timestamp (DateTime)
  - Relationships: benchmark (BenchmarkModel)
  - Purpose: Individual metric values per benchmark.

- **BenchmarkValidationModel** (`__tablename__ = "benchmark_validations"`)
  - Fields: id (String, PK), benchmark_id (String, FK to benchmarks.id), validator_name (String), validation_type (String), result (Boolean), score (Float), details (Text, JSON), timestamp (DateTime)
  - Relationships: benchmark (BenchmarkModel)
  - Purpose: Validation results for benchmarks.

### 2. Other Potential Entities (Inferred from Project Structure and Code)
From src/services (e.g., customer_event_service, sales_service, world_store) and src/fba_events, the project likely has models for:

- **Event Models** (from src/fba_events/*): Events like AgentEvent, CustomerEvent, SalesEvent, InventoryEvent, etc. Tables: events, fba_events (with subtypes via discriminator or separate tables).
  - Fields (inferred): id, type, timestamp, data (JSON), entity_id (FK to related entity like agent or customer).
  - Purpose: Simulation events.

- **Agent Models** (from src/agents/*): Agents, AgentRuns. Tables: agents, agent_runs.
  - Fields: id, name, config (JSON), status, created_at.
  - Purpose: AI agents and their executions.

- **Scenario Models** (from src/scenarios/*): Scenarios, ScenarioConfigs. Tables: scenarios, scenario_runs.
  - Fields: id, name, config (YAML/JSON), tier (e.g., t0, t1), parameters.
  - Purpose: Benchmark scenarios.

- **User/Dashboard Models** (inferred from frontend and API): Users, Sessions (basic auth). Tables: users (if any), sessions.
  - Fields: id, email, api_key, created_at.
  - Purpose: Basic user management (extend for SaaS).

- **Service-Specific Models** (from src/services/*):
  - WorldStore, Ledger (double_entry_ledger_service): Tables: world_state, ledger_entries.
  - CustomerReputation, TrustScore: Tables: customers, reputations, trust_scores.
  - Dispute, FeeCalculation: Tables: disputes, fees.
  - Purpose: Simulation state and business logic persistence.

- **Observability/Metrics Models** (inferred): Run logs, metrics. Tables: logs, metrics (or external like ClearML).

### 3. Alembic Migrations (from alembic/versions/)
- Current migrations: Baseline models (e.g., 0002_models_baseline.py) likely create initial tables like users, events, benchmarks.
- No explicit tenant tables yet; migrations are for core schema.

### 4. Tenant-Owned Entities Identification
For multi-tenancy (RLS or schema-per-tenant), classify entities:

- **High Priority (Per-Tenant Isolation Required)**:
  - Benchmarks, BenchmarkMetrics, BenchmarkValidations: Run results, metrics – isolate to prevent data leakage.
  - AgentRuns, Agents: User-submitted agents and executions.
  - ScenarioRuns: User-specific simulation runs.
  - Events (fba_events): Simulation events tied to user runs.
  - Artifacts/Logs: Run outputs, reports – store per-tenant in object storage with DB metadata.
  - UsageMetering: Billing data per tenant.

- **Medium Priority (Shared with Tenant Scoping)**:
  - Scenarios: Core scenarios shared, but user customizations/forks per-tenant.
  - WorldState, LedgerEntries: Simulation state – scope to tenant runs.
  - Customers, Sales, Inventory: Simulation entities – per-run isolation.

- **Low Priority (Global or Admin-Only)**:
  - Users, Tenants, Subscriptions: SaaS management tables (global with tenant FKs).
  - System Metrics/Logs: Aggregated, anonymized for ops.

- **New Entities for SaaS**:
  - Tenants: id, name, plan_tier, created_at.
  - TenantMemberships: tenant_id, user_id, role.
  - Subscriptions: tenant_id, stripe_id, status, usage_quota.

### 5. Recommendations for Phase 0
- Add tenant_id FK to all high/medium priority tables via new Alembic migration.
- Implement RLS policies on tenant-owned tables.
- Audit queries in services (e.g., src/services/benchmarking.py) to ensure tenant filtering.
- Test isolation with multi-tenant fixtures in tests/integration/.

This inventory is based on code searches; full scan of src/fba_bench_api/models and src/services may reveal more. Next: Threat model.
