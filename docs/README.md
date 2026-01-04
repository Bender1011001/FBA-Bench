# FBA-Bench Documentation

Welcome to the FBA-Bench v3 documentation. This documentation focuses on a smooth new-user experience while accurately reflecting current security defaults and infrastructure.

What you’ll find here:
- Getting Started: one-click Docker setup, first run, and next steps
- API Reference: REST endpoints, authentication, and WebSocket realtime
- Troubleshooting: common problems and fixes across install, auth, CORS, Redis, DB, and Docker

Navigation
- Quick Start Guide: ./getting-started/README.md
- API Reference: ./api/README.md
- Troubleshooting: ./troubleshooting/README.md

Version and compatibility
- This documentation targets FBA-Bench v3.0.0-rc.1 and later.
- Security defaults:
  - Auth enabled by default in protected environments (production/staging).
  - API docs (/docs) are gated when auth is enabled and AUTH_PROTECT_DOCS=true.
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

- Validating docs locally:
  - Run: docker compose -f docker-compose.oneclick.yml up -d --build
  - Verify health: curl -sS http://localhost:8000/api/v1/health
  - If AUTH is disabled (default for one-click), browse Swagger UI: http://localhost:8000/docs
  - If AUTH is enabled, confirm Bearer token flow using an Authorization: Bearer <JWT> header.

Security reminders
- Never commit real secrets. Use .env (gitignored) and follow .env.example guidance.
- In production/staging:
  - Provide AUTH_JWT_PUBLIC_KEY (PEM) and enforce AUTH_ENABLED=true.
  - Use explicit CORS allow-list via FBA_CORS_ALLOW_ORIGINS.
  - Prefer managed Redis/Postgres with TLS-capable URLs (rediss:// for Redis).

Current project state (release readiness snapshot)
- Release candidate: v3.0.0-rc.1 (component versions are consistent across the repo: backend 3.0.0, Godot GUI 1.0.0).
- Validation summary (full reports live in the repo):
  - Quality gates: FAILED — Coverage 22.6% (minimum 80%), 353 failing tests. See quality results: [`quality-gate-results.json`](quality-gate-results.json:1).
  - Test suite baseline: 955 passed, 351 failed, 54 errors = 1362 total tests. See test artifacts: [`python-unit-results.xml`](python-unit-results.xml:1) and [`python-validation-results.xml`](python-validation-results.xml:1).
  - Security audit: 1 Critical, 2 High, 1 Medium findings (detailed below).
  - Observability: NOT_READY — missing OTLP endpoints, insecure exporters, no centralized logs backend.
  - GUI: Godot 4 application in `godot_gui/` — replaces deprecated React frontend.
  - One-click scripts: ISSUES_FOUND — missing PowerShell launch script for Windows, demo scripts are demo-ready but not production hardened.
  - Performance baseline: Established. Snapshot from stress run available: [`perf_results/system_stress_results_run1.json`](perf_results/system_stress_results_run1.json:1).

Known limitations (must be read before deploying)
- Test coverage is far below required levels (22.6%). Many critical integration and unit tests fail; do not assume stability.
- Several services expose development defaults (HTTP endpoints, hardcoded localhost) — these must be removed/parameterized before production.
- Observability and alerting are not configured for production: no secure OTLP endpoints, exporters may be sending telemetry in plaintext.
- Godot GUI is ready for development use. Export templates needed for production builds.
- One-click demo scripts are intended for local demonstration only. They do not configure production-grade secrets, TLS, or hardened deploys.

Performance snapshot (summary)
- EventBus:
  - total_events: 5000, publish_throughput: ~8.5k eps, end_to_end_throughput: ~8.1k eps
  - avg handler latency: 307.4 ms, p95: 572 ms — acceptable throughput but high latency for some handlers. Full details: [`perf_results/system_stress_results_run1.json`](perf_results/system_stress_results_run1.json:1).
- Money (micro-benchmark):
  - iterations: 200k, duration: 2.249s, ops/sec: ~533,510 ops/sec (CPU-bound micro-benchmark).
- AdversarialFramework:
  - injections: 2000, inject_throughput: ~6.9k eps, responses_recorded: 1816
  - resistance_rate: 88.82% (ARS category "general")
- Operational note: EventBus throughput is good for bursts but handler latency indicates hotspots; investigate slow handlers and possible synchronous I/O.

Security findings (high level)
- Critical: ClearML component flagged — immediate action required to remediate or isolate (see pip audit and security reports).
- High:
  - PyJWT: version in dependency tree has known high severity issues — rotate keys and upgrade package to fixed version.
  - ClearML XSS: reported XSS risk in ClearML web UI integrations — avoid exposing ClearML UI to public networks or upgrade to patched release.
- Medium:
  - Starlette multipart/form rollover bug that can block the event loop (CVE-2025-54121) — upgrade to starlette >= 0.47.2 as recommended.
- Recommendations:
  - Block/patch vulnerable packages, upgrade to fixed versions, and re-run pip-audit. See [`pip_audit_report.json`](pip_audit_report.json:1) for full dependency listing.
  - Enforce dependency pinning (lockfile) and introduce a secure CVE acceptance policy.
  - Run dynamic dependency checks in CI and fail releases on Critical/High unplanned findings.

Setup & deployment guidance (current safe path)
- Local demo (recommended for evaluation only):
  - Use the one-click Docker compose: docker compose -f docker-compose.oneclick.yml up -d --build
  - This starts a demo environment with development defaults (AUTH may be disabled).
- Production readiness checklist (must be completed before production):
  1) Fix failing tests and raise coverage: aim for >= 80% coverage and 0 test failures.
  2) Upgrade/patch vulnerable dependencies (ClearML, PyJWT, Starlette).
  3) Harden configuration:
     - Enforce AUTH_ENABLED=true and set AUTH_JWT_PUBLIC_KEY
     - Replace dev DB/Redis with managed TLS-capable instances (rediss://, postgres+ssl)
     - Parameterize and remove hardcoded localhost URLs in frontend and backend
  4) Observability:
     - Configure OTLP endpoints over TLS, add logs backend (e.g. hosted ELK/Tempo/Datadog), secure exporters.
  5) GUI:
     - Godot 4 GUI in `godot_gui/` is functional; export for production with signed binaries if distributing.
  6) CI/CD:
     - Add gating to block releases when Quality gates fail (coverage/failed tests) and for unmitigated Critical/High CVEs.
  7) One-click scripts:
     - Provide production-ready PowerShell and bash scripts or document recommended deployment recipes (Helm/Terraform) for cloud environments.

Where to find the artifacts
- Quality gates: [`quality-gate-results.json`](quality-gate-results.json:1)
- Unit & validation test reports: [`python-unit-results.xml`](python-unit-results.xml:1), [`python-validation-results.xml`](python-validation-results.xml:1)
- Perf results: [`perf_results/system_stress_results_run1.json`](perf_results/system_stress_results_run1.json:1) (canonical stress run)
- Dependency audit: [`pip_audit_report.json`](pip_audit_report.json:1)

Contact & next steps
- For any security or high-severity blocking issues, tag the on-call security engineer and open a remediation PR.
- For performance investigations, capture flamegraphs for slow handlers, and run targeted EventBus handler profiling.
- For test flakiness, isolate failing suites (integration vs unit) and set focused PRs to restore passing CI.
