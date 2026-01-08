# Services - Context

> **Last Updated**: 2026-01-08

## Purpose

Central business logic layer for FBA-Bench. All domain services are unified here to provide a single source of truth for simulation operations, financial tracking, market dynamics, and external integrations.

## Simulation Fidelity (New in Audit 2026-01-07)
- **Competitors**: Now have finite `inventory` and go `out_of_stock`. Reference price calculation ignores OOS competitors (Supply Shock mechanics).
- **Supply Chain**: "Black Swan" events and stochastic lead time variance are now **active**. Orders can be delayed by port congestion/customs.
- **Fees**: `MarketSimulationService` now uses `FeeCalculationService` for accurate FBA/Referral/Storage fees instead of placeholders.


## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Public API - exports all services for use across codebase |
| `world_store.py` | **Core** - Centralized state manager with command arbitration, persistence backends |
| `dashboard_api_service.py` | Real-time simulation state aggregator for GUI/API, subscribes to EventBus |
| `fee_calculation_service.py` | Amazon FBA fee calculations (referral, fulfillment, storage) |
| `market_simulator.py` | Market dynamics, demand curves, competitive pricing simulation |
| `competitor_manager.py` | AI competitor behavior, pricing strategies, market response |
| `supply_chain_service.py` | Inventory flow, supplier management, fulfillment timing |
| `sales_service.py` | Order processing, sales tracking, revenue calculations |
| `bsr_engine_v3.py` | Best Seller Rank simulation engine |
| `trust_score_service.py` | Agent trust/reputation scoring (stateless calculator) |
| `dispute_service.py` | Customer disputes, A-to-Z claims, chargeback handling |
| `external_service.py` | External API integrations (Amazon, Shopify, etc.) |
| `mock_service.py` | Production-ready service implementations with rate limiting, caching |

## Subdirectories

| Directory | Description |
|-----------|-------------|
| `ledger/` | Double-entry accounting system (accounts, transactions, statements) |
| `world_store/` | WorldStore components and utilities |
| `logistics/` | Shipping and fulfillment logic |
| `ranking/` | BSR and ranking algorithms |

## Dependencies

- **Internal**: `fba_events.*` (EventBus events), `fba_bench_core.money` (Money type)
- **External**: `pydantic`, `requests`

## Architecture Notes

1. **Event-Driven**: Services subscribe to `EventBus` events and update state
2. **Stateless by Design**: Most services are stateless calculators; state lives in `WorldStore`
3. **Persistence Backends**: `WorldStore` supports `InMemoryStorageBackend` (dev) and `JsonFileStorageBackend` (prod)

## ⚠️ Known Issues

| File | Issue | Severity |
|------|-------|----------|
| `trust_score_service.py:95` | `get_current_trust_score()` raises `NotImplementedError` - deprecated method, use `calculate_trust_score()` instead | Low (intentional deprecation) |
| `double_entry_ledger_service.py` | Thin compatibility layer - actual impl is in `ledger/` subpackage | Info |

## Usage Example

```python
from src.services import WorldStore, DashboardAPIService, FeeCalculationService

# Initialize services
world_store = WorldStore(event_bus=bus)
dashboard = DashboardAPIService(event_bus=bus)
fees = FeeCalculationService()

# Get simulation snapshot
snapshot = dashboard.get_simulation_snapshot()
```

## Related

- [fba_events](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_events/CONTEXT.md) - Event definitions
- [fba_bench_core](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_bench_core/CONTEXT.md) - Core simulation engine
