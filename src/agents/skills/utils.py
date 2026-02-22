"""
Utility functions for skill coordination.
"""

from datetime import datetime
from typing import Any, Dict, List, Tuple

from fba_bench_core.money import Money

from fba_events.base import BaseEvent

from ..skill_modules.base_skill import SkillAction
from .models import CoordinatorTuning


def get_max_concurrent_events(
    skill_name: str, config: Dict[str, Any], coordinator_tuning: CoordinatorTuning
) -> int:
    """
    Returns the maximum concurrent events for a skill.
    Reads from skill-specific config, then coordinator_tuning, then hardcoded default.
    """
    skill_config_max = config.get(f"{skill_name}_max_concurrent")
    if skill_config_max is not None and isinstance(skill_config_max, int):
        return skill_config_max

    if coordinator_tuning.max_concurrent_events_default is not None:
        return coordinator_tuning.max_concurrent_events_default

    return 3  # Default value


def get_urgency_multiplier(
    urgency_level: str, coordinator_tuning: CoordinatorTuning, config: Dict[str, Any]
) -> float:
    """
    Returns the urgency multiplier for a given urgency level.
    Reads from coordinator_tuning, then config, then hardcoded defaults.
    """
    # Check coordinator_tuning first
    if (
        coordinator_tuning.urgency_multipliers is not None
        and isinstance(coordinator_tuning.urgency_multipliers, dict)
        and urgency_level in coordinator_tuning.urgency_multipliers
    ):
        return coordinator_tuning.urgency_multipliers[urgency_level]

    # Fallback to config (dict-based)
    cfg_um = config.get("urgency_multipliers")
    if isinstance(cfg_um, dict) and urgency_level in cfg_um:
        return cfg_um[urgency_level]

    # Hardcoded defaults for backward compatibility
    defaults = {"low": 0.8, "normal": 1.0, "high": 1.3, "critical": 1.5}
    return defaults.get(urgency_level, 1.0)  # Default to 1.0 if urgency_level not found


def get_expected_roi_baseline(
    coordinator_tuning: CoordinatorTuning, config: Dict[str, Any]
) -> float:
    """
    Returns the expected ROI baseline.
    Reads from coordinator_tuning, then config, then hardcoded default.
    """
    if coordinator_tuning.expected_roi_baseline is not None:
        return coordinator_tuning.expected_roi_baseline

    # Fallback to config (dict-based)
    cfg_roi = config.get("expected_roi_baseline")
    if isinstance(cfg_roi, (int, float)):
        return float(cfg_roi)

    return 2.0  # Default value


def log_coordination_decision(
    event: BaseEvent,
    skill_actions: List[Tuple[str, List[SkillAction]]],
    coordinated_actions: List[SkillAction],
    coordination_history: List[Dict[str, Any]],
    coordination_strategy: str,
    resource_allocation: Any,  # ResourceAllocation instance for total_budget
) -> None:
    """
    Log coordination decision for analysis.

    Args:
        event: The event being coordinated
        skill_actions: List of (skill_name, actions) tuples
        coordinated_actions: Final coordinated actions
        coordination_history: List to append the log entry to
        coordination_strategy: Current strategy value
        resource_allocation: ResourceAllocation for budget reference
    """
    coordination_entry = {
        "timestamp": datetime.now(),
        "event_type": type(event).__name__,
        "participating_skills": [skill_name for skill_name, _ in skill_actions],
        "total_actions_generated": sum(len(actions) for _, actions in skill_actions),
        "coordinated_actions_count": len(coordinated_actions),
        "coordination_strategy": coordination_strategy,
        "resource_usage": {
            "budget": sum(
                (Money(cents=action.resource_requirements.get("budget", 0))).cents
                for action in coordinated_actions
            ),
            "tokens": sum(
                action.resource_requirements.get("tokens", 0)
                for action in coordinated_actions
            ),
        },
    }

    coordination_history.append(coordination_entry)

    # Keep history size manageable
    if len(coordination_history) > 1000:
        coordination_history[:] = coordination_history[-500:]
