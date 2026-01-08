from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from fba_events.base import BaseEvent
from fba_bench_core.event_bus import EventBus
from .models import StrategicObjective, PlanType, TacticalAction


@dataclass
class StrategicPlanCreatedEvent(BaseEvent):
    """Event published when a new strategic plan is created."""

    agent_id: str
    strategy_type: str
    objectives_count: int
    objective_summaries: List[Dict[str, Any]]

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": "StrategicPlanCreated",
            "strategy_type": self.strategy_type,
            "objectives_count": self.objectives_count,
        }


@dataclass
class StrategicPlanUpdatedEvent(BaseEvent):
    """Event published when an existing strategic plan is updated."""

    agent_id: str
    update_results: Dict[str, Any]

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": "StrategicPlanUpdated",
            "objectives_modified_count": len(
                self.update_results.get("objectives_modified", [])
            ),
            "objectives_added_count": len(
                self.update_results.get("objectives_added", [])
            ),
            "objectives_cancelled_count": len(
                self.update_results.get("objectives_cancelled", [])
            ),
        }


@dataclass
class TacticalActionsGeneratedEvent(BaseEvent):
    """Event published when new tactical actions are generated."""

    agent_id: str
    actions_count: int
    action_summaries: List[Dict[str, Any]]

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": "TacticalActionsGenerated",
            "actions_count": self.actions_count,
        }


@dataclass
class TacticalActionsPrioritizedEvent(BaseEvent):
    """Event published when tactical actions are prioritized."""

    agent_id: str
    prioritized_actions: List[str]

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": "TacticalActionsPrioritized",
            "prioritized_actions_count": len(self.prioritized_actions),
        }


@dataclass
class TacticalActionCompletedEvent(BaseEvent):
    """Event published when a tactical action is completed."""

    agent_id: str
    action_id: str
    action_type: str
    strategic_objective_id: str
    execution_result: Dict[str, Any]

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": "TacticalActionCompleted",
            "action_id": self.action_id,
            "action_type": self.action_type,
            "strategic_objective_id": self.strategic_objective_id,
        }


import logging

logger = logging.getLogger(__name__)


async def publish_strategic_plan_created_event(
    event_bus: EventBus,
    objectives: Dict[str, StrategicObjective],
    agent_id: str,
    current_strategy_type: PlanType,
):
    """Publish event when strategic plan is created."""
    try:
        event = StrategicPlanCreatedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            agent_id=agent_id,
            strategy_type=current_strategy_type.value,
            objectives_count=len(objectives),
            objective_summaries=[
                {
                    "id": obj.objective_id,
                    "title": obj.title,
                    "priority": obj.priority.value,
                    "timeframe_days": obj.timeframe_days,
                }
                for obj in objectives.values()
            ],
        )
        await event_bus.publish(event)
    except Exception:
        logger.exception(
            f"Failed to publish strategic plan created event for agent {agent_id}"
        )


async def publish_strategic_plan_updated_event(
    event_bus: EventBus,
    update_results: Dict[str, Any],
    agent_id: str,
):
    """Publish event when strategic plan is updated."""
    try:
        event = StrategicPlanUpdatedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            agent_id=agent_id,
            update_results=update_results,
        )
        await event_bus.publish(event)
    except Exception:
        logger.exception(
            f"Failed to publish strategic plan updated event for agent {agent_id}"
        )


async def publish_tactical_actions_generated_event(
    event_bus: EventBus,
    actions: List[TacticalAction],
    agent_id: str,
):
    """Publish event when tactical actions are generated."""
    try:
        event = TacticalActionsGeneratedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            agent_id=agent_id,
            actions_count=len(actions),
            action_summaries=[
                {
                    "id": action.action_id,
                    "title": action.title,
                    "type": action.action_type,
                    "priority": action.priority.value,
                    "scheduled_at": action.scheduled_execution.isoformat(),
                }
                for action in actions
            ],
        )
        await event_bus.publish(event)
    except Exception:
        logger.exception(
            f"Failed to publish tactical actions generated event for agent {agent_id}"
        )


async def publish_tactical_actions_prioritized_event(
    event_bus: EventBus,
    actions: List[TacticalAction],
    agent_id: str,
):
    """Publish event when tactical actions are prioritized."""
    try:
        event = TacticalActionsPrioritizedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            agent_id=agent_id,
            prioritized_actions=[action.action_id for action in actions],
        )
        await event_bus.publish(event)
    except Exception:
        logger.exception(
            f"Failed to publish tactical actions prioritized event for agent {agent_id}"
        )


async def publish_tactical_action_completed_event(
    event_bus: EventBus,
    action: TacticalAction,
    execution_result: Dict[str, Any],
    agent_id: str,
):
    """Publish event when a tactical action is completed."""
    try:
        event = TacticalActionCompletedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            agent_id=agent_id,
            action_id=action.action_id,
            action_type=action.action_type,
            strategic_objective_id=action.strategic_objective_id,
            execution_result=execution_result,
        )
        await event_bus.publish(event)
    except Exception:
        logger.exception(
            f"Failed to publish tactical action completed event for agent {agent_id}"
        )
