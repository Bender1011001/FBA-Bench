"""
Performance tracking and metrics for multi-domain controller.

Handles decision logging, success metrics, and strategic dashboard generation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from agents.skill_modules.base_skill import SkillAction

from .models import StrategicDecision

logger = logging.getLogger(__name__)


class PerformanceManager:
    """
    Manager for performance tracking and metrics in multi-domain control.

    Handles decision logging, success rate calculation, and dashboard metrics.
    """

    def __init__(self, controller):
        """
        Initialize the PerformanceManager.

        Args:
            controller: The parent MultiDomainController instance for shared state access.
        """
        self.controller = controller

    async def get_strategic_dashboard(self) -> Dict[str, Any]:
        """Get strategic dashboard with key metrics and status."""
        return {
            "business_state": {
                "financial_health": self.controller.current_business_state.financial_health,
                "cash_position": self.controller.current_business_state.cash_position,
                "customer_satisfaction": self.controller.current_business_state.customer_satisfaction,
                "operational_efficiency": self.controller.current_business_state.operational_efficiency,
                "current_priority": self.controller.current_priority.value,
                "strategic_focus": [
                    obj.value
                    for obj in self.controller.current_business_state.strategic_focus
                ],
            },
            "resource_allocation": {
                "total_budget": self.controller.resource_plan.total_budget.to_float(),
                "allocations": {
                    domain: allocation.to_float()
                    for domain, allocation in self.controller.resource_plan.allocations.items()
                },
                "utilization": {
                    domain: self.controller.resource_plan.priority_multipliers.get(
                        domain, 1.0
                    )
                    for domain in self.controller.resource_plan.allocations.keys()
                },
            },
            "performance_metrics": {
                "decision_success_rate": round(
                    self.controller.decision_success_rate, 3
                ),
                "resource_utilization_efficiency": round(
                    self.controller.resource_utilization_efficiency, 3
                ),
                "strategic_alignment_score": round(
                    self.controller.strategic_alignment_score, 3
                ),
                "total_decisions": len(self.controller.strategic_decisions),
                "pending_approvals": len(self.controller.pending_approvals),
            },
            "recent_decisions": [
                {
                    "decision_id": decision.decision_id,
                    "timestamp": decision.timestamp.isoformat(),
                    "type": decision.decision_type,
                    "actions_approved": len(decision.actions_approved),
                    "actions_rejected": len(decision.actions_rejected),
                    "expected_impact": decision.expected_impact,
                }
                for decision in self.controller.strategic_decisions[
                    -5:
                ]  # Last 5 decisions
            ],
        }

    def get_performance_summary(self) -> Dict[str, float]:
        """Get summary of controller performance metrics."""
        return {
            "decision_success_rate": self.controller.decision_success_rate,
            "resource_utilization_efficiency": self.controller.resource_utilization_efficiency,
            "strategic_alignment_score": self.controller.strategic_alignment_score,
            "total_decisions_made": len(self.controller.strategic_decisions),
            "avg_actions_per_decision": (
                sum(
                    len(d.actions_approved) for d in self.controller.strategic_decisions
                )
                / max(1, len(self.controller.strategic_decisions))
            ),
            "crisis_responses": len(
                [
                    d
                    for d in self.controller.strategic_decisions
                    if "crisis" in d.decision_type
                ]
            ),
        }

    async def _log_strategic_decision(
        self,
        decision_type: str,
        all_actions: List[SkillAction],
        approved_actions: List[SkillAction],
    ):
        """Log strategic decision for tracking and analysis."""
        rejected_actions = [
            action for action in all_actions if action not in approved_actions
        ]

        # Calculate expected impact
        expected_impact = {}
        for action in approved_actions:
            for outcome, value in action.expected_outcome.items():
                if outcome not in expected_impact:
                    expected_impact[outcome] = 0
                if isinstance(value, (int, float)):
                    expected_impact[outcome] += value  # type: ignore[assignment]

        decision = StrategicDecision(
            decision_id=f"{decision_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            decision_type=decision_type,
            context=self.controller.current_business_state,
            actions_approved=approved_actions,
            actions_rejected=rejected_actions,
            reasoning=f"Arbitration based on {self.controller.current_priority.value} priority and strategic alignment",
            expected_impact=expected_impact,  # type: ignore[arg-type]
        )

        self.controller.strategic_decisions.append(decision)

        # Keep decision history manageable
        if len(self.controller.strategic_decisions) > 1000:
            self.controller.strategic_decisions = self.controller.strategic_decisions[
                -500:
            ]

        # Update decision success tracking
        self._update_decision_tracking(decision)

    def _update_decision_tracking(self, decision: StrategicDecision):
        """Update decision tracking metrics."""
        # Simple success rate calculation based on action confidence
        if decision.actions_approved:
            avg_confidence = sum(
                action.confidence for action in decision.actions_approved
            ) / len(decision.actions_approved)
            # Update running average
            self.controller.decision_success_rate = (
                self.controller.decision_success_rate * 0.9
            ) + (avg_confidence * 0.1)

        # Update strategic alignment score
        alignment_scores = []
        for action in decision.actions_approved:
            is_aligned, alignment_score, _ = (
                self.controller.coordination.validate_strategic_alignment(
                    action,
                    {
                        "objectives": [
                            obj.value
                            for obj in self.controller.current_business_state.strategic_focus
                        ]
                    },
                )
            )
            alignment_scores.append(alignment_score)

        if alignment_scores:
            avg_alignment = sum(alignment_scores) / len(alignment_scores)
            self.controller.strategic_alignment_score = (
                self.controller.strategic_alignment_score * 0.9
            ) + (avg_alignment * 0.1)
