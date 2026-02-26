# DEPRECATED: BotFactory has been consolidated into benchmarking.agents.unified_agent.AgentFactory
# This module remains importable for legacy patches, but methods raise to guide callers.

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BotFactory:  # legacy shim
    def __init__(
        self,
        config_dir: str = "baseline_bots/configs",
        world_store: Optional[Any] = None,
        budget_enforcer: Optional[Any] = None,
        trust_metrics: Optional[Any] = None,
        agent_gateway: Optional[Any] = None,
        openrouter_api_key: Optional[str] = None,
    ):
        logger.warning(
            "baseline_bots.bot_factory.BotFactory is deprecated. "
            "Use benchmarking.agents.unified_agent.AgentFactory via AgentManager."
        )

    @staticmethod
    def create_bot(bot_name: str, tier: str = "T1") -> Any:
        raise ImportError(
            "BotFactory.create_bot is deprecated. "
            "Use AgentManager with unified AgentFactory to create DIY/baseline agents."
        )


# Example usage (for testing/demonstration)
# if __name__ == "__main__":
#     # These would typically be provided by the main simulation orchestrator
#     from services.world_store import get_world_store, set_world_store
#     from constraints.budget_enforcer import BudgetEnforcer
#     from metrics.trust_metrics import TrustMetrics
#     from event_bus import EventBus
#     import asyncio

#     # Initialize core simulation components (mock or real)
#     mock_event_bus = EventBus() # Requires an event loop
#     set_world_store(WorldStore(event_bus=mock_event_bus))
#     world_store_instance = get_world_store()
#     budget_enforcer_instance = BudgetEnforcer.from_tier_config("T0", event_bus=mock_event_bus)
#     trust_metrics_instance = TrustMetrics(trust_score_service=None) # Mock TrustScoreService for now
#     agent_gateway_instance = AgentGateway(budget_enforcer_instance, mock_event_bus)

#     try:
#         # Ensure configs directory exists for testing factory
#         os.makedirs("baseline_bots/configs", exist_ok=True)
#         # Create dummy config files for testing factory directly
#         with open("baseline_bots/configs/dummy_greedy_config.yaml", "w") as f:
#             f.write("bot_name: GreedyScript\n")
#             f.write("expected_score: 10\n")
#             f.write("tier_configs:\n  T0:\n    reorder_threshold: 10\n")

#         with open("baseline_bots/configs/dummy_gpt_config.yaml", "w") as f:
#             f.write("bot_name: GPT-3.5\n")
#             f.write("model: openai/gpt-3.5-turbo\n")
#             f.write("expected_score: 35\n")
#             f.write("tier_configs:\n  T0:\n    max_tokens_per_action: 8000\n    temperature: 0.1\n")

#         factory = BotFactory(
#             world_store=world_store_instance,
#             budget_enforcer=budget_enforcer_instance,
#             trust_metrics=trust_metrics_instance,
#             agent_gateway=agent_gateway_instance,
#             openrouter_api_key="sk-test-key" #dummy
#         )

#         greedy_bot = factory.create_bot("GreedyScript", "T0")
#         print(f"Created: {greedy_bot.agent_id}")

#         # Mock a simulation state for decide method
#         from money import Money
#         from datetime import datetime
#         # Creating a dummy Product for simulation state
#         dummy_product = Product(
#             asin="B00000000A",
#             category="electronics",
#             cost=Money.from_dollars(50.00),
#             price=Money.from_dollars(100.00),
#             base_demand=10.0,
#             competitor_prices=[("C1", Money.from_dollars(95.00)), ("C2", Money.from_dollars(98.00))], # Example competitor prices
#             inventory_units=15,
#             trust_score=0.9
#         )
#         # Update product class to accept competitor prices in __init__ for this mock
#         # Original models/product.py does not have competitor_prices. Adding it temporarily if needed.
#         # For now, just bypass for GreedyScript example.

#         # For GreedyScript, we need a SimulationState that contains products with competitor_prices
#         # As product.py doesn't have competitor_prices, assuming mock data structure or a more complete SimulationState class
#         # will be used by the orchestrator. For this example, let's inject a simplified structure.
#         class MockGreedyProduct:
#             def __init__(self, asin, price, cost, inventory_units, competitor_prices):
#                 self.asin = asin
#                 self.price = price
#                 self.cost = cost
#                 self.inventory_units = inventory_units
#                 self.competitor_prices = competitor_prices # Tuple of (asin, Money)

#         mock_greedy_products = [
#             MockGreedyProduct(
#                 asin="B07XAMPLE",
#                 price=Money.from_dollars(25.00),
#                 cost=Money.from_dollars(15.00),
#                 inventory_units=20,
#                 competitor_prices=[("COMP1", Money.from_dollars(24.00)), ("COMP2", Money.from_dollars(26.00))]
#             )
#         ]
#         mock_greedy_state = GreedySimulationState(
#             products=mock_greedy_products,
#             current_tick=1,
#             simulation_time=datetime.now()
#         )
#         greedy_actions = greedy_bot.decide(mock_greedy_state)
#         print(f"GreedyScriptBot actions: {greedy_actions}")


#         if os.getenv("RUN_LLM_TEST", "false").lower() == "true": # Only run if env var is set
#             # Dummy setup for LLM bot
#             llm_product = Product(
#                 asin="B00000000B",
#                 category="books",
#                 cost=Money.from_dollars(5.00),
#                 price=Money.from_dollars(10.00),
#                 base_demand=5.0,
#                 inventory_units=50,
#                 trust_score=0.8
#             )
#             llm_products = [llm_product]
#             llm_state = LLMSimulationState(
#                 products=llm_products,
#                 current_tick=1,
#                 simulation_time=datetime.now(),
#                 recent_events=[] # Empty for example
#             )

#             # Create an LLM bot
#             gpt_bot = factory.create_bot("GPT-3.5", "T0")
#             print(f"Created: {gpt_bot.agent_id}")

#             print("Attempting LLM bot decision (this will call OpenRouter API)...")
#             # Run async decide method
#             async def run_decide():
#                 llm_actions = await gpt_bot.decide(llm_state)
#                 print(f"GPT-3.5 Bot actions: {llm_actions}")

#             asyncio.run(run_decide())

#     except ValueError as e:
#         print(f"Error: {e}")
#     except FileNotFoundError as e:
#         print(f"Configuration Error: {e}. Please ensure config files are in 'baseline_bots/configs'.")
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}", exc_info=True)
#     finally:
#         # Clean up dummy config files
#         if os.path.exists("baseline_bots/configs/dummy_greedy_config.yaml"):
#             os.remove("baseline_bots/configs/dummy_greedy_config.yaml")
#         if os.path.exists("baseline_bots/configs/dummy_gpt_config.yaml"):
#             os.remove("baseline_bots/configs/dummy_gpt_config.yaml")
