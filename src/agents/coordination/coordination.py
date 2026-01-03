"""
Coordination logic for multi-domain controller.

Handles action arbitration, strategic filtering, business priority evaluation,
and alignment validation for agent actions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

from money import Money

from agents.skill_modules.base_skill import SkillAction

from .models import (
    BusinessPriority,
    StrategicDecision,
    StrategicObjective,
)

logger = logging.getLogger(__name__)


class CoordinationManager:
    """
    Manager for coordination and arbitration logic in multi-domain control.

    Handles strategic filtering, action arbitration, and business state evaluation.
    """

    def __init__(self, controller):
        """
        Initialize the CoordinationManager.

        Args:
            controller: The parent MultiDomainController instance for shared state access.
        """
        self.controller = controller

    async def evaluate_business_priorities(
        self, current_state: Dict[str, Any]
    ) -> BusinessPriority:
        """
        Evaluate current business priorities based on state and context.

        Args:
            current_state: Current business state information

        Returns:
            Determined business priority level
        """
        # Update business state
        await self._update_business_state(current_state)

        # Analyze financial health
        financial_health = current_state.get("financial_health", 0.5)
        cash_position = current_state.get("cash_position", "stable")

        # Determine priority based on critical factors
        if financial_health < 0.3 or cash_position == "critical":
            priority = BusinessPriority.SURVIVAL
        elif financial_health < 0.5 or cash_position == "warning":
            priority = BusinessPriority.STABILIZATION
        elif financial_health > 0.8 and cash_position == "healthy":
            priority = BusinessPriority.GROWTH
        elif financial_health > 0.6:
            priority = BusinessPriority.OPTIMIZATION
        else:
            priority = BusinessPriority.STABILIZATION

        # Update if priority changed
        if priority != self.controller.current_priority:
            logger.info(
                f"Business priority changed from {self.controller.current_priority.value} to {priority.value}"
            )
            self.controller.current_priority = priority
            self.controller._update_priority_multipliers()
            await self.controller._reallocate_resources_for_priority()

        return priority

    async def _update_business_state(self, current_state: Dict[str, Any]):
        """
        Update internal BusinessState from latest financial and operational signals.

        Expected keys in current_state (all optional, with sensible defaults):
          - cash_balance_cents: int
          - revenue_cents_last_window: int
          - cost_cents_last_window: int
          - profit_margin: float in [0,1]
          - financial_health: float in [0,1]
          - cash_position: str in {"critical","warning","stable","healthy"}
          - customer_satisfaction: float in [0,1]
          - operational_efficiency: float in [0,1]
          - growth_rate: float (can be negative)
          - risk_level: str in {"low","moderate","high","critical"}
        """
        fh = float(current_state.get("financial_health", 0.5))
        cash_pos = str(current_state.get("cash_position", "stable"))
        csat = float(current_state.get("customer_satisfaction", 0.8))
        op_eff = float(current_state.get("operational_efficiency", 0.7))
        growth_rate = float(current_state.get("growth_rate", 0.0))
        risk = str(current_state.get("risk_level", "moderate"))

        # Normalize and clamp
        fh = max(0.0, min(1.0, fh))
        csat = max(0.0, min(1.0, csat))
        op_eff = max(0.0, min(1.0, op_eff))

        self.controller.current_business_state.financial_health = fh
        self.controller.current_business_state.cash_position = cash_pos
        self.controller.current_business_state.customer_satisfaction = csat
        self.controller.current_business_state.operational_efficiency = op_eff
        self.controller.current_business_state.growth_trajectory = (
            "growing"
            if growth_rate > 0.02
            else ("declining" if growth_rate < -0.02 else "stable")
        )
        self.controller.current_business_state.risk_level = risk

        # Determine strategic focus based on weakest dimensions and trend
        focus_areas: List[StrategicObjective] = []
        if fh < 0.6 or cash_pos in ("critical", "warning"):
            focus_areas.append(StrategicObjective.FINANCIAL_STABILITY)
        if csat < 0.7:
            focus_areas.append(StrategicObjective.CUSTOMER_SATISFACTION)
        if op_eff < 0.6:
            focus_areas.append(StrategicObjective.OPERATIONAL_EFFICIENCY)
        if not focus_areas:
            # If all healthy, drive profitability and market share
            focus_areas.extend(
                [StrategicObjective.PROFITABILITY, StrategicObjective.MARKET_SHARE]
            )

        # Deduplicate while preserving order
        seen = set()
        deduped: List[StrategicObjective] = []
        for obj in focus_areas:
            if obj not in seen:
                deduped.append(obj)
                seen.add(obj)

        self.controller.current_business_state.strategic_focus = deduped

        # Store snapshot; keep bounded history for memory safety
        self.controller.state_history.append(
            (datetime.now(), self.controller.current_business_state)
        )
        if len(self.controller.state_history) > 200:
            self.controller.state_history = self.controller.state_history[-100:]

    async def arbitrate_actions(
        self, competing_actions: List[SkillAction]
    ) -> List[SkillAction]:
        """
        Arbitrate between competing actions from different skills.

        Args:
            competing_actions: List of competing skill actions

        Returns:
            Arbitrated list of approved actions
        """
        if not competing_actions:
            return []

        # Group actions by domain/skill
        domain_actions = self._group_actions_by_domain(competing_actions)

        # Apply strategic filtering
        strategic_actions = await self._apply_strategic_filter(competing_actions)

        # Apply resource constraints
        resource_approved = await self._apply_resource_constraints(strategic_actions)

        # Apply business rules and approval thresholds
        final_approved = await self._apply_business_rules(resource_approved)

        # Log strategic decision
        await self._log_strategic_decision(
            "action_arbitration", competing_actions, final_approved
        )

        return final_approved

    def _group_actions_by_domain(
        self, actions: List[SkillAction]
    ) -> Dict[str, List[SkillAction]]:
        """Group actions by business domain."""
        domain_mapping = {
            "SupplyManager": "inventory_management",
            "MarketingManager": "marketing",
            "CustomerService": "customer_service",
            "FinancialAnalyst": "financial_operations",
        }

        domain_actions = {}
        for action in actions:
            domain = domain_mapping.get(action.skill_source, "other")
            if domain not in domain_actions:
                domain_actions[domain] = []
            domain_actions[domain].append(action)

        return domain_actions

    async def _apply_strategic_filter(
        self, actions: List[SkillAction]
    ) -> List[SkillAction]:
        """
        Filter actions based on strategic alignment and current business priority.
        Heavily favors cash-preserving actions during SURVIVAL and downranks expensive growth plays.
        """
        if not actions:
            return []

        priority = self.controller.current_priority
        filtered: List[SkillAction] = []

        # Dynamic thresholding by priority
        base_threshold = 0.6
        if priority == BusinessPriority.SURVIVAL:
            threshold = 0.7
        elif priority == BusinessPriority.GROWTH:
            threshold = 0.55
        elif priority == BusinessPriority.OPTIMIZATION:
            threshold = 0.6
        else:
            threshold = base_threshold

        for action in actions:
            align = await self._calculate_strategic_alignment(action)

            # Apply additional penalty/boost based on priority and expected resource use
            budget_required = action.resource_requirements.get("budget", 0)
            budget_cents = (
                budget_required.cents
                if hasattr(budget_required, "cents")
                else int(budget_required or 0)
            )

            if priority == BusinessPriority.SURVIVAL:
                # Penalize high spend marketing; boost cost-saving/financial actions
                if (
                    action.action_type in ("run_marketing_campaign",)
                    and budget_cents > 0
                ):
                    align -= 0.2
                if action.action_type in (
                    "optimize_costs",
                    "cashflow_alert",
                    "budget_alert",
                    "assess_financial_health",
                ):
                    align += 0.2
            elif priority == BusinessPriority.GROWTH:
                # Encourage growth actions
                if action.action_type in (
                    "run_marketing_campaign",
                    "place_order",
                    "set_price",
                ):
                    align += 0.1

            if align >= threshold:
                filtered.append(action)
            else:
                logger.debug(
                    f"Strategic filter removed {action.action_type}: score={align:.2f}, threshold={threshold:.2f}, priority={priority.value}"
                )

        return filtered

    async def _calculate_strategic_alignment(self, action: SkillAction) -> float:
        """Calculate how well an action aligns with strategic objectives."""
        alignment_score = 0.5  # Base alignment

        # Check alignment with current strategic focus
        for objective in self.controller.current_business_state.strategic_focus:
            if self._action_supports_objective(action, objective):
                alignment_score += 0.2

        # Check alignment with business priority
        priority_alignment = self._calculate_priority_alignment(action)
        alignment_score += priority_alignment * 0.3

        # Factor in expected outcomes
        outcome_alignment = self._calculate_outcome_alignment(action)
        alignment_score += outcome_alignment * 0.2

        return min(1.0, alignment_score)

    def _action_supports_objective(
        self, action: SkillAction, objective: StrategicObjective
    ) -> bool:
        """Check if an action supports a strategic objective."""
        action_objective_mapping = {
            StrategicObjective.PROFITABILITY: [
                "set_price",
                "optimize_costs",
                "place_order",
                "run_marketing_campaign",
            ],
            StrategicObjective.FINANCIAL_STABILITY: [
                "budget_alert",
                "cashflow_alert",
                "optimize_costs",
                "assess_financial_health",
            ],
            StrategicObjective.CUSTOMER_SATISFACTION: [
                "respond_to_customer_message",
                "respond_to_review",
                "improve_customer_satisfaction",
            ],
            StrategicObjective.OPERATIONAL_EFFICIENCY: [
                "optimize_costs",
                "improve_response_time",
                "place_order",
            ],
            StrategicObjective.MARKET_SHARE: [
                "run_marketing_campaign",
                "set_price",
                "adjust_pricing_strategy",
            ],
            StrategicObjective.BRAND_REPUTATION: [
                "respond_to_review",
                "respond_to_customer_message",
                "improve_customer_satisfaction",
            ],
        }

        supported_actions = action_objective_mapping.get(objective, [])
        return action.action_type in supported_actions

    def _calculate_priority_alignment(self, action: SkillAction) -> float:
        """Calculate how well action aligns with current business priority."""
        priority_action_weights = {
            BusinessPriority.SURVIVAL: {
                "optimize_costs": 1.0,
                "cashflow_alert": 1.0,
                "budget_alert": 0.9,
                "assess_financial_health": 0.8,
                "place_order": 0.3,  # Lower priority during survival
                "run_marketing_campaign": 0.2,
            },
            BusinessPriority.GROWTH: {
                "run_marketing_campaign": 1.0,
                "set_price": 0.8,
                "place_order": 0.9,
                "respond_to_customer_message": 0.7,
                "optimize_costs": 0.4,
            },
        }

        # Default weights for other priorities
        default_weights = {
            action_type: 0.6
            for action_type in [
                "set_price",
                "place_order",
                "run_marketing_campaign",
                "respond_to_customer_message",
                "optimize_costs",
            ]
        }

        weights = priority_action_weights.get(
            self.controller.current_priority, default_weights
        )
        return weights.get(action.action_type, 0.5)

    def _calculate_outcome_alignment(self, action: SkillAction) -> float:
        """Calculate alignment based on expected outcomes."""
        if not action.expected_outcome:
            return 0.5

        # Weight outcomes based on current strategic focus
        outcome_weights = {
            "profit_improvement": (
                0.8
                if StrategicObjective.PROFITABILITY
                in self.controller.current_business_state.strategic_focus
                else 0.5
            ),
            "customer_satisfaction_improvement": (
                0.8
                if StrategicObjective.CUSTOMER_SATISFACTION
                in self.controller.current_business_state.strategic_focus
                else 0.5
            ),
            "cost_savings": (
                0.9
                if self.controller.current_priority == BusinessPriority.SURVIVAL
                else 0.6
            ),
            "revenue_growth": (
                0.9
                if self.controller.current_priority == BusinessPriority.GROWTH
                else 0.6
            ),
        }

        alignment = 0.0
        outcome_count = 0

        for outcome_key, outcome_value in action.expected_outcome.items():
            if outcome_key in outcome_weights and isinstance(
                outcome_value, (int, float)
            ):
                weight = outcome_weights[outcome_key]
                # Normalize outcome value and apply weight
                normalized_value = min(1.0, abs(outcome_value))
                alignment += weight * normalized_value
                outcome_count += 1

        return alignment / max(1, outcome_count)

    async def _apply_resource_constraints(
        self, actions: List[SkillAction]
    ) -> List[SkillAction]:
        """Apply resource constraints and budget limits."""
        approved_actions = []
        remaining_budgets = {
            domain: allocation
            for domain, allocation in self.controller.resource_plan.allocations.items()
        }

        # Sort actions by priority and strategic alignment
        sorted_actions = sorted(
            actions,
            key=lambda a: a.priority * self._calculate_priority_alignment(a),
            reverse=True,
        )

        for action in sorted_actions:
            # Determine domain for resource allocation
            domain = self._get_action_domain(action)

            # Check budget requirements
            budget_required = action.resource_requirements.get("budget", 0)
            if isinstance(budget_required, int):
                budget_required = Money(budget_required)

            # Check if we have sufficient budget
            if (
                domain in remaining_budgets
                and remaining_budgets[domain].cents >= budget_required.cents
            ):
                approved_actions.append(action)
                remaining_budgets[domain] = Money(
                    remaining_budgets[domain].cents - budget_required.cents
                )
            elif (
                budget_required.cents
                <= self.controller.resource_plan.allocations.get(
                    "strategic_reserve", Money(0)
                ).cents
            ):
                # Use strategic reserve for high-priority actions
                approved_actions.append(action)
                reserve = self.controller.resource_plan.allocations.get(
                    "strategic_reserve", Money(0)
                )
                self.controller.resource_plan.allocations["strategic_reserve"] = Money(
                    reserve.cents - budget_required.cents
                )
            else:
                logger.debug(
                    f"Action {action.action_type} rejected due to insufficient budget: required {budget_required}, available {remaining_budgets.get(domain, Money(0))}"
                )

        return approved_actions

    def _get_action_domain(self, action: SkillAction) -> str:
        """Get the business domain for an action."""
        skill_domain_mapping = {
            "SupplyManager": "inventory_management",
            "MarketingManager": "marketing",
            "CustomerService": "customer_service",
            "FinancialAnalyst": "financial_operations",
        }
        return skill_domain_mapping.get(action.skill_source, "other")

    async def _apply_business_rules(
        self, actions: List[SkillAction]
    ) -> List[SkillAction]:
        """Apply business rules and approval thresholds."""
        approved_actions = []

        for action in actions:
            # Check approval thresholds
            budget_required = action.resource_requirements.get("budget", 0)
            if isinstance(budget_required, int):
                budget_required = Money(budget_required)

            domain = self._get_action_domain(action)
            threshold = self.controller.resource_plan.approval_thresholds.get(
                domain, Money(0)
            )

            # Auto-approve if under threshold
            if budget_required.cents <= threshold.cents:
                approved_actions.append(action)
            else:
                # Add to pending approvals for manual review
                self.controller.pending_approvals.append((action, datetime.now()))
                logger.info(
                    f"Action {action.action_type} requires approval: budget ${budget_required.to_float():.2f} exceeds threshold ${threshold.to_float():.2f}"
                )

        return approved_actions

    def validate_strategic_alignment(
        self, action: SkillAction, strategic_plan: Dict[str, Any]
    ) -> Tuple[bool, float, str]:
        """
        Validate if action aligns with strategic plan.

        Args:
            action: Action to validate
            strategic_plan: Current strategic plan

        Returns:
            Tuple of (is_aligned, alignment_score, reasoning)
        """
        try:
            # Calculate strategic alignment score
            alignment_score = 0.0
            reasoning_parts = []

            # Check objective alignment
            action_objectives = self._get_action_objectives(action)
            plan_objectives = strategic_plan.get("objectives", [])

            objective_overlap = len(set(action_objectives) & set(plan_objectives))
            if objective_overlap > 0:
                alignment_score += 0.4
                reasoning_parts.append(
                    f"Supports {objective_overlap} strategic objectives"
                )

            # Check resource allocation alignment
            domain = self._get_action_domain(action)
            domain_priority = self.controller.resource_plan.priority_multipliers.get(
                domain, 1.0
            )

            if domain_priority >= 1.0:
                alignment_score += 0.3
                reasoning_parts.append(f"Domain {domain} is strategically prioritized")

            # Check business priority alignment
            priority_alignment = self._calculate_priority_alignment(action)
            alignment_score += priority_alignment * 0.3
            reasoning_parts.append(f"Priority alignment: {priority_alignment:.2f}")

            # Determine if aligned (threshold: 0.6)
            is_aligned = alignment_score >= 0.6

            reasoning = (
                "; ".join(reasoning_parts)
                if reasoning_parts
                else "No clear strategic alignment"
            )

            return is_aligned, alignment_score, reasoning

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Error validating strategic alignment: {e}")
            return False, 0.0, f"Validation error: {e}"

    def _get_action_objectives(self, action: SkillAction) -> List[str]:
        """Get strategic objectives that an action supports."""
        action_objective_mapping = {
            "set_price": ["profitability", "market_share"],
            "place_order": ["operational_efficiency", "profitability"],
            "run_marketing_campaign": ["market_share", "brand_reputation"],
            "respond_to_customer_message": [
                "customer_satisfaction",
                "brand_reputation",
            ],
            "optimize_costs": ["profitability", "financial_stability"],
            "assess_financial_health": ["financial_stability"],
            "budget_alert": ["financial_stability"],
            "cashflow_alert": ["financial_stability"],
        }

        return action_objective_mapping.get(action.action_type, [])

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
                    expected_impact[outcome] += value

        decision = StrategicDecision(
            decision_id=f"{decision_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            decision_type=decision_type,
            context=self.controller.current_business_state,
            actions_approved=approved_actions,
            actions_rejected=rejected_actions,
            reasoning=f"Arbitration based on {self.controller.current_priority.value} priority and strategic alignment",
            expected_impact=expected_impact,
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
            is_aligned, alignment_score, _ = self.validate_strategic_alignment(
                action,
                {
                    "objectives": [
                        obj.value
                        for obj in self.controller.current_business_state.strategic_focus
                    ]
                },
            )
            alignment_scores.append(alignment_score)

        if alignment_scores:
            avg_alignment = sum(alignment_scores) / len(alignment_scores)
            self.controller.strategic_alignment_score = (
                self.controller.strategic_alignment_score * 0.9
            ) + (avg_alignment * 0.1)
