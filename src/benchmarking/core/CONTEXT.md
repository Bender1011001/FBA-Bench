# Benchmarking Core - Context

> **Last Updated**: 2026-01-08

## Purpose

This directory contains the core engine and execution logic for the FBA-Bench benchmarking system. It orchestrates the lifecycle of benchmark runs, agent-scenario interactions, and result collection.

## Key Files

| File | Description |
|------|-------------|
| `engine.py` | The main `BenchmarkEngine` class that manages benchmark execution and loops over agents/scenarios. |
| `results.py` | Data structures for `AgentRunResult`, `MetricResult`, and `BenchmarkResult`. |
| `types.py` | Common type definitions and enums for the benchmarking system. |

## Dependencies

- **Internal**: `benchmarking.agents`, `benchmarking.scenarios`, `benchmarking.metrics`, `benchmarking.config`
- **External**: `asyncio`, `logging`, `pydantic`

## Usage Examples

```python
from benchmarking.core.engine import BenchmarkEngine
from benchmarking.config.pydantic_config import BenchmarkConfig

# Create engine with config
config = BenchmarkConfig(...)
engine = BenchmarkEngine(config=config)
await engine.initialize()

# Run benchmark
results = await engine.run_benchmark()
await engine.save_results()
```

## Architecture Notes

- **BenchmarkEngine**: The heart of the system.
  - Supports both "Classic" mode (using config dicts) and "Pydantic" mode (using `BenchmarkConfig`).
  - Supports dependency injection for agents and scenarios via registries.
  - Instantiates scenarios dynamically, handling both legacy dict configs and modern Pydantic `ScenarioConfig`.
  - Instantiates agents via `agent_registry.create_agent` or directly if pre-configured.

## Related

- [Scenarios Context](../scenarios/CONTEXT.md)
- [Agents Registry](../agents/registry/CONTEXT.md)
