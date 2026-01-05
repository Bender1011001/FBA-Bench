# OpenRouter Free Models Benchmarking Guide

This guide details how to integrate and execute benchmarks using OpenRouter's free tier models within FBA-Bench Enterprise. It enables zero-cost evaluation of AI models against business simulation scenarios, focusing on reasoning, problem-solving, and strategy.

## Overview

The integration leverages the unified LLM interface in `src/llm_interface/` to support OpenRouter's OpenAI-compatible API. Benchmarks assess models across key areas:
- **Business Reasoning**: Profit analysis, pricing strategies, market decisions.
- **Problem Solving**: Logistics, scheduling, constraints, math.
- **Creative Strategy**: Marketing, budgeting, channels, metrics.

Results include success rates, response times, quality scores, token usage, and error handling. Outputs are JSON-formatted and optionally logged to ClearML.

## Supported Models

Pre-configured free models in `configs/model_params.yaml`:
- `deepseek/deepseek-chat-v3.1:free` – Latest DeepSeek chat model.
- `x-ai/grok-4-fast:free` – Speed-optimized Grok.
- `deepseek/deepseek-r1-0528:free` – DeepSeek reasoning.
- `deepseek/deepseek-chat-v3-0324:free` – Prior DeepSeek chat.
- `tngtech/deepseek-r1t2-chimera:free` – Enhanced community variant.

Parameters (e.g., temperature: 0.7, max_tokens: 4096) are tunable per model.

## Setup

### Prerequisites
- Poetry-installed dependencies (`poetry install`).
- Access to OpenRouter free tier.

### 1. API Key Acquisition
- Register at [OpenRouter](https://openrouter.ai).
- Generate key at [Keys Page](https://openrouter.ai/keys) (prefix: `sk-or-`).

### 2. Environment Configuration
In `.env` (copied from `.env.example`):
```
OPENROUTER_API_KEY=sk-or-your-key-here
```
Loaded via Pydantic Settings in `config/model_config.py`.

### 3. Validation
Execute setup check:
```
poetry run python scripts/validate_openrouter.py
```
(If script missing, implement via `src/llm_interface/openrouter_client.py` or ad-hoc import test.)

Verifies:
- Imports: `GenericOpenAIClient`, `ClearMLTracker`, `CostTrackingService`.
- Config: Models in YAML, API key format.
- Client: Initialization, token counting (tiktoken fallback).

Expected: "All checks passed! Setup ready."

## Running Benchmarks

Use the dedicated runner script (create if absent: `scripts/run_openrouter_benchmark.py`).

### All Free Models
```
poetry run python scripts/run_openrouter_benchmark.py
```

### Single Model
```
poetry run python scripts/run_openrouter_benchmark.py --model "deepseek/deepseek-chat-v3.1:free"
```

### Options
- `--verbose`: Detailed logging.
- `--output results/my_benchmark.json`: Custom JSON path.
- `--scenario core.sourcing`: Limit to specific scenario.

Integrates with:
- `src/benchmarking/engine.py` for execution.
- `src/services/cost_tracking_service.py` for usage.
- `src/instrumentation/clearml_tracking.py` for experiments.

## Metrics and Analysis

Evaluated on:
- **Success Rate**: % of valid completions.
- **Latency**: Avg response time (s).
- **Quality**: Relevance/completeness score (0-1).
- **Tokens**: Input/output totals.
- **Errors**: API failures, timeouts.

View results:
- JSON: In `results/` or specified path.
- ClearML: Dashboard at configured host (e.g., `http://localhost:8080`).
- Grafana: Metrics panels (`config/grafana/`).

## Technical Details

- **API Endpoint**: `https://openrouter.ai/api/v1` (OpenAI-compatible).
- **Auth**: Bearer token via env key.
- **Timeout**: 60s/request.
- **Rate Limits**: Handled by OpenRouter; monitor via dashboard.
- **Token Counting**: Tiktoken for unknown models.
- **Error Handling**: Retries on transients; logs via `fba_events`.

Configs in `config_storage/simulations/` for advanced setups (e.g., `gpt5_learning_full.yaml` adaptable).

## Limitations and Notes

- **Free Tier**: Subject to quotas; monitor usage.
- **Availability**: Models may rotate; update `configs/model_params.yaml`.
- **Costs**: Free tier only; paid models via same interface.
- **Testing**: Unit tests in `tests/benchmarking/test_llm_bots.py`; integration in `tests/integration/test_llm_bots.py`.

For custom integrations, extend `src/llm_interface/generic_openai_client.py`.

See [Benchmarking Engine](benchmarking.md) for core concepts and [Configuration](configuration.md) for YAML details.
