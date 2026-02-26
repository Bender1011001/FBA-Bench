from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List

from .models import StrategicObjective, TacticalAction

logger = logging.getLogger(__name__)


async def validate_strategic_objectives(
    objectives: Dict[str, StrategicObjective],
    context: Dict[str, Any],
) -> Dict[str, StrategicObjective]:
    """Validate and potentially modify objectives based on constraints."""
    validated = {}

    for obj_id, objective in objectives.items():
        # Validate target metrics are achievable
        if are_targets_realistic(objective, context):
            validated[obj_id] = objective
        else:
            # Adjust targets to be more realistic
            adjusted_objective = adjust_objective_targets(objective, context)
            validated[obj_id] = adjusted_objective
            logger.warning(
                f"Adjusted targets for objective '{objective.title}' to be more realistic"
            )

    return validated


def are_targets_realistic(
    objective: StrategicObjective,
    context: Dict[str, Any],
) -> bool:
    """Check if objective targets are realistic given current context."""
    current_metrics = context.get("current_metrics", {})

    for metric, target_value in objective.target_metrics.items():
        current_value = current_metrics.get(metric, 0.0)

        # Check if growth rate is reasonable (e.g., not more than 100% improvement)
        if current_value > 0:
            growth_rate = (target_value - current_value) / current_value
            if growth_rate > 1.0:  # More than 100% improvement
                return False

    return True


def adjust_objective_targets(
    objective: StrategicObjective,
    context: Dict[str, Any],
) -> StrategicObjective:
    """Adjust objective targets to be more realistic."""
    current_metrics = context.get("current_metrics", {})
    adjusted_targets = {}

    for metric, target_value in objective.target_metrics.items():
        current_value = current_metrics.get(metric, 0.0)

        if current_value > 0:
            # Limit growth to maximum 50% improvement
            max_improvement = current_value * 1.5
            adjusted_targets[metric] = min(target_value, max_improvement)
        else:
            # For metrics starting from zero, use conservative targets
            adjusted_targets[metric] = target_value * 0.5

    objective.target_metrics = adjusted_targets
    return objective


async def validate_and_schedule_actions(
    actions: List[TacticalAction],
    current_state: Dict[str, Any],
    planner_params: Any,
) -> List[TacticalAction]:
    """Validate actions and optimize their scheduling."""
    validated_actions = []  # type: ignore[var-annotated]

    for action in actions:
        # Validate action parameters
        if await validate_action_parameters(action, current_state):
            # Optimize scheduling based on dependencies and resources
            optimized_action = await optimize_action_scheduling(
                action, validated_actions, planner_params
            )
            validated_actions.append(optimized_action)
        else:
            logger.warning(f"Action {action.title} failed validation and was excluded")

    return validated_actions


async def validate_action_parameters(
    action: TacticalAction,
    current_state: Dict[str, Any],
) -> bool:
    """Validate that action parameters are feasible."""
    # Check budget constraints for actions with costs
    if action.action_type == "run_marketing_campaign":
        budget = action.parameters.get("budget", 0)
        available_budget = current_state.get("available_budget", 0)
        if budget > available_budget:
            return False

    # Check inventory constraints for ordering actions
    if action.action_type == "place_order":
        quantity = action.parameters.get("quantity", 0)
        if quantity <= 0:
            return False

    return True


async def optimize_action_scheduling(
    action: TacticalAction,
    existing_actions: List[TacticalAction],
    planner_params: Any,
) -> TacticalAction:
    """Optimize action scheduling to avoid conflicts and respect dependencies."""
    # Check for scheduling conflicts
    conflicting_actions = [
        a
        for a in existing_actions
        if a.action_type == action.action_type
        and abs((a.scheduled_execution - action.scheduled_execution).total_seconds())
        < int(planner_params.scheduling_conflict_seconds)
    ]

    if conflicting_actions:
        # Reschedule to avoid conflict
        latest_conflict = max(conflicting_actions, key=lambda a: a.scheduled_execution)
        action.scheduled_execution = latest_conflict.scheduled_execution + timedelta(
            hours=1
        )

    return action
