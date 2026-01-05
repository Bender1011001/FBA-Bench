# FBA-Bench Deployment Guide

This guide covers deploying FBA-Bench to production environments. It assumes development setup from [getting-started.md](getting-started.md). Focus on Docker for simplicity; Kubernetes for scaling. For architecture: [docs/architecture.md](architecture.md).

## Production Setup with Docker Compose

Use `docker-compose.prod.yml` for secure, scaled deployment.

### Prerequisites

- Docker 20+ & Compose 2+.
- Domain/SSL certs (e.g., Let's Encrypt for HTTPS).
- Secrets: API keys, DB creds (use Docker secrets or env files).
- Services: External Postgres/Redis (RDS/ElastiCache) or local.

### Steps

1. **Configure Environment**:
   - Copy `.env.prod` from `.env.example`; set:
     - `AUTH_ENABLED=true`
     - `AUTH_JWT_PUBLIC_KEY`: RS256 public key (generate pair).
     - `DATABASE_URL`: Prod DB (e.g., postgresql://user:pass@prod-db:5432/fba).
     - `REDIS_URL`: Prod Redis.
     - `API_RATE_LIMIT=500/minute` (scale up).
     - OTEL: `OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector:4317` (secure).
     - ClearML: External host or disable (`CLEARML_WEB_HOST=`).
   - Secrets: Use `docker secret create` for keys; mount in compose.

2. **Build & Start**:
   ```bash
   # Build images (if custom)
   docker compose -f docker-compose.prod.yml build

   # Up (detached, scaled)
   docker compose -f docker-compose.prod.yml up -d --scale api=3 --scale agent-worker=2
   ```
   - Services: api (FastAPI, scaled), frontend (Nginx static), db (Postgres), redis, otel-collector, prometheus, grafana, clearml (optional).
   - Ports: 80/443 (Nginx reverse proxy), 3000 (Grafana internal).
   - Volumes: Persist DB (/var/lib/postgresql/data), results (/app/results).

3. **Database Migration**:
   ```bash
   docker compose -f docker-compose.prod.yml exec api make be-migrate
   ```
   - Runs Alembic on startup if needed (check logs).

4. **Health & Verification**:
   - API: `curl -k https://your-domain/api/v1/health` → `{"status": "healthy"}`
   - Frontend: https://your-domain (Nginx serves React build).
   - Monitoring: Grafana http://your-domain:3000 (admin/admin; change password).
   - Logs: `docker compose logs -f api`

5. **SSL/TLS**:
   - Nginx config in docker-compose.prod.yml (certbot or mount certs).
   - OTLP: TLS enforced (see observability.md).

6. **Domain Configuration (fbabench.com)**:
   The production domain is configured in `config/config.yaml`:
   ```yaml
   app:
     name: "FBA-Bench Enterprise"
     version: "1.0.0"
     domain: "fbabench.com"
   
   server:
     host: "0.0.0.0"
     port: 8000
     cors_origins:
       - "http://localhost:8080"  # Godot Local
       - "https://fbabench.com"   # Production Domain
       - "https://www.fbabench.com"
   ```
   - Ensure DNS points to your server/load balancer.
   - CORS is pre-configured for both local Godot development and production.

### Environment-Specific

- **Staging**: Use docker-compose.staging.yml (similar to prod, test data).
- **Dev**: docker-compose.dev.yml (no TLS, hot-reload).

## Scaling with Kubernetes

Manifests in infrastructure/deployment/kubernetes.yaml.

1. **Setup**:
   - Cluster: EKS/GKE/AKS.
   - Secrets: `kubectl create secret generic fba-secrets --from-env-file=.env.prod`
   - ConfigMaps: For YAML configs.

2. **Deploy**:
   ```bash
   kubectl apply -f infrastructure/deployment/kubernetes.yaml
   ```
   - Deployments: api (3 replicas, HPA on CPU>70%), agent-worker (scale on demand).
   - Services: LoadBalancer for api/frontend.
   - PersistentVolumes: For DB/results.
   - Ingress: Nginx Ingress with TLS.

3. **Scaling**:
   - Horizontal Pod Autoscaler (HPA): For api (requests/min), agents (queue length).
   - Redis Cluster: For high-throughput events.
   - DB: Read replicas for queries.

4. **CI/CD**: GitHub Actions or ArgoCD; build images on push, deploy to K8s.

## Cloud Deployments

For managed cloud platforms, use container services. Examples below; adapt for your provider. Focus on Docker images from Dockerfile.prod.

### AWS ECS (Elastic Container Service)

1. **Setup**:
   - ECR repository for images.
   - RDS for Postgres, ElastiCache for Redis.
   - ALB for load balancing/SSL.

2. **Terraform Snippet** (infrastructure/terraform/main.tf):
   ```hcl
   provider "aws" {
     region = var.aws_region
   }

   resource "aws_ecs_cluster" "fba" {
     name = "fba-bench-cluster"
   }

   resource "aws_ecs_task_definition" "app" {
     family                   = "fba-app"
     network_mode             = "awsvpc"
     requires_compatibilities = ["FARGATE"]
     cpu                      = "1024"
     memory                   = "2048"
     execution_role_arn       = aws_iam_role.ecs_execution.arn
     task_role_arn            = aws_iam_role.ecs_task.arn

     container_definitions = jsonencode([
       {
         name  = "fba-app"
         image = "${var.ecr_repo_url}:latest"
         portMappings = [
           {
             containerPort = 80
             hostPort      = 80
           }
         ]
         environment = [
           { name = "DOMAIN", value = var.domain }
         ]
         logConfiguration = {
           logDriver = "awslogs"
           options = {
             awslogs-group         = aws_cloudwatch_log_group.fba.name
             awslogs-region        = var.aws_region
             awslogs-stream-prefix = "fba"
           }
         }
       }
     ])
   }

   resource "aws_ecs_service" "app" {
     name            = "fba-app-service"
     cluster         = aws_ecs_cluster.fba.id
     task_definition = aws_ecs_task_definition.app.arn
     desired_count   = 2
     launch_type     = "FARGATE"

     network_configuration {
       subnets         = var.subnet_ids
       security_groups = [aws_security_group.ecs.id]
       assign_public_ip = true
     }

     load_balancer {
       target_group_arn = aws_lb_target_group.app.arn
       container_name   = "fba-app"
       container_port   = 80
     }
   }
   ```

3. **Deploy**:
   - Build/push: `docker build -t fba-app:latest -f Dockerfile.prod . && docker tag fba-app:latest <account>.dkr.ecr.us-west-2.amazonaws.com/fba-app:latest && docker push`
   - Apply Terraform: `terraform apply`
   - Update task definition for new image.

### GCP Cloud Run

1. **Setup**:
   - Artifact Registry for images.
   - Cloud SQL for Postgres, Memorystore for Redis.
   - Load Balancer for custom domain/SSL.

2. **Deploy**:
   ```bash
   # Build and push
   gcloud builds submit --tag gcr.io/PROJECT_ID/fba-app:latest

   # Deploy to Cloud Run
   gcloud run deploy fba-app \
     --image gcr.io/PROJECT_ID/fba-app:latest \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --port 80 \
     --memory 1Gi \
     --cpu 2 \
     --concurrency 80 \
     --max-instances 10 \
     --set-env-vars DOMAIN=your-domain.com,POSTGRES_PASSWORD=secret

   # Map custom domain
   gcloud run domain-mappings create --service fba-app --domain your-domain.com
   ```

3. **Scaling**: Auto-scales to zero; set min-instances=1 for always-on.

### Railway/Heroku (PaaS)

1. **Railway**:
   - Connect GitHub repo.
   - Add services: Postgres, Redis add-ons.
   - Buildpack: Docker (use Dockerfile.prod).
   - Env vars from .env.prod.
   - Deploy: `railway up`; custom domain in dashboard.

2. **Heroku**:
   - `heroku create fba-bench-prod`
   - Add-ons: Heroku Postgres, Redis.
   - `heroku buildpacks:add heroku/python` (for Poetry), but use Docker for multi-stage.
   - Dockerfile: Use Dockerfile.prod; `heroku container:push web --app fba-bench-prod`
   - Env: `heroku config:set DOMAIN=your-domain.com`
   - Scale: `heroku ps:scale web=2`

For Helm (K8s): Use charts in infrastructure/helm/; `helm upgrade --install fba ./charts/fba --values values-prod.yaml --set image.tag=1.0.0`

See provider docs for costs, SLAs.

## Monitoring Setup

Observability via OTEL (see [docs/observability.md](observability.md)).

1. **Prometheus/Grafana**:
   - Config: config/prometheus/prometheus.yml, config/grafana/provisioning/.
   - Dashboards: FBA-Overview.json (latency, errors, CPU/RAM, experiment metrics).
   - Alerts: config/prometheus/alerts.yml (HighLatencyP95, HighErrorRate); routes to Slack/PagerDuty via Alertmanager.

2. **Deploy**:
   - Included in docker-compose.prod.yml (prometheus:9090, grafana:3000).
   - K8s: Prometheus Operator; scrape api/otel.

3. **Key Metrics**:
   - API: requests_total, latency_bucket (p95 <500ms).
   - Experiments: runs_active, score_avg.
   - System: cpu_utilization, memory_usage.

Access Grafana: Default admin/admin; provisioned datasources (Prometheus, Loki, Tempo).

## Security in Production

- **Auth Flows**: JWT for API; enable `AUTH_ENABLED=true`. Login via /auth/login (implement if needed); validate scopes for routes.
- **Secret Management**: Docker secrets/K8s secrets; Vault for rotation. No .env in images.
- **Audit Summary**: [docs/security_audit_summary.md](security_audit_summary.md) - bump Starlette, PyJWT; run `safety check` in CI.
- **Network**: Firewall ports (80/443 public, 5432/6379 internal); mTLS for OTLP.
- **Input Sanitization**: Pydantic validates all payloads; rate limit prevents DoS.
- **Compliance**: Logs anonymized; no PII in simulations.

Scan images: `docker scout` or Trivy in CI.

## Performance Tuning

- **Cache TTLs**: Redis: Set EXPIRE on keys (e.g., world_state:300s); config in redis_client.py.
- **Pool Sizes**: DB: connection_pool_size=20; Redis: max_connections=50.
- **Load Testing**: `make load-test` (locust on /experiments); target 1000 req/min.
- **Optimization**: Gunicorn workers=4 for api; async endpoints.

See [docs/performance.md](performance.md) for details.

## Migration and Rollouts

- **DB Migrations**: Alembic; `make be-migrate` on deploy. Backup before.
- **Gradual Rollout**: Blue-green in K8s; monitor errors post-deploy.
- **Rollback**: Git revert; `docker compose down && up -d`.

## Troubleshooting Deployment

- **Services Fail**: `docker compose logs`; check env vars, ports.
- **DB Connection**: Verify URL/creds; test `psql $DATABASE_URL`.
- **High Latency**: Check Grafana; scale api pods.
- **Secrets Exposed**: Rotate keys; audit logs.

For ops scripts: scripts/. Questions: GitHub issues.
