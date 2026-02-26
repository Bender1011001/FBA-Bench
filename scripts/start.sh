#!/bin/sh
set -e

# Production startup script for FBA-Bench API
# - Runs database migrations
# - Starts Uvicorn API server in background
# - Starts Nginx in foreground for serving static files and proxying

cd /app

# Set PYTHONPATH for src/ structure
export PYTHONPATH="/app/src:${PYTHONPATH:-}"

# Run Alembic migrations if needed (idempotent)
echo "Running database migrations..."
poetry run alembic upgrade head || true

# Start Uvicorn in background with optimized settings for production
echo "Starting API server on port 8001..."
poetry run uvicorn api_server:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers ${UVICORN_WORKERS:-4} \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout-keep-alive ${UVICORN_TIMEOUT:-120} \
    --access-log \
    --log-level info &

# Wait for Uvicorn to be ready
echo "Waiting for API server to start..."
sleep 5

# Verify API is responding
timeout 30 sh -c 'until curl -f http://localhost:8001/api/v1/health >/dev/null 2>&1; do sleep 1; done' || {
    echo "ERROR: API server failed to start properly"
    exit 1
}

echo "API server is healthy, starting Nginx..."

# Start Nginx in foreground
exec nginx -g 'daemon off;'