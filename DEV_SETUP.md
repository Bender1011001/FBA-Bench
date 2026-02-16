# FBA-Bench Development Setup

This guide provides step-by-step instructions for setting up the FBA-Bench project for local development. It reflects the standardized Poetry workflow, `src/` package structure, and Makefile-based commands for consistency and reproducibility.

## Prerequisites

- **Python**: 3.10–3.13 (tested with 3.10+; Poetry manages versions).
- **Poetry**: Dependency and environment manager. Install via:
  ```
  curl -sSL https://install.python-poetry.org | python3 -
  ```
  Add to PATH if needed (`export PATH="$HOME/.local/bin:$PATH"` on Unix).
- **Git**: For cloning and version control.
- **Docker** (optional): For containerized services like PostgreSQL, Redis, or full-stack dev.
- **Node.js** (if using frontend components): 18+ for any JS/TS tools (e.g., in `web/` or `frontend/` if present).
- **Make**: Standard on Unix; on Windows, use Git Bash, WSL, or install via Chocolatey (`choco install make`).

Ensure your system meets these for smooth operation. No additional global packages are required—Poetry handles everything.

## Installation

### 1. Clone the Repository
```
git clone https://github.com/your-org/FBA-Bench.git
cd FBA-Bench
```

### 2. Install Dependencies with Poetry
Poetry creates a virtual environment and installs from `pyproject.toml` and `poetry.lock`:
```
poetry install
```
This includes:
- Runtime: FastAPI, SQLAlchemy, Pydantic, etc.
- Dev groups: pytest, ruff, mypy, black, isort.
- Optional: Add `--with dev` explicitly if needed.

Activate the shell for commands:
```
poetry shell
```
Or prefix with `poetry run` (e.g., `poetry run pytest`).

**Notes**:
- Locks ensure reproducibility; commit `poetry.lock`.
- If switching Python versions, run `poetry env use python3.11` and reinstall.
- For editable installs of sub-packages (e.g., `src/fba_bench_core`), Poetry handles via paths in `pyproject.toml`.

### 3. Verify Installation
Run a quick check:
```
poetry run python -c "import fba_bench_core; print('Core imported successfully')"
```
Expected: No errors, confirming `src/` imports.

## Environment Configuration

1. Copy the example:
   ```
   cp .env.example .env
   ```

2. Edit `.env` for your setup (defaults are dev-friendly):
   - **Database**: `DATABASE_URL=sqlite:///./fba_bench.db` (local SQLite; no server needed). For PostgreSQL: `postgresql+psycopg2://user:pass@localhost/fba_bench`.
   - **Secrets**: `SECRET_KEY=dev-secret-change-me` (generate secure for prod), `JWT_SECRET=dev-jwt-secret`.
   - **API Keys**: `OPENAI_API_KEY=sk-...` (or OpenRouter, etc.), `CLEARML_API_HOST=http://localhost:8080`.
   - **Argon2 Params**: Defaults secure; tune for performance (`ARGON2_TIME_COST=3`, etc.).
   - **Stripe** (if using billing): `STRIPE_SECRET_KEY=sk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...`.

Pydantic Settings in `config/model_config.py` loads `.env` automatically. Never commit `.env`—add to `.gitignore`.

**Security Note**: Use `.env.prod` for production; tools like Docker secrets for orchestration.

## Database Setup and Migrations

The API uses Alembic for schema management (`alembic/`).

1. Ensure `DATABASE_URL` in `.env`.

2. Apply migrations:
   ```
   make be-migrate
   ```
   Or directly: `poetry run alembic upgrade head`.

This creates tables (e.g., `users`, `experiments`, `metrics`) in the DB. For SQLite, `fba_bench.db` appears in root.

**Verification**:
- SQLite: `sqlite3 fba_bench.db "SELECT name FROM sqlite_master WHERE type='table';"`
- PostgreSQL: `psql $DATABASE_URL -c "\dt"`.
- Expected: Tables like `users` (id, email, password_hash, etc.).

**Troubleshooting**:
- "No such table": Re-run migrations.
- Connection errors: Check URL format; ensure Postgres running (`docker-compose up postgres` if using Docker).
- Alembic config: `alembic.ini` points to `.env`; edit if custom.

## Running the Project

### API Server
Start the FastAPI app:
```
poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 0.0.0.0 --port 8000
```
- `--reload`: Auto-restarts on code changes (dev only).
- Access: http://localhost:8000/docs (Swagger UI), /redoc (ReDoc).
- Logs: Includes startup checks (DB connect, env validation).

For full stack (with Redis, ClearML):
```
make dev-up  # If Makefile target; else docker-compose -f docker-compose.dev.yml up
```

### Example Runs
- Simple simulation: `poetry run python examples/learning_example.py`
- Benchmark: `poetry run python scripts/run_benchmark.py --config configs/smoketest.yaml`
- Experiment CLI: `poetry run python experiment_cli.py --scenario core.sourcing`

Outputs to `results/` or `artifacts/`; tracked in ClearML if configured.

### Frontend (if applicable)
If JS components (e.g., dashboard in `web/`):
```
cd web
npm install
npm run dev  # Vite server at http://localhost:5173
```
Set `VITE_API_BASE_URL=http://localhost:8000` in `web/.env`.

## Standardized Commands (Makefile)

The `Makefile` provides CI/CD parity. Run from root:

- **Lint**: `make lint` – Ruff static analysis.
- **Format Check**: `make format-check` – Verify black/ruff-format/isort.
- **Format Fix**: `make format-fix` – Auto-format sources.
- **Type Check**: `make type-check` – Mypy strict on `src/`.
- **Tests**:
  - Contracts: `make test-contracts` – Fast schema/API checks.
  - Unit/Integration: `poetry run pytest -m "not integration"` (default skips integration).
  - Full Suite + Coverage: `make test-all` – All tests, generates `.coverage` and `coverage.xml`.
  - Integration Only: `poetry run pytest -m integration -v`.
- **Local CI**: `make ci-local` – Full lint/format/type/test bundle (mirrors GitHub Actions).
- **Migrations**: `make be-migrate` – Alembic upgrade.
- **Pre-Commit**: Install hooks: `make pre-commit-install`; Run: `make pre-commit-run`.

**Example Workflow**:
```
make ci-local  # All checks
git add .
git commit -m "feat(benchmarking): add validator"
```

**Customization**: Edit `Makefile` for new targets; uses `poetry run` internally.

## Testing

### Running Tests
- All (fast): `poetry run pytest -q` – Unit/contracts only.
- Coverage: `make test-all` – Reports missing lines.
- Specific: `poetry run pytest tests/benchmarking/ -v`.

Framework: Pytest with markers (`@pytest.mark.unit`, `@pytest.mark.integration`). Fixtures in `tests/fixtures/`. Coverage targets `src/` (>80% goal).

**DB for Tests**: Uses in-memory SQLite; no external DB needed. Run `make test-all` post-setup.

### Linting and Formatting
Pre-commit hooks enforce on `git commit`. Manual:
```
make lint  # Check only
make format-fix  # Apply
```

## Troubleshooting Common Issues

### Poetry/Venv Problems
- **"Poetry not found"**: Add to PATH; restart terminal.
- **Version mismatch**: `poetry env info`; recreate: `poetry env remove --all && poetry install`.
- **Lock conflicts**: `poetry lock --no-update`; resolve manually.

### Database Errors
- **SQLite locked**: Close other connections; delete `*.db` and re-migrate.
- **Postgres connection refused**: Start server (`docker run -p 5432:5432 -e POSTGRES_PASSWORD=pass postgres`), update URL.
- **Migration fails**: `poetry run alembic downgrade -1`; check `alembic/versions/`.

### Import Errors
- **"Module not found"**: Ensure `poetry shell` or `poetry run`; check `PYTHONPATH` if needed (rare).
- **Cyclic imports**: Review `src/` layers; use absolute imports (`from src.fba_bench_core import ...`).

### API Startup Fails
- **Env missing**: Verify `.env` vars (e.g., `SECRET_KEY`); app logs specifics.
- **Port in use**: Change `--port 8001`; kill process (`netstat -ano | findstr :8000` on Windows).
- **CORS/HTTPS**: Dev defaults allow localhost; prod configure in `src/fba_bench_api/main.py`.

### Tests Fail
- **Integration skips**: Add `-m integration`.
- **Coverage low**: Run `make test-all`; fix in `src/`.
- **Fixture errors**: Check `tests/conftest.py`; ensure deps installed.

### Performance/Slowdown
- **Large simulations**: Use `--max-tokens 1024` in configs; monitor with `make lint` for inefficiencies.
- **Memory**: Poetry envs are isolated; close unused terminals.

### General
- **Windows Paths**: Use forward slashes in URLs; Git Bash for commands.
- **Clear Cache**: `poetry cache clear --all`; `rm -rf .mypy_cache .ruff_cache`.
- **Logs**: Enable debug in `.env` (`LOG_LEVEL=DEBUG`); check `logs/`.
- **Reinstall**: Nuclear option: `rm -rf .venv poetry.lock && poetry install`.

For persistent issues, check [troubleshooting/](docs/troubleshooting/) or open an issue.

## Next Steps

- Run `make ci-local` to validate setup.
- Explore examples: `examples/real_world_integration_example.py`.
- Contribute: See [CONTRIBUTING.md](CONTRIBUTING.md).

This setup ensures a robust, reproducible dev environment aligned with project standards.
