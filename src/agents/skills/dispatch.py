"""
Event dispatch logic for skill coordination.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fba_events.base import BaseEvent

from ..skill_modules.base_skill import BaseSkill, SkillAction
from .metrics import MetricsTracker
from .models import ResourceAllocation, SkillSubscription
from .utils import get_urgency_multiplier

logger = logging.getLogger(__name__)


class DispatchManager:
    """
    Manages event dispatch to skills, including priority calculation, filtering,
    and concurrent processing with load tracking.
    """

    def __init__(
        self,
        event_bus: "EventBus",  # Forward ref for EventBus
        config: Dict,
        coordinator_tuning: "CoordinatorTuning",  # Forward ref
        skill_subscriptions: Dict[str, SkillSubscription],
        event_skill_mapping: Dict[str, List[str]],
        resource_allocation: ResourceAllocation,
        performance_tracking_enabled: bool,
        conflict_resolution_timeout: float,
        metrics_tracker: MetricsTracker,
    ):
        """
        Initialize the DispatchManager.

        Args:
            event_bus: Event bus for communication
            config: Configuration parameters
            coordinator_tuning: Tuning parameters
            skill_subscriptions: Registered skill subscriptions
            event_skill_mapping: Mapping of event types to skills
            resource_allocation: Resource allocation tracker
            performance_tracking_enabled: Whether to track performance
            conflict_resolution_timeout: Timeout for skill processing
        """
        self.event_bus = event_bus
        self.config = config
        self.coordinator_tuning = coordinator_tuning
        self.skill_subscriptions = skill_subscriptions
        self.event_skill_mapping = event_skill_mapping
        self.resource_allocation = resource_allocation
        self.performance_tracking_enabled = performance_tracking_enabled
        self.conflict_resolution_timeout = conflict_resolution_timeout
        self.metrics_tracker = metrics_tracker

    async def dispatch_event(
        self, event: BaseEvent
    ) -> List[Tuple[str, List[SkillAction]]]:
        """
        Dispatch event to relevant skills based on priority and generate actions.

        Args:
            event: Event to dispatch

        Returns:
            List of (skill_name, actions) tuples from skills
        """
        event_type = type(event).__name__

        # Find skills interested in this event type
        interested_skills = self.event_skill_mapping.get(event_type, [])

        if not interested_skills:
            logger.debug(f"No skills registered for event type: {event_type}")
            return []

        try:
            # Calculate skill priorities for this event
            skill_priorities = await self._calculate_skill_priorities(
                event, interested_skills
            )

            # Filter skills based on resource availability and load
            available_skills = self._filter_available_skills(skill_priorities)

            # Dispatch to skills concurrently
            skill_actions = await self._dispatch_to_skills(event, available_skills)

            logger.debug(
                f"Dispatched event {event_type} to {len(skill_actions)} skills"
            )
            return skill_actions

        except Exception as e:
            logger.error(f"Error dispatching event {event_type}: {e}")
            return []

    async def _calculate_skill_priorities(
        self, event: BaseEvent, interested_skills: List[str]
    ) -> List[Tuple[str, float]]:
        """Calculate priority scores for skills handling this event."""
        skill_priorities = []

        for skill_name in interested_skills:
            subscription = self.skill_subscriptions.get(skill_name)
            if not subscription:
                continue

            try:
                # Get base priority from skill
                base_priority = subscription.skill.get_priority_score(event)

                # Apply urgency multiplier if event has an urgency level
                urgency_level = getattr(event, "urgency_level", "normal")
                urgency_multiplier = get_urgency_multiplier(
                    urgency_level, self.coordinator_tuning, self.config
                )

                # Apply skill-specific priority multiplier and then urgency multiplier
                adjusted_priority = (
                    base_priority
                    * subscription.priority_multiplier
                    * urgency_multiplier
                )

                # Factor in current load, guarding against ZeroDivisionError
                max_events = max(1, int(subscription.max_concurrent_events or 0))
                load_factor = 1.0 - (subscription.current_load / max_events)
                final_priority = adjusted_priority * load_factor

                skill_priorities.append((skill_name, final_priority))

            except Exception as e:
                logger.error(f"Error calculating priority for skill {skill_name}: {e}")

        # Sort by priority (highest first)
        skill_priorities.sort(key=lambda x: x[1], reverse=True)
        return skill_priorities

    def _filter_available_skills(
        self, skill_priorities: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        """Filter skills based on resource availability and load."""
        available_skills = []

        for skill_name, priority in skill_priorities:
            subscription = self.skill_subscriptions.get(skill_name)
            if not subscription:
                continue

            # Check if skill has capacity
            if subscription.current_load >= subscription.max_concurrent_events:
                continue

            # Check if we have available execution slots
            if (
                self.resource_allocation.used_slots
                >= self.resource_allocation.concurrent_slots
            ):
                break  # No more concurrent slots available

            available_skills.append((skill_name, priority))

        return available_skills

    async def _dispatch_to_skills(
        self, event: BaseEvent, available_skills: List[Tuple[str, float]]
    ) -> List[Tuple[str, List[SkillAction]]]:
        """Dispatch event to available skills concurrently."""
        dispatch_tasks = []
        skill_actions = []

        for skill_name, priority in available_skills:
            subscription = self.skill_subscriptions.get(skill_name)
            if not subscription:
                continue

            # Create dispatch task
            task = asyncio.create_task(
                self._process_skill_event(subscription.skill, event, skill_name)
            )
            dispatch_tasks.append((skill_name, task))

            # Update load tracking
            subscription.current_load += 1
            self.resource_allocation.used_slots += 1

        # Wait for all skills to process the event
        for skill_name, task in dispatch_tasks:
            try:
                actions = await asyncio.wait_for(
                    task, timeout=self.conflict_resolution_timeout
                )
                if actions:
                    skill_actions.append((skill_name, actions))
            except asyncio.TimeoutError:
                logger.warning(f"Skill {skill_name} timed out processing event")
            except Exception as e:
                logger.error(f"Error in skill {skill_name} processing: {e}")
            finally:
                # Update load tracking
                subscription = self.skill_subscriptions.get(skill_name)
                if subscription:
                    subscription.current_load = max(0, subscription.current_load - 1)
                self.resource_allocation.used_slots = max(
                    0, self.resource_allocation.used_slots - 1
                )

        return skill_actions

    async def _process_skill_event(
        self, skill: BaseSkill, event: BaseEvent, skill_name: str
    ) -> Optional[List[SkillAction]]:
        """Process event with a single skill and return actions."""
        try:
            start_time = datetime.now()

            # Process event through skill
            actions = await skill.process_event(event)

            # Update response time metric (partial; full metrics in MetricsTracker)
            if self.performance_tracking_enabled:
                response_time = (datetime.now() - start_time).total_seconds()
                await self.metrics_tracker.update_event_processing(
                    skill_name, response_time, actions or []
                )

            return actions

        except Exception as e:
            logger.error(f"Error processing event in skill {skill_name}: {e}")
            return None
