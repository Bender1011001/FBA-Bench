# FBA-Bench Startup Guide

This guide provides instructions for starting the FBA-Bench application. The project uses a Python FastAPI backend with a Godot 4 GUI for immersive simulation visualization.

## Prerequisites

Before starting, ensure the following are installed and configured:

- **Docker Desktop**: Required for backend services (Postgres/SQLite, Redis, API). Download from [docker.com](https://www.docker.com/products/docker-desktop/). Start Docker and ensure it's running (check system tray).
- **Python 3.9+**: Required for the backend and launcher scripts.
- **Poetry**: Python dependency manager for the backend. Install via `pip install poetry` or [official guide](https://python-poetry.org/docs/#installation). Verify: `poetry --version`.
- **Godot 4.3+** (optional): For the immersive GUI. Download from [godotengine.org](https://godotengine.org/download). The GUI can also be exported as a standalone executable.
- **Git**: To clone the repo if needed. Verify: `git --version`.

**Hardware**: At least 4GB RAM free, 2 CPU cores.

**Ports**: Ensure the following are free:
- 8000: API (FastAPI)
- 5432: Postgres (if using)
- 6379: Redis
- 3000: Grafana (optional)
- 9090: Prometheus (optional)

Kill conflicting processes if needed (e.g., `netstat -ano | findstr :8000` on Windows).

## Quick Start

### 1. Install Dependencies

```bash
git clone <repo-url> fba-bench
cd fba-bench
poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys (e.g., OPENROUTER_API_KEY=sk-or-v1-...)
```

### 3. Start the Application

**Option A: Using the Godot GUI Launcher (Recommended)**

```bash
poetry run python launch_godot_gui.py
```

This starts the FastAPI backend and launches the Godot GUI application. The GUI provides:
- Real-time simulation visualization
- Interactive leaderboard with filtering
- Sandbox mode for experiment configuration

**Option B: Backend Only (API Server)**

```bash
poetry run python api_server.py
```

Access the API docs at http://localhost:8000/docs.

**Option C: Docker Compose**

```bash
docker compose up -d
```

This starts the full backend stack (API, Postgres, Redis).

## Using the Godot GUI

The Godot GUI is located in `godot_gui/`. To run it:

1. **With Godot Editor**: Open the project in Godot 4.3+ and press F5
2. **With the Launcher**: Run `python launch_godot_gui.py` (starts backend automatically)
3. **Standalone Export**: Export the project from Godot and run the executable

### GUI Features

- **Simulation View**: Real-time 2D visualization of agent decisions, warehouse operations, and market dynamics
- **Leaderboard**: Sortable, filterable rankings of AI models with verification status
- **Sandbox**: Configure experiments with custom scenarios, agent models, and parameters

## Verification

After startup, verify status:

| Component       | Endpoint/Command                              | Expected Status                          |
|-----------------|-----------------------------------------------|------------------------------------------|
| API             | `curl http://localhost:8000/health`           | `{"status": "healthy", ...}` (200 OK)   |
| Database        | `docker compose logs db`                      | No errors; connections accepted          |
| Redis           | `docker exec fba-redis-1 redis-cli ping`      | `PONG`                                   |
| Godot GUI       | Launch via `launch_godot_gui.py`              | Green "Connected" status indicator       |

## Stopping and Cleanup

```bash
# Stop Docker services
docker compose down

# Stop with volume cleanup (removes DB data)
docker compose down -v
```

## Troubleshooting

### Common Issues

1. **Docker Not Running**:
   - Error: "docker compose up failed"
   - Fix: Start Docker Desktop. On Windows, ensure WSL2 enabled.

2. **Port Conflicts**:
   - Error: "Bind address already in use"
   - Fix: Kill processes using the port or edit ports in `.env`.

3. **Godot Not Found**:
   - Warning: "Godot not found in PATH"
   - Fix: Install Godot 4.3+ or add it to your PATH. The backend still runs without Godot.

4. **WebSocket Connection Failed**:
   - Symptom: GUI shows "Disconnected"
   - Fix: Ensure the backend is running on port 8000. Check firewall settings.

5. **API Health Check Fails**:
   - Fix: Check backend logs: `docker compose logs api`. Ensure `.env` is configured.

### Advanced Troubleshooting

- **Full Restart**: `docker compose down -v && docker compose up -d`
- **Logs**: `docker compose logs api | tail -50`
- **Debug Mode**: Set `UVICORN_RELOAD=true` in `.env`

For issues, check [CONTRIBUTING.md](CONTRIBUTING.md) or open a GitHub issue with logs.

Last updated: January 2026