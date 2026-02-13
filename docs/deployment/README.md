# Deployment

This repo supports multiple deployment shapes via Docker Compose and direct uvicorn runs.

## Compose Files

- `docker-compose.oneclick.yml`: local demo stack (Nginx front door on `:8080`)
- `docker-compose.dev.yml`: development stack (hot reload, dev-friendly defaults)
- `docker-compose.test.yml`: CI/testing stack
- `docker-compose.prod.yml`: production-ish stack (Postgres/Redis/OTEL/Prometheus/Grafana)
- `docker-compose.yml`: base stack (may be used for local infra bring-up)

## One-Click Demo

```bash
docker compose -f docker-compose.oneclick.yml up -d --build
```

Open:
- http://localhost:8080

Stop:
```bash
docker compose -f docker-compose.oneclick.yml down
```

## Production Notes

Minimum requirements:
- Run the API behind TLS (reverse proxy / ingress)
- Set `AUTH_ENABLED=true` and configure RS256 JWT public keys
- Set explicit `FBA_CORS_ALLOW_ORIGINS`
- Use Postgres + Redis with durable storage

Health:
- `GET /api/v1/health`

