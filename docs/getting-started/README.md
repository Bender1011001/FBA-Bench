# Getting Started

This guide gets you from zero to a working local environment.

## Fastest Path: One-Click Demo (Docker)

This starts a local demo stack (Nginx front door + API + Redis).

```bash
docker compose -f docker-compose.oneclick.yml up -d --build
```

Open:
- UI + docs site: http://localhost:8080
- FastAPI docs (proxied): http://localhost:8080/docs

Verify API health:
```bash
curl -sS http://localhost:8080/api/v1/health
```

Verify API health (Windows PowerShell):
```powershell
curl.exe -sS http://localhost:8080/api/v1/health
```

Stop:
```bash
docker compose -f docker-compose.oneclick.yml down
```

## Backend Only (No Docker)

Prereqs:
- Python 3.10 to 3.13
- Poetry

Install and run:
```bash
poetry install
poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 127.0.0.1 --port 8000
```

Open Swagger UI:
- http://localhost:8000/docs

## Godot GUI (Optional)

Option A: Godot Editor
1. Open Godot 4.5+
2. Import `godot_gui/`
3. Press F5

Option B: Launcher
```bash
poetry run python launch_godot_gui.py
```

If Godot is not on PATH, set `GODOT_EXE` to your Godot executable.

## Next Steps

- API reference: `docs/api/README.md`
- Configuration: `docs/configuration.md`
- Testing: `docs/testing.md`
- Architecture: `docs/architecture.md`
