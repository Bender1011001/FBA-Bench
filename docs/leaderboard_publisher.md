# Leaderboard Publishing

The static leaderboard site is served from `docs/` (GitHub Pages compatible).

Data files:
- `docs/api/leaderboard.json`
- `docs/api/leaderboard_agentic.json` (optional)
- `docs/api/leaderboard_prompt.json` (optional)
- `docs/api/live.json`

Generating/updating:
- Use the scripts under `tools/` and `scripts/` that write these JSON files during runs.

Local preview:
```bash
python -m http.server 8080 --directory docs
```
