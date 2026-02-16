# Learning & Analysis Tooling

## Overview

This repo includes learning-related modules that support research workflows (ablations, curricula, and post-run analysis). They are not necessarily “always-on” in every runtime path, but they exist as first-class components for experiments.

Key directories:
- Learning algorithms: `src/learning/`
- Outcome analysis service: `src/services/outcome_analysis_service.py`
- Benchmark analysis scripts: `src/benchmarking/integration/analyze_gpt5_learning.py`
- Data output folders (run artifacts): `learning_data/`, `metrics/`, `results/`, `public_results/`

## Learning Modules

Files in `src/learning/` include:
- `curriculum_learning.py`
- `episodic_learning.py`
- `meta_learning.py`
- `reinforcement_learning.py`

These modules provide scaffolding for:
- running repeated episodes against scenarios
- adapting difficulty or event distributions over time
- evaluating improvements across runs

## Outcome Analysis

`src/services/outcome_analysis_service.py` is the bridge between raw simulation events and higher-level “what happened” summaries suitable for:
- dashboards
- post-run reports
- generating training signals

## Notes On Integration

Some learning workflows are run via scripts and benchmarking pipelines rather than the default API demo loop. Treat these modules as an experiment layer unless you explicitly wire them into your production runner.

