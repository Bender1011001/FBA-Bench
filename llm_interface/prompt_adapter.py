"""Prompt adapter for building LLM prompts from simulation state."""
from typing import Any


class PromptAdapter:
    """Adapts simulation state into prompts for LLM agents."""

    def build_prompt(self, state: Any) -> str:
        """
        Build a prompt from simulation state.

        Args:
            state: SimulationState with products, current_tick, simulation_time, recent_events

        Returns:
            Formatted prompt string for the LLM
        """
        # Simple default prompt for demo/test purposes
        try:
            tick = getattr(state, "current_tick", 0)
            time = getattr(state, "simulation_time", "unknown")
            products = getattr(state, "products", [])
            events = getattr(state, "recent_events", [])

            prompt = f"""You are an FBA (Fulfillment by Amazon) agent making pricing decisions.

Current State:
- Tick: {tick}
- Time: {time}
- Products: {len(products)} available
- Recent Events: {len(events)}

Your task is to analyze the market and decide on pricing actions.
Respond with JSON containing "actions" array with pricing decisions.

Example response:
{{
  "actions": [
    {{"type": "set_price", "product_asin": "PRODUCT123", "price": 29.99, "reason": "Competitive pricing"}}
  ]
}}
"""
            return prompt
        except Exception:
            # Fallback for minimal state
            return "Analyze the current market state and provide pricing actions in JSON format."
