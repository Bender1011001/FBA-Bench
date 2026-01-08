# Benchmarking - Context

> **Last Updated**: 2026-01-08

## Purpose

The `src/benchmarking` directory contains the core orchestration, configuration, and evaluation framework for FBA-Bench simulations. It manages the execution of benchmark runs across various scenarios and agents.

## Key Files

| File | Description |
|------|-------------|
| `agents/unified_agent.py` | Unified interface for different agent frameworks (DIY, CrewAI, LangChain). |
| `config/pydantic_config.py` | Centralized Pydantic-based configuration management. |
| `core/engine.py` | Main orchestration engine for running benchmarks. |
| `core/results.py` | Result models and storage for benchmark outcomes. |
| `integration/integration_manager.py` | Central coordinator linking benchmarking with external services and agent runners. |
| `evaluation/enhanced_evaluation_framework.py` | Comprehensive evaluation logic for agent performance. |

## Dependencies

- **Internal**: `agent_runners`, `fba_bench`, `fba_bench_core`, `metrics`, `services`, `constraints`, `events`
- **External**: `pydantic`, `asyncio`, `yaml`, `json`

## Usage Examples

```python
from src.benchmarking.core.engine import BenchmarkEngine
from src.benchmarking.config.pydantic_config import BenchmarkConfig

# Create a config
config = BenchmarkConfig(
    benchmark_id="demo_run",
    agents=[...],
    scenarios=[...]
)

# Run benchmark
engine = BenchmarkEngine()
result = await engine.run_benchmark(config=config)
print(f"Overall Score: {result.overall_score}")
```

## Architecture Notes

- **Dual-Mode Engine**: Supports a synchronous "quick path" for unit tests and a full asynchronous implementation for production runs.
- **Unified Agents**: Uses an adapter pattern to wrap various agent frameworks into a consistent interface.
- **Pydantic v2**: Leverages Pydantic v2 for robust configuration validation and serialization.

## Related

- [.agent/context.md](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/.agent/context.md)
- [src/benchmarking/agents/CONTEXT.md](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/benchmarking/agents/CONTEXT.md)
