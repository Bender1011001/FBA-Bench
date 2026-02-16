# Promo Video: Fast Path

This repo includes a Godot "Simulation Theater" designed for observer-only recording (cinematic camera, live feed, end-of-run recap).

## Recommended Settings (good for a 30-45s clip)

- `max_ticks`: 240-365
- `speed`: 1.0 (keeps motion readable)
- Cinematic Mode: ON (toggle in UI or press `C`)

## Record With The Script (Windows)

Prereqs:
- Godot 4.5+ installed (set `GODOT_EXE` if it is not on PATH)
- `ffmpeg` on PATH
- Recommended: run the one-click Docker stack (includes Redis + nginx front door):
  ```powershell
  docker compose -f docker-compose.oneclick.yml up -d --build
  ```

Command:
```powershell
poetry install
pwsh scripts/record_godot_demo.ps1 -NoBackend -Port 8080 -Output artifacts/promo/fba_bench_demo.mp4 -MaxTicks 300 -Speed 1.0
```

Notes:
- The script launches the backend (unless `-NoBackend` is set), launches the Godot GUI in demo mode, and records the Godot window by title using `ffmpeg`.
- If window-title capture fails on your machine, run the GUI once, note the actual window title, and pass `-WindowTitle "..."`.

## Suggested Shot List (30s)

1. 0-2s: Title card overlay (add in post): "FBA-Bench: long-horizon agent simulation"
2. 2-10s: Cinematic Mode: camera sweeps the warehouse zones while the live feed shows events.
3. 10-25s: A couple "shock" spikes (inventory drops, restock arrives, demand jumps).
4. 25-30s: End card recap: revenue, profit, units, highlights.

## Suggested On-screen Text

- "One decision per simulated day"
- "Stateful. Adversarial. Long horizon."
- "Bad decisions compound"
- "Observer mode + cinematic recap"
