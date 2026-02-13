# FBA-Bench Documentation

Welcome to the FBA-Bench documentation.

What you’ll find here:
- Getting Started: one-click Docker setup, first run, and next steps
- API Reference: REST endpoints, authentication, and WebSocket realtime
- Troubleshooting: common problems and fixes across install, auth, CORS, Redis, DB, and Docker

Navigation
- Quick Start Guide: ./getting-started/README.md
- API Reference: ./api/README.md
- Architecture: ./architecture.md
- Configuration: ./configuration.md
- Deployment: ./deployment/README.md
- Observability: ./observability.md
- Troubleshooting: ./troubleshooting/README.md
- Testing: ./testing.md
- Golden Masters: ./quality/golden_master.md

Local demo (one-click)
- Start: `docker compose -f docker-compose.oneclick.yml up -d --build`
- Open: http://localhost:8080
- API health (proxied): http://localhost:8080/api/v1/health
- FastAPI docs (proxied): http://localhost:8080/docs

Security defaults (important)
- Auth enabled by default in protected environments (production/staging).
- API docs (`/docs`) are gated when auth is enabled and `AUTH_PROTECT_DOCS=true`.
- CORS must be explicitly allow-listed (wildcards rejected) in protected environments.

Contributing to the docs
- How to propose changes:
  1) Edit or add markdown under ./docs/.
  2) Keep instructions concrete and runnable; prefer step-by-step commands over prose.
  3) For security-sensitive sections, clearly label production vs. development defaults.
  4) Submit a pull request with a concise summary of changes.

- Style and content guidelines:
  - Favor short paragraphs, numbered steps, and copy/paste-ready commands.
  - When referencing code or endpoints, include stable paths and exact URLs where possible.
  - Keep examples minimal but complete (no placeholders that can’t run as-is).
  - Note platform-specific commands separately when needed (Windows PowerShell vs. macOS/Linux bash).

Validating docs locally:
- Run: `docker compose -f docker-compose.oneclick.yml up -d --build`
- Verify health: `curl -sS http://localhost:8080/api/v1/health`
- Browse Swagger UI: http://localhost:8080/docs

Security reminders
- Never commit real secrets. Use .env (gitignored) and follow .env.example guidance.
- In production/staging:
  - Provide AUTH_JWT_PUBLIC_KEY (PEM) and enforce AUTH_ENABLED=true.
  - Use explicit CORS allow-list via FBA_CORS_ALLOW_ORIGINS.
  - Prefer managed Redis/Postgres with TLS-capable URLs (rediss:// for Redis).
