"""
FBA-Bench Integration Testing Suite

This module provides comprehensive integration testing for FBA-Bench to validate
all tier-1 benchmark requirements and ensure seamless operation of all components.

The integration tests are organized into five main categories:

1. **Tier-1 Requirements Validation** (`test_tier1_requirements.py`)
   - Multi-dimensional measurement with 7-domain scoring
   - Instrumented root-cause analysis with failure mode tracking
   - Deterministic reproducibility with identical results
   - First-class extensibility with plugin system
   - Gradient curriculum with T0-T3 progression
   - Baseline bot performance validation
   - ARS (Adversarial Resistance Score) measurement
   - Memory experiment capabilities

2. **End-to-End Workflow Testing** (`test_end_to_end_workflow.py`)
   - Complete simulation lifecycle from start to completion
   - Multi-agent scenarios with different frameworks
   - Curriculum progression through T0→T1→T2→T3 tiers
   - Real-time monitoring and instrumentation
   - Event stream capture and golden snapshot generation

3. **Cross-System Integration** (`test_cross_system_integration.py`)
   - Event bus propagation across all services
   - Metrics integration for all 7 domains
   - Budget enforcement across all frameworks
   - Memory + adversarial testing integration
   - Curriculum + leaderboard coordination
   - OpenTelemetry instrumentation coverage

4. **Performance Benchmarks** (`test_performance_benchmarks.py`)
   - Simulation speed targets (1000 ticks/minute for T0)
   - Memory usage validation (<2GB for 3 agents)
   - Concurrent agent scalability (10+ agents)
   - Database/storage performance
   - Real-time dashboard responsiveness

5. **Scientific Reproducibility** (`test_scientific_reproducibility.py`)
   - Identical results with same seed+config
   - Golden snapshot validation for regression testing
   - Statistical consistency across multiple runs
   - Configuration sensitivity testing
   - Platform independence verification

Usage:
    Run all integration tests:
    ```bash
    pytest integration_tests/ -v
    ```

    Run specific test categories:
    ```bash
    pytest integration_tests/test_tier1_requirements.py -v
    pytest integration_tests/test_end_to_end_workflow.py -v
    ```

    Run with performance markers:
    ```bash
    pytest integration_tests/ -m "performance" -v
    ```
"""

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict

# Agent framework imports
# Baseline bot imports
# Constraints imports
from constraints.agent_gateway import AgentGateway
from constraints.budget_enforcer import BudgetEnforcer
from event_bus import EventBus, get_event_bus
from metrics.metric_suite import STANDARD_WEIGHTS, MetricSuite

# Core imports for integration testing
from simulation_orchestrator import SimulationConfig, SimulationOrchestrator

# Financial audit is optional in this environment; provide a resilient fallback
try:
    from financial_audit import FinancialAuditService  # type: ignore
except Exception:
    class FinancialAuditService:  # minimal no-op service used by MetricSuite wiring
        def __init__(self, config: Dict[str, Any] | None = None) -> None:
            self.config = config or {}
        def analyze(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"status": "ok", "analysis": {}}

# Adversarial testing and services
from src.services.fee_calculation_service import FeeCalculationService
from src.services.sales_service import SalesService
from src.services.trust_score_service import TrustScoreService

# Services imports
from src.services.world_store import WorldStore

# Set up logging for integration tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IntegrationTestConfig:
    """Configuration for integration tests."""

    seed: int = 42
    max_duration_minutes: int = 10
    performance_mode: bool = False
    verbose_logging: bool = True
    skip_slow_tests: bool = False


class IntegrationTestSuite:
    """
    Base class for integration test suites providing common functionality.
    """

    def __init__(self, config: IntegrationTestConfig = None):
        self.config = config or IntegrationTestConfig()
        self.setup_logging()

    def setup_logging(self):
        """Configure logging for integration tests."""
        if self.config.verbose_logging:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.INFO)

    async def create_test_simulation(self, tier: str = "T0", seed: int = None) -> Dict[str, Any]:
        """
        Create a complete test simulation environment.

        Returns:
            Dict containing all initialized components:
            - orchestrator: SimulationOrchestrator
            - event_bus: EventBus
            - metric_suite: MetricSuite
            - budget_enforcer: BudgetEnforcer
            - world_store: WorldStore
            - services: Dict of initialized services
        """
        seed = seed or self.config.seed

        # Initialize core components
        # Allow override via SIM_* env vars; fall back to existing defaults to preserve behavior when unset
        max_ticks = int(os.getenv("SIM_MAX_TICKS", "1000"))
        tick_interval = float(os.getenv("SIM_TICK_INTERVAL_SECONDS", "0.01"))
        time_accel = float(os.getenv("SIM_TIME_ACCELERATION", "50.0"))
        sim_config = SimulationConfig(
            seed=seed,
            max_ticks=max_ticks,
            tick_interval_seconds=tick_interval,
            time_acceleration=time_accel,
        )
        orchestrator = SimulationOrchestrator(sim_config)
        event_bus: EventBus = get_event_bus()  # Use forward reference for type hint

        # Initialize services
        world_store = WorldStore()
        fee_service = FeeCalculationService(config={})  # Assume default config for now
        sales_service = SalesService(
            config={}, fee_service=fee_service
        )  # Pass config and fee_service
        trust_service = TrustScoreService(config={})  # Pass config
        financial_audit_service = FinancialAuditService()  # Config removed to match shim

        # Initialize metrics
        metric_suite = MetricSuite(
            tier=tier,
            financial_audit_service=financial_audit_service,  # Now correctly initialized and passed
            sales_service=sales_service,
            trust_score_service=trust_service,
        )

        # Initialize constraints
        budget_enforcer = BudgetEnforcer.from_tier_config(tier, event_bus)

        # Initialize agent gateway
        agent_gateway = AgentGateway(budget_enforcer, event_bus)

        return {
            "orchestrator": orchestrator,
            "event_bus": event_bus,  # event_bus object is already correct
            "metric_suite": metric_suite,
            "budget_enforcer": budget_enforcer,
            "world_store": world_store,
            "services": {
                "sales": sales_service,
                "trust": trust_service,
                "financial_audit": financial_audit_service,  # Add financial audit service to the services dict
            },
            "agent_gateway": agent_gateway,  # Add agent_gateway to the returned dict
        }

    def assert_tier1_requirements(self, test_results: Dict[str, Any]):
        """
        Assert that all tier-1 benchmark requirements are met.

        Args:
            test_results: Dictionary containing test results from various subsystems
        """
        # Multi-dimensional measurement validation
        assert "metric_breakdown" in test_results
        breakdown = test_results["metric_breakdown"]

        # Verify all 7 domains are present
        expected_domains = [
            "finance",
            "ops",
            "marketing",
            "trust",
            "cognitive",
            "stress_recovery",
            "cost",
        ]
        for domain in expected_domains:
            assert domain in breakdown, f"Missing metric domain: {domain}"

        # Verify weight distribution sums correctly (allowing for adversarial_resistance)
        total_weight = sum(STANDARD_WEIGHTS.values())
        assert (
            abs(total_weight - 0.95) < 0.01
        ), f"Metric weights don't sum to expected value: {total_weight}"

        # Deterministic reproducibility validation
        assert "reproducibility_verified" in test_results
        assert test_results["reproducibility_verified"], "Reproducibility verification failed"

        # Instrumented failure mode tracking
        assert "failure_modes_tracked" in test_results
        assert test_results["failure_modes_tracked"], "Failure mode tracking not operational"

        # Extensibility validation
        assert "plugin_system_operational" in test_results
        assert test_results["plugin_system_operational"], "Plugin system not operational"

        logger.info("✅ All tier-1 requirements validated successfully")


# Export key components for use in test modules
__all__ = ["IntegrationTestConfig", "IntegrationTestSuite", "logger"]
