# Testing

This repo uses pytest and a Makefile to standardize local and CI runs.

## Quick Commands

Install:
```bash
poetry install
```

Unit tests (fast):
```bash
make test-unit
```

Contracts:
```bash
make test-contracts
```

Full suite + coverage gate:
```bash
make test-all
```
Note: `make test-all` is currently a heavier/legacy target; CI runs a curated fast unit+contract suite for stability.

## Markers

Pytest markers are used to keep the default run fast:
- `unit`: fast, deterministic tests
- `integration`: tests that require external services or slower end-to-end paths
- `contracts`: schema/contract checks
- `validation`: consistency checks across configs and outputs
- `performance`: benchmarks and stress checks

Run integration explicitly:
```bash
poetry run pytest -m integration -v
```

## Golden Masters

Golden master verification:
```bash
make verify-golden
```

## Lint / Format / Types

Lint:
```bash
make lint
```

Format:
```bash
make format-fix
make format-check
```

Type checking (currently strict, but may require staged adoption depending on repo state):
```bash
make type-check
```
