# FBA-Bench SaaS Threat Model and Data Isolation Strategy (RLS-First)

## Context
This document drafts the threat model for the FBA-Bench SaaS migration, with a focus on data isolation using Row-Level Security (RLS) in Postgres as the baseline strategy. It identifies key threats, especially around multi-tenancy, and outlines mitigations. This is part of Phase 0 Foundations, building on the data model inventory ([docs/data-model-inventory.md](docs/data-model-inventory.md)) and IAM/queue ADR ([docs/adrs/001-iam-and-queue-selection.md](docs/adrs/001-iam-and-queue-selection.md)). The strategy prioritizes RLS for shared DB to balance simplicity, cost, and security for MVP, with paths to advanced isolation.

## Threat Model Overview
Using STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) framework, scoped to multi-tenancy, auth, data access, and job execution. Assumptions: Hosted on AWS/GCP, Auth0 for IAM, Celery/Redis for queues, RLS on Postgres.

### 1. Spoofing (Impersonation)
- **Threat**: Attacker impersonates another tenant/user to access data (e.g., via stolen JWT or weak auth).
- **Impact**: High – Cross-tenant data access, benchmark result tampering.
- **Mitigations**:
  - Auth0 OIDC with short-lived JWTs (15min access, 1hr refresh); validate issuer, audience, signature in FastAPI dependency ([src/fba_bench_api/api/dependencies.py](src/fba_bench_api/api/dependencies.py)).
  - TenantContext extracts and verifies tenant_id from JWT claims; reject mismatched tenant.
  - Rate limit login attempts; multi-factor auth (MFA) for high-tier plans.

### 2. Tampering (Data Modification)
- **Threat**: Malicious user modifies another tenant's benchmarks, agents, or simulation results via API or DB injection.
- **Impact**: High – Corrupted analytics, unfair leaderboards.
- **Mitigations**:
  - RLS policies on all tenant-owned tables (e.g., benchmarks, agent_runs): `CREATE POLICY tenant_isolation ON benchmarks USING (tenant_id = current_setting('app.current_tenant_id')) WITH CHECK (tenant_id = current_setting('app.current_tenant_id'))`. Set GUC in DB session via SQLAlchemy event listener in app startup.
  - Input validation/sanitization with Pydantic in API routers (e.g., [src/fba_bench_api/api/routers/medusa.py](src/fba_bench_api/api/routers/medusa.py)).
  - Idempotency keys for job submissions; audit logs of all mutations with tenant/user context.

### 3. Repudiation (Non-Reputable Actions)
- **Threat**: User denies running a benchmark or incurring costs; disputes billing.
- **Impact**: Medium – Billing disputes, compliance issues.
- **Mitigations**:
  - Immutable audit trail: Log all actions (job enqueue, run start/end, API calls) to dedicated audit_logs table with tenant_id, user_id, timestamp, IP. Use immutable append-only storage.
  - Stripe webhooks for billing events; sync subscription state to DB.
  - Signed job artifacts in object storage (S3/GCS) with tenant-scoped paths.

### 4. Information Disclosure (Data Leakage)
- **Threat**: Unauthorized access to sensitive data (e.g., proprietary agent configs, run results, API keys in logs).
- **Impact**: Critical – IP theft, competitive advantage loss.
- **Mitigations**:
  - RLS as primary isolation: Enforce on SELECT/INSERT/UPDATE/DELETE for high-priority entities (benchmarks, agents, events from [docs/data-model-inventory.md](docs/data-model-inventory.md)). Default DENY policy.
  - Query scoping: All services (e.g., src/services/benchmarking.py) filter by tenant_id via TenantContext.
  - Log redaction: Sanitize PII/agent configs in logs ([src/fba_bench/core/logging.py](src/fba_bench/core/logging.py)); use structured logging with trace IDs.
  - Least privilege: API keys scoped to tenant; no global read access.

### 5. Denial of Service (DoS)
- **Threat**: Resource exhaustion (e.g., infinite job loops, DB query floods, Redis backlog from malicious benchmarks).
- **Impact**: High – Platform downtime, cost spikes from LLM calls.
- **Mitigations**:
  - Per-tenant quotas (runs/day, compute hours) enforced in API/job orchestrator; usage metering in DB.
  - Rate limiting at API gateway (e.g., 100 req/min per tenant) and Celery worker concurrency limits.
  - Job timeouts (e.g., 2hr max per benchmark); circuit breakers for external LLM calls.
  - Autoscaling with resource limits (Kubernetes pod limits); Redis eviction policies.

### 6. Elevation of Privilege (EoP)
- **Threat**: User escalates from viewer to admin, accessing global configs or other tenants.
- **Impact**: Critical – Full compromise.
- **Mitigations**:
  - RBAC via Auth0 roles (viewer, admin, owner) checked in dependencies.py; no implicit escalation.
  - Separate admin endpoints with elevated checks (e.g., /admin/tenants).
  - Principle of least privilege in DB roles; app user has no superuser rights.

## Data Isolation Strategy: RLS-First
- **Why RLS?**: Enforces isolation at DB level without schema proliferation. Cost-effective for MVP (single DB instance), performant with indexes on tenant_id, easy to audit/test. Aligns with Postgres strengths; supports hybrid (RLS + schema-per-tenant later).
- **Implementation**:
  - **Tables**: Add tenant_id (UUID, FK to tenants.id, indexed) to all tenant-owned entities (benchmarks, agent_runs, events, etc.). New tables: tenants (id, name, plan_tier), tenant_memberships (tenant_id, user_id, role), subscriptions (tenant_id, stripe_id, status).
  - **Policies**: Per-table RLS with USING/CHECK clauses on tenant_id. Enable RLS: `ALTER TABLE benchmarks ENABLE ROW LEVEL SECURITY;`. Set session: In SQLAlchemy, use event.listen to `SET app.current_tenant_id = :tenant_id` on connect.
  - **Enforcement**: TenantContext in API sets session var; services propagate to queries (e.g., .filter(Benchmark.tenant_id == current_tenant)). Workers inherit via env var or DB connection pooling with tenant context.
  - **Bypass for Admins**: Separate superuser role with policy exemptions for global queries.
  - **Testing**: Unit tests for RLS (force different tenant_id, assert no access); integration tests with multi-tenant fixtures.
  - **Limitations & Evolution**: RLS overhead on large tables (mitigate with partitioning by tenant_id in Phase 2). For ultra-sensitive tenants, offer schema-per-tenant (dynamic schema creation on signup).
- **Global Entities**: Shared tables (e.g., system_configs, public_scenarios) without RLS or with admin-only access.
- **Queue/Storage Alignment**: Celery tasks include tenant_id metadata; Redis keys prefixed by tenant (e.g., "tenant:{id}:jobs"). Object storage paths: "tenants/{tenant_id}/runs/{run_id}/".

## Risks Specific to Isolation
- **Incomplete Scoping**: Forgotten tenant filter in legacy query → leakage.
  - Mitigation: Code scan for raw SQL; static analysis tool (e.g., sqlfluff); mandatory TenantContext in service methods.
- **Session Var Tampering**: Attacker sets GUC directly.
  - Mitigation: App-only DB user with no SET rights; validate var on each query.
- **Performance Degradation**: RLS policy evaluation overhead.
  - Mitigation: Index tenant_id; cache frequent queries; monitor query plans.

## Next Steps
- Prototype RLS in local DB ([scripts/init-db.sql](scripts/init-db.sql)) with sample tables.
- Update data model inventory with tenant_id additions.
- Integrate with IAM spike (Auth0 tenant orgs map to DB tenants).

Date: 2025-09-28
Author: Master Engineer
