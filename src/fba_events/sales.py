"""
Event definitions related to sales transactions within the FBA-Bench simulation.

This module defines the `SaleOccurred` event, which is the primary mechanism
for signaling completed sales. This event carries comprehensive details about
each transaction, including financial metrics, product information, and market
conditions at the time of sale. It is crucial for downstream services for
financial auditing, performance tracking, and behavioral analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fba_bench_core.money import Money  # External dependency for precise financial calculations

from .base import BaseEvent


@dataclass
class SaleOccurred(BaseEvent):
    """
    Signals the completion of a sales transaction within the simulation.
    Published by a `SalesService` or equivalent component.

    This event carries comprehensive transaction details, including financial data,
    product information, and relevant market conditions that were present at the
    time of sale. It's crucial for financial auditing, agent performance tracking,
    and overall simulation metrics.

    Attributes:
        event_id (str): Unique identifier for this specific sale event. Inherited from `BaseEvent`.
        timestamp (datetime): The real-world UTC datetime when the sale was successfully processed.
                              Inherited from `BaseEvent`.
        asin (str): The Amazon Standard Identification Number of the product sold.
        units_sold (int): The number of units of the product sold in this transaction.
        units_demanded (int): The total number of units demanded,
                               used to calculate the effective conversion rate.
        unit_price (Money): The price per unit at which the sale occurred.
        total_revenue (Money): Gross revenue from this sale (`units_sold * unit_price`).
        total_fees (Money): Total fees deducted from the revenue.
                            (e.g., marketplace fees, referral fees, fulfillment fees).
        total_profit (Money): Net profit after fees and cost of goods sold
                              (`revenue - fees - costs_basis`).
        cost_basis (Money): The total cost associated with the `units_sold`
                            (e.g., cost of goods, inbound shipping).
        trust_score_at_sale (float): The product's trust score or reputation metric
                                     at the time of the sale (0.0 to 1.0).
        bsr_at_sale (int): The Best Seller Rank of the product at the time of the sale.
                           (lower is better, e.g., BSR of 1).
        conversion_rate (float): The conversion rate for this transaction
                                 (`units_sold / units_demanded`). Auto-calculated if 0.0 and `units_demanded` > 0.
        fee_breakdown (Dict[str, Money]): A detailed breakdown of all fees applied, by type.
                                          Keys are fee names (e.g., 'referral_fee'), values are `Money` amounts.
        market_conditions (Dict[str, Any]): A snapshot of the market state at the time of sale,
                                            containing relevant data like average competitor prices, demand elasticity.
        customer_segment (Optional[str]): The segment of the customer who made the purchase (if known),
                                          e.g., 'premium', 'loyal', 'new'.
    """

    asin: str
    units_sold: int
    units_demanded: int
    unit_price: Money
    total_revenue: Money
    total_fees: Money
    total_profit: Money
    cost_basis: Money
    trust_score_at_sale: float
    bsr_at_sale: int
    conversion_rate: float
    fee_breakdown: Dict[str, Money] = field(default_factory=dict)
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    customer_segment: Optional[str] = None

    def __post_init__(self):
        """
        Validates all attributes of the `SaleOccurred` event upon initialization.
        Performs checks for non-empty strings, non-negative numbers,
        correct `Money` types, and financial consistency.
        """
        super().__post_init__()  # Call base class validation

        # ASIN validation: Must be a non-empty string.
        if not self.asin or not isinstance(self.asin, str):
            raise ValueError("ASIN must be a non-empty string for SaleOccurred event.")

        # Unit quantity validations: Must be non-negative, and units_sold cannot exceed units_demanded.
        if self.units_sold < 0:
            raise ValueError("Units sold must be >= 0.")
        if self.units_demanded < 0:
            raise ValueError("Units demanded must be >= 0.")
        if self.units_sold > self.units_demanded:
            raise ValueError("Units sold cannot exceed units demanded.")

        # Validate all core financial fields are Money-like.
        # Accept:
        # - our Money type
        # - duck-typed objects exposing `.cents: int` (e.g., external money.Money)
        # - numeric values (interpreted as cents) which will be coerced to Money
        money_fields = [
            "unit_price",
            "total_revenue",
            "total_fees",
            "total_profit",
            "cost_basis",
        ]
        for field_name in money_fields:
            value = getattr(self, field_name)
            if isinstance(value, Money):
                continue
            cents = getattr(value, "cents", None)
            if isinstance(cents, int):
                # Accept duck-typed Money with cents attribute
                continue
            if isinstance(value, (int, float)):
                # Coerce numeric (assumed cents) to Money
                object.__setattr__(self, field_name, Money(int(round(value))))
                continue
            raise TypeError(
                f"'{field_name}' must be Money-like (has .cents) or int cents, but got {type(value)}."
            )

        # Normalize/validate fee_breakdown values to Money-like
        if self.fee_breakdown:
            normalized: Dict[str, Money] = {}
            for fee_type, amount in self.fee_breakdown.items():
                if isinstance(amount, Money):
                    normalized[fee_type] = amount
                    continue
                cents = getattr(amount, "cents", None)
                if isinstance(cents, int):
                    # Accept as-is (duck-typed Money)
                    normalized[fee_type] = amount  # type: ignore[assignment]
                    continue
                if isinstance(amount, (int, float)):
                    normalized[fee_type] = Money(int(round(amount)))
                    continue
                raise TypeError(
                    f"Fee breakdown '{fee_type}' must be Money-like or int cents, but got {type(amount)}."
                )
            object.__setattr__(self, "fee_breakdown", normalized)

        # Validate `trust_score_at_sale`: Must be within the valid range [0.0, 1.0].
        if not 0.0 <= self.trust_score_at_sale <= 1.0:
            raise ValueError("Trust score must be between 0.0 and 1.0.")

        # Validate `bsr_at_sale`: Must be a positive integer (>= 1).
        if self.bsr_at_sale < 1:
            raise ValueError("BSR must be >= 1.")

        # Validate `conversion_rate`: Must be within the valid range [0.0, 1.0].
        if not 0.0 <= self.conversion_rate <= 1.0:
            raise ValueError("Conversion rate must be between 0.0 and 1.0.")

        # Perform financial consistency check for `total_revenue`.
        # This checks if `total_revenue` aligns with `unit_price * units_sold`.
        if self.units_sold > 0:
            expected_revenue = self.unit_price * self.units_sold
            # Allow for minor discrepancies due to potential external rounding issues, up to 1 cent.
            if abs(self.total_revenue.cents - expected_revenue.cents) > 1:
                raise ValueError(
                    f"Revenue mismatch: expected {expected_revenue}, but got {self.total_revenue}."
                )

        # Auto-calculate `conversion_rate` if not provided (0.0) and demand was present.
        if self.conversion_rate == 0.0 and self.units_demanded > 0:
            # Use object.__setattr__ for dataclasses if setting default values post-init.
            object.__setattr__(
                self, "conversion_rate", self.units_sold / self.units_demanded
            )

    def get_profit_margin_percentage(self) -> float:
        """
        Calculates the profit margin as a percentage of total revenue for this specific sale.

        The formula used is (total_profit / total_revenue) * 100.

        Returns:
            float: The profit margin percentage (0.0 if total revenue is zero to avoid division by zero).
        """
        if self.total_revenue.cents == 0:
            return 0.0
        return (self.total_profit.cents / self.total_revenue.cents) * 100

    def get_fee_percentage(self) -> float:
        """
        Calculates the total fees incurred as a percentage of total revenue for this sale.

        The formula used is (total_fees / total_revenue) * 100.

        Returns:
            float: The fee percentage (0.0 if total revenue is zero to avoid division by zero).
        """
        if self.total_revenue.cents == 0:
            return 0.0
        return (self.total_fees.cents / self.total_revenue.cents) * 100

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `SaleOccurred` event instance into a concise summary dictionary.

        Financial `Money` objects are converted to their string representation,
        and derived percentages (profit margin, fee percentage) are rounded
        for readability in logs and reports. This method ensures that the
        output is JSON-serializable.

        Returns:
            Dict[str, Any]: A dictionary containing key attributes of the sale event for summary purposes.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "asin": self.asin,
            "units_sold": self.units_sold,
            "units_demanded": self.units_demanded,
            "conversion_rate": round(self.conversion_rate, 3),
            "unit_price": str(self.unit_price),
            "total_revenue": str(self.total_revenue),
            "total_fees": str(self.total_fees),
            "total_profit": str(self.total_profit),
            "profit_margin_pct": round(self.get_profit_margin_percentage(), 2),
            "fee_percentage": round(self.get_fee_percentage(), 2),
            "trust_score_at_sale": round(self.trust_score_at_sale, 3),
            "bsr_at_sale": self.bsr_at_sale,
            "customer_segment": self.customer_segment,
        }
