"""
Scenarios module for the FBA-Bench benchmarking framework.

This module provides the core components for defining and managing scenarios
that are used to benchmark agents. It includes base classes, configurations,
and a registry for scenario implementations.
"""

# Ensure that necessary components from other modules are importable for scenarios
from ..agents.base import BaseAgent
from ..core.results import AgentRunResult, MetricResult
from .base import BaseScenario, ScenarioConfig
from .demand_forecasting import DemandForecastingScenario, DemandForecastingScenarioConfig
from .marketing_campaign import MarketingCampaignScenario
from .price_optimization import PriceOptimizationScenario

# Refined scenarios framework
from .refined_scenarios import (
    ScenarioDifficulty,
    ScenarioType,
    ScenarioMetrics,
    ScenarioContext,
)
from .registry import ScenarioRegistry, scenario_registry
from .supply_chain_disruption import SupplyChainDisruptionScenario

__all__ = [
    # Refined scenarios framework types
    "ScenarioDifficulty",
    "ScenarioType",
    "ScenarioMetrics",
    "ScenarioContext",
    # Registry and Results
    "ScenarioRegistry",
    "scenario_registry",
    "BaseScenario",
    "ScenarioConfig",
    "AgentRunResult",
    "MetricResult",
    # Scenario Implementations
    "MarketingCampaignScenario",
    "PriceOptimizationScenario",
    "DemandForecastingScenario",
    "DemandForecastingScenarioConfig",
    "SupplyChainDisruptionScenario",
    "BaseAgent",
]


# You can add logic here to automatically register built-in scenarios if desired
def _register_builtin_scenarios():
    """Register built-in scenarios on module import."""
    scenario_registry.register("marketing_campaign", MarketingCampaignScenario)
    scenario_registry.register("price_optimization", PriceOptimizationScenario)
    scenario_registry.register("demand_forecasting", DemandForecastingScenario)
    scenario_registry.register("supply_chain_disruption", SupplyChainDisruptionScenario)


_register_builtin_scenarios()
