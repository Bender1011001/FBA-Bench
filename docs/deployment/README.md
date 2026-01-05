# FBA-Bench Deployment Guide (v3.0.0-rc1)

This guide provides production-ready deployment procedures, hardened configurations, one-click scripts, environment templates, and CI/CD integration strategies. It enables reliable deployments across development, staging, and production.

Key goals:
- One-click Windows and bash automation for local and CI/CD
- Hardened defaults (auth, TLS, CORS, rate limiting, security headers)
- Environment-specific stacks (dev/staging/prod)
- Health checks, validation, rollback, and notifications

## Overview of Artifacts

- One-click and setup scripts:
  - PowerShell: [scripts/oneclick-launch.ps1](../../scripts/oneclick-launch.ps1), [scripts/oneclick-stop.ps1](../../scripts/oneclick-stop.ps1), [scripts/oneclick-configure.ps1](../../scripts/oneclick-configure.ps1), [scripts/install.ps1](../../scripts/install.ps1), [scripts/docker-setup.ps1](../../scripts/docker-setup.ps1), [scripts/deploy.ps1](../../scripts/deploy.ps1)
  - Bash (existing): [scripts/oneclick-launch.sh](../../scripts/oneclick-launch.sh), [scripts/oneclick-stop.sh](../../scripts/oneclick-stop.sh), [scripts/install.sh](../../scripts/install.sh), [scripts/docker-setup.sh](../../scripts/docker-setup.sh)
- Environment templates: [config/env/dev.env](../../config/env/dev.env), [config/env/staging.env](../../config/env/staging.env), [config/env/prod.env](../../config/env/prod.env), [.env.example](../../.env.example)
- Hardened reverse proxy:
  - One-click HTTP proxy: [config/nginx/oneclick.conf](../../config/nginx/oneclick.conf)
  - TLS proxy (prod/staging): [nginx.conf](../../nginx.conf)
- Compose stacks:
  - Local dev: [docker-compose.yml](../../docker-compose.yml), [docker-compose.dev.yml](../../docker-compose.dev.yml)
  - One-click: [docker-compose.oneclick.yml](../../docker-compose.oneclick.yml)
  - Staging: [docker-compose.staging.yml](../../docker-compose.staging.yml)
  - Production: [docker-compose.prod.yml](../../docker-compose.prod.yml)
  - Optional Postgres overlay: [docker-compose.postgres.yml](../../docker-compose.postgres.yml)
  - Observability add-on: [docker-compose-otel-collector.yml](../../docker-compose-otel-collector.yml)
- Validation and health:
  - Config validation: [scripts/validate_config.py](../../scripts/validate_config.py)
  - Health checks: [scripts/healthcheck.py](../../scripts/healthcheck.py)

## Security Hardening Summary

Server-side enforcement (see [src/fba_bench_api/server/app_factory.py](../../src/fba_bench_api/server/app_factory.py)):
- Auth enabled by default in protected envs (ENVIRONMENT=staging|production)
- JWT RS256 verification via AUTH_JWT_PUBLIC_KEY(S)/FILE
- Docs gated when protected (AUTH_PROTECT_DOCS=true)
- HTTPS redirect enforced in protected envs (ENFORCE_HTTPS=true)
- Explicit CORS allow-list required (FBA_CORS_ALLOW_ORIGINS not '*')
- Global rate limiting via API_RATE_LIMIT (default 100/minute)

Reverse proxy hardening:
- TLS termination, HSTS, security headers in [nginx.conf](../../nginx.conf)
- HTTP->HTTPS redirect
- WebSocket and API proxy with timeouts

Container hardening:
- Non-root user in [Dockerfile](../../Dockerfile)
- read_only filesystem, no-new-privileges, cap_drop, tmpfs /tmp
- Healthchecks for api, nginx, redis
- Resource limits and reservations across services

Secrets management:
- JWT public key mounted as Docker secret in staging/prod:
  - Provide file at ./config/secrets/jwt_public_key.pem
  - Compose mounts to /run/secrets/jwt_public_key
  - API configured via AUTH_JWT_PUBLIC_KEY_FILE=/run/secrets/jwt_public_key

## Prerequisites

- Docker Desktop (Compose v2) or Docker Engine + docker-compose
- Python 3.9+ for scripts
- Valid TLS certs for staging/prod (mount to ./config/tls/server.crt and ./config/tls/server.key)
- Valid JWT public key PEM for staging/prod (./config/secrets/jwt_public_key.pem)

## Quick Starts

### One-Click Local (Windows)
- Configure env (optional keys): [scripts/oneclick-configure.ps1](../../scripts/oneclick-configure.ps1)
- Launch stack (api + redis + nginx http proxy):
  - [scripts/oneclick-launch.ps1](../../scripts/oneclick-launch.ps1)
- Stop:
  - [scripts/oneclick-stop.ps1](../../scripts/oneclick-stop.ps1)
- Access: http://localhost:8080 (proxy) or http://localhost:8000 (API)

### Local Dev (Compose)
- Start dev stack: [scripts/docker-setup.ps1](../../scripts/docker-setup.ps1) start
- Logs: [scripts/docker-setup.ps1](../../scripts/docker-setup.ps1) logs api
- Stop: [scripts/docker-setup.ps1](../../scripts/docker-setup.ps1) stop

## Environment Configuration

Use these templates to populate environment variables:
- Dev: [config/env/dev.env](../../config/env/dev.env)
- Staging: [config/env/staging.env](../../config/env/staging.env)
- Production: [config/env/prod.env](../../config/env/prod.env)
- Example: [.env.example](../../.env.example)

Critical variables:
- ENVIRONMENT=production|staging|development
- AUTH_ENABLED, AUTH_TEST_BYPASS, AUTH_PROTECT_DOCS
- AUTH_JWT_PUBLIC_KEY or AUTH_JWT_PUBLIC_KEY_FILE (PEM)
- FBA_CORS_ALLOW_ORIGINS (comma-separated allow-list; no '*')
- API_RATE_LIMIT (e.g., 100/minute)
- DATABASE_URL (use Postgres in staging/prod)
- FBA_BENCH_REDIS_URL (use rediss:// with auth in staging/prod)
- LOG_LEVEL

Validate configs:
- [scripts/validate_config.py](../../scripts/validate_config.py) --env-file config/env/staging.env

## Deployment Procedures

### Windows PowerShell Automated Deploy
- Script: [scripts/deploy.ps1](../../scripts/deploy.ps1)
- Examples:
  - Staging (with Postgres overlay):
    - powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -Env staging -OverlayPostgres
  - Production with image tags and rollback:
    - powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -Env prod -NewImageTag v3.0.0-rc1 -PrevImageTag v3.0.0-rc0
  - Dev:
    - powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -Env dev

What it does:
1) Validates configuration via [scripts/validate_config.py](../../scripts/validate_config.py)
2) Builds and deploys Compose stack (staging/prod include nginx/TLS)
3) Runs health checks via [scripts/healthcheck.py](../../scripts/healthcheck.py) against API and nginx
4) If health fails and -PrevImageTag is provided, performs automated rollback
5) Optional webhook notifications via DEPLOY_WEBHOOK_URL

### Compose Files
- Staging: [docker-compose.staging.yml](../../docker-compose.staging.yml)
- Production: [docker-compose.prod.yml](../../docker-compose.prod.yml)
- Postgres overlay: [docker-compose.postgres.yml](../../docker-compose.postgres.yml)
- Observability: [docker-compose-otel-collector.yml](../../docker-compose-otel-collector.yml)

Compose examples:
- docker compose -f docker-compose.staging.yml up -d --build
- docker compose -f docker-compose.prod.yml -f docker-compose.postgres.yml up -d --build

## Health Checks and Validation

- API: http://localhost:8000/api/v1/health
- Nginx: https://localhost/nginx-health
- Health script:
  - [scripts/healthcheck.py](../../scripts/healthcheck.py) --urls http://localhost:8000/api/v1/health,https://localhost/nginx-health --allow-insecure

- Config validation:
  - [scripts/validate_config.py](../../scripts/validate_config.py) --env-file config/env/prod.env

Exit codes:
- validate_config: 0 OK, 2 warnings, 3 errors (fatal)
- healthcheck: 0 all healthy, 1 failure

## Secrets and TLS

- JWT public key: place PEM at ./config/secrets/jwt_public_key.pem
  - Mounted as Docker secret jwt_public_key
  - API reads via AUTH_JWT_PUBLIC_KEY_FILE=/run/secrets/jwt_public_key
- TLS certs: place at ./config/tls/server.crt and ./config/tls/server.key
  - Mounted by nginx in staging/prod compose

Ensure these paths are excluded from VCS:
- config/secrets/*
- config/tls/*

## CI/CD Integration (Template)

Use [scripts/deploy.ps1](../../scripts/deploy.ps1) in Windows runners. For Linux runners, call Compose directly following the same sequence:
1) python scripts/validate_config.py --env-file config/env/staging.env
2) API_IMAGE_TAG=$TAG docker compose -f docker-compose.staging.yml up -d --build
3) python scripts/healthcheck.py --urls http://localhost:8000/api/v1/health,https://localhost/nginx-health --allow-insecure
4) On failure, set API_IMAGE_TAG=$PREV_TAG and re-run compose to rollback

Recommended pipeline gates:
- Run unit/integration tests
- Run [scripts/validate_config.py](../../scripts/validate_config.py)
- Deploy to staging and run [scripts/healthcheck.py](../../scripts/healthcheck.py)
- Promote to production with -NewImageTag/-PrevImageTag strategy

## Rollback Procedure

Automated (recommended):
- Provide -PrevImageTag to [scripts/deploy.ps1](../../scripts/deploy.ps1). If health checks fail, script rolls back automatically and posts webhook notification when configured.

Manual:
- Set API_IMAGE_TAG to a known-good tag and redeploy:
  - $env:API_IMAGE_TAG = 'v3.0.0-rc0'
  - docker compose -f docker-compose.prod.yml up -d

## Troubleshooting

Common issues and fixes: [docs/troubleshooting/README.md](../troubleshooting/README.md)

Quick checks:
- docker compose ps, docker compose logs -f api
- Health endpoints: /api/v1/health, /nginx-health
- JWT key presence when AUTH_ENABLED=true
- FBA_CORS_ALLOW_ORIGINS must not be '*' in staging/prod
- DATABASE_URL must be Postgres (not SQLite) for staging/prod

## Maintenance

- To rotate JWT keys, update ./config/secrets/jwt_public_key.pem and redeploy
- To update rate limits, set API_RATE_LIMIT (e.g. 200/minute) and redeploy
- To add origins, update FBA_CORS_ALLOW_ORIGINS in env file and redeploy
- To upgrade images, set API_IMAGE_TAG and redeploy

## Reference

- App security defaults and enforcement: [src/fba_bench_api/server/app_factory.py](../../src/fba_bench_api/server/app_factory.py)
- Centralized settings: [src/fba_bench_core/config.py](../../src/fba_bench_core/config.py)
