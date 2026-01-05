# FBA-Bench Enterprise Deployment Guide (Optimized)

This guide covers the optimized deployment configurations for FBA-Bench Enterprise, updated for the new `src/` project structure and standardized Docker workflows.

## Overview

The deployment infrastructure has been optimized with:
- ✅ Updated Dockerfiles for `src/` structure compatibility
- ✅ Standardized Docker Compose configurations
- ✅ Poetry-based dependency management
- ✅ Consistent environment variable usage
- ✅ Professional security practices
- ✅ Production-ready observability stack

## Docker Configurations

### Dockerfiles

| File | Purpose | Optimizations |
|------|---------|---------------|
| `Dockerfile` | Production API container | Updated for `src/` structure, Poetry workflow, security hardening |
| `Dockerfile.api` | Development/testing container | Updated paths, includes test dependencies |
| `Dockerfile.prod` | Multi-stage production build | Frontend + API with Nginx, optimized layers |

### Docker Compose Files

| File | Environment | Use Case |
|------|-------------|----------|
| `docker-compose.yml` | Default/Local | Basic setup with PostgreSQL, Redis, API, Frontend |
| `docker-compose.dev.yml` | Development | Hot-reload, debug settings, relaxed security |
| `docker-compose.test.yml` | Testing/CI | Test runner, isolated databases, coverage reporting |
| `docker-compose.prod.yml` | Production | Full observability stack, security hardened |
| `docker-compose.staging.yml` | Staging | Production-like with staging-specific settings |

### Specialized Configurations

| File | Purpose |
|------|---------|
| `docker-compose.oneclick.yml` | Quick demo/evaluation setup |
| `docker-compose.postgres.yml` | PostgreSQL add-on (compose layering) |
| `docker-compose.clearml.yml` | ClearML experiment tracking |
| `docker-compose-otel-collector.yml` | Observability stack only |

## Environment Configuration

### Environment Files Structure

```
.env.example          # Template with all variables documented
.env                  # Local development (gitignored)
.env.prod             # Production template (secrets placeholders)
config/env/           # Environment-specific configs
├── development.env
├── staging.env
└── production.env
```

### Key Environment Variables

#### Core Application
```bash
ENVIRONMENT=development|staging|production
PYTHONPATH=/app/src
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
FBA_BENCH_REDIS_URL=redis://:password@host:6379/0
```

#### Security & Authentication  
```bash
AUTH_ENABLED=true
AUTH_JWT_ALGORITHM=RS256
AUTH_JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
FBA_CORS_ALLOW_ORIGINS=https://yourdomain.com
```

#### Observability
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
LOG_LEVEL=INFO
SENTRY_DSN=https://...
```

## Deployment Scenarios

### 1. Local Development

```bash
# Quick start with defaults
docker compose up -d

# Development mode with hot-reload
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose logs -f api
```

**Features:**
- SQLite database for simplicity
- Hot-reload enabled
- Debug logging
- Relaxed CORS and rate limiting

### 2. Testing/CI

```bash
# Run full test suite
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# Run specific test profile
docker compose -f docker-compose.test.yml --profile testing up
```

**Features:**
- Isolated test databases
- Test runner container with coverage
- JUnit XML output for CI integration

### 3. Production Deployment

```bash
# Ensure environment is configured
cp .env.prod .env.prod.local
# Edit .env.prod.local with real values

# Deploy with full observability
docker compose -f docker-compose.prod.yml up -d

# Health checks
docker compose -f docker-compose.prod.yml ps
curl -f http://localhost/api/v1/health
```

**Production Features:**
- PostgreSQL with connection pooling
- Redis with password authentication
- Nginx with SSL termination support
- Full observability stack (OTEL, Prometheus, Grafana, Jaeger)
- Security hardening (read-only containers, non-root users)

### 4. Staging Environment

```bash
# Staging with production-like settings
docker compose -f docker-compose.staging.yml up -d

# Layer with PostgreSQL if needed
docker compose -f docker-compose.staging.yml -f docker-compose.postgres.yml up -d
```

## Build Processes

### Poetry Workflow

All containers now use Poetry for dependency management:

```dockerfile
# Install Poetry
RUN python -m pip install "poetry==${POETRY_VERSION}"

# Install dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi
```

### Multi-stage Builds

Production builds use multi-stage Docker builds:

1. **Frontend Build Stage**: Compiles React/Vite assets
2. **API Build Stage**: Installs Python dependencies
3. **Production Stage**: Combines assets with optimized runtime

### Build Scripts

Updated scripts for Poetry workflow:
- `scripts/start-local.sh` - Local development startup
- `scripts/deploy.sh` - Production deployment with health checks
- `start.sh` - Container startup script with migrations

## Security Considerations

### Container Security

- ✅ Non-root user execution
- ✅ Read-only root filesystem where possible
- ✅ Minimal base images (Alpine/slim variants)
- ✅ Security capabilities dropped
- ✅ Resource limits enforced

### Secrets Management

```yaml
# Production secret injection example
secrets:
  jwt_public_key:
    file: ./config/secrets/jwt_public_key.pem
  
services:
  api:
    secrets:
      - jwt_public_key
    environment:
      AUTH_JWT_PUBLIC_KEY_FILE: /run/secrets/jwt_public_key
```

### Network Security

```yaml
networks:
  backend:
    driver: bridge
  public:
    driver: bridge

services:
  api:
    networks: [backend]  # Internal only
  web:
    networks: [backend, public]  # Internet facing
```

## Monitoring & Observability

### Health Checks

All services include comprehensive health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Logging

Structured logging with consistent formats:
- JSON logs for production parsing
- Container log rotation configured
- Centralized log aggregation via OTEL Collector

### Metrics & Tracing

Full observability stack:
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **Jaeger**: Distributed tracing
- **OTEL Collector**: Telemetry data pipeline

## Troubleshooting

### Common Issues

**1. Module Import Errors**
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH="/app/src:${PYTHONPATH:-}"
```

**2. Database Connection Issues**
```bash
# Check PostgreSQL health
docker compose exec postgres pg_isready

# Verify environment variables
docker compose exec api env | grep DATABASE_URL
```

**3. Container Build Failures**
```bash
# Clear Docker cache
docker system prune -a

# Rebuild with no cache
docker compose build --no-cache
```

### Debug Commands

```bash
# View service logs
docker compose logs -f <service-name>

# Execute shell in running container
docker compose exec api bash

# Check service health
docker compose ps

# View resource usage
docker stats
```

## Migration from Legacy Structure

If migrating from the old root-level package structure:

1. **Update Import Paths**: Change imports to use `src/` packages
2. **Environment Variables**: Update `PYTHONPATH=/app/src`
3. **Volume Mounts**: Adjust volume paths in compose files
4. **Build Contexts**: Ensure Dockerfiles reference correct paths

## Production Checklist

Before deploying to production:

- [ ] Update all secrets in `.env.prod`
- [ ] Configure SSL certificates
- [ ] Set up backup procedures for PostgreSQL
- [ ] Configure monitoring alerts
- [ ] Test disaster recovery procedures
- [ ] Review security settings
- [ ] Performance test under load
- [ ] Set up log aggregation
- [ ] Configure health check endpoints
- [ ] Verify CORS and domain settings

## Support & Maintenance

### Regular Tasks

- Monitor disk usage for Docker volumes
- Rotate log files
- Update base images regularly
- Review security vulnerabilities
- Backup database and Redis data
- Monitor application performance

### Scaling Considerations

- Use Docker Swarm or Kubernetes for horizontal scaling
- Consider Redis Cluster for high availability
- Implement read replicas for PostgreSQL
- Use load balancers for multiple API instances
- Monitor and tune resource limits

---

For additional support, refer to:
- `docs/architecture.md` - System architecture overview
- `docs/testing.md` - Testing procedures
- `CONTRIBUTING.md` - Development guidelines
