# syntax=docker/dockerfile:1.7
# Production-grade container for FBA-Bench API
# - Uses Poetry to install dependencies (no dev deps)
# - Runs as non-root
# - Healthcheck hits /api/v1/health
# - Exposes 8000
# - Optimized for new src/ structure

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false

# System dependencies for common wheels (e.g., cryptography) and build
RUN apt-get update -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libffi-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "poetry==${POETRY_VERSION}"

WORKDIR /app
ENV PYTHONPATH=/app/src

# Leverage Docker layer caching: copy lock/manifest first
COPY pyproject.toml poetry.lock ./

# Install only main dependencies for production
RUN poetry install --only main --no-interaction --no-ansi

# Copy source code and configuration
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY api_server.py ./

# Copy optional configuration files (handled in docker-compose)
# clearml.conf will be mounted as volume if needed

# Create an unprivileged user and writable data dir
RUN useradd -ms /bin/bash appuser \
    && mkdir -p /data /app/logs \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

# Basic healthcheck against FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=6 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# Default command optimized for the new structure
CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
