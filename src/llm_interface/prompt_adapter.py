import json
from datetime import datetime
from typing import Any, Dict, List

from services.world_store import WorldStore  # Assuming WorldStore is accessible

from constraints.budget_enforcer import BudgetEnforcer  # For budget details
from fba_events import (
    BaseEvent,
    BudgetExceeded,
    BudgetWarning,
    ConstraintViolation,
)
from fba_events.competitor import CompetitorPricesUpdated
from fba_events.pricing import (
    ProductPriceUpdated,
    SetPriceCommand,  # Moved import to correct location
)
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent


class PromptAdapter:
    """
    Converts simulation state and events into a structured prompt format for LLM agents.
    """

    # Example output structure compliant with expected schemas.
    # Centralized here to avoid hardcoding within method bodies.
    SCHEMA_EXAMPLE = {
        "actions": [{"type": "action_name", "parameters": {"key": "value"}}],
        "reasoning": "Your decision rationale",
        "confidence": 0.0,  # confidence must be a float between 0.0 and 1.0
    }

    def __init__(self, world_store: WorldStore, budget_enforcer: BudgetEnforcer):
        self.world_store = world_store
        self.budget_enforcer = budget_enforcer

    def generate_prompt(
        self,
        current_tick: int,
        simulation_time: datetime,
        recent_events: List[BaseEvent],
        available_actions: Dict[
            str, Any
        ],  # e.g., {"set_price": {"description": "Adjust product pricing", "parameters": {"asin": "str", "price": "float"}}}
        scenario_context: str = "",
    ) -> str:
        """
        Generates a comprehensive prompt string for the LLM.

        Args:
            current_tick: The current simulation tick number.
            simulation_time: The current simulation timestamp.
            recent_events: A list of recent events that occurred in the simulation.
            available_actions: A dictionary of available actions and their schemas/descriptions.
            scenario_context: Additional context about the current scenario from the curriculum system.

        Returns:
            A formatted string representing the LLM prompt.
        """
        prompt_parts = []

        # 1. Simulation State Header
        prompt_parts.append("=== FBA SIMULATION STATE ===")
        prompt_parts.append(
            f"Tick: {current_tick} | Day: {simulation_time.day} | Time: {simulation_time.strftime('%H:%M UTC')}"
        )
        prompt_parts.append("")

        # 2. Budget Status (from BudgetEnforcer)
        budget_status = self.budget_enforcer.format_budget_status_for_prompt()
        prompt_parts.append(budget_status)
        prompt_parts.append("")

        # 3. Product Portfolio (from WorldStore, converted to concise JSON)
        prompt_parts.append("PRODUCT PORTFOLIO:")
        product_portfolio_json = self._get_product_portfolio_summary()
        prompt_parts.append(json.dumps(product_portfolio_json, indent=2))
        prompt_parts.append("")

        # 4. Recent Events Summary
        prompt_parts.append("RECENT EVENTS:")
        if recent_events:
            for event in recent_events:
                prompt_parts.append(f"- {self._format_event_for_prompt(event)}")
        else:
            prompt_parts.append("- No significant events recently.")
        prompt_parts.append("")

        # 5. Scenario Context
        if scenario_context:
            prompt_parts.append("SCENARIO CONTEXT:")
            prompt_parts.append(scenario_context)
            prompt_parts.append("")

        # 6. Available Actions
        prompt_parts.append("AVAILABLE ACTIONS:")
        for action_type, action_info in available_actions.items():
            params_str = ", ".join(
                [f"{k}: {v}" for k, v in action_info.get("parameters", {}).items()]
            )
            prompt_parts.append(
                f"- {action_type}: {action_info.get('description', 'No description available')}"
            )
            if params_str:
                prompt_parts.append(f"  Parameters: {{{params_str}}}")
        prompt_parts.append("")

        # 7. Required Output Format (from schema_validator)
        prompt_parts.append("REQUIRED OUTPUT FORMAT:")
        # Use the class constant for the example format
        prompt_parts.append(json.dumps(self.SCHEMA_EXAMPLE, indent=2))
        prompt_parts.append("")
        prompt_parts.append("---")
        prompt_parts.append(
            "Your response MUST be a single JSON object conforming strictly to the 'REQUIRED OUTPUT FORMAT'. Do NOT include any other text or formatting outside the JSON."
        )

        return "\n".join(prompt_parts)

    def _get_product_portfolio_summary(self) -> Dict[str, Any]:
        """
        Creates a concise JSON summary of all products in the portfolio.
        Converts Money objects to float for LLM consumption.
        """
        portfolio = {}
        all_products = self.world_store.get_all_product_states()
        for asin, product in all_products.items():
            portfolio[asin] = {
                "current_price": product.price.to_float(),  # Convert Money to float
                "inventory": product.inventory_quantity,
                "cost_basis": product.cost_basis.to_float(),  # Convert Money to float
                # Add sales velocity, competitor prices etc. if WorldStore tracks or if derived from recent events
                # For now, keeping it minimal based on ProductState
            }
        return portfolio

    def _format_event_for_prompt(self, event: BaseEvent) -> str:
        """
        Converts a BaseEvent into a human-readable summary string for the prompt.
        This can be extended to provide more detailed, specific summaries per event type.
        """
        event_type = type(event).__name__
        timestamp = event.timestamp.strftime("%H:%M:%S")

        # Custom formatting for specific event types
        if isinstance(event, SaleOccurred):
            return f"{event_type} at {timestamp}: ASIN {event.asin} sold {event.units_sold} units at {event.unit_price.to_float():.2f}."
        elif isinstance(event, CompetitorPricesUpdated):
            competitor_info = ", ".join(
                [f"{c.asin} @ {c.price.to_float():.2f}" for c in event.competitors]
            )
            return f"{event_type} at {timestamp}: Competitor prices updated ({competitor_info})."
        elif isinstance(event, SetPriceCommand):
            return f"{event_type} at {timestamp}: Agent {event.agent_id} requested price change for {event.asin} to {event.new_price.to_float():.2f}."
        elif isinstance(event, ProductPriceUpdated):
            return f"{event_type} at {timestamp}: ASIN {event.asin} price changed from {event.previous_price.to_float():.2f} to {event.new_price.to_float():.2f}."
        elif isinstance(event, BudgetWarning):
            return f"BUDGET WARNING at {timestamp}: {event.reason} (Type: {event.budget_type}, Usage: {event.current_usage}/{event.limit})."
        elif isinstance(event, BudgetExceeded):
            return f"BUDGET EXCEEDED at {timestamp}: {event.reason} (Severity: {event.severity}, Usage: {event.current_usage}/{event.limit}). SIMULATION MAY TERMINATE."
        elif isinstance(event, ConstraintViolation):
            return f"CONSTRAINT VIOLATION at {timestamp}: Type: {event.constraint_type}, Critical: {event.is_critical}. Details: {event.violation_details.get('message', 'N/A')}."
        elif isinstance(event, TickEvent):
            return f"{event_type} at {timestamp}: Tick {event.tick_number} completed."

        # Default fallback for unhandled event types
        return f"{event_type} at {timestamp}: {event.event_id}"
