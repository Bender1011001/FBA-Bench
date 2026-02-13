# OpenRouter Benchmarking Guide

This repo includes scripts for running benchmark runs against OpenRouter (OpenAI-compatible API).

## Prereqs

- An OpenRouter API key (usually `sk-or-...`)
- Poetry environment installed (`poetry install`)

## Configure

Set the key in your local `.env` (do not commit):
- `OPENROUTER_API_KEY=...`

## Run

```bash
poetry run python run_openrouter_benchmark.py
```

If you need to point at a different base URL or model set, check script flags and config files under `configs/`.

