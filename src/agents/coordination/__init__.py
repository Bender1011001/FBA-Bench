"""
Multi-Domain Controller for FBA-Bench Agent Architecture.

This module provides the CEO-level coordination controller, delegating to specialized managers for different concerns.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

from fba_bench_core.money import Money

from agents.skill_modules.base_skill import SkillAction

from ..skills import SkillCoordinator
from .coordination import CoordinationManager
from .crisis import CrisisManager
from .models import (
    BusinessPriority,
    BusinessState,
    ResourceAllocationPlan,
    StrategicDecision,
    StrategicObjective,
)
from .performance import PerformanceManager
from .resources import ResourceManager

logger = logging.getLogger(__name__)


class MultiDomainController:
    """
    CEO-level coordination controller for multi-skill agents.

    Manages strategic decision making, resource allocation, crisis handling, and performance tracking.
    """

    def __init__(
        self,
        agent_id: str,
        skill_coordinator: SkillCoordinator,
        config: Dict[str, Any] = None,
    ):
        """
        Initialize the Multi-Domain Controller.

        Args:
            agent_id: ID of the agent this controller manages
            skill_coordinator: Skill coordinator for event routing
            config: Configuration parameters for strategic management
        """
        self.agent_id = agent_id
        self.skill_coordinator = skill_coordinator
        self.config = config or {}
        # Cooldown is configurable; default 60s; sourced from config if provided.
        self.crisis_cooldown_seconds: int = int(
            self.config.get("crisis_cooldown_seconds", 60)
        )

        # Strategic configuration
        self.business_objectives = [
            StrategicObjective.PROFITABILITY,
            StrategicObjective.FINANCIAL_STABILITY,
            StrategicObjective.CUSTOMER_SATISFACTION,
        ]
        self.current_priority = BusinessPriority.STABILIZATION
        self.strategic_planning_horizon = self.config.get("planning_horizon_days", 30)

        # Resource management
        self.resource_plan = ResourceAllocationPlan(
            total_budget=Money(
                self.config.get("total_budget_cents", 1000000)
            )  # $10,000
        )

        # Business state tracking
        self.current_business_state = BusinessState()
        self.state_history: List[Tuple[datetime, BusinessState]] = []

        # Decision tracking
        self.strategic_decisions: List[StrategicDecision] = []
        self.pending_approvals: List[Tuple[SkillAction, datetime]] = []

        # Performance tracking
        self.decision_success_rate = 0.7
        self.resource_utilization_efficiency = 0.8
        self.strategic_alignment_score = 0.8
        self.last_strategic_review = datetime.now()

        # Instantiate managers
        self.coordination = CoordinationManager(self)
        self.resources = ResourceManager(self)
        self.crisis = CrisisManager(self)
        self.performance = PerformanceManager(self)

        # Initialize resource allocations
        self.resources._initialize_resource_allocations()

        logger.info(f"MultiDomainController initialized for agent {agent_id}")

    async def arbitrate_actions(
        self, competing_actions: List[SkillAction]
    ) -> List[SkillAction]:
        """
        Arbitrate between competing actions from different skills.

        Args:
            competing_actions: List of competing skill actions

        Returns:
            Arbitrated list of approved actions
        """
        return await self.coordination.arbitrate_actions(competing_actions)

    async def evaluate_business_priorities(
        self, current_state: Dict[str, Any]
    ) -> BusinessPriority:
        """
        Evaluate current business priorities based on state and context.

        Args:
            current_state: Current business state information

        Returns:
            Determined business priority level
        """
        return await self.coordination.evaluate_business_priorities(current_state)

    async def allocate_resources(
        self, skill_requests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Allocate resources across skill requests based on strategic priorities.

        Args:
            skill_requests: List of resource requests from skills

        Returns:
            Resource allocation decisions
        """
        return await self.resources.allocate_resources(skill_requests)

    async def handle_crisis_mode(
        self, crisis_type: str, severity: str
    ) -> List[SkillAction]:
        """Handle crisis situations with emergency protocols."""
        return await self.crisis.handle_crisis_mode(crisis_type, severity)

    async def get_strategic_dashboard(self) -> Dict[str, Any]:
        """Get strategic dashboard with key metrics and status."""
        return await self.performance.get_strategic_dashboard()

    def get_performance_summary(self) -> Dict[str, float]:
        """Get summary of controller performance metrics."""
        return self.performance.get_performance_summary()

    def validate_strategic_alignment(
        self, action: SkillAction, strategic_plan: Dict[str, Any]
    ) -> Tuple[bool, float, str]:
        """
        Validate if action aligns with strategic plan.

        Args:
            action: Action to validate
            strategic_plan: Current strategic plan

        Returns:
            Tuple of (is_aligned, alignment_score, reasoning)
        """
        return self.coordination.validate_strategic_alignment(action, strategic_plan)
