"""
Models for skill coordination in the FBA-Bench agent architecture.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from fba_bench_core.money import Money

from ..skill_modules.base_skill import BaseSkill


class CoordinationStrategy(Enum):
    """Coordination strategies for handling multiple skill actions."""

    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    RESOURCE_OPTIMAL = "resource_optimal"
    CONSENSUS_BASED = "consensus_based"


@dataclass
class SkillSubscription:
    """
    Skill subscription to event types with priority and filters.

    Attributes:
        skill: The skill instance
        event_types: Event types this skill subscribes to
        priority_multiplier: Multiplier for skill priority calculations
        filters: Optional filters for event processing
        max_concurrent_events: Maximum concurrent events this skill can handle
        current_load: Current processing load
    """

    skill: BaseSkill
    event_types: Set[str]
    priority_multiplier: float = 1.0
    filters: Dict[str, Any] = field(default_factory=dict)
    max_concurrent_events: int = field(
        default=3
    )  # Will be overridden in register_skill
    current_load: int = 0


@dataclass
class ResourceAllocation:
    """
    Resource allocation tracking for skill coordination.

    Attributes:
        total_budget: Total budget available
        allocated_budget: Budget allocated to skills
        remaining_budget: Remaining available budget
        token_budget: Total token budget for LLM calls
        allocated_tokens: Tokens allocated to skills
        remaining_tokens: Remaining token budget
        concurrent_slots: Available concurrent execution slots
        used_slots: Currently used execution slots
    """

    total_budget: Money = field(
        default_factory=lambda: Money(cents=1000000)
    )  # $10,000 in cents
    allocated_budget: Money = field(default_factory=lambda: Money(cents=0))
    remaining_budget: Money = field(default_factory=lambda: Money(cents=1000000))
    token_budget: int = 100000
    allocated_tokens: int = 0
    remaining_tokens: int = 100000
    concurrent_slots: int = 5
    used_slots: int = 0

    def __post_init__(self):
        """Ensure budget fields are Money instances and handle int to Money conversion for back-compat."""
        if isinstance(self.total_budget, int):
            self.total_budget = Money(cents=self.total_budget)
        if isinstance(self.allocated_budget, int):
            self.allocated_budget = Money(cents=self.allocated_budget)
        if isinstance(self.remaining_budget, int):
            self.remaining_budget = Money(cents=self.remaining_budget)


@dataclass
class CoordinatorTuning:
    """
    Optional tuning parameters for SkillCoordinator behavior.

    Attributes:
        exclusive_pairs: List of skill action type pairs that are mutually exclusive.
        max_concurrent_events_default: Default maximum concurrent events for skills.
        total_budget_cents: Total budget in cents for resource allocation.
        urgency_multipliers: Multipliers for different urgency levels.
        expected_roi_baseline: Baseline expected ROI for action prioritization.
    """

    exclusive_pairs: Optional[List[Tuple[str, str]]] = None
    max_concurrent_events_default: Optional[int] = None
    total_budget_cents: Optional[int] = None
    urgency_multipliers: Optional[Dict[str, float]] = field(
        default_factory=lambda: {
            "low": 0.8,
            "normal": 1.0,
            "high": 1.3,
            "critical": 1.5,
        }
    )
    expected_roi_baseline: Optional[float] = 2.0


@dataclass
class SkillPerformanceMetrics:
    """
    Performance metrics for skill coordination analysis.

    Attributes:
        skill_name: Name of the skill
        total_events_processed: Total events processed by skill
        total_actions_generated: Total actions generated
        average_response_time: Average response time in seconds
        success_rate: Success rate of skill actions
        resource_efficiency: Resource utilization efficiency
        conflict_rate: Rate of conflicts with other skills
        last_update: Last metrics update timestamp
    """

    skill_name: str
    total_events_processed: int = 0
    total_actions_generated: int = 0
    average_response_time: float = 0.0
    success_rate: float = 0.0
    resource_efficiency: float = 1.0
    conflict_rate: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
