# Godot Recording Mode Guide

## Goal
Record a full simulation run in 16:9 with readable text, cinematic motion, and replay controls.

## Prerequisites
- Godot 4.5+ on PATH (or set `GODOT_EXE`)
- `ffmpeg` on PATH (for automated capture script)
- Poetry dependencies installed

```powershell
poetry install
```

## Quick Verify (Launcher)
This command was executed and verified in this environment:

```powershell
poetry run python launch_godot_gui.py --help
```

## Workflow A: Manual Run + Manual Capture
1. Start backend + GUI:

```powershell
poetry run python launch_godot_gui.py
```

2. In the top bar, click **Recording Layout** (forces 1920x1080 windowed layout).
3. In **Simulation** tab:
- Choose scenario/model
- Click **Start**
- Toggle **Observer Cinematic Mode** (or press `C`) for cleaner framing
4. Use your capture software at **1920x1080 @ 60 FPS**.

## Workflow B: Automated One-Command Video (Recommended)
This script auto-starts a run, enables cinematic mode, records the Godot window, and exits after end card.

```powershell
pwsh scripts/record_godot_demo.ps1 -Output artifacts/promo/fba_bench_demo.mp4 -MaxTicks 300 -Speed 1.0 -Fps 60
```

Optional host override:
```powershell
pwsh scripts/record_godot_demo.ps1 -ApiHost 127.0.0.1 -Port 8000 -Output artifacts/promo/fba_bench_demo.mp4
```

### Use One-Click Docker Backend (`:8080`)
```powershell
docker compose -f docker-compose.oneclick.yml up -d --build
pwsh scripts/record_godot_demo.ps1 -NoBackend -Port 8080 -Output artifacts/promo/fba_bench_demo.mp4 -MaxTicks 300 -Speed 1.0 -Fps 60
```

## Recommended Capture Settings
- Resolution: `1920x1080`
- Frame rate: `60`
- Encoder: `H.264`
- Bitrate target: `16-24 Mbps`
- Audio: off (unless narration required)

## Replay Capture Tips
- Let the run finish once.
- Use bottom replay controls in Simulation view:
  - `Play/Pause`
  - `Scrub`
  - `Speed` (`x0.5` to `x3.0`)
  - `Go Live`
- For social clips, scrub to event spikes (strategy shift, attack, stockout, revenue surge).

## Capture Notes (Before/After)
- **Before**: no replay scrubber, limited visual hierarchy.
- **After**: observer HUD, story feed, replay transport controls, recording layout toggle.

## Troubleshooting
- Godot not found:

```powershell
$env:GODOT_EXE = "C:\Path\To\Godot_v4.5-stable_win64.exe"
poetry run python launch_godot_gui.py
```

- Window capture fails (title mismatch): pass `-WindowTitle` to `record_godot_demo.ps1`.
- Backend not reachable: check `http://127.0.0.1:8000/api/v1/health` (or port `8080` for one-click).
