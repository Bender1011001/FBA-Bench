"""
Main SkillCoordinator for FBA-Bench Multi-Domain Agent Architecture.

This module provides event-driven coordination for skill modules, managing
event subscription, priority-based dispatch, resource allocation, and
concurrent execution of multiple skills with performance tracking.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from money import Money

from fba_bench_core.event_bus import EventBus
from fba_events.base import BaseEvent

from ..skill_modules.base_skill import BaseSkill, SkillAction
from .conflicts import ConflictResolver
from .dispatch import DispatchManager
from .metrics import MetricsTracker
from .models import (
    CoordinationStrategy,
    CoordinatorTuning,
    ResourceAllocation,
    SkillPerformanceMetrics,
    SkillSubscription,
)
from .resources import ResourceManager
from .utils import get_max_concurrent_events, log_coordination_decision

logger = logging.getLogger(__name__)


class SkillCoordinator:
    """
    Event-driven coordination system for skill modules.

    Manages skill registration, event routing, resource allocation,
    and concurrent execution with performance monitoring and conflict resolution.
    """

    def __init__(
        self,
        agent_id: str,
        event_bus: EventBus,
        config: Optional[Dict[str, Any]] = None,
        coordinator_tuning: Optional[CoordinatorTuning] = None,
    ):
        """
        Initialize the Skill Coordinator.

        Args:
            agent_id: ID of the agent this coordinator serves
            event_bus: Event bus for communication
            config: Configuration parameters for coordination
        """
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.config = config or {}
        self.coordinator_tuning = coordinator_tuning or CoordinatorTuning()

        # Configuration parameters
        self.coordination_strategy = CoordinationStrategy(
            self.config.get("coordination_strategy", "priority_based")
        )
        self.max_concurrent_skills = (
            self.coordinator_tuning.max_concurrent_events_default
            if self.coordinator_tuning.max_concurrent_events_default is not None
            else self.config.get("max_concurrent_skills", 3)
        )
        self.conflict_resolution_timeout = self.config.get(
            "conflict_resolution_timeout", 5.0
        )
        self.performance_tracking_enabled = self.config.get(
            "performance_tracking_enabled", True
        )

        # Skill management
        self.skill_subscriptions: Dict[str, SkillSubscription] = {}
        self.event_skill_mapping: Dict[str, List[str]] = defaultdict(list)

        # Resource management
        initial_total_budget_cents = (
            self.coordinator_tuning.total_budget_cents
            if self.coordinator_tuning.total_budget_cents is not None
            else self.config.get("total_budget_cents", 1000000)
        )
        self.resource_allocation = ResourceAllocation(
            total_budget=Money(cents=initial_total_budget_cents),
            token_budget=self.config.get("token_budget", 100000),
            concurrent_slots=self.max_concurrent_skills,
        )

        # Performance tracking
        self.skill_metrics: Dict[str, SkillPerformanceMetrics] = {}
        self.coordination_history: List[Dict[str, Any]] = []
        self.conflict_log: List[Dict[str, Any]] = []

        # Execution management
        self.active_executions: Dict[str, asyncio.Task] = {}
        self.pending_actions: List[Tuple[str, SkillAction]] = []
        self.execution_lock = asyncio.Lock()

        # Initialize managers
        self.metrics_tracker = MetricsTracker(
            self.skill_metrics,
            self.coordination_history,
            self.conflict_log,
            self.resource_allocation,
            self.skill_subscriptions,
        )
        self.resource_manager = ResourceManager(self.resource_allocation)
        self.conflict_resolver = ConflictResolver(
            self.coordination_strategy,
            self.coordinator_tuning,
            self.config,
            self.conflict_log,
            self.skill_metrics,
            self.resource_allocation,
        )
        self.dispatch_manager = DispatchManager(
            self.event_bus,
            self.config,
            self.coordinator_tuning,
            self.skill_subscriptions,
            self.event_skill_mapping,
            self.resource_allocation,
            self.performance_tracking_enabled,
            self.conflict_resolution_timeout,
            self.metrics_tracker,
        )

        logger.info(f"SkillCoordinator initialized for agent {agent_id}")

    async def register_skill(
        self,
        skill: BaseSkill,
        event_types: List[str],
        priority_multiplier: float = 1.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a skill with the coordinator for event processing.

        Args:
            skill: Skill instance to register
            event_types: List of event types the skill should handle
            priority_multiplier: Multiplier for skill priority calculations
            filters: Optional filters for event processing

        Returns:
            True if registration successful, False otherwise
        """
        try:
            skill_name = skill.skill_name

            # Create subscription
            subscription = SkillSubscription(
                skill=skill,
                event_types=set(event_types),
                priority_multiplier=priority_multiplier,
                filters=filters or {},
                max_concurrent_events=get_max_concurrent_events(
                    skill_name, self.config, self.coordinator_tuning
                ),
            )

            self.skill_subscriptions[skill_name] = subscription

            # Update event-skill mapping
            for event_type in event_types:
                if skill_name not in self.event_skill_mapping[event_type]:
                    self.event_skill_mapping[event_type].append(skill_name)

            # Initialize performance metrics
            self.skill_metrics[skill_name] = SkillPerformanceMetrics(
                skill_name=skill_name
            )

            # Subscribe skill to event bus
            await skill.subscribe_to_events(event_types)

            logger.info(f"Registered skill {skill_name} for events: {event_types}")
            return True

        except Exception as e:
            logger.error(f"Error registering skill {skill.skill_name}: {e}")
            return False

    async def dispatch_event(self, event: BaseEvent) -> List[SkillAction]:
        """
        Dispatch event to relevant skills based on priority and generate coordinated actions.

        Args:
            event: Event to dispatch

        Returns:
            List of coordinated actions from skills
        """
        event_type = type(event).__name__

        # Find skills interested in this event type
        interested_skills = self.event_skill_mapping.get(event_type, [])

        if not interested_skills:
            return []

        try:
            # Dispatch to skills concurrently
            skill_actions = await self.dispatch_manager.dispatch_event(event)

            if not skill_actions:
                return []

            # Flatten all actions with skill attribution
            all_actions = []
            for skill_name, actions in skill_actions:
                for action in actions:
                    action.skill_source = skill_name
                    all_actions.append(action)

            # Coordinate and resolve conflicts
            coordinated_actions = await self.conflict_resolver.coordinate_actions(
                all_actions
            )

            # Update performance metrics
            if self.performance_tracking_enabled:
                await self.metrics_tracker.update_performance_metrics(
                    event, skill_actions
                )

            # Log coordination decision
            log_coordination_decision(
                event,
                skill_actions,
                coordinated_actions,
                self.coordination_history,
                self.coordination_strategy.value,
                self.resource_allocation,
            )

            return coordinated_actions

        except Exception as e:
            logger.error(f"Error dispatching event {event_type}: {e}")
            return []

    async def coordinate_actions(
        self, skill_actions: List[SkillAction]
    ) -> List[SkillAction]:
        """
        Public method to coordinate pre-generated skill actions.

        Args:
            skill_actions: List of actions from various skills

        Returns:
            Coordinated list of actions
        """
        return await self.conflict_resolver.coordinate_actions(skill_actions)

    def get_skill_performance_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get performance metrics for all registered skills.

        Returns:
            Dictionary of skill names to their performance metrics
        """
        return self.metrics_tracker.get_skill_performance_metrics()

    def get_coordination_statistics(self) -> Dict[str, Any]:
        """Get coordination statistics and analytics."""
        return self.metrics_tracker.get_coordination_statistics()

    async def update_resource_allocation(
        self, budget_delta: int = 0, token_delta: int = 0
    ) -> bool:
        """
        Update resource allocation for the coordinator.

        Args:
            budget_delta: Change in budget allocation (cents)
            token_delta: Change in token allocation

        Returns:
            True if update successful, False if insufficient resources
        """
        return await self.resource_manager.update_resource_allocation(
            budget_delta, token_delta
        )

    async def shutdown(self):
        """Shutdown the coordinator and clean up resources."""
        # Cancel any active execution tasks
        for task_id, task in self.active_executions.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.active_executions.clear()

        # Reset skill loads
        for subscription in self.skill_subscriptions.values():
            subscription.current_load = 0

        self.resource_allocation.used_slots = 0

        logger.info(f"SkillCoordinator for agent {self.agent_id} shutdown complete")
