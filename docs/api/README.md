# API Reference

Base URL (local default)
- http://localhost:8000

API style
- REST over HTTP for resources and controls
- WebSocket (Redis pub/sub-backed) for realtime events

Security and defaults
- JWT-based authentication (RS256) enforced when enabled
  - Header: Authorization: Bearer <JWT>
  - Config via environment (see below)
- API docs (Swagger UI and Redoc) are gated when auth is enabled and AUTH_PROTECT_DOCS=true
- Global rate limit via API_RATE_LIMIT (SlowAPI-compatible; health endpoints are exempt)
- CORS is explicit allow-list; wildcards are rejected in protected environments

Implementation references
- App factory and security defaults: [python.function create_app()](../../fba_bench_api/server/app_factory.py:241)
- JWT middleware: [python.class JWTAuthMiddleware](../../fba_bench_api/server/app_factory.py:157)
- CORS configuration: [python.function _get_cors_allowed_origins()](../../fba_bench_api/server/app_factory.py:221)
- Health endpoints: [python.function health()](../../fba_bench_api/server/app_factory.py:358), [python.function health_v1()](../../fba_bench_api/server/app_factory.py:462)
- WebSocket handler: [python.function websocket_realtime()](../../fba_bench_api/api/routes/realtime.py:251)

Authentication

Enable RS256 JWT verification by setting:
- AUTH_ENABLED=true
- AUTH_JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----" (PEM; use \n for newlines)
- Optional: AUTH_JWT_ISSUER, AUTH_JWT_AUDIENCE, AUTH_JWT_CLOCK_SKEW (seconds, default 60)

Behavior
- When AUTH_ENABLED=true and a public key is set, all endpoints except UNPROTECTED_PATHS require a Bearer token.
- UNPROTECTED_PATHS include: /health, /api/v1/health, /healthz, /livez, / (root), and optionally /docs, /openapi.json, /redoc if docs are not gated.
- Docs gating: AUTH_PROTECT_DOCS=true + AUTH_ENABLED=true hides Swagger/Redoc/OpenAPI; use your tooling against /openapi.json with a token instead.

Example (Bearer):
  curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/experiments

WebSocket auth (if enabled):
- Provide JWT via Sec-WebSocket-Protocol "auth.bearer.token.<JWT>" or via ?token=<JWT> query parameter.
- See [python.function websocket_realtime()](../../fba_bench_api/api/routes/realtime.py:251).

OpenAPI / Swagger UI

- When not gated:
  - Swagger UI: /docs
  - Redoc: /redoc
  - OpenAPI JSON: /openapi.json
- In protected environments, generate a client from OpenAPI by fetching /openapi.json with a valid Bearer token.

Rate limiting

- Default: API_RATE_LIMIT=100/minute (configurable via env)
- Health endpoints are exempt
- Configured in [python.module app_factory](../../fba_bench_api/server/app_factory.py:311)

CORS

- Allowed origins computed from FBA_CORS_ALLOW_ORIGINS (comma-separated)
- In protected environments, an explicit allow-list is required; "*" is rejected
- See [python.function _get_cors_allowed_origins()](../../fba_bench_api/server/app_factory.py:221)

Realtime WebSocket

Endpoint
- ws://HOST:8000/ws/realtime
- Legacy alias: ws://HOST:8000/ws/events (delegates to the same handler)

Protocol (JSON frames)
- Client → Server:
  - {"type":"subscribe","topic":"X"}
  - {"type":"unsubscribe","topic":"X"}
  - {"type":"publish","topic":"X","data":{...}}
  - {"type":"ping"}
- Server → Client:
  - {"type":"event","topic":"X","data":{...},"ts":"..."}
  - {"type":"pong","ts":"..."}
  - {"type":"subscribed" | "unsubscribed", ...}
  - {"type":"warning","warning":"redis_unavailable",...} when Redis is down
  - {"type":"error","error":"..."}

Auth for WS (if enabled)
- Subprotocol: "auth.bearer.token.<JWT>"
  - Example (browser):
      new WebSocket("wss://api.example.com/ws/realtime", ["auth.bearer.token."+jwt]);
- Or query param: wss://api.example.com/ws/realtime?token=<JWT>

Redis configuration
- Preferred: FBA_BENCH_REDIS_URL, e.g., rediss://:PASSWORD@your-redis.example.com:6380/0
- Fallback: REDIS_URL
- See [.env.example](../../.env.example:39)

Key REST endpoints

Health
- GET /health
- GET /api/v1/health
- GET /healthz
- GET /livez

Simulation (read-only)
- GET /api/v1/simulation/snapshot
  - [python.function get_simulation_snapshot()](../../fba_bench_api/api/routes/realtime.py:203)
- GET /api/v1/simulation/events?event_type={sales|commands}&limit=20&since_tick=0
  - [python.function get_recent_events()](../../fba_bench_api/api/routes/realtime.py:223)

Medusa
Endpoints for managing the Medusa trainer process, implemented in [src/fba_bench_api/api/routes/medusa.py](src/fba_bench_api/api/routes/medusa.py). All under `/api/v1/medusa`. No authentication required in dev mode.

Agents
Prefix: /api/v1/agents (see [python.module agents](../../fba_bench_api/api/routes/agents.py:1))
- GET /frameworks — list supported frameworks
- GET /available — list available baseline agent templates/configs
- POST /validate — validate an agent configuration payload
- CRUD:
  - GET / — list agents
  - POST / — create agent
  - GET /{agent_id} — get agent
  - PATCH /{agent_id} — update agent
  - DELETE /{agent_id} — delete agent

Experiments
Prefix: /api/v1/experiments (see [python.module experiments](../../fba_bench_api/api/routes/experiments.py:1))
- GET / — list experiments
- POST / — create experiment (starts as draft)
- GET /{experiment_id} — get experiment
- PATCH /{experiment_id} — update metadata or transition status (validated)
- DELETE /{experiment_id} — delete experiment
- POST /{experiment_id}/stop — gracefully stop a running experiment (completed)
- GET /{experiment_id}/results — retrieve results payload (shape may evolve)

Note: Additional routers are mounted in the app factory (config, settings, metrics, golden, root). Consult Swagger UI or /openapi.json for the complete set.

Usage examples

curl (dev mode, auth disabled):
  curl -sS http://localhost:8000/api/v1/simulation/snapshot | jq .

curl with JWT:
  curl -H "Authorization: Bearer <JWT>" -sS http://localhost:8000/api/v1/experiments | jq .

WebSocket (browser, dev mode):
  const ws = new WebSocket("ws://localhost:8000/ws/realtime");
  ws.onmessage = (e) => console.log(e.data);
  ws.onopen = () => {
    ws.send(JSON.stringify({type:"subscribe", topic:"demo"}));
    ws.send(JSON.stringify({type:"publish", topic:"demo", data:{hello:"world"}}));
  };

WebSocket (JWT via subprotocol):
  const ws = new WebSocket("wss://api.example.com/ws/realtime", ["auth.bearer.token."+jwt]);

Python smoke clients
- REST: [bash.file scripts/smoke/curl-smoke.sh](../../scripts/smoke/curl-smoke.sh:1), [powershell.file scripts/smoke/curl-smoke.ps1](../../scripts/smoke/curl-smoke.ps1:1)
- WebSocket: [python.file scripts/smoke/ws_smoke.py](../../scripts/smoke/ws_smoke.py:1)

Environment configuration summary

Auth and docs gating (see [python.module app_factory](../../fba_bench_api/server/app_factory.py:126)):
- AUTH_ENABLED=true|false
- AUTH_TEST_BYPASS=true|false
- AUTH_PROTECT_DOCS=true|false
- AUTH_JWT_PUBLIC_KEY="PEM"
- AUTH_JWT_ISSUER="..."
- AUTH_JWT_AUDIENCE="..."
- AUTH_JWT_CLOCK_SKEW=60

CORS:
- FBA_CORS_ALLOW_ORIGINS="https://app.example.com,https://console.example.com"

Rate limit:
- API_RATE_LIMIT="100/minute"

Redis for realtime:
- FBA_BENCH_REDIS_URL="rediss://:PASSWORD@host:6380/0"
- REDIS_URL="redis://:PASSWORD@host:6379/0"

Link to schema
- Swagger UI: /docs (when not gated)
- OpenAPI JSON: /openapi.json (use Authorization header when gated)
