"""
Resource management for skill coordination.
"""

from fba_bench_core.money import Money

from .models import ResourceAllocation


class ResourceManager:
    """
    Manages resource allocation updates for the skill coordinator.
    """

    def __init__(self, resource_allocation: ResourceAllocation):
        """
        Initialize the ResourceManager.

        Args:
            resource_allocation: The ResourceAllocation instance to manage
        """
        self.resource_allocation = resource_allocation

    async def update_resource_allocation(
        self, budget_delta: int = 0, token_delta: int = 0
    ) -> bool:
        """
        Update resource allocation for the coordinator.

        Args:
            budget_delta: Change in budget allocation (cents)
            token_delta: Change in token allocation

        Returns:
            True if update successful, False if insufficient resources
        """
        budget_delta_money = Money(cents=budget_delta)
        new_budget: Money = (
            self.resource_allocation.remaining_budget + budget_delta_money
        )
        new_tokens = self.resource_allocation.remaining_tokens + token_delta

        if new_budget.cents < 0 or new_tokens < 0:
            return False

        self.resource_allocation.remaining_budget = new_budget
        self.resource_allocation.remaining_tokens = new_tokens

        if budget_delta < 0:
            self.resource_allocation.allocated_budget += budget_delta_money.abs()
        if token_delta < 0:
            self.resource_allocation.allocated_tokens += abs(token_delta)

        return True
