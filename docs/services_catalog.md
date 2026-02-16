# Services Catalog (`src/services/`)

This page lists the main service modules and what they model. Treat this as a “directory index” for the simulation layer.

## Core Runtime Services

- `src/services/world_store.py`: canonical state store (price, inventory, metadata), arbitration, snapshots.
- `src/services/market_simulator.py`: demand and sales processing (elasticity or customer-agent mode), fees, trust score, events.
- `src/services/supply_chain_service.py`: inbound ordering, lead times, disruptions, black swans, inventory arrivals.

## Economics / Unit Economics

- `src/services/fee_calculation_service.py`: referral/FBA/storage/return/prep/etc fee breakdowns.
- `src/services/cost_tracking_service.py`: tracks costs of LLM/tool usage (used for reporting/metrics).

## Competitors / Market Pressure

- `src/services/competitor_manager.py`: competitor state evolution and `CompetitorPricesUpdated` publication.

## Trust / Reputation / Customer Experience

- `src/services/trust_score_service.py`: stateless trust-score calculator from violations + feedback.
- `src/services/trust_score_handler.py`: glue layer for ingesting trust-related events/signals (where wired).
- `src/services/customer_event_service.py`: models view/cart/purchase event streams and conversion proxies.
- `src/services/customer_reputation_service.py`: reputation-related state and derived signals (where wired).

## Marketing / Ads

- `src/services/marketing_service.py`: marketing spend/control surfaces (where wired).
- `src/services/ad_auction.py`: ad auction primitives (where wired).

## Reporting / Dashboards / Journaling

- `src/services/dashboard_api_service.py`: aggregates events into dashboard-friendly snapshots and recent-event feeds.
- `src/services/journal_service.py`: event journaling/persistence helper (SQLite-backed) used by some flows.

## Disputes / Edge-Case Workflows

- `src/services/dispute_service.py`: dispute decisioning and (optional) ledger-impacting workflows.

## Tooling Helpers

- `src/services/toolbox_api_service.py`: tool-call service surface (API-side utility).
- `src/services/toolbox_schemas.py`: tool schema definitions used for structured tool calls.
- `src/services/external_service.py`: adapter for integrating external APIs/services in a controlled way.
- `src/services/mock_service.py`: mock/test doubles for simulation services.

## Ledger Package (Subsystem)

The double-entry ledger implementation lives under:
- `src/services/ledger/`

See: `docs/ledger_system.md`

## Ranking Package (Subsystem)

Ranking/reviews live under:
- `src/services/ranking/`

See: `docs/market_dynamics.md`

