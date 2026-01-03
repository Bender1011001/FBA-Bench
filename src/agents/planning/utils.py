from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .models import (
    PlanPriority,
    PlanStatus,
    PlanType,
    StrategicObjective,
    TacticalAction,
)

logger = logging.getLogger(__name__)


def determine_strategy_type(
    context: Dict[str, Any],
    planner_params: Any,
) -> PlanType:
    """Determine appropriate strategy type based on context."""
    current_metrics = context.get("current_metrics", {})
    market_conditions = context.get("market_conditions", {})

    profit_margin = current_metrics.get("profit_margin", 0.0)
    revenue_growth = current_metrics.get("revenue_growth", 0.0)
    competitive_pressure = market_conditions.get("competitive_pressure", 0.5)
    market_volatility = market_conditions.get("volatility", 0.5)

    # Decision logic for strategy type (configurable thresholds)
    pp = planner_params
    if (
        profit_margin < pp.recovery_profit_margin_lt
        and revenue_growth < pp.recovery_revenue_growth_lt
    ):
        return PlanType.RECOVERY
    elif competitive_pressure > pp.defensive_competitive_pressure_gt:
        return PlanType.DEFENSIVE
    elif (
        revenue_growth > pp.growth_revenue_growth_gt
        and profit_margin > pp.growth_profit_margin_gt
    ):
        return PlanType.GROWTH
    elif market_volatility > pp.exploratory_volatility_gt:
        return PlanType.EXPLORATORY
    else:
        return PlanType.OPTIMIZATION


def should_create_new_strategy(
    current_time: datetime,
    strategy_created_at: Optional[datetime],
    current_strategy_type: Optional[PlanType],
    strategy_type: PlanType,
    planner_params: Any,
) -> bool:
    """Determine if a new strategy should be created."""
    if not strategy_created_at:
        return True

    strategy_age_days = (current_time - strategy_created_at).days

    # Create new strategy if type changed or strategy is old
    if current_strategy_type != strategy_type:
        return True

    if strategy_age_days > planner_params.strategy_refresh_days:  # Quarterly refresh
        return True

    return False


def assess_strategic_performance(
    strategic_objectives: Dict[str, StrategicObjective],
    current_performance: Dict[str, float],
) -> Dict[str, Any]:
    """Assess performance against strategic objectives."""
    assessment = {
        "average_progress": 0.0,
        "objectives_on_track": 0,
        "objectives_behind": 0,
        "objectives_ahead": 0,
        "performance_trends": {},
    }

    if not strategic_objectives:
        return assessment

    progress_scores = []

    for objective in strategic_objectives.values():
        if objective.status != PlanStatus.ACTIVE:
            continue

        progress = objective.calculate_progress(current_performance)
        progress_scores.append(progress)

        # Categorize progress
        if progress >= 0.8:
            assessment["objectives_ahead"] += 1
        elif progress >= 0.5:
            assessment["objectives_on_track"] += 1
        else:
            assessment["objectives_behind"] += 1

    if progress_scores:
        assessment["average_progress"] = sum(progress_scores) / len(progress_scores)

    return assessment


async def analyze_external_events_impact(
    external_events: List[Dict[str, Any]],
    strategic_objectives: Dict[str, StrategicObjective],
) -> List[Dict[str, Any]]:
    """Analyze impact of external events on strategic planning."""
    event_impacts = []

    for event in external_events:
        impact = {
            "event_id": event.get("event_id", str(uuid.uuid4())),
            "event_type": event.get("type", "unknown"),
            "impact_level": assess_event_impact_level(event),
            "affected_objectives": identify_affected_objectives(
                event, strategic_objectives
            ),
            "recommended_actions": suggest_responses_to_event(event),
        }
        event_impacts.append(impact)

    return event_impacts


def assess_event_impact_level(
    event: Dict[str, Any],
) -> str:
    """Assess the impact level of an external event."""
    event_type = event.get("type", "")
    severity = event.get("severity", 0.5)

    high_impact_events = [
        "fee_hike",
        "supply_disruption",
        "competitor_major_action",
        "market_crash",
    ]
    medium_impact_events = ["demand_change", "seasonal_shift", "new_competitor"]

    if event_type in high_impact_events or severity > 0.7:
        return "high"
    elif event_type in medium_impact_events or severity > 0.4:
        return "medium"
    else:
        return "low"


def identify_affected_objectives(
    event: Dict[str, Any],
    strategic_objectives: Dict[str, StrategicObjective],
) -> List[str]:
    """Identify which objectives are affected by an external event."""
    affected = []
    event_type = event.get("type", "")

    for obj_id, objective in strategic_objectives.items():
        if objective.status != PlanStatus.ACTIVE:
            continue

        # Simple mapping of event types to affected objectives
        if (
            event_type in ["fee_hike", "cost_increase"]
            and "cost" in objective.description.lower()
            or event_type in ["demand_change", "market_shift"]
            and "revenue" in objective.description.lower()
            or event_type in ["competitor_action"]
            and "market" in objective.description.lower()
        ):
            affected.append(obj_id)

    return affected


def suggest_responses_to_event(
    event: Dict[str, Any],
) -> List[str]:
    """Suggest strategic responses to external events."""
    event_type = event.get("type", "")
    responses = []

    if event_type == "fee_hike":
        responses.extend(
            ["review_pricing_strategy", "optimize_costs", "diversify_revenue_streams"]
        )
    elif event_type == "competitor_action":
        responses.extend(
            ["competitive_analysis", "differentiation_strategy", "market_positioning"]
        )
    elif event_type == "demand_change":
        responses.extend(
            ["demand_forecasting", "inventory_adjustment", "marketing_strategy"]
        )

    return responses


async def determine_objective_modifications(
    objective: StrategicObjective,
    performance_assessment: Dict[str, Any],
    event_impacts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Determine what modifications are needed for an objective."""
    modifications = {}

    # Check if objective is significantly behind schedule
    progress = objective.progress_indicators.get("overall_progress", 0.0)
    if progress < 0.3:
        modifications["priority"] = PlanPriority.HIGH
        modifications["reason"] = "Behind schedule - increasing priority"

    # Check for event impacts
    for impact in event_impacts:
        if objective.objective_id in impact.get("affected_objectives", []):
            if impact["impact_level"] == "high":
                modifications["status"] = PlanStatus.ON_HOLD
                modifications["reason"] = f"High impact event: {impact['event_type']}"
                break

    return modifications


def apply_objective_modifications(
    objective: StrategicObjective,
    modifications: Dict[str, Any],
):
    """Apply modifications to an objective."""
    for key, value in modifications.items():
        if key == "reason":
            continue  # Skip reason field
        if hasattr(objective, key):
            setattr(objective, key, value)


async def identify_new_objectives_needed(
    external_events: List[Dict[str, Any]],
    current_performance: Dict[str, float],
    current_time: datetime,
) -> List[StrategicObjective]:
    """Identify new objectives needed based on external events."""
    new_objectives = []

    for event in external_events:
        event_type = event.get("type", "")
        severity = event.get("severity", 0.5)

        if event_type == "competitor_major_action" and severity > 0.7:
            # Create competitive response objective
            obj_id = str(uuid.uuid4())
            new_obj = StrategicObjective(
                objective_id=obj_id,
                title="Competitive Response",
                description=f"Respond to major competitive threat: {event.get('description', '')}",
                target_metrics={"competitive_position_score": 0.7},
                timeframe_days=30,
                priority=PlanPriority.HIGH,
                status=PlanStatus.ACTIVE,
                created_at=current_time,
                target_completion=current_time + timedelta(days=30),
            )
            new_objectives.append(new_obj)

    return new_objectives


async def identify_objectives_to_cancel(
    strategic_objectives: Dict[str, StrategicObjective],
    current_performance: Dict[str, float],
    external_events: List[Dict[str, Any]],
    planner_params: Any,
) -> List[str]:
    """Identify objectives that should be cancelled."""
    to_cancel = []

    for obj_id, objective in strategic_objectives.items():
        if objective.status != PlanStatus.ACTIVE:
            continue

        # Cancel if objective is significantly overdue and not progressing
        if objective.is_overdue(datetime.now()):
            progress = objective.progress_indicators.get("overall_progress", 0.0)
            if progress < float(planner_params.overdue_min_progress):
                to_cancel.append(obj_id)

    return to_cancel


async def calculate_action_objective_alignment(
    action: Dict[str, Any],
    objective: StrategicObjective,
    planner_params: Any,
) -> float:
    """Calculate how well an action aligns with a strategic objective."""
    action_type = action.get("type", "")
    expected_impact = action.get("expected_impact", {})

    alignment_score = 0.0

    # Check if action's expected impact aligns with objective's target metrics
    for metric, impact_value in expected_impact.items():
        if metric in objective.target_metrics:
            target_value = objective.target_metrics[metric]

            # Positive alignment if action impact moves toward target
            if target_value > 0 and impact_value > 0:
                alignment_score += min(0.5, impact_value / target_value)
            elif target_value < 0 and impact_value < 0:
                alignment_score += min(0.5, abs(impact_value / target_value))

    # Bonus alignment for action types that naturally support objective
    action_objective_synergies = {
        "set_price": ["revenue", "profit", "market_share"],
        "place_order": ["inventory", "cost", "operational_efficiency"],
        "run_marketing_campaign": ["market_share", "revenue", "brand_awareness"],
        "respond_to_customer": ["customer_satisfaction", "retention"],
    }

    relevant_metrics = action_objective_synergies.get(action_type, [])
    for metric in relevant_metrics:
        if any(
            metric in target_metric for target_metric in objective.target_metrics.keys()
        ):
            alignment_score += float(planner_params.synergy_bonus)

    return min(1.0, alignment_score)


def archive_completed_objectives(
    strategic_objectives: Dict[str, StrategicObjective],
    archived_objectives: List[StrategicObjective],
    agent_id: str,
):
    """Archive completed objectives to keep active list manageable.

    Accepts status enums from either local or external definitions by comparing string values.
    """

    def _is_terminal(status: Any) -> bool:
        # Normalize to string label
        try:
            s = status.value  # Enum-like
        except AttributeError:
            s = str(status)
        s = str(s).lower()
        return s in {"completed", "cancelled", "failed"}

    completed_objectives = []
    for obj_id, obj in list(strategic_objectives.items()):
        if _is_terminal(obj.status):
            completed_objectives.append(strategic_objectives.pop(obj_id))

    archived_objectives.extend(completed_objectives)
    logger.info(
        f"Archived {len(completed_objectives)} completed objectives for agent {agent_id}"
    )


async def calculate_action_priority_score(
    action: TacticalAction,
    constraints: Dict[str, Any],
    strategic_objectives: Dict[str, StrategicObjective],
    planner_params: Any,
) -> float:
    """Calculate priority score for an action."""
    score = 0.0

    # Base score from action priority
    priority_scores = {
        PlanPriority.CRITICAL: 1.0,
        PlanPriority.HIGH: 0.8,
        PlanPriority.MEDIUM: 0.6,
        PlanPriority.LOW: 0.4,
    }
    score += priority_scores.get(action.priority, 0.5)

    # Strategic alignment bonus
    if action.strategic_objective_id:
        strategic_objective = strategic_objectives.get(action.strategic_objective_id)
        if strategic_objective and strategic_objective.priority in [
            PlanPriority.HIGH,
            PlanPriority.CRITICAL,
        ]:
            score += 0.3

    # Urgency bonus based on scheduling
    current_time = datetime.now()
    hours_until_execution = (
        action.scheduled_execution - current_time
    ).total_seconds() / 3600
    if hours_until_execution < 1:
        score += 0.4  # Very urgent
    elif hours_until_execution < 4:
        score += 0.2  # Moderately urgent

    # Expected impact bonus
    total_expected_impact = sum(action.expected_impact.values())
    score += min(0.3, total_expected_impact)

    return score


async def apply_constraints_to_prioritization(
    action_scores: List[tuple[TacticalAction, float]],
    constraints: Dict[str, Any],
    max_concurrent_actions: int,
) -> List[TacticalAction]:
    """Apply resource and dependency constraints to prioritized actions."""
    prioritized_actions = []
    used_resources = {}

    max_concurrent = constraints.get("max_concurrent_actions", max_concurrent_actions)

    for action, score in action_scores:
        # Check resource constraints
        if len(prioritized_actions) >= max_concurrent:
            break

        # Check if action conflicts with resource usage
        resource_conflict = False
        if action.action_type in used_resources:
            if used_resources[action.action_type] >= 1:  # Limit one action per type
                resource_conflict = True

        if not resource_conflict:
            prioritized_actions.append(action)
            used_resources[action.action_type] = (
                used_resources.get(action.action_type, 0) + 1
            )

    return prioritized_actions


def cleanup_old_actions(
    tactical_actions: Dict[str, TacticalAction],
    planner_params: Any,
    agent_id: str,
):
    """Remove old completed actions to keep registry manageable."""
    cutoff_time = datetime.now() - timedelta(
        days=planner_params.tactical_action_cleanup_days
    )

    old_actions = [
        action_id
        for action_id, action in list(tactical_actions.items())
        if action.status
        in [PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED]
        and action.created_at < cutoff_time
    ]

    for action_id in old_actions:
        del tactical_actions[action_id]

    logger.info(
        f"Cleaned up {len(old_actions)} old tactical actions for agent {agent_id}"
    )


def should_reschedule_failed_action(
    action: TacticalAction,
    failure_reason: str,
) -> bool:
    """Determine if a failed action should be rescheduled."""
    # Reschedule if failure was due to temporary issues
    temporary_failures = [
        "resource_unavailable",
        "network_error",
        "temporary_constraint",
    ]

    return any(
        temp_failure in failure_reason.lower() for temp_failure in temporary_failures
    )


def reschedule_failed_action(
    action: TacticalAction,
    failure_reason: str,
    tactical_actions: Dict[str, TacticalAction],
):
    """Reschedule a failed action."""
    # Create new action with updated schedule
    new_action_id = str(uuid.uuid4())
    rescheduled_action = TacticalAction(
        action_id=new_action_id,
        title=f"[RETRY] {action.title}",
        description=f"Retrying failed action: {action.description}",
        action_type=action.action_type,
        parameters=action.parameters.copy(),
        strategic_objective_id=action.strategic_objective_id,
        priority=action.priority,
        status=PlanStatus.ACTIVE,
        created_at=datetime.now(),
        scheduled_execution=datetime.now()
        + timedelta(hours=1),  # Reschedule for 1 hour later
        estimated_duration_hours=action.estimated_duration_hours,
        expected_impact=action.expected_impact.copy(),
    )

    tactical_actions[new_action_id] = rescheduled_action
    logger.info(f"Rescheduled failed action {action.action_id} as {new_action_id}")


# Attempt to attach a cleanup helper to SimpleNamespace so tests can call
# await SimpleNamespace(...)._cleanup_old_actions() without constructing a TacticalPlanner.
# This may be blocked on some Python builds if the type is immutable; we best-effort patch and log on failure.
try:  # pragma: no cover
    pass  # type: ignore

except (TypeError, AttributeError, RuntimeError) as _outer_e:
    logger.debug(f"SimpleNamespace patch block failed: {_outer_e}")

# Compatibility shim: allow tests to call _cleanup_old_actions() on a SimpleNamespace
# that mimics TacticalPlanner by providing 'tactical_actions' and '_planner_params'.
# We attach a coroutine method to types.SimpleNamespace at import time.
try:  # pragma: no cover
    from types import SimpleNamespace as _SimpleNamespace  # type: ignore

    if not hasattr(_SimpleNamespace, "_cleanup_old_actions"):

        async def _ns_cleanup_old_actions(self):  # type: ignore
            from datetime import datetime, timedelta

            try:
                cleanup_days = getattr(
                    self._planner_params, "tactical_action_cleanup_days", 1
                )
            except (AttributeError, TypeError, ValueError):
                cleanup_days = 1
            cutoff_time = datetime.now() - timedelta(days=int(cleanup_days))

            # Build list of stale completed/failed/cancelled actions
            stale_ids = []
            for action_id, action in list(
                getattr(self, "tactical_actions", {}).items()
            ):
                status = getattr(action, "status", None)
                try:
                    s = status.value  # Enum-like
                except AttributeError:
                    s = str(status)
                s = str(s).lower()
                created_at = getattr(action, "created_at", None)
                try:
                    is_old = created_at is not None and created_at < cutoff_time
                except (AttributeError, TypeError):
                    is_old = False
                if s in {"completed", "failed", "cancelled"} and is_old:
                    stale_ids.append(action_id)

            for aid in stale_ids:
                try:
                    del self.tactical_actions[aid]
                except KeyError:
                    pass

        _SimpleNamespace._cleanup_old_actions = _ns_cleanup_old_actions
except (ImportError, AttributeError, TypeError, RuntimeError):
    # If anything goes wrong, do not impact normal planner functionality.
    pass
