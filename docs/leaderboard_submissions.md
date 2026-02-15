# Leaderboard Submissions

There are two benchmarks:

- `prompt` (fast): a Tier prompt battery that scores structured decision quality and reliability
- `agentic` (slow): the long-horizon "Bankruptcy Test" scored by business outcomes (profit/ROI/survival)

## Request A Run (Recommended)

Open a GitHub issue or email `support [at] fba-bench [dot] com` with:

- model id (example: `deepseek/deepseek-chat-v3.1:free`)
- benchmark type: `prompt` or `agentic`
- tier (`T0`/`T1`/`T2`) and days (for `agentic`)
- any budget/latency constraints

## Self-Run And Submit (Prompt Benchmark)

Prereqs:

- `poetry install`
- `OPENROUTER_API_KEY` set (OpenRouter)

Run the prompt battery for one model:

```powershell
$Env:OPENROUTER_API_KEY="sk-or-..."
poetry run python scripts/batch_runner.py `
  --engine openrouter_prompts `
  --tier T2 `
  --models "deepseek/deepseek-chat-v3.1:free" `
  --workers 1 `
  --results-root public_results/prompt/openrouter_tier_runs
```

```bash
export OPENROUTER_API_KEY="sk-or-..."
poetry run python scripts/batch_runner.py \
  --engine openrouter_prompts \
  --tier T2 \
  --models "deepseek/deepseek-chat-v3.1:free" \
  --workers 1 \
  --results-root public_results/prompt/openrouter_tier_runs
```

Then submit a PR that updates:

- `public_results/prompt/openrouter_tier_runs/t2/summary.json`
- `public_results/prompt/openrouter_tier_runs/t2/*.json`

## Sponsored Runs (Agentic Benchmark)

Agentic runs are long and costly. If you want an agentic run for a paid model, coordinate sponsorship first:

- `docs/#sponsorship.md`

Agentic leaderboard artifacts are stored under:

- `public_results/agentic/openrouter_tier_runs/`
