# FBA-Bench Enterprise

<div align="center">
  <img src="https://img.shields.io/badge/Live-Leaderboard-9d50bb?style=for-the-badge&logo=github&logoColor=white" alt="Live Leaderboard" />
  <img src="https://img.shields.io/badge/Status-Active-00d2ff?style=for-the-badge" alt="Status" />
  <br/>
  <strong><a href="https://fbabench.com">View the Live Benchmark Leaderboard</a></strong>
</div>

<br/>

<!-- LEADERBOARD_BADGE_START -->
[![Benchmark Status](https://img.shields.io/badge/Benchmark-Results_Ready-success?style=flat-square)](https://fbabench.com)
<!-- LEADERBOARD_BADGE_END -->

## Two Benchmark Modes

| | **Prompt Battery (`prompt`)** | **Agentic Simulation (`agentic`)** |
|---|:---:|:---:|
| **Tests** | Raw model capability | Your full agent system |
| **Memory/RAG** | None | Bring your own |
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

- **Tick-Based Simulation**: Each day is a separate LLM call with real feedback loops.
- **Double-Entry Ledger Subsystem**: GAAP-style accounting primitives and an optional integrity check ("Panic Button") for hard-stop validation on math violations.
- **Red Team Gauntlet**: Automated adversarial attacks (phishing, compliance traps) to test agent security.
- **Long-Term Memory (Per-Day Consolidation)**: Agents reflect nightly to promote/forget memories (prevents context saturation).
- **Competition Awareness Modes**: Agents can be configured to be "aware" vs "unaware" of competition.
- **Agent-Based Consumer Modeling**: Customers make utility-based purchase decisions, not simple demand curves.
- **Budget & Cost Constraints**: Enforce token/cost budgets per tick/run and per tool.
- **Reproducibility Toolkit**: Deterministic seeding + LLM response caching + golden-master regression checks.
- **Plugin Framework**: Extend with scenario/agent/tool/metrics plugins.
- **Modular Agent Ecosystem**: Supports CrewAI, LangChain, and custom frameworks via `src/agent_runners/`.
- **Rich Scenarios**: Supply chain shocks, price wars, demand spikes, and compliance traps.
- **Observer-Mode Visualization**: Godot Simulation Theater (cinematic camera, live feed, end-of-run recap) for recording runs.
- **API & Dashboard**: FastAPI backend with WebSocket streaming.
- **Observability**: ClearML, Prometheus, and OpenTelemetry integration.
- **Settings File**: Configure everything in `simulation_settings.yaml`.

## Quick Start

### One-Click Local Demo (Docker)
```powershell
docker compose -f docker-compose.oneclick.yml up -d --build
```
Open http://localhost:8080

- API health (proxied): `curl.exe -sS http://localhost:8080/api/v1/health`
- FastAPI docs (proxied): http://localhost:8080/docs

### Backend Only (Local, No Docker)
```powershell
poetry install
poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 127.0.0.1 --port 8000
```
Swagger UI: http://localhost:8000/docs

### Godot GUI (Local)
The GUI reads connection settings from environment variables:
- `FBA_BENCH_HTTP_BASE_URL` (default: `http://localhost:8080`)
- `FBA_BENCH_WS_URL` (default: derived from HTTP base, `/ws/realtime`)

Option 1: Use the launcher (starts backend if needed):
```powershell
poetry run python launch_godot_gui.py
```
If Godot is not on PATH, set `GODOT_EXE` to your Godot executable path.

Option 2: Connect the GUI to the one-click Docker stack (nginx on `:8080`):
```powershell
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
- [Features Overview](docs/features_overview.md): Map of major systems and where they live.
- [Ledger System](docs/ledger_system.md): Double-entry accounting primitives and integrity checks.
- [Red Team Gauntlet](docs/red_team_gauntlet.md): Adversarial injection (phishing, compliance traps, manipulation).
- [Long-Term Memory & Modes](docs/cognitive_memory.md): Per-day memory consolidation + competition awareness.
- [Agent-Based Consumer Modeling](docs/consumer_utility_model.md): Utility-based shoppers + visibility multipliers.
- [Simulation Services](docs/simulation_services.md): WorldStore + market simulation + supply chain disruptions.
- [Market Dynamics](docs/market_dynamics.md): Competitors, reviews, ranking, and marketing/ads.
- [Agent Runners](docs/agent_runners.md): Runner adapters, modes, and configuration entry points.
- [Services Catalog](docs/services_catalog.md): Index of `src/services/` modules.
- [Benchmarking System](docs/benchmarking_system.md): Benchmark engine, configs, validators, and adapters.
- [Metrics Suite](docs/metrics_suite.md): Finance/ops/trust/stress/adversarial/cost scoring.
- [Budget Constraints](docs/budget_constraints.md): Token/cost budgets and tier configs.
- [Reproducibility Toolkit](docs/reproducibility.md): Deterministic seeding, caches, and golden masters.
- [Plugin Framework](docs/plugin_framework.md): Extension points for scenarios, agents, tools, and metrics.
- [Contribution Guidelines](CONTRIBUTING.md): Coding standards and PR process.

## Press / Recording

- [Promo Video Runbook](docs/press/promo_video.md): Record an observer-mode run (Godot + ffmpeg).
- [Social Post Copy](docs/press/social_posts.md): Ready-to-paste launch content.

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
