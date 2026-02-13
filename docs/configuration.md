# Configuration

Configuration is primarily driven by environment variables and YAML configs under `config/` and `configs/`.

## Environment Variables (Common)

API / runtime:
- `ENVIRONMENT`: `development`, `test`, `staging`, `production`
- `LOG_LEVEL`: logging verbosity (e.g., `INFO`, `DEBUG`)
- `DATABASE_URL`: SQLAlchemy URL (SQLite in dev, Postgres in prod)
- `FBA_BENCH_REDIS_URL`: Redis URL

Auth:
- `AUTH_ENABLED`: enable JWT enforcement
- `AUTH_TEST_BYPASS`: dev-only bypass for auth
- `AUTH_PROTECT_DOCS`: gate `/docs`, `/redoc`, `/openapi.json` when auth is enabled
- `AUTH_JWT_PUBLIC_KEY` / `AUTH_JWT_PUBLIC_KEYS` / `AUTH_JWT_PUBLIC_KEY_FILE`: RS256 public key material
- `AUTH_JWT_ISSUER`, `AUTH_JWT_AUDIENCE`, `AUTH_JWT_CLOCK_SKEW`: validation constraints

CORS:
- `FBA_CORS_ALLOW_ORIGINS`: comma-separated allow-list
  - In protected environments, `*` is rejected and startup fails.

Rate limiting:
- `API_RATE_LIMIT`: e.g. `100/minute`

## YAML Configuration

- `config/` and `configs/` contain template configs used by scripts and benchmark runs.
- `simulation_settings.yaml` provides a top-level “knobs” file used by some run scripts.

## Safety Rules

- Never commit `.env` files with real secrets.
- Prefer `.env.example` and production secret managers (KMS, Docker secrets, CI secret stores).

