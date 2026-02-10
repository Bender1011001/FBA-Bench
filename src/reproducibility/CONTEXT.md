# Reproducibility Module - Context

> **Last Updated**: 2026-01-10
> 
> This context file documents the reproducibility infrastructure for FBA-Bench Enterprise.

## Purpose

This module provides **world-class deterministic simulation** capabilities, ensuring that:
- The same seed produces identical simulation results
- Every random operation is traceable and auditable
- Different simulation components have isolated RNG streams
- Real-world statistical distributions model economic phenomena

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `deterministic_rng.py` | **NEW** - Component-isolated RNG with economic distributions | ✅ Complete |
| `sim_seed.py` | Legacy seed management (still used, but superseded for new code) | ⚠️ Legacy |
| `simulation_modes.py` | Mode controller that initializes both RNG systems | ✅ Updated |

## Files Converted to Deterministic RNG

| File | Changes | Status |
|------|---------|--------|
| `src/services/competitor_manager.py` | All random calls converted | ✅ Complete |
| `src/benchmarking/scenarios/templates.py` | ECommerceScenario, HealthcareScenario fully converted | ✅ Partial (more scenarios remain) |
| `src/scenarios/scenario_framework.py` | ScenarioGenerator, event timing methods | ✅ Complete |

## Calculated Metrics (Replaces Fake Random)

| Metric | Location | Old (Fake) | New (Real) |
|--------|----------|-----------|------------|
| `customer_satisfaction` | ECommerceScenario | `random.uniform(0.7, 0.95)` | `_calculate_customer_satisfaction()` |
| `patient_satisfaction` | HealthcareScenario | `random.uniform(0.7, 0.95)` | `_calculate_patient_satisfaction()` |

### Usage

```python
from reproducibility.deterministic_rng import DeterministicRNG

# Initialize master seed once at simulation start
DeterministicRNG.set_master_seed(42)

# Get component-specific RNG
rng = DeterministicRNG.for_component("my_component")

# Use instead of random.random()
value = rng.random()
choice = rng.choice(["a", "b", "c"])
shock = rng.market_shock()  # Realistic price movement
```

### Components Using DeterministicRNG

- `competitor_manager.py` → `"competitor_manager"`
- `ECommerceScenario` → `"ecommerce_scenario"`
- `HealthcareScenario` → `"healthcare_scenario"`

## Calculated vs Simulated Metrics

**CRITICAL**: The following metrics are now **calculated from real simulation state**, not randomly generated:

| Metric | Old (Fake) | New (Real) |
|--------|-----------|------------|
| `customer_satisfaction` | `random.uniform(0.7, 0.95)` | `_calculate_customer_satisfaction()` based on fulfillment, price, inventory |
| `patient_satisfaction` | `random.uniform(0.7, 0.95)` | `_calculate_patient_satisfaction()` based on wait time, treatment success |

## Configuration

Master seed is configured in `simulation_settings.yaml`:

```yaml
simulation:
  seed: 42  # Change this to run different deterministic variations
```

## Testing Reproducibility

```python
# Verify identical runs
DeterministicRNG.set_master_seed(42)
rng1 = DeterministicRNG.for_component("test")
values1 = [rng1.random() for _ in range(100)]

DeterministicRNG.reset()
DeterministicRNG.set_master_seed(42)
rng2 = DeterministicRNG.for_component("test")
values2 = [rng2.random() for _ in range(100)]

assert values1 == values2  # Bit-perfect reproduction
```

## Migration Guide

When encountering `random.random()` in production code:

```python
# BEFORE (non-deterministic)
import random
value = random.random()

# AFTER (deterministic)
# In __init__:
self._rng = DeterministicRNG.for_component("component_name")

# In methods:
value = self._rng.random()
```
