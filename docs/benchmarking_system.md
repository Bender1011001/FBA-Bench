# Benchmarking System

## Overview

The benchmarking layer is responsible for:
- defining benchmark runs (configs, scenarios, agents)
- orchestrating execution and collecting artifacts
- scoring via metrics and validators
- publishing results (for leaderboards and reports)

Primary directory: `src/benchmarking/`

## Major Components

- Engine and run models:
  - `src/benchmarking/core/engine.py`
  - `src/benchmarking/core/models.py`
- Configuration manager and schemas:
  - `src/benchmarking/config/manager.py`
  - `src/benchmarking/config/schema.py`
  - `src/benchmarking/config/templates/`
- Registries (agents/scenarios/metrics):
  - `src/benchmarking/agents/registry.py`
  - `src/benchmarking/scenarios/registry.py`
  - `src/benchmarking/metrics/registry.py`
- Validators (fairness, determinism, schema adherence, etc.):
  - `src/benchmarking/validators/`
- Integration adapters (bridging legacy metrics and systems):
  - `src/benchmarking/integration/metrics_adapter.py`
  - `src/benchmarking/integration/agent_adapter.py`

## Metrics

There are two “layers” of metrics in the repo:
- Legacy simulation KPI suite under `src/metrics/` (finance/ops/trust/stress/etc.)
- Benchmarking metrics under `src/benchmarking/metrics/` (prompt-battery style and evaluation framework)

The adapter layer exists to merge/bridge outputs when needed.

See: `docs/metrics_suite.md`

## API Surface

Benchmark operations are exposed through FastAPI routes:
- `src/fba_bench_api/api/routes/benchmarks.py`

See: `docs/api/README.md`

