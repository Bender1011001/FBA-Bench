# Public Results

This folder holds checked-in benchmark result summaries used to build the static site under `docs/` without requiring CI to run expensive simulations.

Layout:

- `public_results/agentic/openrouter_tier_runs/` : long-horizon simulation summaries ("Bankruptcy Test")
- `public_results/prompt/openrouter_tier_runs/` : prompt battery summaries (cheap + reproducible)

Update (prompt example):

```powershell
$Env:OPENROUTER_API_KEY="sk-or-..."
poetry run python scripts/batch_runner.py `
  --engine openrouter_prompts `
  --tier T2 `
  --models "deepseek/deepseek-chat-v3.1:free" `
  --workers 1 `
  --results-root public_results/prompt/openrouter_tier_runs
python generate_github_pages.py
```

