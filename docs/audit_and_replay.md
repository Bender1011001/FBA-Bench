# Audit & Replay (Forensic Traceability)

FBA-Bench runs are designed to be inspectable: you should be able to explain *why* a result happened and replay it without waiting for model latency.

This page consolidates the audit and replay mechanisms that are otherwise spread across runbooks and subsystem docs.

## What “Replay” Means Here

There are two practical replay paths:

1. **Simulation Theater replay (instant, observer-friendly)**: turns a saved results JSON into a scrub-able playback timeline for `docs/sim-theater.html`.
2. **Offline decision replay (determinism check)**: re-runs the simulator while loading the exact day-by-day decisions from a prior results file (no LLM calls).

## What “Audit” Means Here

Audit is layered:

- **Financial correctness**: double-entry ledger invariants, trial balance, and accounting equation checks.
- **Determinism evidence**: seed discipline + cached LLM responses + golden masters (when used).
- **Event-level traceability**: event bus structured logs and optional recording.

Which layers are active depends on the run path (some tooling is opt-in).

## Key Artifacts (Where To Look)

- Primary results artifact (live runs): `results/grok_proper_sim_*.json`
- Offline replay output: `results/grok_proper_sim_replay_*.json`
- Simulation Theater trace JSON (consumed by `docs/sim-theater.html`): `docs/api/sim_theater_live.json`
- Benchmark audit trails (when enabled by benchmarking/validator paths): `audit_trails/*.json`

## Replay: Simulation Theater (Instant Playback)

Replay the newest completed run:

```powershell
python scripts/sim_theater_demo.py --mode replay --latest-results --open-browser
```

Replay a specific artifact:

```powershell
python scripts/sim_theater_demo.py --mode replay --results-file results/grok_proper_sim_<timestamp>.json --open-browser
```

Notes:
- Replay mode is deterministic because it only reads the saved results JSON.
- The demo script writes a playback trace to `docs/api/sim_theater_live.json`.

See also: `docs/RUNBOOK_SIM_THEATER.md`

## Replay: Offline Deterministic Re-Run (No LLM Calls)

This is the “credibility” check: same simulator code + same seed + same per-day decisions should produce the same outputs (within the contract’s expectations).

```powershell
python run_grok_proper_sim.py --replay-results-file results/grok_proper_sim_<timestamp>.json --seed 42 --quiet --no-live-trace
```

The replay run writes `results/grok_proper_sim_replay_*.json`.

See also: `docs/RUNBOOK_SIM_BENCHMARK_V1.md`

## Audit: Financial Correctness (Ledger)

Ledger docs:
- `docs/ledger_system.md`

Code:
- `src/services/ledger/` (double-entry ledger service)

Practical checks:
- Use `verify_integrity()` as an optional hard-stop integrity check (callers can treat failure as fatal).
- Use transaction history (`get_transaction_history`) for forensic review of “what moved money”.

## Audit: Determinism & Reproducibility Toolkit

Docs:
- `docs/reproducibility.md`
- `docs/quality/golden_master.md`

Key components:
- Deterministic seed tracking + audit trail: `src/reproducibility/sim_seed.py` (`SimSeed`)
- Deterministic RNG wrapper + audit records: `src/reproducibility/deterministic_rng.py`
- LLM response cache (SQLite-backed): `src/reproducibility/llm_cache.py`
- Deterministic LLM wrapper: `src/llm_interface/deterministic_client.py`
- Golden master record/compare: `src/reproducibility/golden_master.py`

Quick golden-master verification:

```powershell
make verify-golden
```

## Audit: Event-Level Traceability

Event bus:
- `src/fba_events/bus.py` (structured logging on publish + optional in-memory recording)

Notes:
- Structured publish logs are **redacted** for common sensitive keys (tokens, api_key, authorization, etc.).
- In-memory event recording is **off by default** and is intended for debugging/diagnostics (not long-term storage).

## Gaps / Caveats (Truthful Defaults)

- `src/services/journal_service.py` (SQLite event journal for event-sourcing style replay) exists but is not currently a default dependency of the main benchmark runbooks.
- `audit.py` contains a legacy “per-tick hash” audit harness; treat it as experimental unless you intentionally wire it into the current run paths.
