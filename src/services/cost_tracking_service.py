from decimal import Decimal

from fba_bench_core.event_bus import EventBus
from llm_interface.pricing import get_model_pricing


class CostTrackingService:
    """
    A singleton service to track token usage and cost for all LLM calls in a simulation.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = Decimal("0.0")

        # Optional granular tracking
        self._by_agent: dict[str, dict[str, Decimal | int]] = {}
        self._by_cycle: dict[str, dict[str, Decimal | int]] = {}

    def record_usage(
        self,
        model: str,
        usage: dict,
        agent_id: str | None = None,
        cycle_id: str | None = None,
    ):
        """
        Records the token usage from an API call and updates the totals.
        Optionally attribute usage to an agent and/or decision cycle.
        """
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)

        pricing = get_model_pricing(model)

        # Calculate cost in USD per token
        input_cost_per_token = Decimal(pricing["input"]) / Decimal("1000000")
        output_cost_per_token = Decimal(pricing["output"]) / Decimal("1000000")

        call_cost = (Decimal(prompt_tokens) * input_cost_per_token) + (
            Decimal(completion_tokens) * output_cost_per_token
        )

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost += call_cost

        # Attribute to agent if provided
        if agent_id:
            agg = self._by_agent.setdefault(
                agent_id,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost": Decimal("0.0"),
                },
            )
            agg["prompt_tokens"] = int(agg["prompt_tokens"]) + prompt_tokens
            agg["completion_tokens"] = int(agg["completion_tokens"]) + completion_tokens
            agg["cost"] = Decimal(agg["cost"]) + call_cost

        # Attribute to cycle if provided
        if cycle_id:
            agg = self._by_cycle.setdefault(
                cycle_id,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost": Decimal("0.0"),
                },
            )
            agg["prompt_tokens"] = int(agg["prompt_tokens"]) + prompt_tokens
            agg["completion_tokens"] = int(agg["completion_tokens"]) + completion_tokens
            agg["cost"] = Decimal(agg["cost"]) + call_cost

        # Emit an event with the latest usage data (async in real runtime)
        # await self.event_bus.publish(LLMUsageReportedEvent(...))

    def get_totals(self) -> dict:
        """Returns the current totals."""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost": self.total_cost,
        }

    def get_breakdown(self) -> dict:
        """Optional detailed cost breakdowns if tracked."""
        return {
            "by_agent": self._by_agent.copy(),
            "by_cycle": self._by_cycle.copy(),
        }

    def reset(self):
        """Resets the tracker for a new simulation run."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = Decimal("0.0")
        self._by_agent.clear()
        self._by_cycle.clear()
