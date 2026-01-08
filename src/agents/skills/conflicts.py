"""
Conflict resolution and action coordination for skills.
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from money import Money

from ..skill_modules.base_skill import SkillAction
from .models import CoordinationStrategy, CoordinatorTuning, ResourceAllocation
from .utils import get_expected_roi_baseline

logger = logging.getLogger(__name__)


class ConflictResolver:
    """
    Resolves conflicts and coordinates actions from multiple skills using various strategies.
    """

    def __init__(
        self,
        coordination_strategy: CoordinationStrategy,
        coordinator_tuning: CoordinatorTuning,
        config: Dict[str, Any],
        conflict_log: List[Dict[str, Any]],
        skill_metrics: Dict[str, "SkillPerformanceMetrics"],  # Forward ref
        resource_allocation: ResourceAllocation,
    ):
        """
        Initialize the ConflictResolver.

        Args:
            coordination_strategy: The coordination strategy to use
            coordinator_tuning: Tuning parameters including exclusive pairs
            config: Configuration dictionary
            conflict_log: List to append conflict entries
            skill_metrics: Dictionary of skill metrics for rate updates
        """
        self.coordination_strategy = coordination_strategy
        self.coordinator_tuning = coordinator_tuning
        self.config = config
        self.conflict_log = conflict_log
        self.skill_metrics = skill_metrics
        self.resource_allocation = resource_allocation

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
        # Flatten all actions with skill attribution if from multiple sources
        all_actions = []
        for action in skill_actions:
            if not hasattr(action, "skill_source") or not action.skill_source:
                action.skill_source = "external"  # Default for direct calls
            all_actions.append(action)

        if len(all_actions) <= 1:
            return all_actions

        # Apply coordination strategy
        if self.coordination_strategy == CoordinationStrategy.PRIORITY_BASED:
            return self._coordinate_by_priority(all_actions)
        elif self.coordination_strategy == CoordinationStrategy.RESOURCE_OPTIMAL:
            return self._coordinate_by_resources(all_actions)
        elif self.coordination_strategy == CoordinationStrategy.CONSENSUS_BASED:
            return await self._coordinate_by_consensus(all_actions)
        else:  # ROUND_ROBIN
            return self._coordinate_round_robin(all_actions)

    def _coordinate_by_priority(self, actions: List[SkillAction]) -> List[SkillAction]:
        """Coordinate actions based on priority scores."""
        # Sort by priority and confidence
        sorted_actions = sorted(
            actions, key=lambda a: a.priority * a.confidence, reverse=True
        )

        # Check for conflicts and resolve
        coordinated_actions = []
        resource_usage = {"budget": Money(cents=0), "tokens": 0}

        for action in sorted_actions:
            action_budget_money = Money(
                cents=action.resource_requirements.get("budget", 0)
            )
            action_tokens = action.resource_requirements.get("tokens", 0)

            if (
                resource_usage["budget"] + action_budget_money
                <= self.resource_allocation.remaining_budget
                and resource_usage["tokens"] + action_tokens
                <= self.resource_allocation.remaining_tokens
                and not self._has_conflict(action, coordinated_actions)
            ):
                coordinated_actions.append(action)
                resource_usage["budget"] += action_budget_money
                resource_usage["tokens"] += action_tokens
            else:
                # Log conflict
                self._log_conflict(action, coordinated_actions)

        return coordinated_actions

    def _coordinate_by_resources(self, actions: List[SkillAction]) -> List[SkillAction]:
        """Coordinate actions to optimize resource utilization."""
        # Calculate resource efficiency for each action
        efficient_actions = []

        expected_roi_baseline = get_expected_roi_baseline(
            self.coordinator_tuning, self.config
        )

        for action in actions:
            budget_req = action.resource_requirements.get("budget", 0)
            tokens_req = action.resource_requirements.get("tokens", 0)

            # Calculate efficiency score (expected outcome / resource cost)
            expected_value = (
                sum(action.expected_outcome.values())
                if action.expected_outcome
                else expected_roi_baseline
            )
            resource_cost = budget_req + tokens_req + 1  # Avoid division by zero
            efficiency = (expected_value * action.confidence) / resource_cost

            efficient_actions.append((action, efficiency))

        # Sort by efficiency and select within resource constraints
        efficient_actions.sort(key=lambda x: x[1], reverse=True)

        coordinated_actions = []
        resource_usage = {"budget": Money(cents=0), "tokens": 0}

        for action, efficiency in efficient_actions:
            action_budget_money = Money(
                cents=action.resource_requirements.get("budget", 0)
            )
            action_tokens = action.resource_requirements.get("tokens", 0)

            if (
                resource_usage["budget"] + action_budget_money
                <= self.resource_allocation.remaining_budget
                and resource_usage["tokens"] + action_tokens
                <= self.resource_allocation.remaining_tokens
                and not self._has_conflict(action, coordinated_actions)
            ):
                coordinated_actions.append(action)
                resource_usage["budget"] += action_budget_money
                resource_usage["tokens"] += action_tokens

        return coordinated_actions

    async def _coordinate_by_consensus(
        self, actions: List[SkillAction]
    ) -> List[SkillAction]:
        """Coordinate actions based on consensus among skills."""
        # Group actions by type
        action_groups = defaultdict(list)
        for action in actions:
            action_groups[action.action_type].append(action)

        coordinated_actions = []

        for action_type, group_actions in action_groups.items():
            if len(group_actions) == 1:
                # No conflict, include the action
                coordinated_actions.append(group_actions[0])
            else:
                # Multiple skills suggest same action type - find consensus
                consensus_action = await self._find_consensus_action(group_actions)
                if consensus_action:
                    coordinated_actions.append(consensus_action)

        return coordinated_actions

    def _coordinate_round_robin(self, actions: List[SkillAction]) -> List[SkillAction]:
        """Coordinate actions using round-robin selection."""
        # Group actions by skill
        skill_actions = defaultdict(list)
        for action in actions:
            skill_actions[action.skill_source].append(action)

        coordinated_actions = []
        skill_list = list(skill_actions.keys())
        skill_index = 0

        while any(skill_actions.values()):
            current_skill = skill_list[skill_index]
            if skill_actions[current_skill]:
                action = skill_actions[current_skill].pop(0)
                if not self._has_conflict(action, coordinated_actions):
                    coordinated_actions.append(action)

            skill_index = (skill_index + 1) % len(skill_list)

            # Prevent infinite loop
            if not any(skill_actions.values()):
                break

        return coordinated_actions

    def _has_conflict(
        self, action: SkillAction, existing_actions: List[SkillAction]
    ) -> bool:
        """Check if action conflicts with existing actions."""
        for existing in existing_actions:
            # Check for same action type targeting same resource
            if action.action_type == existing.action_type and action.parameters.get(
                "asin"
            ) == existing.parameters.get("asin"):
                return True

            # Check for mutually exclusive actions
            if self._are_mutually_exclusive(action.action_type, existing.action_type):
                return True

        return False

    def _are_mutually_exclusive(self, action_type1: str, action_type2: str) -> bool:
        """Check if two action types are mutually exclusive."""
        exclusive_pairs = self._get_exclusive_pairs()
        return (action_type1, action_type2) in exclusive_pairs or (
            action_type2,
            action_type1,
        ) in exclusive_pairs

    def _get_exclusive_pairs(self) -> List[Tuple[str, str]]:
        """
        Returns a list of mutually exclusive skill action type pairs.
        Reads from coordinator_tuning or falls back to hardcoded defaults.
        """
        if self.coordinator_tuning.exclusive_pairs is not None:
            return self.coordinator_tuning.exclusive_pairs

        # Hardcoded defaults for backward compatibility
        return [
            ("set_price", "adjust_pricing_strategy"),
            ("place_order", "implement_cost_reduction"),
            ("run_marketing_campaign", "reduce_campaign_spend"),
        ]

    async def _find_consensus_action(
        self, actions: List[SkillAction]
    ) -> Optional[SkillAction]:
        """Find consensus action from multiple similar actions."""
        if not actions:
            return None

        # Calculate weighted average of parameters based on confidence
        total_confidence = sum(action.confidence for action in actions)
        if total_confidence == 0:
            return actions[0]  # Fallback to first action

        # Use the action with highest confidence as base
        base_action = max(actions, key=lambda a: a.confidence)

        # Average numeric parameters weighted by confidence
        numeric_params = {}
        for param_name in base_action.parameters:
            if isinstance(base_action.parameters[param_name], (int, float)):
                weighted_sum = sum(
                    action.parameters.get(param_name, 0) * action.confidence
                    for action in actions
                    if param_name in action.parameters
                )
                numeric_params[param_name] = weighted_sum / total_confidence

        # Create consensus action
        consensus_action = SkillAction(
            action_type=base_action.action_type,
            parameters={**base_action.parameters, **numeric_params},
            confidence=total_confidence / len(actions),  # Average confidence
            reasoning=f"Consensus from {len(actions)} skills: {base_action.reasoning}",
            priority=max(action.priority for action in actions),
            resource_requirements=base_action.resource_requirements,
            expected_outcome=base_action.expected_outcome,
            skill_source="consensus",
        )

        return consensus_action

    def _log_conflict(
        self, conflicting_action: SkillAction, existing_actions: List[SkillAction]
    ) -> None:
        """Log action conflict for analysis."""
        conflict_entry = {
            "timestamp": datetime.now(),
            "conflicting_action": {
                "type": conflicting_action.action_type,
                "skill": conflicting_action.skill_source,
                "priority": conflicting_action.priority,
            },
            "existing_actions": [
                {
                    "type": action.action_type,
                    "skill": action.skill_source,
                    "priority": action.priority,
                }
                for action in existing_actions
            ],
            "resolution": "priority_override",
        }

        self.conflict_log.append(conflict_entry)

        # Update conflict rate metrics
        if conflicting_action.skill_source in self.skill_metrics:
            metrics = self.skill_metrics[conflicting_action.skill_source]
            my_conflicts = [
                c
                for c in self.conflict_log
                if c["conflicting_action"]["skill"] == conflicting_action.skill_source
            ]
            metrics.conflict_rate = len(my_conflicts) / max(
                1, metrics.total_actions_generated
            )
