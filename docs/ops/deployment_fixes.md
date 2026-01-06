# FBA-Bench Local Development & Deployment Fixes

## 🚀 Quick Access (Current Session)

**Live Public URL**: https://pst-increased-mats-cool.trycloudflare.com

| Endpoint | URL |
|----------|-----|
| Health Check | https://pst-increased-mats-cool.trycloudflare.com/api/v1/health |
| Leaderboard | https://pst-increased-mats-cool.trycloudflare.com/api/v1/leaderboard |
| API Docs | https://pst-increased-mats-cool.trycloudflare.com/docs |

> ⚠️ This is a temporary tunnel URL. It will change when you restart the tunnel.
> For permanent access, set up a named tunnel with your Cloudflare account.

This document captures the deployment fixes and learnings from the January 2026 deployment session.

## Summary

Successfully deployed FBA-Bench API locally with Docker Compose:
- **API Endpoint**: `http://localhost/api/v1/health` → `{"status": "healthy"}`
- **Leaderboard API**: `http://localhost/api/v1/leaderboard` → Works (returns data)
- **Services**: Redis, PostgreSQL, App (all healthy)

## Files Fixed During Deployment

### 1. `infrastructure/scripts/provision_demo_tenant.sh`
- **Issue**: Incorrect REPO_ROOT path calculation (3 levels up instead of 2)
- **Fix**: Changed `$SCRIPT_DIR/../../..` to `$SCRIPT_DIR/../..`
- **Issue**: Terraform not found in bash PATH on Windows/WSL
- **Fix**: Added fallback to check for `terraform.exe` in parent directory

### 2. `infrastructure/scripts/generate_tenant_configs.py`
- **Issue**: Template variable names didn't match the actual template placeholders
- **Fix**: Updated mapping dict to use lowercase keys matching templates (`domain`, `environment`, `tenant`, etc.)

### 3. `docker-compose.prod.yml`
- **Issue**: Circular dependency (app → otel-collector → app)
- **Fix**: Removed app from otel-collector's depends_on
- **Issue**: Invalid ulimits syntax for alertmanager
- **Fix**: Changed `nofile: 65536:65536` to proper object syntax
- **Issue**: Redis command failing due to empty env var interpolation
- **Fix**: Hardcoded Redis password in command array
- **Issue**: App depending on otel-collector which wasn't configured
- **Fix**: Removed otel-collector dependency from app

### 4. `Dockerfile`
- **Issue**: Trying to use nginx and start.sh which weren't properly configured
- **Fix**: Removed nginx installation, use uvicorn directly via default CMD

### 5. `scripts/deploy.sh`
- **Issue**: Invalid bash `for...else` syntax
- **Fix**: Replaced with proper flag-based pattern using `HEALTHY=false` variable

### 6. `pyproject.toml`
Missing production dependencies that weren't in the main group:
- Added `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`
- Added `psycopg2-binary` (PostgreSQL driver)
- Added `dependency-injector` (DI framework)
- Added `prometheus-client` (metrics)

### 7. `poetry.lock`
- **Issue**: Git merge conflict markers at line 742
- **Fix**: Resolved conflict, keeping both HEAD and incoming package entries

### 8. `.env.prod`
- **Issue**: Using PostgreSQL URL that required async driver
- **Fix**: Changed to SQLite for simpler local deployment

## Quick Start Commands

```bash
# Build and start services
docker compose -f docker-compose.prod.yml build app
docker compose -f docker-compose.prod.yml up -d app redis postgres

# Check health
curl http://localhost/api/v1/health

# View logs
docker compose -f docker-compose.prod.yml logs app --tail 50

# Stop everything
docker compose -f docker-compose.prod.yml down
```

## Cloudflare Tunnel (Quick Testing)

For quick public access without DNS setup:

```powershell
# Install cloudflared
winget install --id Cloudflare.cloudflared -e

# Start quick tunnel (temporary URL)
cloudflared tunnel --url http://localhost:80

# Or use the script
.\scripts\cloudflare-tunnel.ps1
```

## Production Deployment to fbabench.com

### Option 1: Cloudflare Tunnel (Persistent)

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create named tunnel
cloudflared tunnel create fba-bench

# Configure tunnel (creates config in ~/.cloudflared/)
# Add to Cloudflare DNS: CNAME fbabench.com → <tunnel-id>.cfargotunnel.com

# Run tunnel
cloudflared tunnel run fba-bench
```

### Option 2: VPS Deployment

1. Deploy to a VPS (DigitalOcean, Linode, Vultr)
2. Get the server's public IP
3. In Cloudflare DNS, add A record:
   - Type: A
   - Name: @ (for fbabench.com)
   - IPv4: <server-ip>
   - Proxy status: Proxied (orange cloud)

### Required Environment Variables for Production

```env
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/fba_prod
REDIS_PASSWORD=<secure-password>
POSTGRES_PASSWORD=<secure-password>
DOMAIN=fbabench.com
JWT_SECRET=<secure-random-string>
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

## Lessons Learned

1. **Windows/WSL Path Issues**: Always test bash scripts in the actual deployment environment
2. **Docker Compose Variable Interpolation**: Empty env vars can break shell commands; use array syntax
3. **Poetry Groups**: Production images need all main dependencies, not dev/test groups
4. **Circular Dependencies**: Review docker-compose depends_on chains carefully
5. **Line Endings**: Convert CRLF to LF for bash scripts (`python -c "..."` trick)

## Verification Endpoints

| Endpoint | Expected Response |
|----------|-------------------|
| `GET /api/v1/health` | `{"status": "healthy", "db": "ok"}` |
| `GET /api/v1/leaderboard` | `[]` or leaderboard data |
| `GET /docs` | Swagger UI |
| `GET /redoc` | ReDoc documentation |
