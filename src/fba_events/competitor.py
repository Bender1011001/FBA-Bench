"""
Event and data definitions related to competitor dynamics in the FBA-Bench simulation.

This module defines `CompetitorState` for capturing competitor metrics and
`CompetitorPricesUpdated` event to signal changes in the competitive landscape.
These are crucial for agents to perform market analysis and adjust their
strategies based on competitor actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from money import Money  # External dependency for precise financial calculations

from .base import BaseEvent


@dataclass
class CompetitorState:
    """
    A compact snapshot of a competitor's key performance metrics at a given time.

    This dataclass is primarily used within `CompetitorPricesUpdated` events
    to provide all essential data for downstream services (e.g., SalesService)
    to perform market analysis and demand calculations without requiring
    additional queries or state lookups. It represents the current known state
    of a single competitor's product offering.

    Attributes:
        asin (str): Amazon Standard Identification Number (ASIN) for the competitor's product.
                    This uniquely identifies the product in the simulated marketplace.
        price (Money): The current selling price of the competitor's product.
                       Represented using the `Money` class for accurate financial calculations.
        bsr (int): Best Seller Rank (BSR) at the time of the snapshot. A lower BSR indicates
                   higher sales performance (e.g., BSR of 1 is the best).
        sales_velocity (float): The estimated current sales velocity of the competitor's
                                product, typically in units per day or per hour.
    """

    asin: str
    price: Money
    bsr: int
    sales_velocity: float
    inventory: int = 5000
    is_out_of_stock: bool = False

    # Back-compat alias expected by tests
    @property
    def competitor_id(self) -> str:
        return self.asin

    def __post_init__(self):
        """
        Validates the integrity of the competitor state data upon initialization.
        Ensures data types and logical constraints (e.g., positive values) are met.
        """
        # Validate ASIN: Must be a non-empty string.
        if not self.asin or not isinstance(self.asin, str):
            raise ValueError("Competitor ASIN must be a non-empty string.")

        # Validate price: Must be an instance of the Money class.
        if not isinstance(self.price, Money):
            raise TypeError(
                f"Competitor price must be a Money type, but got {type(self.price)}."
            )

        # Validate BSR: Best Seller Rank must be a positive integer (>= 1).
        if self.bsr < 1:
            raise ValueError(f"Competitor BSR must be >= 1, but got {self.bsr}.")

        # Validate sales_velocity: Must be non-negative.
        if self.sales_velocity < 0:
            raise ValueError(
                f"Competitor sales velocity must be >= 0, but got {self.sales_velocity}."
            )


@dataclass
class CompetitorPricesUpdated(BaseEvent):
    """
    Signals that the market's competitive landscape has been updated.

    This event is published by the `CompetitorManager` (or similar service)
    after each `TickEvent` when competitors in the simulated marketplace
    update their pricing and other relevant metrics. It provides a complete
    snapshot of the current competitive state, which is vital for agents
    to recalculate demand, adjust pricing, and refine their market strategies.

    Attributes:
        event_id (str): Unique identifier for this competitor update event. Inherited from `BaseEvent`.
        timestamp (datetime): When the competitor updates were processed and this event was generated.
                              Inherited from `BaseEvent`.
        tick_number (int): The associated simulation tick number that triggered this update.
                           Links this market snapshot to a specific point in simulation time.
        competitors (List[CompetitorState]): A list of `CompetitorState` objects, each
                                             representing the current state of a distinct competitor's product.
                                             Ensures no duplicate ASINs.
        market_summary (Dict[str, Any]): Optional aggregated market metrics for quick analysis,
                                         e.g., average competitor price, total market sales volume.
    """

    tick_number: int
    competitors: List[CompetitorState] = field(default_factory=list)
    market_summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Validates the attributes of the `CompetitorPricesUpdated` event.
        Ensures tick number is valid and the `competitors` list contains
        valid `CompetitorState` objects with no duplicate ASINs.
        """
        super().__post_init__()  # Call base class validation

        # Validate tick_number: Must be non-negative.
        if self.tick_number < 0:
            raise ValueError(
                "Tick number must be >= 0 for CompetitorPricesUpdated event."
            )

        # Validate competitors list: Ensure all elements are `CompetitorState` instances.
        for i, competitor in enumerate(self.competitors):
            if not isinstance(competitor, CompetitorState):
                raise TypeError(
                    f"Element at index {i} in 'competitors' must be a CompetitorState instance, but got {type(competitor)}."
                )

        # Validate for duplicate ASINs within the competitors list to maintain data integrity.
        asins = [comp.asin for comp in self.competitors]
        if len(asins) != len(set(asins)):
            raise ValueError(
                "Duplicate competitor ASINs found in the 'competitors' list."
            )

    def get_competitor_by_asin(self, asin: str) -> Optional[CompetitorState]:
        """
        Retrieves a `CompetitorState` object from the `competitors` list by its ASIN.

        Args:
            asin (str): The Amazon Standard Identification Number of the competitor to find.

        Returns:
            Optional[CompetitorState]: The `CompetitorState` object if found, otherwise `None`.
        """
        for competitor in self.competitors:
            if competitor.asin == asin:
                return competitor
        return None

    def get_average_competitor_price(self) -> Optional[Money]:
        """
        Calculates the average price across all competitors in the current snapshot.

        Returns:
            Optional[Money]: The average competitor price as a `Money` object,
                             or `None` if there are no competitors.
        """
        if not self.competitors:
            return None
        total_cents = sum(comp.price.cents for comp in self.competitors)
        # Integer division to return Money in cents, then convert back to Money object
        return Money(total_cents // len(self.competitors))

    def get_price_range(self) -> Optional[Tuple[Money, Money]]:
        """
        Determines the minimum and maximum prices among all competitors.

        Returns:
            Optional[Tuple[Money, Money]]: A tuple containing the minimum and maximum
                                          `Money` prices, or `None` if no competitors exist.
        """
        if not self.competitors:
            return None
        prices = [comp.price for comp in self.competitors]
        return min(prices), max(prices)

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `CompetitorPricesUpdated` event into a concise summary dictionary.

        This dictionary format is suitable for logging, debugging, and external
        data consumption. `Money` objects are converted to string representation,
        and relevant metrics are rounded for readability.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "tick_number": self.tick_number,
            "competitor_count": len(self.competitors),
            "competitors": [
                {
                    "asin": comp.asin,
                    "price": str(comp.price),
                    "bsr": comp.bsr,
                    "sales_velocity": comp.sales_velocity,
                }
                for comp in self.competitors
            ],
            # Use conditional expressions to handle None for average_price and price_range
            "average_price": (
                str(self.get_average_competitor_price())
                if self.get_average_competitor_price()
                else None
            ),
            "price_range": (
                [str(p) for p in self.get_price_range()]
                if self.get_price_range()
                else None
            ),
            "market_summary": self.market_summary,
        }
