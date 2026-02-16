# FBA-Bench: Launch Plan

This is an execution checklist for shipping a public-facing demo (observer-first), verified run instructions, and outbound-ready marketing assets.

## Current Status (as of 2026-02-16)

- Docs are in place (repo README + `docs/` site build).
- Godot GUI exists for observer viewing (`godot_gui/`) and can be recorded via the provided script (`scripts/record_godot_demo.ps1`).
- Press collateral exists under `docs/press/`.
- Open work: convert this into a repeatable “run, record, publish” pipeline and remove/flag any unverifiable claims (e.g., billing).

## Deliverables (Definition Of Done)

- A 60 to 120 second screen-recorded demo video:
  - Output at `artifacts/promo/fba_bench_demo.mp4`
  - Repro instructions in `docs/press/promo_video.md`
- Public docs/leaderboard pages build cleanly:
  - `make build-docs` produces a valid `docs/` output for GitHub Pages
- “How to run” commands are copy/pasteable on Windows PowerShell and documented consistently:
  - `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/STARTUP.md`
- Provider outreach packet is ready to send:
  - `docs/press/submission_kit.md`
  - `docs/press/provider_outreach.md`
  - `docs/press/social_posts.md`

## Go/No-Go Gates

- `make lint` passes
- `make format-check` passes
- `make type-check-strict` passes (or any failures are explicitly waived in writing with justification)
- `make test-contracts` passes
- `make build-docs` passes
- One demo run is recorded end-to-end, from clean start to exported MP4, with no manual editing required

## Runbook (Verified Commands)

### Backend (Docker one-click)

```powershell
docker compose -f docker-compose.oneclick.yml up -d --build
curl.exe -sS http://localhost:8080/api/v1/health
```

### Backend (local dev)

```powershell
poetry install
poetry run uvicorn fba_bench_api.main:get_app --factory --reload --host 127.0.0.1 --port 8000
curl.exe -sS http://localhost:8000/api/v1/health
```

### Observer Demo (recorded)

Follow `docs/press/promo_video.md`. The default recording script targets the Godot window title and writes to `artifacts/promo/`.

## 2-Week Execution Plan

### Week 1: “Record and Publish”

1. Record one clean demo video using the current recommended path in `docs/press/promo_video.md`.
2. Add the resulting MP4 to the release workflow (or store it in a separate distribution location if repo size is a concern).
3. Run all Go/No-Go gates above locally once and capture outputs in the release notes.
4. Publish refreshed GitHub Pages build (`make build-docs`).

### Week 2: “Outbound and Iteration”

1. Send provider outreach emails using `docs/press/provider_outreach.md`.
2. Post 2 to 3 clips/threads from `docs/press/social_posts.md` and track engagement.
3. Run at least 3 benchmark submissions (different models/providers) and publish results to validate the funnel.

## Claims Audit (Keep It True)

- Do not claim billing is “implemented” or “scaffolded” unless it is clearly present, wired, and tested.
- Prefer phrasing like “planned” or “under evaluation” for items that are not production-ready.

