# Scenarios System

## Overview

Scenarios define the environment an agent is evaluated in: event distributions, starting state, and what actions matter.

There are two scenario layers in this repo:
- Benchmarking scenarios (registered and run by the benchmark engine).
- Simulation/event utilities that can generate or coordinate scenario-like runs.

## Where Scenarios Live

Primary directory:
- `src/scenarios/`

Related registries (benchmark layer):
- `src/benchmarking/scenarios/registry.py`
- `src/benchmarking/scenarios/base.py`

## Scenario Generation & Coordination Utilities

The repo includes utilities for generating or coordinating scenarios:
- `src/scenarios/scenario_generator.py`: programmatic scenario generation helpers.
- `src/scenarios/multi_agent_coordinator.py`: helpers for coordinating multi-agent runs.

## Integration Notes

Some “dynamic generator” code paths are experimental and may depend on template directories that are not present in this repo snapshot. If you intend to ship scenario templating as a public feature, treat it as an explicit deliverable:
- ensure templates exist under version control
- document the supported schema
- provide at least one end-to-end example that runs via the API and/or benchmark runner

## Recommended Next Steps (Productized Scenarios)

1. Publish a small set of canonical tiers (T0–T3) with clear definitions:
   - what shocks happen
   - how frequently
   - what the agent is allowed to do
2. Provide a “scenario contract” doc and validation tests.
3. Ensure every scenario can be replayed deterministically (seeded).

