"""
Models for multi-domain coordination in FBA-Bench agents.

Defines enums and dataclasses for business state, resource plans, and strategic decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from fba_bench_core.money import Money

from agents.skill_modules.base_skill import SkillAction


class BusinessPriority(Enum):
    """Business priority levels for resource allocation."""

    SURVIVAL = "survival"  # Cash flow crisis, immediate threats
    STABILIZATION = "stabilization"  # Addressing critical issues
    GROWTH = "growth"  # Scaling and expansion
    OPTIMIZATION = "optimization"  # Efficiency improvements
    INNOVATION = "innovation"  # New opportunities


class StrategicObjective(Enum):
    """Strategic business objectives."""

    PROFITABILITY = "profitability"
    MARKET_SHARE = "market_share"
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    OPERATIONAL_EFFICIENCY = "operational_efficiency"
    FINANCIAL_STABILITY = "financial_stability"
    BRAND_REPUTATION = "brand_reputation"


@dataclass
class BusinessState:
    """
    Current business state for strategic decision making.

    Attributes:
        financial_health: Financial health score (0.0 to 1.0)
        cash_position: Current cash position status
        market_position: Competitive market position
        customer_satisfaction: Customer satisfaction level
        operational_efficiency: Operational efficiency score
        growth_trajectory: Business growth direction
        risk_level: Overall business risk assessment
        strategic_focus: Current strategic focus areas
    """

    financial_health: float = 0.5
    cash_position: str = "stable"
    market_position: str = "competitive"
    customer_satisfaction: float = 0.8
    operational_efficiency: float = 0.7
    growth_trajectory: str = "stable"
    risk_level: str = "moderate"
    strategic_focus: List[StrategicObjective] = field(default_factory=list)


@dataclass
class ResourceAllocationPlan:
    """
    Resource allocation plan across business domains.

    Attributes:
        total_budget: Total available budget
        allocations: Budget allocations by domain
        constraints: Resource constraints and limits
        priority_multipliers: Priority multipliers by domain
        reallocation_triggers: Conditions for budget reallocation
        approval_thresholds: Thresholds requiring approval
    """

    total_budget: Money
    allocations: Dict[str, Money] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    priority_multipliers: Dict[str, float] = field(default_factory=dict)
    reallocation_triggers: Dict[str, float] = field(default_factory=dict)
    approval_thresholds: Dict[str, Money] = field(default_factory=dict)


@dataclass
class StrategicDecision:
    """
    Strategic decision record for tracking and analysis.

    Attributes:
        decision_id: Unique identifier for the decision
        timestamp: When decision was made
        decision_type: Type of strategic decision
        context: Business context at time of decision
        actions_approved: Actions that were approved
        actions_rejected: Actions that were rejected
        reasoning: Strategic reasoning for the decision
        expected_impact: Expected business impact
        success_metrics: Metrics to track decision success
    """

    decision_id: str
    timestamp: datetime
    decision_type: str
    context: BusinessState
    actions_approved: List[SkillAction]
    actions_rejected: List[SkillAction]
    reasoning: str
    expected_impact: Dict[str, float]
    success_metrics: Dict[str, str] = field(default_factory=dict)
