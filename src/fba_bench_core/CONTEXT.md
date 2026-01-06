# FBA-Bench Core - Context

> **Last Updated**: 2026-01-05

## Purpose

Core simulation engine and foundational types for FBA-Bench. Contains the **source-of-truth** implementations for Money, EventBus, configuration, and the simulation orchestrator. Other packages depend on this.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package metadata, exports `__version__` (3.0.0rc1) and `get_build_metadata()` |
| `money.py` | **Core** - Money type with integer cents, currency support, Pydantic compatibility |
| `event_bus.py` | **Core** - Legacy compatibility shim bridging to `fba_events.bus` |
| `config.py` | `AppSettings` (Pydantic Settings) - centralized config with YAML/env overlay |
| `settings.py` | Additional configuration settings |
| `simulation_orchestrator.py` | Async tick generator, publishes `TickEvent` on schedule |
| `logging.py` | Centralized logging configuration |
| `cli.py` | Command-line interface for running benchmarks |

## Subdirectories

| Directory | Description |
|-----------|-------------|
| `core/` | Core types: `fba_types.py` (SimulationState, ToolCall), `llm_validation.py` |
| `domain/` | Domain models: `finance/`, `market/` |
| `models/` | Pydantic models: `competitor.py`, `product.py`, `sales_result.py` |
| `agents/` | Agent-related core utilities |
| `benchmarking/` | Core benchmarking utilities |

## Key Types

```python
# Money (integer cents, performant)
from fba_bench_core.money import Money
m = Money(1234, "USD")  # $12.34
m = Money(amount="12.34", currency="USD")  # Legacy Pydantic format

# Configuration
from fba_bench_core.config import get_settings
settings = get_settings()

# EventBus (compatibility shim)
from fba_bench_core.event_bus import EventBus, get_event_bus
bus = get_event_bus()

# Simulation types
from fba_bench_core.core.fba_types import SimulationState, ToolCall
```

## Architecture Notes

1. **Money is integer cents** - All monetary calculations use integer cents to avoid floating-point errors
2. **EventBus compatibility** - `event_bus.py` shims legacy code to use `fba_events.bus` internally
3. **Config priority**: Built-in defaults → YAML overlay (`FBA_CONFIG_PATH`) → Environment variables
4. **Version**: Currently `3.0.0rc1` (release candidate)

## Related

- [fba_events](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_events/CONTEXT.md) - Event types
- [services](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/services/CONTEXT.md) - Unified services (canonical location)
