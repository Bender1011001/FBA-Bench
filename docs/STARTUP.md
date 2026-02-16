# FBA-Bench Startup Guide

This guide provides instructions for starting the FBA-Bench application. The project uses a Python FastAPI backend with a Godot 4 GUI for immersive simulation visualization.

## Prerequisites

Before starting, ensure the following are installed and configured:

- **Docker Desktop**: Required for backend services (Postgres, Redis, API). Download from [docker.com](https://www.docker.com/products/docker-desktop/). Start Docker and ensure it's running (check system tray).
- **Python 3.10+**: Required for the backend and launcher scripts.
- **Poetry**: Python dependency manager for the backend. Install via `pip install poetry` or [official guide](https://python-poetry.org/docs/#installation). Verify: `poetry --version`.
- **Godot 4.5+**: For the immersive GUI. Download from [godotengine.org](https://godotengine.org/download). 
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

### Option A: One-Click Local Demo (Recommended)
```
docker compose -f docker-compose.oneclick.yml up -d --build
```
Open http://localhost:8080

- API health (proxied): `curl.exe -sS http://localhost:8080/api/v1/health`
- FastAPI docs (proxied): http://localhost:8080/docs

### Option B: Backend Only (No Docker)
```
poetry install
poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 127.0.0.1 --port 8000
```
Access the API docs at http://localhost:8000/docs.

### Option C: Godot GUI Launcher
```
python launch_godot_gui.py
```
If Godot is not on PATH, set `GODOT_EXE` to your Godot executable path.

## Using the Godot GUI

The Godot GUI is located in `godot_gui/`. 

### Running the GUI

1. **Open with Godot Editor**:
   - Launch Godot 4.5+
   - Click **Import** → Browse to `godot_gui/`
   - Select `project.godot` → **Import & Edit**
   - Press **F5** to run the simulation

2. **With the Launcher** (if Godot is in PATH):
   ```bash
   python launch_godot_gui.py
   ```

3. **Standalone Export**: Export the project from Godot and run the executable

### GUI Features

- **Simulation View**: Real-time 2D visualization of agent decisions, warehouse operations with zone visualization (Receiving, Storage, Packing, Shipping)
- **Leaderboard**: Sortable, filterable rankings of AI models with verification status
- **Sandbox**: Configure experiments with custom scenarios, agent models, and parameters

### GUI Navigation

- **Top Bar**: Switch between Simulation, Leaderboard, and Sandbox views
- **Status Indicator**: Shows connection status (Green = Connected, Red = Disconnected)
- **Simulation Controls**: Start/Stop/Step buttons, speed slider, scenario/model dropdowns

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/simulation` | POST | Create new simulation |
| `/api/v1/simulation/{id}/start` | POST | Start simulation |
| `/api/v1/simulation/{id}/run` | POST | Run simulation (generates tick events) |
| `/api/v1/scenarios` | GET | List available scenarios |
| `/api/v1/llm/models` | GET | List available LLM models |
| `/api/v1/leaderboard` | GET | Get leaderboard data |
| `/ws/realtime` | WebSocket | Real-time event streaming |

## Verification

After startup, verify status:

| Component       | Endpoint/Command                              | Expected Status                          |
|-----------------|-----------------------------------------------|------------------------------------------|
| API             | `curl http://localhost:8000/api/v1/health`    | `{"status": "healthy", ...}` or `{"status": "degraded"}` |
| Database        | `docker compose logs fba-postgres`            | No errors; connections accepted          |
| Redis           | `docker exec fba-redis redis-cli -a fba_dev_redis ping` | `PONG`                       |
| Godot GUI       | Launch via Godot Editor                       | Green "Connected" status indicator       |

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

3. **Godot Project Won't Open**:
   - Error: Parse errors in GDScript files
   - Fix: Clear the `.godot/` cache folder and reimport the project.

4. **Godot Not Found**:
   - Warning: "Godot not found in PATH"
   - Fix: Open Godot manually and import the `godot_gui/` project.

5. **WebSocket Connection Failed**:
   - Symptom: GUI shows "Disconnected"
   - Fix: Ensure the backend is running on port 8000. Check firewall settings.

6. **API Health Check Fails**:
   - Fix: Check backend logs: `docker compose logs fba-api`. Ensure `.env` is configured.

7. **Docker Container Import Errors**:
   - Error: "Could not import fba_bench_api"
   - Fix: See the Docker note in Quick Start section for manual dependency installation.

### Advanced Troubleshooting

- **Full Restart**: `docker compose down -v && docker compose up -d`
- **Logs**: `docker compose logs fba-api --tail 50`
- **Debug Mode**: Set `UVICORN_RELOAD=true` in `.env`
- **Clear Godot Cache**: Delete `godot_gui/.godot/` folder

For issues, check [CONTRIBUTING.md](CONTRIBUTING.md) or open a GitHub issue with logs.

Last updated: January 2026
