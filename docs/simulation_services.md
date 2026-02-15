# Simulation Services (World, Market, Supply Chain)

## Why This Exists

A lot of the “simulation fidelity” in this repo lives in services under `src/services/`.
These systems are easy to miss because they sit behind the API runner and event bus.

This page documents the major simulation subsystems that drive outcomes over time.

## WorldStore (Canonical State + Arbitration)

File: `src/services/world_store.py`

WorldStore is the authoritative state holder for:
- Product state (price, inventory, cost basis, metadata)
- Command arbitration / conflict resolution (multiple agents issuing commands)
- Snapshot persistence (in-memory and JSON-file backends)

WorldStore also exposes a few “economic knobs” via metadata helpers:
- Marketing visibility multipliers:
  - `get_marketing_visibility(asin)` / `set_marketing_visibility(asin, visibility)`
- Reputation score:
  - `get_reputation_score(asin)` / `set_reputation_score(asin, score)`
- Supplier catalog (lead times):
  - `set_supplier_catalog(...)`, `get_supplier_lead_time(supplier_id)`

## MarketSimulationService (Demand, Sales, Fees, Trust)

File: `src/services/market_simulator.py`

MarketSimulationService is tick-driven and produces realized sales:
- Reads canonical price/inventory from WorldStore
- Computes demand via:
  - Elasticity mode (reference-price demand curve), or
  - Agent-based customer pool (utility-based purchasing)
- Applies a **marketing visibility multiplier** (if present in WorldStore)
- Posts `SaleOccurred` and `InventoryUpdate` events

Important integrations inside this service:
- **Fee model**: `src/services/fee_calculation_service.py`
  - Computes referral/FBA/storage/return/etc fees and returns a breakdown
- **Trust score**: `src/services/trust_score_service.py`
  - Derives a trust score from policy violations + buyer feedback metadata

## SupplyChainService (Orders, Lead Times, Disruptions, Black Swans)

File: `src/services/supply_chain_service.py`

SupplyChainService subscribes to:
- `PlaceOrderCommand` (agents placing inbound inventory orders)
- `TickEvent` (time progression)

It supports:
- Scheduling inbound deliveries at future ticks (base lead time + variance)
- Disruption controls (lead time increase, partial fulfillment rate)
- Stochastic lead time variance (seeded)
- Black swan events (customs holds, port congestion, container shortages, etc.)

When orders arrive, it publishes `InventoryUpdate` events to update canonical inventory.

## Where These Are Wired

The API stack wires core services during app startup:
- `src/fba_bench_api/core/lifespan.py` starts:
  - `WorldStore`
  - `SupplyChainService`
  - `AgentManager` (agent pipeline)

The demo-style simulation loop used by the GUI runs via:
- `src/fba_bench_api/core/simulation_runner.py` (`RealSimulationRunner`)
  - Instantiates `WorldStore` and `MarketSimulationService`
  - Includes an auto-restock helper for visually interesting observer-mode runs

