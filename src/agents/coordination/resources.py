"""
Resource allocation logic for multi-domain controller.

Handles budget allocation, priority multipliers, and resource validation for agent skills.
"""

import logging
from typing import Any, Dict, List

from fba_bench_core.money import Money

from .models import BusinessPriority

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Manager for resource allocation and budgeting in multi-domain control.

    Handles budget distribution, priority adjustments, and resource request validation.
    """

    def __init__(self, controller):
        """
        Initialize the ResourceManager.

        Args:
            controller: The parent MultiDomainController instance for shared state access.
        """
        self.controller = controller

    def _initialize_resource_allocations(self):
        """Initialize default resource allocations across domains."""
        # Default allocation percentages based on business priority
        default_allocations = {
            "inventory_management": 0.35,  # 35% for inventory/supply chain
            "marketing": 0.25,  # 25% for marketing and growth
            "customer_service": 0.15,  # 15% for customer satisfaction
            "financial_operations": 0.10,  # 10% for financial management
            "strategic_reserve": 0.15,  # 15% reserve for opportunities
        }

        for domain, percentage in default_allocations.items():
            allocation = Money(
                int(self.controller.resource_plan.total_budget.cents * percentage)
            )
            self.controller.resource_plan.allocations[domain] = allocation

        # Set priority multipliers based on current business priority
        self._update_priority_multipliers()

        # Set approval thresholds
        self.controller.resource_plan.approval_thresholds = {
            "inventory_management": Money(50000),  # $500
            "marketing": Money(25000),  # $250
            "customer_service": Money(10000),  # $100
            "financial_operations": Money(100000),  # $1000
            "emergency": Money(20000),  # $200
        }

    def _update_priority_multipliers(self):
        """Update priority multipliers based on current business priority."""
        if self.controller.current_priority == BusinessPriority.SURVIVAL:
            # Focus on cash flow and cost reduction
            self.controller.resource_plan.priority_multipliers = {
                "inventory_management": 1.2,
                "marketing": 0.5,
                "customer_service": 0.8,
                "financial_operations": 1.5,
            }
        elif self.controller.current_priority == BusinessPriority.GROWTH:
            # Focus on marketing and expansion
            self.controller.resource_plan.priority_multipliers = {
                "inventory_management": 1.1,
                "marketing": 1.5,
                "customer_service": 1.2,
                "financial_operations": 0.9,
            }
        else:  # STABILIZATION, OPTIMIZATION, INNOVATION
            # Balanced approach
            self.controller.resource_plan.priority_multipliers = {
                "inventory_management": 1.0,
                "marketing": 1.0,
                "customer_service": 1.0,
                "financial_operations": 1.0,
            }

    async def allocate_resources(
        self, skill_requests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Allocate resources across skill requests based on strategic priorities.

        Args:
            skill_requests: List of resource requests from skills

        Returns:
            Resource allocation decisions
        """
        allocation_decisions = {
            "approved_allocations": {},
            "rejected_requests": [],
            "pending_requests": [],
            "total_allocated": Money(0),
            "remaining_budget": self.controller.resource_plan.total_budget,
        }

        # Sort requests by strategic priority
        prioritized_requests = await self._prioritize_resource_requests(skill_requests)

        total_allocated = Money(0)

        for request in prioritized_requests:
            skill_name = request.get("skill_name")
            requested_amount = Money(request.get("amount_cents", 0))
            purpose = request.get("purpose", "general")

            # Check if allocation is strategically justified
            if await self._validate_resource_request(request):
                # Check if we have sufficient budget
                if (
                    total_allocated.cents + requested_amount.cents
                    <= self.controller.resource_plan.total_budget.cents
                ):
                    allocation_decisions["approved_allocations"][skill_name] = {
                        "amount": requested_amount.cents,
                        "purpose": purpose,
                        "approval_reason": "strategic_alignment",
                    }
                    total_allocated = Money(
                        total_allocated.cents + requested_amount.cents
                    )
                else:
                    allocation_decisions["rejected_requests"].append(
                        {
                            "skill_name": skill_name,
                            "amount": requested_amount.cents,
                            "rejection_reason": "insufficient_budget",
                        }
                    )
            else:
                allocation_decisions["rejected_requests"].append(
                    {
                        "skill_name": skill_name,
                        "amount": requested_amount.cents,
                        "rejection_reason": "poor_strategic_alignment",
                    }
                )

        allocation_decisions["total_allocated"] = total_allocated
        allocation_decisions["remaining_budget"] = Money(
            self.controller.resource_plan.total_budget.cents - total_allocated.cents
        )

        return allocation_decisions

    async def _prioritize_resource_requests(
        self, requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize resource requests based on strategic value."""
        scored_requests = []

        for request in requests:
            priority_score = await self._calculate_request_priority(request)
            scored_requests.append((request, priority_score))

        # Sort by priority score (highest first)
        scored_requests.sort(key=lambda x: x[1], reverse=True)

        return [request for request, score in scored_requests]

    async def _calculate_request_priority(self, request: Dict[str, Any]) -> float:
        """Calculate priority score for resource request."""
        base_score = 0.5

        # Factor in skill type and current business priority
        skill_name = request.get("skill_name", "")
        domain = self._skill_to_domain(skill_name)
        priority_multiplier = self.controller.resource_plan.priority_multipliers.get(
            domain, 1.0
        )

        # Factor in expected ROI
        expected_roi = request.get("expected_roi", 1.0)
        roi_score = min(1.0, expected_roi / 2.0)  # Normalize to 0-1

        # Factor in urgency
        urgency = request.get("urgency", "medium")
        urgency_multiplier = {
            "low": 0.8,
            "medium": 1.0,
            "high": 1.3,
            "critical": 1.5,
        }.get(urgency, 1.0)

        final_score = base_score * priority_multiplier * roi_score * urgency_multiplier
        return min(1.0, final_score)

    def _skill_to_domain(self, skill_name: str) -> str:
        """Map skill name to business domain."""
        mapping = {
            "SupplyManager": "inventory_management",
            "MarketingManager": "marketing",
            "CustomerService": "customer_service",
            "FinancialAnalyst": "financial_operations",
        }
        return mapping.get(skill_name, "other")

    async def _validate_resource_request(self, request: Dict[str, Any]) -> bool:
        """Validate if resource request aligns with strategic objectives."""
        # Check strategic alignment
        purpose = request.get("purpose", "general")
        skill_name = request.get("skill_name", "")

        # Strategic purposes get higher validation scores
        strategic_purposes = [
            "growth_investment",
            "crisis_response",
            "customer_retention",
            "cost_optimization",
            "market_expansion",
        ]

        if purpose in strategic_purposes:
            return True

        # Check if skill is aligned with current strategic focus
        domain = self._skill_to_domain(skill_name)
        priority_multiplier = self.controller.resource_plan.priority_multipliers.get(
            domain, 1.0
        )

        return priority_multiplier >= 1.0

    async def _reallocate_resources_for_priority(self):
        """Reallocate resources based on changed business priority."""
        logger.info(
            f"Reallocating resources for priority: {self.controller.current_priority.value}"
        )

        # Calculate new allocation percentages based on priority
        if self.controller.current_priority == BusinessPriority.SURVIVAL:
            new_percentages = {
                "inventory_management": 0.30,  # Reduce inventory investment
                "marketing": 0.15,  # Cut marketing spend
                "customer_service": 0.20,  # Maintain customer service
                "financial_operations": 0.15,  # Increase financial focus
                "strategic_reserve": 0.20,  # Increase reserve for crisis
            }
        elif self.controller.current_priority == BusinessPriority.GROWTH:
            new_percentages = {
                "inventory_management": 0.40,  # Increase inventory for growth
                "marketing": 0.35,  # Boost marketing spend
                "customer_service": 0.15,  # Maintain service levels
                "financial_operations": 0.05,  # Minimal financial overhead
                "strategic_reserve": 0.05,  # Minimal reserve, invest in growth
            }
        else:  # Balanced allocation for other priorities
            new_percentages = {
                "inventory_management": 0.35,
                "marketing": 0.25,
                "customer_service": 0.15,
                "financial_operations": 0.10,
                "strategic_reserve": 0.15,
            }

        # Update allocations
        for domain, percentage in new_percentages.items():
            allocation = Money(
                int(self.controller.resource_plan.total_budget.cents * percentage)
            )
            self.controller.resource_plan.allocations[domain] = allocation

        logger.info(
            f"Resource reallocation completed for {self.controller.current_priority.value} priority"
        )
