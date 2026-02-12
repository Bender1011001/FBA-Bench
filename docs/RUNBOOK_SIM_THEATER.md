# Simulation Theater Runbook

## Purpose
- Run a live sim and visualize decisions in real time.
- Replay any completed run instantly for demos without waiting on model latency.

## Prerequisites
- `OPENROUTER_API_KEY` must be set for live mode.
- Python available in shell.

## One-Command Live Demo
```bash
python scripts/sim_theater_demo.py --mode live --days 120 --open-browser
```

Use tuned realism profile:
```bash
python scripts/sim_theater_demo.py --mode live --days 120 --realism-config configs/sim_realism.yaml --open-browser
```

What it does:
- Launches the sim (`run_grok_proper_sim.py`).
- Continuously writes live trace to `docs/api/sim_theater_live.json`.
- Serves docs and opens `docs/sim-theater.html`.

## One-Command Replay Demo
Replay a specific run:
```bash
python scripts/sim_theater_demo.py --mode replay --results-file results/grok_proper_sim_<timestamp>.json --open-browser
```

Replay the newest run automatically:
```bash
python scripts/sim_theater_demo.py --mode replay --latest-results --open-browser
```

## Fast Smoke Commands
Live smoke (2 days, no web server):
```bash
python scripts/sim_theater_demo.py --mode live --days 2 --quiet --no-serve
```

Replay smoke (latest run, no web server):
```bash
python scripts/sim_theater_demo.py --mode replay --latest-results --no-serve
```

## Notes for Demo Reliability
- If serving manually: `python -m http.server 8080 --directory docs`, then open `http://localhost:8080/sim-theater.html`.
- If you want the page to stay up after live completion: add `--keep-serving`.
- Replay mode is deterministic because it only reads saved results JSON.
