# Market Dynamics (Competitors, Reviews, Ranking, Ads)

## Overview

The simulation contains several subsystems that create realistic feedback loops:
- competitor pricing pressure
- review/reputation effects
- ranking/visibility multipliers
- ads/auction-style spend mechanics

These systems are implemented under `src/services/` and may be enabled depending on the runner/entrypoint.

## Competitor Simulation

File: `src/services/competitor_manager.py`

CompetitorManager:
- subscribes to `TickEvent`
- updates competitor states (price/BSR/velocity)
- publishes `CompetitorPricesUpdated` events consumed by other services

Related:
- competitor personas: `src/personas/__init__.py`
- competitor events: `src/fba_events/competitor.py`

## Reviews, Ranking, BSR

There are two related (but separate) approaches in the codebase:

1) Review flywheel model:
- `src/services/ranking/review_system.py`

2) EMA-based BSR/velocity indices:
- `src/services/bsr_engine_v3.py`

Integration note:
- Some run paths derive BSR from metadata or heuristics when a dedicated rank engine is not wired.

## Customer Events & Reputation

Files:
- `src/services/customer_event_service.py`
- `src/services/customer_reputation_service.py`
- `src/services/trust_score_service.py`

These modules model:
- views, cart adds, purchases, conversion proxies
- customer service/reputation signals
- trust scores used by metrics and event summaries

## Marketing / Ads / Auctions

Files:
- `src/services/marketing_service.py`
- `src/services/ad_auction.py`
- WorldStore visibility knob: `src/services/world_store.py` (`marketing_visibility`)

The market simulator uses a visibility multiplier (when present) to scale demand, which is the intended “bridge” between marketing spend and realized sales.

## Where To Start

If you want a single “source of truth” for what’s currently wired in the API demo runner, start here:
- `src/fba_bench_api/core/simulation_runner.py` (`RealSimulationRunner`)

And for the always-on core runtime services started with the API:
- `src/fba_bench_api/core/lifespan.py`

