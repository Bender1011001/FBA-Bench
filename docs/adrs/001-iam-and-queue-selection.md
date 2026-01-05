# ADR 001: Selection of IAM Provider and Queue Technology for FBA-Bench SaaS

## Context
As part of Phase 0 Foundations, we need to select an Identity and Access Management (IAM) provider for authentication/authorization and a queue technology for job orchestration in the multi-tenant SaaS migration. The choices must be cloud-agnostic where possible, integrate well with the existing FastAPI/React stack, support scalability, and minimize vendor lock-in. Current project uses Celery (for tasks), Redis (caching/queue), and basic auth stubs.

## Decision Drivers
- **IAM**: Secure OIDC/OAuth2 support, easy JWT integration with FastAPI dependencies ([src/fba_bench_api/api/dependencies.py](src/fba_bench_api/api/dependencies.py)), multi-tenant user management, social/federated login, and low ops overhead. Prefer managed service to avoid self-hosting.
- **Queue**: Durable, reliable async job processing for benchmarks/simulations, integration with Celery (already a dependency), horizontal scaling, and portability (on-prem to cloud). Support for dead-letter queues, retries, and monitoring.
- **Constraints**: Maintain local dev compatibility (e.g., mock or dev instances), cost-effective for startup, Python ecosystem compatibility.

## Options Considered

### IAM Providers
1. **Auth0**: Managed OIDC provider with free tier, easy SDKs for FastAPI/React, built-in RBAC, multi-tenancy support via organizations. Integrates with Stripe for user billing linkage.
2. **AWS Cognito**: Native AWS IAM, OIDC compliant, user pools for auth, integrates with API Gateway. Good for AWS hosting but adds lock-in.
3. **Supabase Auth**: Open-source alternative with Postgres backend (aligns with DB), but less mature for enterprise RBAC.
4. **Self-hosted (Keycloak)**: Full control, but high ops burden for startup.

### Queue Technologies
1. **Celery + Redis**: Leverage existing Celery dep, Redis already in Docker setup. Simple, Pythonic, supports distributed workers. Portable (Redis on any cloud/on-prem).
2. **Celery + RabbitMQ**: More robust for high-throughput, but heavier than Redis.
3. **AWS SQS/SNS**: Managed, scalable, but AWS-specific; requires boto3 abstraction.
4. **RQ (Redis Queue)**: Lighter than Celery, but less feature-rich for complex workflows.

## Decision
- **IAM Provider: Auth0**
  - Reasoning: Easiest integration for MVP (auth0-python SDK for FastAPI, auth0-spa-js for React). Supports tenant organizations out-of-box, free for <7k users, scales to enterprise. Cloud-agnostic (API-based), with dev sandboxes for local testing. Avoids self-hosting ops. Integrates seamlessly with JWT validation in dependencies.py and frontend token management in [frontend/src/api/medusa.ts](frontend/src/api/medusa.ts).
  - Trade-offs: Monthly cost post-free tier (~$23/mo base), but value in reduced dev time. Fallback: Cognito if AWS hosting chosen.

- **Queue Technology: Celery with Redis Backend**
  - Reasoning: Builds on existing Celery dep (poetry deps include celery ^5.3.0) and Redis setup (docker-compose.test.yml). Redis as broker/result backend is lightweight, performant for job queuing, and already portable. Supports async benchmarks (e.g., enqueue in API routers like medusa.py, workers in src/services). Easy to scale workers horizontally and monitor with Flower or Sentry.
  - Trade-offs: Redis single point of failure (mitigate with Redis Sentinel/cluster in Phase 2). Simpler than SQS for local dev. No major rewrite needed for job flows in src/scenarios or src/benchmarking.

## Consequences
- **Positive**: Quick MVP implementation (1-2 weeks for IAM integration, 1 week for queue setup). Low learning curve. Aligns with project Python/FastAPI ecosystem.
- **Negative**: Auth0 costs scale with users; monitor usage. Redis requires careful config for production durability (e.g., AOF persistence).
- **Migration Impact**: Update [scripts/start-local.sh](scripts/start-local.sh) for local Auth0 dev keys/mock. Extend Celery config in src/fba_bench_api/celery.py (if exists) or add new. Add tenant_id to Celery task metadata for isolation.
- **Next Steps**: Implement spike for Auth0 JWT in dependencies.py; configure Celery app with tenant-aware tasks.

Date: 2025-09-28
Author: Master Engineer
Status: Accepted
