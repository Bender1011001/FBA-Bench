# Reproducibility Toolkit

## Overview

Long-horizon simulations are only credible if you can reproduce and audit them. This repo includes a reproducibility toolkit that targets three sources of nondeterminism:
- Randomness inside the simulator
- External LLM API variability
- Regression drift across code changes

Key modules:
- `src/reproducibility/deterministic_rng.py`: deterministic RNG helpers and audit hooks
- `src/reproducibility/sim_seed.py`: seed derivation and component isolation
- `src/reproducibility/llm_cache.py`: persistent LLM response cache (SQLite-backed)
- `src/llm_interface/deterministic_client.py`: deterministic wrapper around any `BaseLLMClient`
- `src/reproducibility/golden_master.py`: golden master record/compare tooling
- `src/reproducibility/simulation_modes.py`: controller for deterministic vs stochastic vs research modes

Note: depending on the run path you use, these modules may be used as an **opt-in toolkit** rather than always-on runtime defaults.

## Simulation Modes

`src/reproducibility/simulation_modes.py` defines:
- `SimulationMode.DETERMINISTIC`: fixed seeds + cached responses only (cache misses should fail)
- `SimulationMode.STOCHASTIC`: live calls + variability allowed (optionally record responses)
- `SimulationMode.RESEARCH`: hybrid mode for controlled variability and robustness studies

The `SimulationModeController` can coordinate mode changes across registered components.

## Deterministic LLM Calls (Caching)

The two pieces are:

1) `LLMResponseCache` (`src/reproducibility/llm_cache.py`)
- Computes a stable prompt hash.
- Stores response payloads in SQLite (with optional compression).
- Supports memory cache + persistence for cross-session replay.

2) `DeterministicLLMClient` (`src/llm_interface/deterministic_client.py`)
- Wraps a real provider client implementing `llm_interface.contract.BaseLLMClient`.
- Supports `OperationMode`:
  - `DETERMINISTIC`: cache-only
  - `STOCHASTIC`: live-only (optionally record)
  - `HYBRID`: cache-first, then live + record

This lets you do things like:
- Record an experiment once
- Re-run it many times deterministically for debugging and regression testing

## Golden Masters

Golden masters are baseline artifacts used to detect regressions in simulation outputs.

Implementation:
- `src/reproducibility/golden_master.py` (`GoldenMasterTester`)

Docs/policy:
- `docs/quality/golden_master.md`

The golden master system supports:
- Recording a labeled baseline run
- Comparing new runs with tolerances (numeric tolerance, ignored fields/patterns, timestamp tolerance)
- Detailed diffs to localize what changed

## Where This Shows Up

You’ll see reproducibility tooling referenced in:
- Test strategy docs (golden masters)
- Benchmarking integration code (deterministic replay expectations)
- CI workflows/scripts that publish or validate run artifacts

