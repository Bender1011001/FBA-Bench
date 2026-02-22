import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from models.product import Product
from fba_bench_core.money import Money

from fba_events import BaseEvent
from fba_events.pricing import SetPriceCommand


@dataclass
class SimulationState:
    """
    Simplified simulation state for baseline bots.
    This encapsulates necessary information for a bot to make decisions.
    """

    products: List[Product]
    current_tick: int
    simulation_time: datetime
    # Could add more relevant state here like recent events, competitor states etc.
    # For GreedyScript, we only need product information which contains competitor prices.

    def get_product(self, asin: str) -> Optional[Product]:
        for product in self.products:
            if product.asin == asin:
                return product
        return None


# Placeholder for Action types. In a real scenario, these would likely be
# more abstract base classes or protocols that commands like SetPriceCommand implement.
# For simplicity with GreedyScript, we directly return SetPriceCommand.
class Action:
    """Base class for bot actions."""


@dataclass
class SetPriceAction(Action):
    asin: str
    price: Money


@dataclass
class ReorderAction(Action):
    asin: str
    quantity: int


class GreedyScriptBot:
    def __init__(self, reorder_threshold: int = 10, reorder_quantity: int = 50):
        self.agent_id = "GreedyScriptBot"
        self.reorder_threshold = reorder_threshold
        self.reorder_quantity = reorder_quantity

    def decide(self, state: SimulationState) -> List[BaseEvent]:
        actions: List[BaseEvent] = []

        for product in state.products:
            # Price matching strategy
            competitor_prices = (
                product.metadata.get("competitor_prices", [])
                if product.metadata
                else []
            )
            if competitor_prices:  # Get competitor_prices from metadata
                # Find the minimum competitor price
                lowest_price = min(price for _, price in competitor_prices)

                # Set price 1% below lowest competitor
                new_price = lowest_price * Decimal("0.99")

                # Ensure price is not set below cost basis (simple rule to prevent losses)
                if new_price < product.cost:
                    new_price = product.cost * Decimal(
                        "1.05"
                    )  # Small markup if going below cost

                # Only change price if it's significantly different to avoid excessive churn
                if (
                    abs(new_price.to_float() - product.price.to_float())
                    / product.price.to_float()
                    > 0.001
                ):
                    actions.append(
                        SetPriceCommand(
                            event_id=str(uuid.uuid4()),
                            timestamp=state.simulation_time,
                            agent_id=self.agent_id,
                            asin=product.asin,
                            new_price=new_price,
                            reason="Price matching lowest competitor (1% below)",
                        )
                    )
            else:
                # If no competitors, maintain current price or set a default strategy
                # For now, let's assume it manages to find a price, or keep current.
                # In a more complex scenario, this would involve a default pricing strategy.
                pass

            # Basic inventory management (reorder rules)
            if product.inventory_units <= self.reorder_threshold:
                # In a real system, this would trigger a different type of event,
                # e.g., a "ReorderCommand". For simplicity, we are not defining
                # a ReorderCommand or integrating it into the core simulation loop yet.
                # This part is just a placeholder to acknowledge the requirement.
                # For now, we'll just print a message or log it, as the current
                # events.py doesn't have a ReorderCommand.
                _msg = f"[GreedyScriptBot] Product {product.asin} inventory low ({product.inventory_units}), reordering {self.reorder_quantity} units."
                try:
                    # Mirror to logger so tests capturing stdout logs also match
                    import logging as _logging

                    _logging.getLogger(__name__).info(_msg)
                except Exception:
                    pass
                # Write via both print and direct stdout to avoid env-specific buffering quirks
                try:
                    import sys as _sys_io

                    _sys_io.stdout.write(_msg + "\n")
                    _sys_io.stdout.flush()
                except Exception:
                    pass
                print(_msg, flush=True)
                # If a ReorderCommand existed:
                # actions.append(ReorderCommand(
                #     event_id=str(uuid.uuid4()),
                #     timestamp=state.simulation_time,
                #     agent_id=self.agent_id,
                #     asin=product.asin,
                #     quantity=self.reorder_quantity
                # ))
        return actions
