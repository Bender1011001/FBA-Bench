# Metrics Suite (Beyond Profit)

## Overview

FBA-Bench includes a multi-dimensional scoring system intended to measure more than “final profit”.

Core modules live in:
- `src/metrics/metric_suite.py` (orchestration + weighting)
- `src/metrics/finance_metrics.py`
- `src/metrics/operations_metrics.py`
- `src/metrics/marketing_metrics.py`
- `src/metrics/trust_metrics.py`
- `src/metrics/cognitive_metrics.py`
- `src/metrics/stress_metrics.py`
- `src/metrics/adversarial_metrics.py`
- `src/metrics/cost_metrics.py`

Integration into the benchmarking layer is handled by:
- `src/benchmarking/integration/metrics_adapter.py`

## Metric Categories (Legacy Suite)

The legacy metric suite is organized into categories:
- Finance: profitability, efficiency, drawdowns, etc.
- Ops: inventory health, stockouts, execution stability
- Marketing: visibility/conversion proxies, spend efficiency (when applicable)
- Trust: policy violations, buyer feedback signals, derived trust score
- Cognitive: memory load / retention signals (runner-dependent)
- Stress recovery: resilience to shocks over time
- Adversarial resistance: redteam-style exploit handling (when running gauntlets)
- Cost: token/call/cost efficiency penalties

## Weighting

The adapter provides default weights (and allows overrides) in:
- `src/benchmarking/integration/metrics_adapter.py` (`MetricsAdapter._default_legacy_weights`)

This is the intended mechanism for tuning “what matters” without rewriting the metric implementations.

## Notes On Availability

Some metrics require specific subsystems to be active (for example, adversarial metrics require running the redteam gauntlet, and some cognitive metrics require memory consolidation to be enabled).

If a subsystem is not wired for a run, the corresponding metrics will typically degrade gracefully (default values or missing detail fields), and the adapter will still produce a combined output.

