# FBA-Bench API Documentation

The FBA-Bench API is built with [FastAPI](https://fastapi.tiangolo.com/), providing a RESTful interface for managing agents, experiments, benchmarks, and simulations. It includes automatic OpenAPI documentation, async support, and Pydantic validation for requests/responses.

All endpoints are under `/api/v1/` (versioned). Base URL: http://localhost:8000 (dev).

Note (Windows PowerShell): `curl` is an alias for `Invoke-WebRequest`. Use `curl.exe` if you want curl-compatible flags.

## Accessing Auto-Generated Docs

- **Swagger UI**: http://localhost:8000/docs (interactive, try requests)
- **ReDoc**: http://localhost:8000/redoc (formatted spec)
- **OpenAPI JSON**: http://localhost:8000/openapi.json (machine-readable)

In production, docs are protected (AUTH_PROTECT_DOCS=true); use JWT Bearer token.

To export spec:
macOS/Linux:
```bash
curl -sS http://localhost:8000/openapi.json -o fba-openapi.json
```

Windows (PowerShell):
```powershell
curl.exe -sS http://localhost:8000/openapi.json -o fba-openapi.json
```
Use tools like [Swagger Editor](https://editor.swagger.io/) or [Postman](https://postman.com/) to import.

## Authentication Guide

Authentication uses JWT (RS256 algorithm) for protected routes (agents, experiments in prod).

### JWT Flow

1. **Login** (if /auth/login implemented; otherwise, generate token via settings):
   ```bash
   curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "pass"}'
   ```
   Response: `{"access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600}` (200)

2. **Use Token**:
   - Header: `Authorization: Bearer <token>`
   - Example:
     ```bash
     curl -X GET "http://localhost:8000/api/v1/experiments" \
       -H "Authorization: Bearer eyJ..."
     ```

3. **Dev Bypass**: Set `AUTH_TEST_BYPASS=true` in .env; no token needed.
4. **Validation**: Tokens validated via public key (AUTH_JWT_PUBLIC_KEY in .env); issuer/audience checked.
5. **Expiration**: Default 1h; refresh via /auth/refresh if implemented.
6. **Errors**: 401 Unauthorized - missing/invalid token; 403 Forbidden - insufficient scopes.

In Swagger UI, authorize via "Authorize" button (enter Bearer token).

## Rate Limiting

- **Enabled**: Via `API_RATE_LIMIT` (default: 100 requests/minute per IP).
- **Headers** (response):
  - `X-RateLimit-Limit`: Total requests allowed.
  - `X-RateLimit-Remaining`: Requests left.
  - `X-RateLimit-Reset`: Time until reset (Unix timestamp).
- **Error**: 429 Too Many Requests - body: `{"detail": "Rate limit exceeded"}`; Retry-After header.
- **Bypass**: Internal calls or `AUTH_TEST_BYPASS=true`.

Tune in .env or config.yaml.

## Error Codes and Responses

All errors use standard HTTP status with JSON body: `{"detail": "Error message"}`. Common codes:

| Code | Description | Example Trigger | Response Example |
|------|-------------|-----------------|------------------|
| 400 | Bad Request | Validation failure (Pydantic) | `{"detail": "name must be non-empty"}` |
| 401 | Unauthorized | Missing/invalid JWT | `{"detail": "Not authenticated"}` |
| 403 | Forbidden | Insufficient permissions | `{"detail": "Access denied"}` |
| 404 | Not Found | Invalid ID (agent/experiment) | `{"detail": "Agent not found"}` |
| 429 | Too Many Requests | Rate limit hit | `{"detail": "Rate limit exceeded"}`; Retry-After: 60 |
| 500 | Internal Server Error | Unhandled exception | `{"detail": "Internal server error"}` |
| 422 | Unprocessable Entity | Schema mismatch | `{"detail": [{"loc": ["params"], "msg": "Invalid type"}]}` |

Logs include trace_id for debugging (OTEL correlation).

## Key Endpoints

Endpoints grouped by router. All support JSON; async where noted. Use Swagger for full schemas/parameters.

### Agents (/api/v1/agents)

Manage agent configurations, validation, baselines.

- **GET /frameworks**: List supported frameworks (diy, crewai, langchain).
  Response: `{"frameworks": ["diy", "crewai", "langchain"]}` (200)

- **GET /available**: List available agent types/examples.
  Response: Array of configs (framework, type, description, example).

- **GET /bots**: List baseline bots (YAML configs).
  Response: Array `[{"bot_name": "gpt-4o-mini", "model": "gpt-4o-mini", "config": {...}}]`

- **POST /validate**: Validate agent config YAML/JSON.
  Request: `{"agent_config": {"framework": "crewai", "agent_id": "my-agent", "llm_config": {"model": "gpt-4o", "api_key": "sk-..."}}}` 
  Response: `{"is_valid": true, "message": "Valid", "details": {...}}` (200) or errors (400)

- **CRUD**:
  - POST / : Create agent `{"name": "MyAgent", "framework": "baseline", "config": {"model": "gpt-4o-mini"}}` → 201
  - GET /{agent_id} : Retrieve (200)
  - PATCH /{agent_id} : Update (200)
  - DELETE /{agent_id} : No content (204)

### Experiments (/api/v1/experiments)

Manage experiment lifecycle and runs.

- **GET /**: List all (200)
- **POST /**: Create draft `{"name": "test", "agent_id": "uuid", "scenario_id": "basic", "params": {"seed": 42}}` → `{"id": "uuid", "status": "draft"}` (201)
- **GET /{id}**: Retrieve (200)
- **PATCH /{id}**: Update metadata/status (200)
- **DELETE /{id}**: No content (204)

- **POST /{id}/start**: Start run `{"scenario_id": "basic", "participants": [{"agent_id": "uuid", "role": "buyer"}], "params": {}}` → `{"run_id": "uuid", "status": "pending"}` (202)
- **GET /{id}/status**: Run status `{"status": "running", "progress_percent": 50.0, "current_tick": 50, "total_ticks": 100}` (200)
- **GET /{id}/progress**: Detailed progress (elapsed, estimated remaining, participant status) (200)
- **POST /{id}/stop**: Stop run → updated status (200)
- **GET /{id}/results**: Final results/summary (200)

### Benchmarks (/benchmarks)

High-level benchmarking (create/run/monitor).

- **POST /**: Create `{"config": {"scenarios": ["basic"], "agents": ["gpt-4o-mini"]}}` → `{"benchmark_id": "uuid", "status": "created"}` (201)
- **POST /{id}/run**: Start execution → `{"status": "completed", "result": {...}}` (200)
- **GET /{id}/status**: Status/metadata (200)
- **GET /**: List all (200)
- **POST /{id}/stop**: Stop (200)
- **DELETE /{id}**: Delete (200)
- **GET /health**: Service health `{"status": "healthy", "services": {...}}` (200)

### Simulation (/api/v1/simulation)

Low-level simulation control.

- **POST /**: Create `{"experiment_id": "uuid", "metadata": {"note": "ad-hoc"}}` → `{"id": "uuid", "status": "pending", "websocket_topic": "simulation-progress:uuid"}` (201)
- **POST /{id}/start**: Start → status "running" (200)
- **POST /{id}/stop**: Stop → status "stopped" (200)
- **GET /{id}**: Status (cached via Redis) (200)

Subscribe to WebSocket topic for real-time progress via the `/ws/realtime` endpoint (send `{"type":"subscribe", "topic":"..."}`).
Verify with `scripts/smoke/ws_smoke.py`.

## Request/Response Examples

### POST /api/v1/experiments (Create)

**Request**:
```json
{
  "name": "test-benchmark",
  "description": "Basic agent test",
  "agent_id": "agent-uuid",
  "scenario_id": "basic",
  "params": {
    "seed": 42,
    "iterations": 100
  }
}
```

**Response** (201):
```json
{
  "id": "exp-uuid",
  "name": "test-benchmark",
  "status": "draft",
  "created_at": "2025-09-21T14:00:00Z",
  "updated_at": "2025-09-21T14:00:00Z"
}
```

### POST /api/v1/experiments/{id}/start (Start Run)

**Request**:
```json
{
  "scenario_id": "basic",
  "participants": [
    {
      "agent_id": "agent-uuid",
      "role": "buyer"
    }
  ],
  "params": {}
}
```

**Response** (202):
```json
{
  "run_id": "run-uuid",
  "experiment_id": "exp-uuid",
  "status": "pending",
  "message": "Experiment run started successfully",
  "created_at": "2025-09-21T14:01:00Z",
  "participants_count": 1
}
```

### GET /api/v1/experiments/{id}/status

**Response** (200):
```json
{
  "experiment_id": "exp-uuid",
  "run_id": "run-uuid",
  "status": "running",
  "progress_percent": 45.5,
  "current_tick": 45,
  "total_ticks": 100,
  "started_at": "2025-09-21T14:01:00Z",
  "updated_at": "2025-09-21T14:02:30Z",
  "error_message": null,
  "metrics": {
    "score": 0.85,
    "decisions": 45
  }
}
```

For full schemas, see OpenAPI spec or source routers:
- [agents.py](src/fba_bench_api/api/routes/agents.py)
- [experiments.py](src/fba_bench_api/api/routes/experiments.py)
- [benchmarks.py](src/fba_bench_api/api/routes/benchmarks.py)
- [simulation.py](src/fba_bench_api/api/routes/simulation.py)

## Best Practices

- **Pagination**: Use ?limit=50&offset=0 for lists (if implemented).
- **Async**: Endpoints like /start return 202 Accepted; poll /status.
- **Validation**: Always validate configs via /agents/validate before creating.
- **Real-Time**: Use WebSockets for progress (subscribe to topics).
- **Security**: Enable auth in prod; validate inputs client-side.
- **Testing**: Use Swagger or Postman collections (generate from OpenAPI).

For user workflows: [docs/user-guide.md](user-guide.md). Report issues: GitHub.
