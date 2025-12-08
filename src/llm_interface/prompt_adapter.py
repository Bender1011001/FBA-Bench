import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Union

# Assuming WorldStore is accessible
from services.world_store import WorldStore
# For budget details
from constraints.budget_enforcer import BudgetEnforcer
from fba_events import (
    BaseEvent,
    BudgetExceeded,
    BudgetWarning,
    ConstraintViolation,
)
from fba_events.competitor import CompetitorPricesUpdated
from fba_events.pricing import (
    ProductPriceUpdated,
    SetPriceCommand,
)
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent
from llm_interface.prompt_templates import PromptTemplates

logger = logging.getLogger(__name__)

class PromptAdapter:
    """
    Converts simulation state and events into a structured prompt format for LLM agents.
    Uses PromptTemplates to ensure consistent formatting across the application.
    """

    def __init__(self, world_store: WorldStore, budget_enforcer: BudgetEnforcer):
        self.world_store = world_store
        self.budget_enforcer = budget_enforcer

    def generate_prompt(
        self,
        current_tick: int,
        simulation_time: datetime,
        recent_events: List[BaseEvent],
        available_actions: Dict[str, Any],
        scenario_context: str = "",
        template_name: str = "regular_update"
    ) -> str:
        """
        Generates a comprehensive prompt string for the LLM using standard templates.

        Args:
            current_tick: The current simulation tick number.
            simulation_time: The current simulation timestamp.
            recent_events: A list of recent events that occurred in the simulation.
            available_actions: A dictionary of available actions and their schemas.
            scenario_context: Additional context about the current scenario.
            template_name: The name of the template to use (default: "regular_update").

        Returns:
            A formatted string representing the LLM prompt.
        """
        # 1. Format Events
        formatted_events = []
        if recent_events:
            for event in recent_events:
                formatted_events.append(f"- {self._format_event_for_prompt(event)}")
        else:
            formatted_events.append("- No significant events recently.")
        
        events_str = "\n".join(formatted_events)

        # 2. Format Actions
        actions_str_parts = []
        for action_type, action_info in available_actions.items():
            description = action_info.get('description', 'No description available')
            actions_str_parts.append(f"- {action_type}: {description}")
            
            params = action_info.get("parameters", {})
            if params:
                params_str = ", ".join([f"{k}: {v}" for k, v in params.items()])
                actions_str_parts.append(f"  Parameters: {{{params_str}}}")
        
        actions_str = "\n".join(actions_str_parts)

        # 3. Format Portfolio
        product_portfolio_json = self._get_product_portfolio_summary()
        portfolio_str = json.dumps(product_portfolio_json, indent=2)

        # 4. Prepare Output Format (Hardcoded for now, ideal to fetch from validator)
        example_output = {
            "actions": [{"type": "action_name", "parameters": {"key": "value"}}],
            "reasoning": "Your decision rationale",
            "confidence": 0.0
        }
        output_format_str = json.dumps(example_output, indent=2)

        # 5. Build Context
        context = {
            'current_tick': current_tick,
            'simulation_time': simulation_time,
            'budget_status': self.budget_enforcer.format_budget_status_for_prompt(),
            'product_portfolio': portfolio_str,
            'recent_events': events_str,
            'available_actions': actions_str,
            'required_output_format': output_format_str,
            'scenario_context': scenario_context
        }

        # 6. Render
        try:
            return PromptTemplates.get_template(template_name, context)
        except ValueError:
            logger.warning(f"Template '{template_name}' not found, falling back to 'regular_update'.")
            return PromptTemplates.get_template("regular_update", context)

    def _safe_money_to_float(self, value: Any) -> float:
        """
        Safely converts a value (potentially a Money object) to float.
        Fixes Issue #100: Relies on Money.to_float() method; may break if Money implementation changes.
        """
        if value is None:
            return 0.0
        
        # Try specific Money interface
        if hasattr(value, 'to_float') and callable(value.to_float):
            try:
                return float(value.to_float())
            except (ValueError, TypeError):
                pass
        
        # Try direct amount attribute (common pattern)
        if hasattr(value, 'amount'):
            try:
                return float(value.amount)
            except (ValueError, TypeError):
                pass

        # Try native float conversion
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert value {value!r} to float in PromptAdapter.")
            return 0.0

    def _get_product_portfolio_summary(self) -> Dict[str, Any]:
        """
        Creates a concise JSON summary of all products in the portfolio.
        """
        portfolio = {}
        all_products = self.world_store.get_all_product_states()
        for asin, product in all_products.items():
            portfolio[asin] = {
                "current_price": self._safe_money_to_float(product.price),
                "inventory": getattr(product, 'inventory_quantity', 0),
                "cost_basis": self._safe_money_to_float(getattr(product, 'cost_basis', 0.0)),
            }
        return portfolio

    def _format_event_for_prompt(self, event: BaseEvent) -> str:
        """
        Converts a BaseEvent into a human-readable summary string for the prompt.
        """
        event_type = type(event).__name__
        timestamp = event.timestamp.strftime("%H:%M:%S")

        if isinstance(event, SaleOccurred):
            price = self._safe_money_to_float(event.unit_price)
            return f"{event_type} at {timestamp}: ASIN {event.asin} sold {event.units_sold} units at {price:.2f}."
        
        elif isinstance(event, CompetitorPricesUpdated):
            comps = []
            for c in event.competitors:
                p = self._safe_money_to_float(c.price)
                comps.append(f"{c.asin} @ {p:.2f}")
            competitor_info = ", ".join(comps)
            return f"{event_type} at {timestamp}: Competitor prices updated ({competitor_info})."
        
        elif isinstance(event, SetPriceCommand):
            new_price = self._safe_money_to_float(event.new_price)
            return f"{event_type} at {timestamp}: Agent {event.agent_id} requested price change for {event.asin} to {new_price:.2f}."
        
        elif isinstance(event, ProductPriceUpdated):
            prev = self._safe_money_to_float(event.previous_price)
            new_p = self._safe_money_to_float(event.new_price)
            return f"{event_type} at {timestamp}: ASIN {event.asin} price changed from {prev:.2f} to {new_p:.2f}."
        
        elif isinstance(event, BudgetWarning):
            return f"BUDGET WARNING at {timestamp}: {event.reason} (Type: {event.budget_type}, Usage: {event.current_usage}/{event.limit})."
        
        elif isinstance(event, BudgetExceeded):
            return f"BUDGET EXCEEDED at {timestamp}: {event.reason} (Severity: {event.severity}, Usage: {event.current_usage}/{event.limit})."
        
        elif isinstance(event, ConstraintViolation):
            details = event.violation_details.get('message', 'N/A')
            return f"CONSTRAINT VIOLATION at {timestamp}: Type: {event.constraint_type}, Critical: {event.is_critical}. Details: {details}."
        
        elif isinstance(event, TickEvent):
            return f"{event_type} at {timestamp}: Tick {event.tick_number} completed."

        return f"{event_type} at {timestamp}: {getattr(event, 'event_id', 'Unknown ID')}"
