version: "3.9"

services:
  postgres:
    image: postgres:15-alpine
    container_name: ${tenant}-postgres
    environment:
      POSTGRES_USER: ${tenant}_user
      POSTGRES_PASSWORD: ${tenant}_password
      POSTGRES_DB: ${tenant}_db
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "${postgres_port}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${tenant}_user -d ${tenant}_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - ${tenant}-net

  redis:
    image: redis:7-alpine
    container_name: ${tenant}-redis
    command: redis-server --appendonly yes --requirepass ${redis_password}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${redis_password}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped
    ports:
      - "${redis_port}:6379"
    networks:
      - ${tenant}-net

  api:
    image: fba-bench:${api_image_tag}
    container_name: ${tenant}-api
    # If using local build:
    # build:
    #   context: .
    #   dockerfile: Dockerfile
    command: ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
    environment:
      DATABASE_URL: "postgresql+asyncpg://${tenant}_user:${tenant}_password@postgres:5432/${tenant}_db"
      FBA_BENCH_REDIS_URL: "redis://:${redis_password}@redis:6379/0"
      LOG_LEVEL: "INFO"
      ENVIRONMENT: "${environment}"
      # Add other env vars from .env here if needed or use env_file
    env_file:
      - .env
    ports:
      - "${api_port}:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - ${tenant}-net
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  ${tenant}-net:
    driver: bridge
