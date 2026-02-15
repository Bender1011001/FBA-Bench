# API: Less-Obvious Endpoints

This page documents API routes that exist in the codebase but are easy to miss in high-level summaries.

Canonical router registration happens in `src/fba_bench_api/server/app_factory.py`.

## Golden Masters

Route module: `src/fba_bench_api/api/routes/golden.py`

Purpose:
- Create and validate golden-run artifacts
- Support regression checks and credibility workflows

## Medusa

Route module: `src/fba_bench_api/api/routes/medusa.py`

Purpose:
- Internal evaluation/analysis route group used by benchmark workflows

## War Games (Experimental)

Route module: `src/fba_bench_api/api/routes/wargames.py`

Purpose:
- A “micro-sim” / stress harness API surface for running short adversarial or scenario-style games

Important:
- Treat this route group as **experimental** until it is aligned with the current production services
  (there are signs of stale imports and older ledger interfaces in the module).

