# FBA-Bench Configuration Guide

The project uses a single source of truth for runtime configuration in [python.file config.py](src/fba_bench_core/config.py:1) powered by Pydantic Settings. This eliminates scattered environment reads and makes behavior consistent across components.

Precedence order (lowest to highest):
1) Built-in defaults in [python.file config.py](src/fba_bench_core/config.py:1)
2) YAML overlay file referenced by env FBA_CONFIG_PATH
3) Environment variables

Access the configuration anywhere via [python.function get_settings()](src/fba_bench_core/config.py:199). The result is cached; call get_settings.cache_clear() to reload after changing environment or YAML.

## Key Settings

- API and rate limiting: API_RATE_LIMIT
- CORS: FBA_CORS_ALLOW_ORIGINS (comma-separated)
- Auth: AUTH_ENABLED, AUTH_TEST_BYPASS, AUTH_PROTECT_DOCS
- JWT: AUTH_JWT_ALG, AUTH_JWT_PUBLIC_KEY, AUTH_JWT_ISSUER, AUTH_JWT_AUDIENCE, AUTH_JWT_CLOCK_SKEW
- Database/Redis URLs: FBA_BENCH_DB_URL or DATABASE_URL; FBA_BENCH_REDIS_URL or REDIS_URL
- Logging: FBA_LOG_LEVEL, FBA_LOG_FORMAT, FBA_LOG_FILE, FBA_LOG_INCLUDE_TRACEBACKS
- CLI/ClearML: CLEARML_WEB_HOST, FBA_BENCH_CLEARML_LOCAL_UI, FBA_BENCH_CLEARML_WEB_PORT, FBA_BENCH_CLEARML_API_PORT, FBA_BENCH_CLEARML_FILE_PORT, FBA_BENCH_CLEARML_COMPOSE, FBA_BENCH_ROOT

Derived helpers:
- settings.is_protected_env: true in production/prod/staging
- settings.cors_allow_origins: parsed list with sensible dev defaults
- settings.auth_enabled, settings.auth_test_bypass, settings.auth_protect_docs: environment-aware defaults
- settings.preferred_db_url: db_url or db_url_fba
- settings.preferred_redis_url: redis_url_fba or redis_url_compat

## YAML Overlay

Point FBA_CONFIG_PATH to a YAML file. Supported structure maps to the flat settings above.

Example:

```yaml
environment: development
api:
  rate_limit: "100/minute"
cors:
  allow_origins: ["http://localhost:3000", "http://localhost:5173"]
auth:
  enabled: false
  test_bypass: true
  protect_docs: false
  jwt_alg: "RS256"
  jwt_public_key: "-----BEGIN PUBLIC KEY-----...END PUBLIC KEY-----"
  jwt_issuer: "https://issuer.example"
  jwt_audience: "fba-bench"
  jwt_clock_skew: 60
database:
  url: "sqlite:///./fba_bench.db"
redis:
  url: "redis://localhost:6379/0"
logging:
  level: "INFO"
  format: "text"   # or: "json"
  file: null
  include_tracebacks: true
clearml:
  web_host: "https://app.clear.ml"
  local_ui: "http://localhost:8080"
  web_port: 8080
  api_port: 8008
  file_port: 8081
  compose_filename: "docker-compose.clearml.yml"
  root_hint: "./"
```

Enable overlay:

```bash
export FBA_CONFIG_PATH=./config/example.yaml
```

Env vars still override YAML. For example:

```bash
export DATABASE_URL=postgresql://user:pass@localhost/db
```

## Module Integrations

- API server: reads CORS/auth/rate-limit in [python.file app_factory.py](fba_bench_api/server/app_factory.py:1)
- Redis client: uses settings.preferred_redis_url in [python.file redis_client.py](fba_bench_api/core/redis_client.py:1)
- Database (sync): uses settings.preferred_db_url in [python.file database.py](fba_bench_api/core/database.py:1)
- Database (async): uses settings.preferred_db_url with driver mapping in [python.file database_async.py](fba_bench_api/core/database_async.py:1)
- Logging: central resolver in [python.file logging.py](src/fba_bench_core/core/logging.py:1)
- CLI defaults (ClearML): sourced from settings in [python.file cli.py](src/fba_bench_core/cli.py:1)

## Protected Environments

The [python.class AppSettings](src/fba_bench_core/config.py:35) determines protected status via the environment field. In protected envs (production/prod/staging):
- auth_enabled defaults to true
- auth_protect_docs defaults to true
- auth_test_bypass defaults to false

Override explicitly with AUTH_ENABLED, AUTH_PROTECT_DOCS, AUTH_TEST_BYPASS.

## Reloading Settings

[python.function get_settings()](src/fba_bench_core/config.py:199) caches results. After changing env or YAML at runtime:

```python
from fba_bench_core.config import get_settings
get_settings.cache_clear()
settings = get_settings()
```

## Troubleshooting

- YAML overlay not applied: ensure PyYAML is installed and FBA_CONFIG_PATH points to a readable file.
- Unexpected values: remember environment variables override YAML.
- Logging format JSON has no effect: install python-json-logger or keep format=text.

## Source

- Settings implementation: [python.file config.py](src/fba_bench_core/config.py:1)
- Accessor: [python.function get_settings()](src/fba_bench_core/config.py:199)
