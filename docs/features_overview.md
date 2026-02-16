# Features Overview

This page is the “map” of the major systems in FBA-Bench Enterprise and where to find the implementation.

## Core Benchmark Modes

- Prompt Battery (`prompt`): fast, model-only evaluation (no tools/memory implied).
- Agentic Simulation (`agentic`): long-horizon, stateful simulation for full agent systems.

See: `docs/benchmark_philosophy.md`

## Simulation Fidelity

- World state + arbitration: `docs/simulation_services.md` (WorldStore)
- Market demand + sales processing: `docs/simulation_services.md` (MarketSimulationService)
- Supply chain disruptions + black swans: `docs/simulation_services.md` (SupplyChainService)
- Fees and unit economics: `docs/simulation_services.md` (FeeCalculationService)
- Trust/reputation signals: `docs/simulation_services.md` (TrustScoreService)

## Security & Adversarial Testing

- Red Team Gauntlet (adversarial injections + scoring): `docs/red_team_gauntlet.md`

## Memory & Agent Modes

- Per-day long-term memory consolidation + competition awareness modes: `docs/cognitive_memory.md`

## Consumers & Demand Modeling

- Utility-based autonomous shoppers: `docs/consumer_utility_model.md`

## Constraints & Fairness

- Token/cost/call budgets and enforcement: `docs/budget_constraints.md`

## Reproducibility

- Deterministic seeding + response caching + golden masters: `docs/reproducibility.md`

## Extensibility

- Plugin framework (scenarios/agents/tools/metrics): `docs/plugin_framework.md`

## Scoring

- Multi-axis metrics suite (finance/ops/trust/stress/adversarial/cost): `docs/metrics_suite.md`

## Observability

- Logs, metrics, tracing, ClearML hooks: `docs/observability_stack.md`

## Learning / Research

- Learning modules and post-run analysis tooling: `docs/learning_systems.md`

## Visualization / Observer Mode

- Godot Simulation Theater (observer-friendly GUI) and recording workflows:
  - `docs/RUNBOOK_SIM_THEATER.md`
  - `docs/press/promo_video.md`
  - `scripts/record_godot_demo.ps1`
