# Simulation Benchmark V1 Runbook

This runbook defines the minimum quality gate for `run_grok_proper_sim.py` artifacts.

## 1) Validate a single run artifact

Latest artifact:

```bash
python scripts/verify_sim_benchmark_contract.py --latest
```

Specific artifact:

```bash
python scripts/verify_sim_benchmark_contract.py --results-file results/grok_proper_sim_<timestamp>.json --json
```

Contract file used by default:

`configs/sim_benchmark_contract_v1.json`

## 2) Run benchmark matrix (multi-seed, multi-profile)

Default profiles:
- `baseline` -> `configs/sim_realism.yaml`
- `stress_returns` -> `configs/sim_realism_stress_returns.yaml`

Run:

```bash
python scripts/run_sim_benchmark_matrix.py --days 14 --seeds 42,43,44 --strict-contract
```

Dry-run (no simulation calls):

```bash
python scripts/run_sim_benchmark_matrix.py --days 14 --seeds 42,43,44 --print-only
```

Output bundle:

`results/sim_benchmark_matrix/<UTC_TIMESTAMP>/summary.json`

The bundle includes:
- per-run status and key metrics
- per-run contract validation report
- profile-level aggregates (mean/stddev/min/max)

## 3) Profile overrides

Custom profile list (repeat `--profile`):

```bash
python scripts/run_sim_benchmark_matrix.py \
  --days 14 \
  --seeds 42,43 \
  --profile baseline=configs/sim_realism.yaml \
  --profile stress=configs/sim_realism_stress_returns.yaml
```

## 4) What "pass" means

A run is considered contract-valid when all invariants pass, including:
- accounting identities (`net_profit`, `equity_profit`, `final_equity`)
- ROI consistency
- daily series sums and length checks
- decision-day contiguity (`1..days`)
- minimum execution sanity (`llm_calls >= days`)

## 5) Deterministic replay (credibility)

Every live run stores `decisions_raw` per day inside the results artifact.

Replay the run offline (no LLM calls) to verify the simulator is deterministic given:
- same code revision
- same `--seed`
- same `--realism-config`
- same `decisions_raw`

```bash
python run_grok_proper_sim.py --replay-results-file results/grok_proper_sim_<timestamp>.json --seed 42 --quiet --no-live-trace
```

Replay artifacts are written as:

`results/grok_proper_sim_replay_*.json`
