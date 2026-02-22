"""
Event definitions related to product pricing within the FBA-Bench simulation.

This module defines `SetPriceCommand`, an agent-issued command to change prices,
and `ProductPriceUpdated`, a canonical event signaling an official price change.
These events are central to the dynamic pricing strategies of agents and
the overall market simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fba_bench_core.money import Money  # External dependency for precise financial calculations

from .base import BaseEvent


@dataclass
class SetPriceCommand(BaseEvent):
    """
    Represents an agent's command to change a product's price.

    Agents publish this command to signal their intent to modify pricing.
    The `WorldStore` is responsible for arbitrating any potential conflicts
    (e.g., multiple agents attempting to set a price simultaneously) and
    then applying the valid price changes to the canonical product state.

    Attributes:
        event_id (str): Unique identifier for this price setting command. Inherited from `BaseEvent`.
        timestamp (datetime): The real-world UTC datetime when the command was issued by the agent.
                              Inherited from `BaseEvent`.
        agent_id (str): Unique identifier of the agent who issued this command.
        asin (str): The Amazon Standard Identification Number of the product whose price is to be updated.
        new_price (Money): The requested new price for the product. Represented using the `Money` class.
        reason (Optional[str]): An optional, human-readable reason or justification for the price change.
                                 Useful for auditing and understanding agent behavior.
    """

    agent_id: str
    asin: str
    new_price: Money
    reason: Optional[str] = None

    def __post_init__(self):
        """
        Validates the attributes of the `SetPriceCommand` upon initialization.
        Ensures agent ID and ASIN are provided, and the new price is a positive `Money` object.
        """
        super().__post_init__()  # Call base class validation

        # Validate agent_id: Must be a non-empty string.
        if not self.agent_id or not isinstance(self.agent_id, str):
            raise ValueError("Agent ID must be a non-empty string for SetPriceCommand.")

        # Validate ASIN: Must be a non-empty string.
        if not self.asin or not isinstance(self.asin, str):
            raise ValueError("ASIN must be a non-empty string for SetPriceCommand.")

        # Validate/normalize new_price: accept Money-like or numeric cents
        np = self.new_price
        if isinstance(np, (int, float)):
            # Interpret numeric as cents
            object.__setattr__(self, "new_price", Money(int(round(np))))
        else:
            cents = getattr(np, "cents", None)
            if not isinstance(cents, int):
                raise TypeError(
                    f"New price must be Money-like (has .cents) or int cents, but got {type(np)}."
                )
        # Validate new_price value: Must be positive.
        if getattr(self.new_price, "cents", 0) <= 0:
            raise ValueError(f"New price must be positive, but got {self.new_price}.")

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `SetPriceCommand` into a concise summary dictionary.
        `Money` objects are converted to their string representation.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "asin": self.asin,
            "new_price": str(self.new_price),
            "reason": self.reason,
        }


@dataclass
class ProductPriceUpdated(BaseEvent):
    """
    Signals that a product's canonical price has been officially updated.
    Published by `WorldStore` after processing `SetPriceCommand` or other price-modifying events.

    This event serves as the single source of truth for product price changes
    across the simulation. All other services and agents should listen to this
    event to get the most current product prices.

    Attributes:
        event_id (str): Unique identifier for this price update event. Inherited from `BaseEvent`.
        timestamp (datetime): When the price was officially updated in the canonical state.
                              Inherited from `BaseEvent`.
        asin (str): The product ASIN whose price was updated.
        new_price (Money): The new canonical price of the product after any arbitration.
                           Represented using the `Money` class.
        previous_price (Money): The product's price immediately before this update.
                                Represented using the `Money` class.
        agent_id (Optional[str]): The ID of the agent (if any) that triggered this price change.
                                  Useful for attributing strategic decisions.
        command_id (Optional[str]): The event ID of the `SetPriceCommand` (or similar) that led to this update.
                                    Provides a link back to the originating command.
        arbitration_notes (Optional[str]): Optional notes detailing any arbitration that occurred
                                           if multiple agents attempted conflicting price changes.
    """

    asin: str
    new_price: Money
    previous_price: Money
    agent_id: Optional[str] = None
    command_id: Optional[str] = None
    arbitration_notes: Optional[str] = None

    def __post_init__(self):
        """
        Validates the attributes of the `ProductPriceUpdated` event upon initialization.
        Ensures ASIN is provided and both `new_price` and `previous_price` are positive `Money` objects.
        Also checks for consistency between the two prices.
        """
        super().__post_init__()  # Call base class validation

        # Validate ASIN: Must be a non-empty string.
        if not self.asin or not isinstance(self.asin, str):
            raise ValueError(
                "ASIN must be a non-empty string for ProductPriceUpdated event."
            )

        # Validate/normalize Money-like values for new and previous prices.
        for field_name in ("new_price", "previous_price"):
            val = getattr(self, field_name)
            if isinstance(val, (int, float)):
                # Interpret numeric as cents
                object.__setattr__(self, field_name, Money(int(round(val))))
            else:
                cents = getattr(val, "cents", None)
                if not isinstance(cents, int):
                    raise TypeError(
                        f"{field_name.replace('_', ' ').capitalize()} must be Money-like (has .cents) or int cents, but got {type(val)}."
                    )
        # Validate prices are positive.
        if getattr(self.new_price, "cents", 0) <= 0:
            raise ValueError(f"New price must be positive, but got {self.new_price}.")
        if getattr(self.previous_price, "cents", 0) <= 0:
            raise ValueError(
                f"Previous price must be positive, but got {self.previous_price}."
            )

    def get_price_change_percentage(self) -> float:
        """
        Calculates the percentage change between the new price and the previous price.

        Returns:
            float: The price change as a percentage (0.0 if previous price was zero).
        """
        if self.previous_price.cents == 0:
            return 0.0
        return (
            (self.new_price.cents - self.previous_price.cents)
            / self.previous_price.cents
        ) * 100

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `ProductPriceUpdated` event into a concise summary dictionary.
        `Money` objects are converted to string representation, and the calculated
        price change percentage is rounded for readability.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "asin": self.asin,
            "new_price": str(self.new_price),
            "previous_price": str(self.previous_price),
            "price_change_pct": round(self.get_price_change_percentage(), 2),
            "agent_id": self.agent_id,
            "command_id": self.command_id,
            "arbitration_notes": self.arbitration_notes,
        }
