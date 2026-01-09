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

FBA-Bench Enterprise is an advanced benchmarking framework for evaluating AI agents in complex business simulations, with a focus on e-commerce fulfillment, strategic decision-making, and multi-agent interactions. Built on Python with a modular `src/` architecture, it supports integration with leading LLM providers, custom agent runners, and comprehensive metrics for performance analysis. This enterprise edition extends the core FBA-Bench with proprietary features, API services, observability, and production-ready tooling.

## Key Features

- **Modular Agent Ecosystem**: Supports diverse agent frameworks (e.g., CrewAI, LangChain) via unified runners in `src/agent_runners/`.
- **Rich Simulation Scenarios**: Pre-built business scenarios in `src/scenarios/` covering sourcing, logistics, pricing, and competitive analysis.
- **Benchmarking Engine**: Robust validation and metrics in `src/benchmarking/` for success rates, efficiency, and quality scoring.
- **API and Dashboard**: FastAPI-based services in `src/fba_bench_api/` with real-time event streaming via WebSockets.
- **Observability and Tracking**: Integrated ClearML, Prometheus, and OpenTelemetry for experiment management and monitoring.
- **Plugin System**: Extensible plugins in `src/plugins/` for custom tools, constraints, and integrations.
- **Poetry-Managed Dependencies**: Standardized build and testing with `pyproject.toml` for reproducible environments.
- **Comprehensive Testing**: Unit, integration, contract, and performance tests in `tests/`, with CI parity via Makefile targets.

## Two Benchmarks, Two Purposes

FBA-Bench provides **two distinct benchmarks** to isolate what you're testing:

### 🧠 LLM Benchmark (Pure Model Capability)
```
Input:  Full state + yesterday's results → LLM → Decision
```
- **Tests the LLM itself**, not scaffolding
- No external memory systems, no vector DBs, no RAG
- Every piece of information is in the prompt
- If the model fails, it's the model's fault
- **Runtime: ~6 hours for 1 year** (365 API calls with feedback loop)
- **Cost: ~$1.35** via OpenRouter

**This is the honest benchmark.** No shortcuts, no memory crutches, no excuses.

See: [Why It Takes Hours](docs/why_it_takes_hours.md)

### 🤖 Agent Benchmark (Full System)
```
Input: Context window → Agent (LLM + Memory + Tools + RAG) → Decision
```
- Tests **your agent architecture**, not just the LLM
- Bring your own memory systems, tools, and scaffolding
- Fair comparison of agent frameworks (CrewAI vs LangChain vs DIY)
- Measures system resilience, not just model capability

**Use this when benchmarking your agent code**, not raw models.

## Quick Start

### Prerequisites
- Python 3.9–3.12
- Poetry (install via `curl -sSL https://install.python-poetry.org | python3 -`)

### Installation
1. Clone the repository:
   ```
   git clone https://github.com/<YOUR-ORG>/FBA-Bench-Enterprise.git
   cd FBA-Bench-Enterprise
   ```

2. Install dependencies:
   ```
   poetry install
   ```

3. Copy and configure environment:
   ```
   cp .env.example .env
   # Edit .env for API keys (e.g., OPENAI_API_KEY, CLEARML_API_HOST) and database (default: SQLite)
   ```

4. Run database migrations (for API features):
   ```
   make be-migrate
   ```

### Basic Usage Example
Run a simple benchmark with a baseline agent:
```
poetry run python examples/learning_example.py
```
This executes a learning scenario, tracks metrics, and outputs results to `results/`.

For API server:
```
python api_server.py
```
Access docs at http://localhost:8000/docs.

For the Godot GUI:
```
# Option 1: Open Godot 4.5+, import godot_gui/, press F5
# Option 2: Use the launcher (starts backend automatically)
python launch_godot_gui.py
```

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
- [API Reference](docs/api.md): Endpoints for simulations, experiments, and metrics.
- [Testing Strategy](docs/testing.md): Guidelines for unit, integration, and performance tests.
- [Deployment Guide](docs/deployment.md): Docker Compose setups for dev/prod.
- [Contribution Guidelines](CONTRIBUTING.md): Coding standards and PR process.

## Contributing
We welcome contributions! Follow [CONTRIBUTING.md](CONTRIBUTING.md) for setup, coding standards (ruff, black, mypy), and Conventional Commits. Run `make ci-local` before submitting PRs.

## License
This project is proprietary. See [LICENSE](LICENSE) for details. For support, contact support@fba-bench.com.

## Support
- Issues: [GitHub Issues](../../issues)
- Discussions: [GitHub Discussions](../../discussions)
