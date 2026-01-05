# FBA-Bench Integration Testing Suite

This module provides comprehensive integration testing for FBA-Bench to validate all tier-1 benchmark requirements and ensure seamless operation of all components.

## Overview

The FBA-Bench Integration Testing Suite is designed to validate that FBA-Bench meets all requirements for a tier-1 LLM-agent benchmark as specified in the blueprint. It tests not only individual components but also their integration and the system's performance under realistic conditions.

## Test Modules

### 1. Tier-1 Requirements Validation (`test_tier1_requirements.py`)

Validates all tier-1 blueprint requirements:

- **Multi-dimensional Measurement**: 7-domain scoring system (Finance 25%, Operations 15%, Marketing 10%, Trust 10%, Cognitive 15%, Stress Recovery 15%, Cost -5%)
- **Instrumented Root-cause Analysis**: Failure mode tracking and diagnosis
- **Deterministic Reproducibility**: Identical results with same seed+config
- **First-class Extensibility**: Plugin system and framework abstraction
- **Gradient Curriculum**: T0-T3 progression with appropriate constraints
- **Baseline Bot Performance**: Expected score ranges for all 5 baseline bots
- **ARS Scoring**: Adversarial resistance measurement
- **Memory Experiments**: Ablated vs saturated memory testing

**Key Tests:**
```python
test_multi_dimensional_scoring_validation()
test_deterministic_reproducibility()
test_gradient_curriculum_progression()
test_baseline_bot_performance()
test_adversarial_resistance_scoring()
test_memory_experiment_framework()
test_instrumented_failure_mode_tracking()
test_framework_extensibility()
```

### 2. End-to-End Workflow Testing (`test_end_to_end_workflow.py`)

Tests complete simulation workflows:

- **Complete Simulation Lifecycle**: Full simulation from initialization to completion
- **Multi-Agent Scenarios**: Multiple agents with different frameworks running simultaneously
- **Curriculum Progression**: Agents advancing through T0→T1→T2→T3 tiers
- **Real-time Monitoring**: Dashboard, metrics, and instrumentation during simulation
- **Event Stream Capture**: Golden snapshot generation and replay

**Key Tests:**
```python
test_complete_simulation_lifecycle()
test_multi_agent_scenarios()
test_curriculum_progression_workflow()
test_real_time_monitoring_integration()
test_event_stream_capture_and_replay()
```

### 3. Cross-System Integration (`test_cross_system_integration.py`)

Tests integration between major subsystems:

- **Event Bus → All Services**: Event propagation across all systems
- **Metrics Integration**: All 7 domains collect data correctly from relevant services
- **Constraints → All Frameworks**: Budget enforcement works with DIY, CrewAI, LangChain
- **Memory + Adversarial**: Memory experiments with adversarial attack injection
- **Curriculum + Leaderboard**: Tier-specific scoring and ranking
- **Instrumentation Coverage**: OpenTelemetry traces capture all major operations

**Key Tests:**
```python
test_event_bus_propagation_across_services()
test_metrics_integration_across_domains()
test_budget_enforcement_across_frameworks()
test_memory_adversarial_integration()
test_curriculum_leaderboard_integration()
test_instrumentation_coverage()
```

### 4. Performance Benchmarks (`test_performance_benchmarks.py`)

Validates performance and scalability:

- **Simulation Speed**: Target performance metrics (1000 ticks/minute for T0)
- **Memory Usage**: Resource consumption (<2GB RAM for 3 agents)
- **Concurrent Agents**: Scalability (10+ agents simultaneously)
- **Database/Storage**: Event storage and retrieval performance
- **Real-time Responsiveness**: Dashboard updates <100ms, API responses <500ms

**Performance Targets:**
- Simulation Speed: 1000 ticks/minute minimum for T0 scenarios
- Memory Usage: <2GB RAM for standard simulation with 3 agents
- Response Time: Dashboard updates <100ms, API responses <500ms
- Concurrent Agents: Support 10+ agents simultaneously
- Storage Efficiency: Event streams compressed and indexable

**Key Tests:**
```python
test_simulation_speed_benchmarks()
test_memory_usage_validation()
test_concurrent_agent_scalability()
test_storage_performance()
test_api_response_times()
```

### 5. Scientific Reproducibility (`test_scientific_reproducibility.py`)

Validates scientific rigor:

- **Identical Results**: Same seed+config produces identical outputs across runs
- **Golden Snapshots**: Event streams match exactly for regression testing
- **Statistical Consistency**: Multiple runs with different seeds show expected variance
- **Configuration Sensitivity**: Changes in config properly affect results
- **Platform Independence**: Results consistent across different environments

**Key Tests:**
```python
test_deterministic_identical_results()
test_golden_snapshot_validation()
test_statistical_consistency_across_seeds()
test_configuration_sensitivity_validation()
test_cross_platform_consistency()
```

### 6. Golden Master Baselines (`tests/integration/test_tier2_golden_master.py`)

Validates and generates official golden master baselines for regression testing:

- **Enterprise V1.0 Baseline**: The official Tier 2 ("supply chain crisis") baseline stored in `artifacts/enterprise_v1.0_baseline.parquet`
- **Deterministic Snapshot Generation**: Produces reproducible event streams for future comparison
- **Regression Detection**: Ensures changes don't inadvertently alter simulation outcomes

**Key Files:**
- `artifacts/enterprise_v1.0_baseline.parquet`: Official Enterprise V1.0 golden master snapshot
- `scripts/verify_golden_masters.py`: Verification utility that runs all golden master tests

**Key Tests:**
```python
test_create_enterprise_v1_0_baseline()  # Generates and saves the baseline
```

**Usage:**
```bash
# Run golden master verification
python scripts/verify_golden_masters.py

# Run the Tier 2 golden master test specifically
pytest tests/integration/test_tier2_golden_master.py -v
```

### 7. Demo Scenarios (`demo_scenarios.py`)

Showcases tier-1 capabilities:

- **T0 Baseline Demo**: Simple scenario with GPT-4o performing basic tasks
- **T3 Stress Test**: Complex multi-shock scenario with memory-limited agent
- **Framework Comparison**: Same scenario run with DIY, CrewAI, and LangChain
- **Adversarial Resistance**: Agent facing multiple exploit attempts
- **Memory Ablation**: Compare agent with 7-day vs unlimited memory

**Demo Scenarios:**
```python
run_t0_baseline_demo()         # Basic FBA operations
run_t3_stress_test_demo()      # Multi-shock stress testing
run_framework_comparison_demo() # Framework compatibility
run_memory_ablation_demo()     # Memory experiment comparison
```

## Usage

### Running All Tests

```bash
# Run comprehensive integration tests
python integration_tests/run_integration_tests.py --all --verbose

# Quick validation (skip slow tests)
python integration_tests/run_integration_tests.py --quick --tier1

# Performance benchmarking only
python integration_tests/run_integration_tests.py --performance
```

### Running Individual Test Suites

```bash
# Using pytest
pytest integration_tests/test_tier1_requirements.py -v
pytest integration_tests/test_performance_benchmarks.py -v
pytest integration_tests/test_scientific_reproducibility.py -v

# Using the test runner
python integration_tests/run_integration_tests.py --tier1
python integration_tests/run_integration_tests.py --demo
```

### Generating Reports

```bash
# Generate validation report
python integration_tests/run_integration_tests.py --report --output ./reports

# Run all tests and generate report
python integration_tests/run_integration_tests.py --all --output ./validation_reports
```

## Test Configuration

The integration tests use `IntegrationTestConfig` for configuration:

```python
config = IntegrationTestConfig(
    seed=42,                    # Master seed for deterministic tests
    max_duration_minutes=10,    # Maximum test duration
    performance_mode=False,     # Enable performance optimizations
    verbose_logging=True,       # Detailed logging
    skip_slow_tests=False      # Skip expensive tests
)
```

## Validation Report

The integration tests generate comprehensive validation reports in multiple formats:

### JSON Report
- Detailed test results
- Performance metrics
- Compliance matrix
- Machine-readable format

### Markdown Report
- Executive summary
- Test results table
- Recommendations
- Human-readable format

### Console Summary
- Key metrics
- Pass/fail status
- Top recommendations
- Immediate feedback

## Performance Targets

The integration tests validate these performance targets:

| Metric | Target | Validation |
|--------|--------|------------|
| Simulation Speed | 1000 ticks/minute (T0) | Performance benchmarks |
| Memory Usage | <2GB (3 agents) | Memory validation |
| API Response | <500ms | Response time tests |
| Dashboard Updates | <100ms | Real-time monitoring |
| Concurrent Agents | 10+ simultaneous | Scalability tests |
| Reproducibility | 100% identical | Scientific rigor |

## Tier-1 Compliance Matrix

The tests validate compliance with all tier-1 requirements:

- ✅ Multi-dimensional Measurement
- ✅ Instrumented Root-cause Analysis
- ✅ Deterministic Reproducibility
- ✅ First-class Extensibility
- ✅ Gradient Curriculum (T0-T3)
- ✅ Baseline Bot Performance
- ✅ ARS Scoring
- ✅ Memory Experiments
- ✅ Performance Benchmarks
- ✅ Scientific Reproducibility
- ✅ Demo Scenarios

## Dependencies

The integration tests require:

```python
# Core dependencies
pytest
pytest-asyncio
asyncio
logging

# Performance monitoring
psutil

# FBA-Bench components
simulation_orchestrator
event_bus
metrics
constraints
reproducibility
agent_runners
baseline_bots
memory_experiments
redteam
services
instrumentation
```

## Directory Structure

```
integration_tests/
├── __init__.py                           # Module initialization
├── README.md                             # This file
├── run_integration_tests.py              # Main test runner
├── validation_report.py                  # Report generation
├── demo_scenarios.py                     # Demo scenarios
├── test_tier1_requirements.py            # Tier-1 validation
├── test_end_to_end_workflow.py           # E2E workflow tests
├── test_cross_system_integration.py      # Cross-system tests
├── test_performance_benchmarks.py        # Performance tests
├── test_scientific_reproducibility.py    # Reproducibility tests
└── reports/                              # Generated reports
    ├── fba_bench_validation_YYYYMMDD.json
    ├── fba_bench_validation_YYYYMMDD.md
    └── integration_tests_YYYYMMDD.log
```

## CI/CD Integration

The integration tests are designed for CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: FBA-Bench Integration Tests
on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run integration tests
        run: python integration_tests/run_integration_tests.py --all
      - name: Upload validation report
        uses: actions/upload-artifact@v2
        with:
          name: validation-report
          path: reports/
```

## Contributing

When adding new tests to the integration suite:

1. **Follow the existing patterns**: Use async/await, proper logging, and consistent error handling
2. **Add comprehensive documentation**: Include docstrings and inline comments
3. **Update the validation report**: Ensure new tests are included in the compliance matrix
4. **Test thoroughly**: Validate both success and failure scenarios
5. **Consider performance**: Ensure tests complete in reasonable time

## Troubleshooting

### Common Issues

**Import Errors**: Ensure FBA-Bench is properly installed and PYTHONPATH includes the project root.

**Test Timeouts**: Use `--quick` flag for faster testing or increase timeout values.

**Memory Issues**: Run fewer concurrent tests or increase available memory.

**Reproducibility Failures**: Check for non-deterministic behavior in code or tests.

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
python integration_tests/run_integration_tests.py --all --verbose
```

### Test Isolation

Run individual test modules to isolate issues:

```bash
pytest integration_tests/test_tier1_requirements.py::TestTier1Requirements::test_multi_dimensional_scoring_validation -v -s
```

## Validation Criteria

For FBA-Bench to be considered tier-1 ready:

- **Overall Test Success Rate**: ≥90%
- **Tier-1 Requirements**: 100% compliance
- **Performance Benchmarks**: Meet all targets
- **Scientific Reproducibility**: 100% deterministic
- **Demo Scenarios**: ≥80% success rate
- **Critical Issues**: 0 unresolved

## Future Enhancements

Planned improvements to the integration testing suite:

- **Distributed Testing**: Support for multi-node test execution
- **Load Testing**: Extended stress testing capabilities
- **Visual Reports**: Enhanced reporting with charts and graphs
- **Test Analytics**: Historical trend analysis
- **Auto-healing**: Automatic issue detection and remediation
- **Cloud Integration**: Support for cloud-based testing environments

---

*This integration testing suite ensures FBA-Bench meets the highest standards for a tier-1 LLM-agent benchmark.*
