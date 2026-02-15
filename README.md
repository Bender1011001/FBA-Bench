# FBA-Bench Enterprise

<div align="center">
  <img src="https://img.shields.io/badge/Live-Leaderboard-9d50bb?style=for-the-badge&logo=github&logoColor=white" alt="Live Leaderboard" />
  <img src="https://img.shields.io/badge/Status-Active-00d2ff?style=for-the-badge" alt="Status" />
  <br/>
  <strong><a href="https://fbabench.com">\ud83c\udf10 View the Live Benchmark Leaderboard</a></strong>
</div>

<br/>

<!-- LEADERBOARD_BADGE_START -->
[![Benchmark Status](https://img.shields.io/badge/Benchmark-Results_Ready-success?style=flat-square)](https://fbabench.com)
<!-- LEADERBOARD_BADGE_END -->

## 🎯 Two Benchmark Modes. Know Which One You Need.

| | 🧠 **Prompt Battery (`prompt`)** | 🤖 **Agentic Simulation (`agentic`)** |
|---|:---:|:---:|
| **Tests** | Raw model capability | Your full agent system |
| **Memory/RAG** | ❌ None | ✅ Bring your own |
| **If it fails** | Model's fault | System's fault |
| **Typical runtime** | Minutes | Hours to days |
| **Typical calls** | Dozens of prompts | 180–365 decision steps |
| **Use when** | Comparing LLMs | Comparing architectures |

The prompt battery is the cheap, fast gate. The agentic simulation is the high-fidelity benchmark. The live site supports both: `?mode=prompt` and `?mode=agentic`. For why the agentic benchmark is slow, see [docs/why_it_takes_hours.md](docs/why_it_takes_hours.md).

---

## What is FBA-Bench?

A business simulation benchmark for evaluating AI in complex e-commerce scenarios: inventory, pricing, competitors, and adversarial market events. 

Unlike academic benchmarks that run in minutes, FBA-Bench simulates **real consequences over time**. Each decision affects tomorrow's state. Bad choices compound. Good strategies emerge.

## Key Features

- **Tick-Based Simulation**: Each day is a separate LLM call with real feedback loops
- **Modular Agent Ecosystem**: Supports CrewAI, LangChain, and custom frameworks via `src/agent_runners/`
- **Rich Scenarios**: Supply chain shocks, price wars, demand spikes, and compliance traps
- **Live Visualization**: Watch decisions happen in real-time with `run_grok_live.py`
- **API & Dashboard**: FastAPI backend with WebSocket streaming
- **Observability**: ClearML, Prometheus, and OpenTelemetry integration
- **Settings File**: Configure everything in `simulation_settings.yaml`

## Quick Start

### One-Click Local Demo (Docker)
```
docker compose -f docker-compose.oneclick.yml up -d --build
```
Open http://localhost:8080

- API health (proxied): `curl -sS http://localhost:8080/api/v1/health`
- FastAPI docs (proxied): http://localhost:8080/docs

### Backend Only (Local, No Docker)
```
poetry install
poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 127.0.0.1 --port 8000
```
Swagger UI: http://localhost:8000/docs

### Godot GUI (Local)
The GUI reads connection settings from environment variables:
- `FBA_BENCH_HTTP_BASE_URL` (default: `http://localhost:8080`)
- `FBA_BENCH_WS_URL` (default: derived from HTTP base, `/ws/realtime`)

Option 1: Use the launcher (starts backend if needed):
```
poetry run python launch_godot_gui.py
```
If Godot is not on PATH, set `GODOT_EXE` to your Godot executable path.

Option 2: Connect the GUI to the one-click Docker stack (nginx on `:8080`):
```
docker compose -f docker-compose.oneclick.yml up -d --build
poetry run python launch_godot_gui.py --no-backend --port 8080
```

Tip: toggle "Cinematic Mode" (or press `C`) to hide UI, enable auto-camera, and show the end-of-run recap.

## Development Setup
See [DEV_SETUP.md](DEV_SETUP.md) for detailed instructions, including Makefile commands for linting (`make lint`), testing (`make test-all`), and local CI (`make ci-local`).

## Project Structure
- `src/`: Core packages (`fba_bench_core/`, `fba_bench_api/`, `agents/`, `agent_runners/`, `benchmarking/`, `scenarios/`, `plugins/`, `fba_events/`).
- `godot_gui/`: Immersive Godot 4 GUI for simulation visualization, leaderboards, and sandbox experimentation.
- `tests/`: Unit/integration tests with pytest markers.
- `config/` and `configs/`: YAML configurations and templates.
- `docs/`: Architecture, API, and deployment guides.
- `scripts/`: Utility scripts for experiments and validation.
- `alembic/`: Database migrations.

## Detailed Documentation
- [Architecture Overview](docs/architecture.md): System design and module relationships.
- [API Reference](docs/api/README.md): Endpoints, auth, and realtime WebSocket.
- [Testing Strategy](docs/testing.md): Guidelines for unit, integration, and performance tests.
- [Deployment Guide](docs/deployment.md): Docker Compose setups for dev/prod.
- [Contribution Guidelines](CONTRIBUTING.md): Coding standards and PR process.

## Contributing
We welcome contributions! Follow [CONTRIBUTING.md](CONTRIBUTING.md) for setup, coding standards (ruff, black, mypy), and Conventional Commits. Run `make ci-local` before submitting PRs.

## Sponsorship / Compute Credits
Running long-horizon sims costs money (tokens + infra). If you want the leaderboard updated more often, want a specific model evaluated, or want to sponsor compute credits, see [docs/sponsorship.md](docs/sponsorship.md) or email `support@fba-bench.com`.

## Get On The Leaderboard
Open a GitHub issue using the "Leaderboard Run Request" template, or see [docs/leaderboard_submissions.md](docs/leaderboard_submissions.md).

## License
This project is proprietary. See [LICENSE](LICENSE) for details. For support, contact support@fba-bench.com.

## Support
- Issues: [GitHub Issues](../../issues)
- Discussions: [GitHub Discussions](../../discussions)
