# API Routes Catalog (`src/fba_bench_api/api/routes/`)

This is a quick index of the route modules and their purpose.

Core (most used):
- `root.py`: root landing routes
- `simulation.py`: simulation create/start/stop/run control
- `realtime.py`: WebSocket realtime + simulation snapshot/events
- `metrics.py`: metrics endpoints (`/api/metrics`, plus API-level summaries)
- `leaderboard.py` / `public_leaderboard.py`: leaderboard reads and public snapshot routes
- `experiments.py`: experiment CRUD and listing
- `scenarios.py`: scenario listing and selection helpers
- `agents.py`: agent listing

Benchmarking:
- `benchmarks.py`: benchmark run orchestration and status

Operations / setup:
- `settings.py`: settings/config endpoints
- `config.py`: config inspection
- `setup.py`: environment/setup helpers
- `stack.py`: stack management endpoints (where enabled)
- `templates.py`: templates for scenarios/configs

Demo:
- `demo.py`: demo data population endpoints (development convenience)

Special / experimental:
- `golden.py`: golden master / deterministic replay workflows
- `medusa.py`: internal evaluation route group
- `wargames.py`: war-games micro-sim route group (experimental)

