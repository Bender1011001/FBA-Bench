from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config.model_config import get_model_params
from fba_bench_core.event_bus import EventBus, get_event_bus
from fba_events import BaseEvent

from .events import (
    StrategicPlanCreatedEvent,
    StrategicPlanUpdatedEvent,
    TacticalActionCompletedEvent,
    TacticalActionsGeneratedEvent,
    TacticalActionsPrioritizedEvent,
    publish_strategic_plan_created_event,
    publish_strategic_plan_updated_event,
    publish_tactical_action_completed_event,
    publish_tactical_actions_generated_event,
    publish_tactical_actions_prioritized_event,
)
from .generation import (
    generate_actions_for_objective,
    generate_immediate_response_actions,
    generate_objectives_for_strategy,
)
from .models import (
    PlanPriority,
    PlanStatus,
    PlanType,
    StrategicObjective,
    TacticalAction,
)
from .utils import (
    analyze_external_events_impact,
    apply_constraints_to_prioritization,
    apply_objective_modifications,
    archive_completed_objectives,
    assess_strategic_performance,
    calculate_action_objective_alignment,
    calculate_action_priority_score,
    cleanup_old_actions,
    determine_objective_modifications,
    determine_strategy_type,
    identify_new_objectives_needed,
    identify_objectives_to_cancel,
    reschedule_failed_action,
    should_create_new_strategy,
    should_reschedule_failed_action,
)
from .validation import (
    validate_and_schedule_actions,
    validate_strategic_objectives,
)

logger = logging.getLogger(__name__)


class StrategicPlanner:
    """
    Manages high-level quarterly/phase goals and strategic direction.

    Responsible for creating, updating, and validating strategic plans
    that guide the agent's long-term decision-making.
    """

    def __init__(self, agent_id: str, event_bus: Optional[EventBus] = None):
        """
        Initialize the Strategic Planner.

        Args:
            agent_id: Unique identifier for the agent
            event_bus: Event bus for publishing strategic events
        """
        self.agent_id = agent_id
        self.event_bus = event_bus or get_event_bus()

        # Strategic state
        self.strategic_objectives: Dict[str, StrategicObjective] = {}
        self.archived_objectives: List[StrategicObjective] = []  # In-memory archive
        self.current_strategy_type: Optional[PlanType] = None
        self.strategy_created_at: Optional[datetime] = None
        self.last_strategy_review: Optional[datetime] = None

        # Performance tracking
        self.strategy_performance_history: List[Dict[str, Any]] = []
        self.external_events_impact: List[Dict[str, Any]] = []

        # Centralized planning thresholds
        self._planner_params = get_model_params().planner

        logger.info(f"StrategicPlanner initialized for agent {agent_id}")

    async def create_strategic_plan(
        self, context: Dict[str, Any], timeframe: int
    ) -> Dict[str, StrategicObjective]:
        """
        Generate strategic objectives based on current context and timeframe.

        Args:
            context: Current business context including metrics, market conditions, etc.
            timeframe: Planning horizon in days

        Returns:
            Dictionary of strategic objectives with their IDs as keys
        """
        logger.info(
            f"Creating strategic plan for agent {self.agent_id} with {timeframe}-day horizon"
        )

        current_time = datetime.now()
        strategy_type = determine_strategy_type(context, self._planner_params)

        # Clear existing objectives if starting fresh strategic cycle
        if should_create_new_strategy(
            current_time,
            self.strategy_created_at,
            self.current_strategy_type,
            strategy_type,
            self._planner_params,
        ):
            archive_completed_objectives(
                self.strategic_objectives, self.archived_objectives, self.agent_id
            )
            self.strategic_objectives.clear()
            self.current_strategy_type = strategy_type
            self.strategy_created_at = current_time

        # Generate strategic objectives based on strategy type
        objectives = await generate_objectives_for_strategy(
            strategy_type, context, timeframe, current_time, self._planner_params
        )

        # Validate objective dependencies and feasibility
        validated_objectives = await validate_strategic_objectives(objectives, context)

        # Store objectives and publish strategic plan event
        for obj_id, objective in validated_objectives.items():
            self.strategic_objectives[obj_id] = objective

        await publish_strategic_plan_created_event(
            self.event_bus,
            validated_objectives,
            self.agent_id,
            self.current_strategy_type,
        )

        logger.info(
            f"Created strategic plan with {len(validated_objectives)} objectives"
        )
        return validated_objectives

    async def update_strategic_plan(
        self,
        current_performance: Dict[str, float],
        external_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Adapt strategy based on performance and external events.

        Args:
            current_performance: Current metrics and KPIs
            external_events: List of external events that may impact strategy

        Returns:
            Dictionary containing update results and any new/modified objectives
        """
        logger.info(f"Updating strategic plan for agent {self.agent_id}")

        current_time = datetime.now()
        update_results = {
            "objectives_modified": [],
            "objectives_added": [],
            "objectives_cancelled": [],
            "strategy_changes": [],
            "performance_assessment": {},
        }

        # Assess performance against current objectives
        performance_assessment = assess_strategic_performance(
            self.strategic_objectives, current_performance
        )
        update_results["performance_assessment"] = performance_assessment

        # Analyze impact of external events
        event_impact = await analyze_external_events_impact(
            external_events, self.strategic_objectives
        )
        self.external_events_impact.extend(event_impact)

        # Update objective priorities and status based on performance
        for obj_id, objective in self.strategic_objectives.items():
            progress = objective.calculate_progress(current_performance)
            objective.progress_indicators = {"overall_progress": progress}

            # Modify objectives based on performance and events
            modifications = await determine_objective_modifications(
                objective, performance_assessment, event_impact
            )

            if modifications:
                update_results["objectives_modified"].append(
                    {"objective_id": obj_id, "modifications": modifications}
                )
                apply_objective_modifications(objective, modifications)

        # Add new objectives if needed based on external events
        new_objectives = await identify_new_objectives_needed(
            external_events, current_performance, current_time
        )

        for new_obj in new_objectives:
            obj_id = new_obj.objective_id
            self.strategic_objectives[obj_id] = new_obj
            update_results["objectives_added"].append(obj_id)

        # Cancel objectives that are no longer viable
        cancelled_objectives = await identify_objectives_to_cancel(
            self.strategic_objectives,
            current_performance,
            external_events,
            self._planner_params,
        )

        for obj_id in cancelled_objectives:
            if obj_id in self.strategic_objectives:
                self.strategic_objectives[obj_id].status = PlanStatus.CANCELLED
                update_results["objectives_cancelled"].append(obj_id)

        # Update strategy performance history
        self.strategy_performance_history.append(
            {
                "timestamp": current_time.isoformat(),
                "performance_metrics": current_performance,
                "objectives_count": len(self.strategic_objectives),
                "avg_progress": performance_assessment.get("average_progress", 0.0),
            }
        )

        self.last_strategy_review = current_time
        await publish_strategic_plan_updated_event(
            self.event_bus, update_results, self.agent_id
        )

        logger.info(
            f"Strategic plan updated: {len(update_results['objectives_modified'])} modified, "
            f"{len(update_results['objectives_added'])} added, "
            f"{len(update_results['objectives_cancelled'])} cancelled"
        )

        return update_results

    async def validate_action_alignment(
        self,
        proposed_action: Dict[str, Any],
        current_strategy: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, str]:
        """
        Check if a proposed action aligns with current strategic objectives.

        Args:
            proposed_action: Action to validate (contains type, parameters, expected_impact)
            current_strategy: Optional strategy context for validation

        Returns:
            Tuple of (is_aligned, alignment_score, reasoning)
        """
        if not self.strategic_objectives:
            return (
                True,
                0.5,
                "No strategic objectives defined - action allowed by default",
            )

        action_type = proposed_action.get("type", "unknown")
        expected_impact = proposed_action.get("expected_impact", {})

        alignment_scores = []
        supporting_objectives = []

        # Check alignment against each active strategic objective
        for obj_id, objective in self.strategic_objectives.items():
            if objective.status != PlanStatus.ACTIVE:
                continue

            alignment_score = await calculate_action_objective_alignment(
                proposed_action, objective, self._planner_params
            )

            if alignment_score > self._planner_params.meaningful_alignment_threshold:
                alignment_scores.append(alignment_score)
                supporting_objectives.append(obj_id)

        if not alignment_scores:
            return (
                False,
                0.0,
                f"Action '{action_type}' does not align with any active strategic objectives",
            )

        overall_alignment = max(alignment_scores)  # Use best alignment score

        is_aligned = overall_alignment >= self._planner_params.aligned_threshold

        reasoning = f"Action '{action_type}' alignment score: {overall_alignment:.2f}. "
        if is_aligned:
            reasoning += f"Supports objectives: {supporting_objectives}"
        else:
            reasoning += "Insufficient alignment with strategic goals"

        return is_aligned, overall_alignment, reasoning

    def get_strategic_status(self) -> Dict[str, Any]:
        """Get comprehensive status of strategic planning."""
        current_time = datetime.now()

        active_objectives = [
            obj
            for obj in self.strategic_objectives.values()
            if obj.status == PlanStatus.ACTIVE
        ]

        overdue_objectives = [
            obj for obj in active_objectives if obj.is_overdue(current_time)
        ]

        status = {
            "agent_id": self.agent_id,
            "current_strategy_type": (
                self.current_strategy_type.value if self.current_strategy_type else None
            ),
            "strategy_age_days": (
                (current_time - self.strategy_created_at).days
                if self.strategy_created_at
                else 0
            ),
            "total_objectives": len(self.strategic_objectives),
            "active_objectives": len(active_objectives),
            "overdue_objectives": len(overdue_objectives),
            "last_review": (
                self.last_strategy_review.isoformat()
                if self.last_strategy_review
                else None
            ),
            "performance_history_entries": len(self.strategy_performance_history),
        }

        if active_objectives:
            # Calculate average progress
            progress_scores = []
            for obj in active_objectives:
                if obj.progress_indicators:
                    progress_scores.append(
                        obj.progress_indicators.get("overall_progress", 0.0)
                    )

            status["average_progress"] = (
                sum(progress_scores) / len(progress_scores) if progress_scores else 0.0
            )

            # Identify highest priority objectives
            high_priority_objectives = [
                obj
                for obj in active_objectives
                if obj.priority in [PlanPriority.HIGH, PlanPriority.CRITICAL]
            ]
            status["high_priority_objectives"] = len(high_priority_objectives)

        return status


class TacticalPlanner:
    """
    Manages short-term actions that serve strategic goals.

    Responsible for generating, prioritizing, and scheduling tactical actions
    that implement strategic objectives.
    """

    def __init__(
        self,
        agent_id: str,
        strategic_planner: StrategicPlanner,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Initialize the Tactical Planner.

        Args:
            agent_id: Unique identifier for the agent
            strategic_planner: Reference to strategic planner for alignment
            event_bus: Event bus for publishing tactical events
        """
        self.agent_id = agent_id
        self.strategic_planner = strategic_planner
        self.event_bus = event_bus or get_event_bus()

        # Tactical state
        self.tactical_actions: Dict[str, TacticalAction] = {}
        self.completed_actions: List[str] = []
        self.action_execution_history: List[Dict[str, Any]] = []

        # Planning parameters
        self.planning_horizon_hours = 168  # 1 week default
        self.max_concurrent_actions = 5

        # Centralized planning thresholds for tactical layer
        self._planner_params = get_model_params().planner

        logger.info(f"TacticalPlanner initialized for agent {agent_id}")

    async def generate_tactical_actions(
        self,
        strategic_goals: Dict[str, StrategicObjective],
        current_state: Dict[str, Any],
    ) -> List[TacticalAction]:
        """
        Create action plans that serve strategic goals.

        Args:
            strategic_goals: Active strategic objectives to serve
            current_state: Current business state and context

        Returns:
            List of tactical actions ordered by priority and dependencies
        """
        logger.info(
            f"Generating tactical actions for {len(strategic_goals)} strategic goals"
        )

        current_time = datetime.now()
        new_actions = []

        # Generate actions for each strategic objective
        for objective in strategic_goals.values():
            if objective.status != PlanStatus.ACTIVE:
                continue

            objective_actions = await generate_actions_for_objective(
                objective, current_state, current_time, self._planner_params
            )
            new_actions.extend(objective_actions)

        # Generate immediate response actions based on current state
        immediate_actions = await generate_immediate_response_actions(
            current_state, current_time
        )
        new_actions.extend(immediate_actions)

        # Validate and schedule actions
        validated_actions = await validate_and_schedule_actions(
            new_actions, current_state, self._planner_params
        )

        # Add to tactical actions registry
        for action in validated_actions:
            self.tactical_actions[action.action_id] = action

        # Clean up old completed actions
        cleanup_old_actions(self.tactical_actions, self._planner_params, self.agent_id)

        await publish_tactical_actions_generated_event(
            self.event_bus, validated_actions, self.agent_id
        )

        logger.info(f"Generated {len(validated_actions)} tactical actions")
        return validated_actions

    async def prioritize_actions(
        self, action_list: List[TacticalAction], constraints: Dict[str, Any]
    ) -> List[TacticalAction]:
        """
        Rank actions by urgency, importance, and resource constraints.

        Args:
            action_list: List of actions to prioritize
            constraints: Resource and timing constraints

        Returns:
            Prioritized list of actions
        """
        logger.info(f"Prioritizing {len(action_list)} tactical actions")

        # Calculate priority scores for each action
        action_scores = []

        for action in action_list:
            score = await calculate_action_priority_score(
                action,
                constraints,
                self.strategic_planner.strategic_objectives,
                self._planner_params,
            )
            action_scores.append((action, score))

        # Sort by priority score (descending)
        action_scores.sort(key=lambda x: x[1], reverse=True)

        # Apply resource constraints and dependencies
        prioritized_actions = await apply_constraints_to_prioritization(
            action_scores, constraints, self.max_concurrent_actions
        )

        await publish_tactical_actions_prioritized_event(
            self.event_bus, prioritized_actions, self.agent_id
        )

        logger.info(
            f"Prioritized actions - top priority: {prioritized_actions[0].title if prioritized_actions else 'None'}"
        )
        return prioritized_actions

    def get_ready_actions(
        self, current_time: Optional[datetime] = None
    ) -> List[TacticalAction]:
        """Get actions that are ready for execution."""
        current_time = current_time or datetime.now()

        ready_actions = []
        for action in self.tactical_actions.values():
            if action.is_ready_for_execution(current_time, self.completed_actions):
                ready_actions.append(action)

        return ready_actions

    async def mark_action_completed(
        self, action_id: str, execution_result: Dict[str, Any]
    ):
        """Mark an action as completed and record results."""
        if action_id in self.tactical_actions:
            action = self.tactical_actions[action_id]
            action.status = PlanStatus.COMPLETED

            self.completed_actions.append(action_id)

            # Record execution history
            execution_record = {
                "action_id": action_id,
                "completed_at": datetime.now().isoformat(),
                "execution_result": execution_result,
                "strategic_objective_id": action.strategic_objective_id,
            }
            self.action_execution_history.append(execution_record)

            await publish_tactical_action_completed_event(
                self.event_bus, action, execution_result, self.agent_id
            )

            logger.info(f"Marked action {action_id} as completed")

    async def mark_action_failed(self, action_id: str, failure_reason: str):
        """Mark an action as failed and optionally reschedule."""
        if action_id in self.tactical_actions:
            action = self.tactical_actions[action_id]
            action.status = PlanStatus.FAILED

            # Record failure
            failure_record = {
                "action_id": action_id,
                "failed_at": datetime.now().isoformat(),
                "failure_reason": failure_reason,
                "strategic_objective_id": action.strategic_objective_id,
            }
            self.action_execution_history.append(failure_record)

            # Determine if action should be rescheduled
            should_reschedule = should_reschedule_failed_action(action, failure_reason)

            if should_reschedule:
                reschedule_failed_action(action, failure_reason, self.tactical_actions)

            logger.warning(f"Marked action {action_id} as failed: {failure_reason}")

    def get_tactical_status(self) -> Dict[str, Any]:
        """Get comprehensive status of tactical planning."""
        current_time = datetime.now()

        active_actions = [
            a for a in self.tactical_actions.values() if a.status == PlanStatus.ACTIVE
        ]
        ready_actions = self.get_ready_actions(current_time)
        overdue_actions = [
            a for a in active_actions if a.scheduled_execution < current_time
        ]

        status = {
            "agent_id": self.agent_id,
            "total_actions": len(self.tactical_actions),
            "active_actions": len(active_actions),
            "ready_actions": len(ready_actions),
            "overdue_actions": len(overdue_actions),
            "completed_actions": len(self.completed_actions),
            "execution_history_entries": len(self.action_execution_history),
            "planning_horizon_hours": self.planning_horizon_hours,
        }

        if active_actions:
            # Calculate priority distribution
            priority_counts = {}
            for action in active_actions:
                priority = action.priority.value
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
            status["priority_distribution"] = priority_counts

            # Next scheduled action
            next_action = min(active_actions, key=lambda a: a.scheduled_execution)
            status["next_scheduled_action"] = {
                "action_id": next_action.action_id,
                "title": next_action.title,
                "scheduled_at": next_action.scheduled_execution.isoformat(),
            }

        return status


class HierarchicalPlanner:
    """
    Main orchestrator for hierarchical planning system.

    Composes strategic and tactical planners to provide unified planning interface.
    """

    def __init__(self, agent_id: str, event_bus: Optional[EventBus] = None):
        """
        Initialize the Hierarchical Planner.

        Args:
            agent_id: Unique identifier for the agent
            event_bus: Event bus for publishing planning events
        """
        self.agent_id = agent_id
        self.event_bus = event_bus or get_event_bus()

        self.strategic_planner = StrategicPlanner(agent_id, self.event_bus)
        self.tactical_planner = TacticalPlanner(
            agent_id, self.strategic_planner, self.event_bus
        )

        logger.info(f"HierarchicalPlanner initialized for agent {agent_id}")

    async def create_strategic_plan(
        self, context: Dict[str, Any], timeframe: int
    ) -> Dict[str, StrategicObjective]:
        """Create a new strategic plan and generate initial tactical actions."""
        strategic_objectives = await self.strategic_planner.create_strategic_plan(
            context, timeframe
        )
        await self.tactical_planner.generate_tactical_actions(
            strategic_objectives, context
        )
        return strategic_objectives

    async def update_strategic_plan(
        self,
        current_performance: Dict[str, float],
        external_events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update the strategic plan and refresh tactical actions."""
        update_results = await self.strategic_planner.update_strategic_plan(
            current_performance, external_events
        )
        await self.tactical_planner.generate_tactical_actions(
            self.strategic_planner.strategic_objectives,
            {"current_metrics": current_performance},
        )
        return update_results

    async def generate_tactical_actions(
        self, current_state: Dict[str, Any]
    ) -> List[TacticalAction]:
        """Generate tactical actions based on current state."""
        strategic_goals = self.strategic_planner.strategic_objectives
        return await self.tactical_planner.generate_tactical_actions(
            strategic_goals, current_state
        )

    async def prioritize_actions(
        self, action_list: List[TacticalAction], constraints: Dict[str, Any]
    ) -> List[TacticalAction]:
        """Prioritize tactical actions."""
        return await self.tactical_planner.prioritize_actions(action_list, constraints)

    def get_ready_actions(
        self, current_time: Optional[datetime] = None
    ) -> List[TacticalAction]:
        """Get ready tactical actions."""
        return self.tactical_planner.get_ready_actions(current_time)

    async def mark_action_completed(
        self, action_id: str, execution_result: Dict[str, Any]
    ):
        """Mark tactical action as completed."""
        await self.tactical_planner.mark_action_completed(action_id, execution_result)

    async def mark_action_failed(self, action_id: str, failure_reason: str):
        """Mark tactical action as failed."""
        await self.tactical_planner.mark_action_failed(action_id, failure_reason)

    async def validate_action_alignment(
        self, proposed_action: Dict[str, Any]
    ) -> Tuple[bool, float, str]:
        """Validate action alignment with strategic objectives."""
        return await self.strategic_planner.validate_action_alignment(proposed_action)

    def get_planning_status(self) -> Dict[str, Any]:
        """Get comprehensive planning status."""
        return {
            "strategic": self.strategic_planner.get_strategic_status(),
            "tactical": self.tactical_planner.get_tactical_status(),
        }


# Re-exports for backward compatibility
__all__ = [
    "HierarchicalPlanner",
    "StrategicPlanner",
    "TacticalPlanner",
    "StrategicObjective",
    "TacticalAction",
    "PlanPriority",
    "PlanStatus",
    "PlanType",
    "StrategicPlanCreatedEvent",
    "StrategicPlanUpdatedEvent",
    "TacticalActionsGeneratedEvent",
    "TacticalActionsPrioritizedEvent",
    "TacticalActionCompletedEvent",
]
