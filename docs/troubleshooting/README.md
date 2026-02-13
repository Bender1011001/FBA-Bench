# Troubleshooting

## One-Click Demo Doesn’t Start

1. Confirm Docker is running.
2. Run from repo root:
   ```bash
   docker compose -f docker-compose.oneclick.yml up -d --build
   ```
3. Check container status:
   ```bash
   docker compose -f docker-compose.oneclick.yml ps
   docker compose -f docker-compose.oneclick.yml logs --tail 200
   ```

## API Health Fails

One-click (proxy):
```bash
curl -v http://localhost:8080/api/v1/health
```

Direct:
```bash
curl -v http://localhost:8000/api/v1/health
```

If you enabled auth in a protected environment without keys, the API will fail fast at startup.

## CORS Errors

- In protected environments, set `FBA_CORS_ALLOW_ORIGINS` to an explicit comma-separated allow-list.
- `*` is rejected in staging/production.

