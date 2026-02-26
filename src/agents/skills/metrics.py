"""
Performance metrics tracking for skill coordination.
"""

from datetime import datetime
from typing import Any, Dict, List, Tuple

from fba_events.base import BaseEvent

from ..skill_modules.base_skill import SkillAction
from .models import ResourceAllocation, SkillPerformanceMetrics


class MetricsTracker:
    """
    Tracks performance metrics for skills and coordination statistics.
    """

    def __init__(
        self,
        skill_metrics: Dict[str, SkillPerformanceMetrics],
        coordination_history: List[Dict[str, Any]],
        conflict_log: List[Dict[str, Any]],
        resource_allocation: ResourceAllocation,
        skill_subscriptions: Dict[str, Any],  # Forward ref  # type: ignore[name-defined]
    ):
        """
        Initialize the MetricsTracker.

        Args:
            skill_metrics: Dictionary of skill names to performance metrics
            coordination_history: List of coordination log entries
            conflict_log: List of conflict log entries
            resource_allocation: Resource allocation for utilization stats
            skill_subscriptions: Registered skills for participation tracking
        """
        self.skill_metrics = skill_metrics
        self.coordination_history = coordination_history
        self.conflict_log = conflict_log
        self.resource_allocation = resource_allocation
        self.skill_subscriptions = skill_subscriptions

    async def update_event_processing(
        self, skill_name: str, response_time: float, actions: List[SkillAction]
    ) -> None:
        """
        Update metrics for a skill's event processing (timing and counts).

        Args:
            skill_name: Name of the skill
            response_time: Response time in seconds
            actions: List of actions generated
        """
        metrics = self.skill_metrics.get(skill_name)
        if not metrics:
            return

        metrics.total_events_processed += 1
        n = metrics.total_events_processed
        # Running average for response time
        metrics.average_response_time = (
            metrics.average_response_time * (n - 1) + response_time
        ) / n
        metrics.total_actions_generated += len(actions)

    async def update_performance_metrics(
        self, event: BaseEvent, skill_actions: List[Tuple[str, List[SkillAction]]]
    ) -> None:
        """
        Update performance metrics for skills based on action confidence.

        Args:
            event: The processed event
            skill_actions: List of (skill_name, actions) tuples
        """
        now = datetime.now()
        for skill_name, actions in skill_actions:
            if skill_name not in self.skill_metrics:
                continue

            metrics = self.skill_metrics[skill_name]
            metrics.last_update = now

            # Update success rate based on action confidence
            if actions:
                avg_confidence = sum(action.confidence for action in actions) / len(
                    actions
                )
                metrics.success_rate = (metrics.success_rate * 0.9) + (
                    avg_confidence * 0.1
                )

    def get_skill_performance_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get performance metrics for all registered skills.

        Returns:
            Dictionary of skill names to their performance metrics
        """
        metrics_dict = {}

        for skill_name, metrics in self.skill_metrics.items():
            metrics_dict[skill_name] = {
                "total_events_processed": metrics.total_events_processed,
                "total_actions_generated": metrics.total_actions_generated,
                "average_response_time": round(metrics.average_response_time, 3),
                "success_rate": round(metrics.success_rate, 3),
                "resource_efficiency": round(metrics.resource_efficiency, 3),
                "conflict_rate": round(metrics.conflict_rate, 3),
                "last_update": metrics.last_update.isoformat(),
            }

        return metrics_dict

    def get_coordination_statistics(self) -> Dict[str, Any]:
        """Get coordination statistics and analytics."""
        if not self.coordination_history:
            return {}

        recent_history = self.coordination_history[-100:]  # Last 100 coordinations

        total_coordinations = len(self.coordination_history)
        recent_coordinations = len(recent_history)
        avg_actions_per_coordination = (
            sum(entry["coordinated_actions_count"] for entry in recent_history)
            / recent_coordinations
            if recent_coordinations > 0
            else 0
        )

        # Resource utilization
        budget_utilization = (
            self.resource_allocation.allocated_budget.cents
            / self.resource_allocation.total_budget.cents
            if self.resource_allocation.total_budget.cents > 0
            else 0
        )
        token_utilization = (
            self.resource_allocation.allocated_tokens
            / self.resource_allocation.token_budget
            if self.resource_allocation.token_budget > 0
            else 0
        )

        # Skill participation in recent history
        skill_participation = {}
        for skill_name in self.skill_subscriptions.keys():
            participation_count = sum(
                1
                for entry in recent_history
                if skill_name in entry["participating_skills"]
            )
            skill_participation[skill_name] = participation_count

        return {
            "total_coordinations": total_coordinations,
            "recent_coordinations": recent_coordinations,
            "average_actions_per_coordination": round(avg_actions_per_coordination, 3),
            "total_conflicts": len(self.conflict_log),
            "resource_utilization": {
                "budget_utilization": round(budget_utilization, 3),
                "token_utilization": round(token_utilization, 3),
                "concurrent_slots_used": self.resource_allocation.used_slots,
                "max_concurrent_slots": self.resource_allocation.concurrent_slots,
            },
            "skill_participation": skill_participation,
        }
