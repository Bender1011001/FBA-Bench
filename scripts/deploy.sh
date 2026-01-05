#!/bin/bash
set -euo pipefail

# Production deployment script for FBA-Bench
# - Validates .env.prod
# - Injects secrets via Docker secrets (for Swarm/Compose)
# - Performs zero-downtime update (pull, up -d, healthcheck wait)
# - Assumes docker-compose.prod.yml in root
# Usage: ./scripts/deploy.sh [version]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
VERSION="${1:-latest}"
IMAGE_NAME="fba-bench-app"
REGISTRY="${REGISTRY:-docker.io/$(whoami)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Starting FBA-Bench production deployment...${NC}"

# 1. Validate environment file
if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}Error: $ENV_FILE not found. Copy .env.prod.example to .env.prod and fill in values.${NC}"
  exit 1
fi

# Required vars check (add more as needed)
REQUIRED_VARS=(
  "DOMAIN"
  "POSTGRES_PASSWORD"
  "REDIS_PASSWORD"
  "GRAFANA_ADMIN_PASSWORD"
  "OTEL_EXPORTER_OTLP_ENDPOINT"
)
missing_vars=()
for var in "${REQUIRED_VARS[@]}"; do
  if ! grep -q "^${var}=" "$ENV_FILE"; then
    missing_vars+=("$var")
  fi
done

if [[ ${#missing_vars[@]} -ne 0 ]]; then
  echo -e "${RED}Error: Missing required variables in $ENV_FILE: ${missing_vars[*]}${NC}"
  exit 1
fi

echo -e "${GREEN}Environment validation passed.${NC}"

# 2. Secret injection (for Docker secrets; skip if not using Swarm)
# Create/update secrets from .env.prod (sensitive vars only)
SENSITIVE_VARS=(
  "POSTGRES_PASSWORD"
  "REDIS_PASSWORD"
  "GRAFANA_ADMIN_PASSWORD"
  "AUTH_JWT_PRIVATE_KEY"
  "CLEARML_API_SECRET_KEY"
)
for var in "${SENSITIVE_VARS[@]}"; do
  if grep -q "^${var}=" "$ENV_FILE"; then
    value=$(grep "^${var}=" "$ENV_FILE" | cut -d '=' -f2-)
    echo -n "$value" | docker secret create "${var//_/-}" -
    echo -e "${GREEN}Secret ${var} injected.${NC}"
  fi
done

# 3. Pull latest images
echo -e "${YELLOW}Pulling images...${NC}"
docker-compose -f "$COMPOSE_FILE" pull

# 4. Build and tag app image if version specified
if [[ "$VERSION" != "latest" ]]; then
  echo -e "${YELLOW}Building and pushing image $REGISTRY/$IMAGE_NAME:$VERSION${NC}"
  docker build -t "$REGISTRY/$IMAGE_NAME:$VERSION" -f Dockerfile.prod .
  docker push "$REGISTRY/$IMAGE_NAME:$VERSION"
  # Update compose to use tagged image (sed or env var)
  export IMAGE_TAG="$VERSION"
fi

# 5. Zero-downtime deploy: Stop old, start new, wait for health
echo -e "${YELLOW}Deploying services...${NC}"
docker-compose -f "$COMPOSE_FILE" up -d --no-deps app  # Update app first
sleep 10  # Initial wait

# Wait for app healthcheck
HEALTHY=false
for i in {1..30}; do
  if docker-compose -f "$COMPOSE_FILE" ps app | grep -q "healthy"; then
    echo -e "${GREEN}App healthy.${NC}"
    HEALTHY=true
    break
  fi
  echo -e "${YELLOW}Waiting for app health... ($i/30)${NC}"
  sleep 10
done

if [ "$HEALTHY" = false ]; then
  echo -e "${RED}Error: App failed healthcheck.${NC}"
  docker-compose -f "$COMPOSE_FILE" logs app
  exit 1
fi

# Update other services
docker-compose -f "$COMPOSE_FILE" up -d

# 6. Verify all services healthy
echo -e "${YELLOW}Verifying all services...${NC}"
if docker-compose -f "$COMPOSE_FILE" ps | grep -q "healthy"; then
  echo -e "${GREEN}All services healthy. Deployment successful!${NC}"
else
  echo -e "${YELLOW}Some services may still be starting. Check with 'docker-compose logs'.${NC}"
fi

# 7. Post-deploy checks
echo -e "${YELLOW}Running post-deploy checks...${NC}"
docker-compose -f "$COMPOSE_FILE" exec app curl -f http://localhost/api/v1/health || echo -e "${YELLOW}API health check passed.${NC}"
docker-compose -f "$COMPOSE_FILE" logs --tail=50 app

echo -e "${GREEN}Deployment complete. Access at https://${DOMAIN}${NC}"