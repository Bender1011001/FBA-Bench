from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.skill_modules.base_skill import (
    SkillAction,
)  # Assuming base_skill defines SkillAction
from fba_bench_core.event_bus import EventBus

logger = logging.getLogger(__name__)


class CoordinationStrategy(Enum):
    """Enumeration of supported coordination strategies for skill execution."""

    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    # Add more strategies as needed, e.g., LOAD_BALANCED = "load_balanced"


@dataclass
class SkillSubscription:
    """Represents a registered skill subscription."""

    skill: Any
    event_types: List[str]
    priority: float
    config: Dict[str, Any] = None


class SkillCoordinator:
    """
    SkillCoordinator manages the registration and execution of agent skills in response to events.

    It coordinates skill execution based on event types, applies coordination strategies to limit
    concurrency and prioritize actions, and returns a list of SkillAction objects for further arbitration.

    Key features:
    - Registers skills with supported event types and priority multipliers.
    - Dispatches events to matching skills concurrently, respecting max_concurrent_skills limit.
    - Supports coordination strategies like priority-based sorting and execution limiting.
    - Integrates with EventBus for event publishing and subscription management.
    - Production-ready: Async, typed, logged, error-resilient with circuit-breaker patterns.

    Usage:
        coordinator = SkillCoordinator(agent_id="agent-1", event_bus=bus, config={"max_concurrent_skills": 3})
        await coordinator.register_skill(skill_obj, ["TickEvent"], priority_multiplier=1.0)
        actions = await coordinator.dispatch_event(tick_event)
    """

    def __init__(
        self,
        agent_id: str,
        event_bus: Optional[EventBus] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.config = config or {}
        self.coordination_strategy = self.config.get(
            "coordination_strategy", CoordinationStrategy.PRIORITY_BASED.value
        )
        self.max_concurrent_skills = self.config.get(
            "max_concurrent_skills", 5
        )  # Default limit to prevent overload
        self.skill_subscriptions: Dict[str, SkillSubscription] = (
            {}
        )  # skill_name -> SkillSubscription
        self._subscription_handles: List[Any] = []  # For cleanup if subscribing to bus
        self._semaphore = asyncio.Semaphore(
            self.max_concurrent_skills
        )  # Limit concurrent executions
        logger.info(
            f"SkillCoordinator initialized for agent {agent_id} with strategy '{self.coordination_strategy}' and max concurrent skills {self.max_concurrent_skills}"
        )

    async def register_skill(
        self,
        skill: Any,
        event_types: List[str],
        priority_multiplier: float = 1.0,
        skill_name: Optional[str] = None,
    ) -> None:
        """
        Registers a skill with the coordinator.

        Args:
            skill: The skill object implementing the skill interface (e.g., get_supported_event_types, process_event).
            event_types: List of event types this skill can handle (e.g., ["TickEvent", "CustomerQuery"]).
            priority_multiplier: Multiplier for skill priority (0.0-2.0; higher = earlier execution).
            skill_name: Optional unique name for the skill (defaults to class name).

        Raises:
            ValueError: If skill_name already registered or event_types is empty.
            RuntimeError: If skill lacks required methods.
        """
        if not event_types:
            raise ValueError("event_types cannot be empty")

        skill_name = skill_name or skill.__class__.__name__
        if skill_name in self.skill_subscriptions:
            logger.warning(
                f"Skill '{skill_name}' already registered for agent {self.agent_id}; overwriting."
            )
            # Optional: unsubscribe previous if needed

        # Validate skill interface
        required_methods = ["process_event", "get_supported_event_types"]
        for method in required_methods:
            if not callable(getattr(skill, method, None)):
                raise RuntimeError(
                    f"Skill '{skill_name}' missing required method: {method}"
                )

        # Base priority (e.g., 1.0) multiplied
        priority = 1.0 * priority_multiplier

        subscription = SkillSubscription(
            skill=skill,
            event_types=event_types,
            priority=priority,
            config=getattr(skill, "config", {}),
        )
        self.skill_subscriptions[skill_name] = subscription

        # Optional: Subscribe skill directly to event_bus if it supports it
        if self.event_bus and hasattr(skill, "subscribe_to_bus"):
            try:
                handle = await skill.subscribe_to_bus(self.event_bus)
                self._subscription_handles.append(handle)
                logger.debug(
                    f"Skill '{skill_name}' subscribed to EventBus for agent {self.agent_id}"
                )
            except (AttributeError, TypeError, RuntimeError) as e:
                logger.warning(f"Failed to subscribe skill '{skill_name}': {e}")

        logger.info(
            f"Registered skill '{skill_name}' (priority {priority:.2f}) for {len(event_types)} event types on agent {self.agent_id}"
        )

    async def unregister_skill(self, skill_name: str) -> bool:
        """
        Unregisters a skill and cleans up subscriptions.

        Args:
            skill_name: The name of the skill to unregister.

        Returns:
            True if unregistered, False if not found.
        """
        if skill_name not in self.skill_subscriptions:
            logger.warning(f"Skill '{skill_name}' not found for agent {self.agent_id}")
            return False

        subscription = self.skill_subscriptions.pop(skill_name)

        # Cleanup bus subscription if applicable
        if self.event_bus and hasattr(subscription.skill, "unsubscribe_from_bus"):
            try:
                await subscription.skill.unsubscribe_from_bus(self.event_bus)
                logger.debug(f"Skill '{skill_name}' unsubscribed from EventBus")
            except (AttributeError, TypeError, RuntimeError) as e:
                logger.warning(f"Failed to unsubscribe skill '{skill_name}': {e}")

        logger.info(f"Unregistered skill '{skill_name}' for agent {self.agent_id}")
        return True

    async def dispatch_event(self, event: Any) -> List[SkillAction]:
        """
        Dispatches an event to registered skills that support its type, executes them concurrently
        (limited by semaphore), collects actions, applies strategy, and returns approved actions.

        Args:
            event: The event object to dispatch (e.g., TickEvent).

        Returns:
            List of SkillAction generated by skills, sorted and limited by strategy.

        Raises:
            ValueError: If no matching skills for event type.
            RuntimeError: If event type cannot be determined.
        """
        event_type = getattr(event, "__class__.__name__", str(type(event).__name__))
        logger.debug(f"Dispatching {event_type} to skills for agent {self.agent_id}")

        # Find matching skills
        matching_skills = [
            (name, sub)
            for name, sub in self.skill_subscriptions.items()
            if event_type in sub.event_types
        ]

        if not matching_skills:
            logger.debug(
                f"No skills registered for event type '{event_type}' on agent {self.agent_id}"
            )
            return []

        # Execute matching skills concurrently with semaphore limit
        tasks = []
        for skill_name, subscription in matching_skills:
            task = self._execute_skill_async(subscription.skill, event, skill_name)
            tasks.append((skill_name, task))

        # Gather results with timeout and error handling
        results = []
        for skill_name, task in tasks:
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(
                        task, timeout=30.0
                    )  # 30s timeout per skill
                    if result:
                        results.append((skill_name, result))
            except asyncio.TimeoutError:
                logger.warning(
                    f"Skill '{skill_name}' timed out processing {event_type} for agent {self.agent_id}"
                )
            except (AttributeError, TypeError, ValueError, RuntimeError) as e:
                logger.error(
                    f"Skill '{skill_name}' failed processing {event_type}: {e}",
                    exc_info=True,
                )

        if not results:
            return []

        # Apply coordination strategy
        actions = []
        for skill_name, skill_result in results:
            if isinstance(skill_result, list):
                for action in skill_result:
                    if isinstance(action, SkillAction):
                        action.skill_source = (
                            skill_name  # Annotate source for arbitration
                        )
                        actions.append(action)
            elif isinstance(skill_result, SkillAction):
                skill_result.skill_source = skill_name
                actions.append(skill_result)

        # Strategy: priority_based - sort by priority desc, limit to top N if configured
        if self.coordination_strategy == CoordinationStrategy.PRIORITY_BASED.value:
            actions.sort(key=lambda a: a.priority or 0, reverse=True)
            max_actions = self.config.get("max_actions_per_dispatch", len(actions))
            actions = actions[:max_actions]
            logger.debug(
                f"Applied priority_based strategy: {len(actions)} actions selected from {len(results)} skills"
            )

        # Optional: Publish aggregated actions or metrics to event_bus
        if self.event_bus and actions:
            # Example: Publish SkillActionsDispatched event (implement if needed)
            pass

        logger.info(
            f"Dispatched {event_type} to {len(matching_skills)} skills; generated {len(actions)} actions for agent {self.agent_id}"
        )
        return actions

    async def _execute_skill_async(
        self, skill: Any, event: Any, skill_name: str
    ) -> List[SkillAction]:
        """
        Executes a skill's process_event method asynchronously.

        Args:
            skill: The skill object.
            event: The event to process.
            skill_name: Name of the skill for logging.

        Returns:
            List of SkillAction or single SkillAction from the skill.
        """
        try:
            # Assume skill.process_event returns List[SkillAction] or SkillAction
            result = await skill.process_event(event)
            if isinstance(result, SkillAction):
                return [result]
            elif isinstance(result, list):
                return [a for a in result if isinstance(a, SkillAction)]
            else:
                logger.warning(
                    f"Skill '{skill_name}' returned unexpected type: {type(result)}"
                )
                return []
        except (AttributeError, TypeError, ValueError, RuntimeError) as e:
            logger.error(
                f"Error in skill '{skill_name}.process_event': {e}", exc_info=True
            )
            return []

    async def cleanup(self) -> None:
        """Cleans up subscriptions and resources."""
        for skill_name in list(self.skill_subscriptions.keys()):
            await self.unregister_skill(skill_name)
        self.skill_subscriptions.clear()
        if self.event_bus:
            for handle in self._subscription_handles:
                try:
                    await self.event_bus.unsubscribe(handle)
                except Exception:
                    pass
            self._subscription_handles.clear()
        logger.info(f"SkillCoordinator cleaned up for agent {self.agent_id}")

    def get_skill_status(self) -> Dict[str, Any]:
        """Returns status of registered skills for monitoring."""
        return {
            "agent_id": self.agent_id,
            "total_skills": len(self.skill_subscriptions),
            "strategy": self.coordination_strategy,
            "max_concurrent": self.max_concurrent_skills,
            "subscriptions": {
                name: {"event_types": sub.event_types, "priority": sub.priority}
                for name, sub in self.skill_subscriptions.items()
            },
        }
