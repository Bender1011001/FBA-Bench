"""
Event definitions related to supplier interactions in the FBA-Bench simulation.

This module defines `SupplierResponseEvent`, which captures responses from
simulated suppliers to agent queries or orders, and `PlaceOrderCommand`,
an agent-issued command to initiate a purchase from a supplier. These
events are critical for enabling agents to manage their supply chain
and ensure timely inventory replenishment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from fba_bench_core.money import Money  # External dependency for precise financial calculations

from .base import BaseEvent


@dataclass(kw_only=True)
class SupplierResponseEvent(BaseEvent):
    """
    Represents a response received from a simulated supplier.

    This event is published by a `SupplierService` or equivalent component
    in response to agent actions (e.g., `PlaceOrderCommand`, `RequestQuoteCommand`).
    It carries information regarding quotes, delivery updates, quality reports, etc.

    Attributes:
        event_id (str): Unique identifier for this supplier response event. Inherited from `BaseEvent`.
        timestamp (datetime): When the supplier response was received or processed. Inherited from `BaseEvent`.
        supplier_id (str): The unique identifier of the responding supplier.
        response_type (str): The category of the response, e.g., "quote", "delivery_update",
                             "quality_report", "order_confirmation", "out_of_stock".
        content (str): The free-form message content of the supplier's response (e.g., quote details, status message).
        order_id (Optional[str]): The ID of the related order, if this response pertains to a specific order.
        delivery_date (Optional[datetime]): The promised or estimated delivery date, if applicable.
        quoted_price (Optional[Money]): The quoted price for an item or order, if this is a quote response.
                                        Represented using the `Money` class.
        response_time_hours (float): The time taken for the supplier to respond in hours (simulated time).
    """

    supplier_id: str = ""
    response_type: str = ""
    content: str = ""
    order_id: Optional[str] = None
    delivery_date: Optional[datetime] = None
    quoted_price: Optional[Money] = None
    response_time_hours: float = 0.0

    def __post_init__(self):
        """
        Validates the attributes of the `SupplierResponseEvent` upon initialization.
        Ensures supplier ID, response type, and content are provided.
        """
        super().__post_init__()  # Call base class validation

        # Validate supplier_id: Must be a non-empty string.
        if not self.supplier_id:
            raise ValueError("Supplier ID cannot be empty for SupplierResponseEvent.")

        # Validate response_type: Must be a non-empty string.
        if not self.response_type:
            raise ValueError("Response type cannot be empty for SupplierResponseEvent.")

        # Validate content: Must be a non-empty string.
        if not self.content:
            raise ValueError(
                "Response content cannot be empty for SupplierResponseEvent."
            )

        # Validate quoted_price: If provided, must be a Money instance.
        if self.quoted_price is not None and not isinstance(self.quoted_price, Money):
            raise TypeError(
                f"Quoted price must be a Money type if provided, but got {type(self.quoted_price)}."
            )

        # Validate response_time_hours: Must be non-negative.
        if self.response_time_hours < 0:
            raise ValueError(
                f"Response time (hours) must be non-negative, but got {self.response_time_hours}."
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `SupplierResponseEvent` into a concise summary dictionary.

        Content is truncated for brevity, and `Money`/`datetime` objects
        are converted to string representations for logging and serialization.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "supplier_id": self.supplier_id,
            "response_type": self.response_type,
            "content": (
                self.content[:100] + "..." if len(self.content) > 100 else self.content
            ),  # Truncate long content
            "order_id": self.order_id,
            "delivery_date": (
                self.delivery_date.isoformat() if self.delivery_date else None
            ),
            "quoted_price": str(self.quoted_price) if self.quoted_price else None,
            "response_time_hours": round(self.response_time_hours, 2),
        }


@dataclass(kw_only=True)
class PlaceOrderCommand(BaseEvent):
    """
    Represents an agent's command to place an order with a supplier.

    This command is issued by agents (e.g., an `InventoryManagerSkill`) when
    they determine a need to replenish stock. It specifies the product, quantity,
    and a maximum acceptable price. This command can trigger `SupplierResponseEvent`s.

    Attributes:
        event_id (str): Unique identifier for this order command. Inherited from `BaseEvent`.
        timestamp (datetime): When the order command was issued by the agent. Inherited from `BaseEvent`.
        agent_id (str): The unique identifier of the agent issuing the command.
        supplier_id (str): The unique identifier of the supplier to place the order with.
        asin (str): The Amazon Standard Identification Number of the product to order.
        quantity (int): The number of units to order. Must be a positive integer.
        max_price (Money): The maximum price per unit the agent is willing to pay for this order.
                           Represented using the `Money` class.
        reason (Optional[str]): An optional, human-readable reason or justification for placing the order.
                                Useful for auditing and understanding agent behavior.
    """

    agent_id: str = ""
    supplier_id: str = ""
    asin: str = ""
    quantity: int = 0
    max_price: Money = field(default_factory=lambda: Money("0", "USD"))
    reason: Optional[str] = None

    def __post_init__(self):
        """
        Validates the attributes of the `PlaceOrderCommand` upon initialization.
        Ensures agent ID, supplier ID, ASIN, and quantity are provided, and max price is a valid `Money` object.
        """
        super().__post_init__()  # Call base class validation

        # Validate agent_id: Must be a non-empty string.
        if not self.agent_id:
            raise ValueError("Agent ID cannot be empty for PlaceOrderCommand.")

        # Validate supplier_id: Must be a non-empty string.
        if not self.supplier_id:
            raise ValueError("Supplier ID cannot be empty for PlaceOrderCommand.")

        # Validate ASIN: Must be a non-empty string.
        if not self.asin:
            raise ValueError("ASIN cannot be empty for PlaceOrderCommand.")

        # Validate quantity: Must be a positive integer.
        if self.quantity <= 0:
            raise ValueError(
                f"Order quantity must be positive, but got {self.quantity}."
            )

        # Validate max_price: Must be a Money object.
        if not isinstance(self.max_price, Money):
            raise TypeError(
                f"Max price must be a Money object, but got {type(self.max_price)}."
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `PlaceOrderCommand` into a concise summary dictionary.
        `Money` objects are converted to string representation.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "supplier_id": self.supplier_id,
            "asin": self.asin,
            "quantity": self.quantity,
            "max_price": str(self.max_price),
            "reason": self.reason,
        }


@dataclass(kw_only=True)
class PurchaseOccurred(BaseEvent):
    asin: str = ""
    quantity: int = 0
    unit_cost: float = 0.0
    timestamp: Optional[datetime] = field(default=None)

    def __post_init__(self):
        super().__post_init__()

        if not self.asin:
            raise ValueError("ASIN cannot be empty for PurchaseOccurred event.")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive for PurchaseOccurred event.")
        if self.unit_cost < 0:
            raise ValueError("Unit cost cannot be negative for PurchaseOccurred event.")


@dataclass(kw_only=True)
class SupplierDisputeEvent(BaseEvent):
    """
    Represents a dispute raised with a supplier.

    This event is published when there's a dispute with a supplier,
    such as quality issues, delivery problems, or billing discrepancies.

    Attributes:
        event_id (str): Unique identifier for this dispute event. Inherited from `BaseEvent`.
        timestamp (datetime): When the dispute was raised. Inherited from `BaseEvent`.
        dispute_id (str): Unique identifier for this dispute.
        supplier_id (str): The unique identifier of the supplier.
        purchase_order_id (str): The purchase order ID associated with the dispute.
        disputed_amount (Money): The amount being disputed.
        reason (str): The reason for the dispute.
        details (str): Additional details about the dispute.
    """

    dispute_id: str = ""
    supplier_id: str = ""
    purchase_order_id: str = ""
    reason: str = ""
    disputed_amount: Money = field(default_factory=lambda: Money("0", "USD"))
    details: str = ""

    def __post_init__(self):
        """
        Validates the attributes of the `SupplierDisputeEvent` upon initialization.
        Ensures required fields are provided and valid.
        """
        super().__post_init__()  # Call base class validation

        # Validate dispute_id: Must be a non-empty string.
        if not self.dispute_id:
            raise ValueError("Dispute ID cannot be empty for SupplierDisputeEvent.")

        # Validate supplier_id: Must be a non-empty string.
        if not self.supplier_id:
            raise ValueError("Supplier ID cannot be empty for SupplierDisputeEvent.")

        # Validate purchase_order_id: Must be a non-empty string.
        if not self.purchase_order_id:
            raise ValueError(
                "Purchase order ID cannot be empty for SupplierDisputeEvent."
            )

        # Validate disputed_amount: Must be a Money object.
        if not isinstance(self.disputed_amount, Money):
            raise TypeError(
                f"Disputed amount must be a Money object, but got {type(self.disputed_amount)}."
            )

        # Validate reason: Must be a non-empty string.
        if not self.reason:
            raise ValueError("Reason cannot be empty for SupplierDisputeEvent.")

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `SupplierDisputeEvent` into a concise summary dictionary.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "dispute_id": self.dispute_id,
            "supplier_id": self.supplier_id,
            "purchase_order_id": self.purchase_order_id,
            "disputed_amount": str(self.disputed_amount),
            "reason": self.reason,
            "details": (
                self.details[:100] + "..." if len(self.details) > 100 else self.details
            ),
        }


@dataclass(kw_only=True)
class SupplyChainDisruptionEvent(BaseEvent):
    """
    Represents a disruption in the supply chain that affects agent operations.

    This event is published when there's a disruption in the supply chain,
    such as delays, quality issues, or other problems that impact the
    agent's ability to receive inventory or fulfill orders.

    Attributes:
        event_id (str): Unique identifier for this disruption event. Inherited from `BaseEvent`.
        timestamp (datetime): When the disruption was detected or occurred. Inherited from `BaseEvent`.
        supplier_id (str): The unique identifier of the supplier experiencing the disruption.
        disruption_type (str): The type of disruption (e.g., "delay", "quality_issue", "shortage").
        details (str): Additional details about the disruption.
        expected_duration (Optional[int]): Expected duration of the disruption in simulation ticks.
        affected_products (Optional[List[str]]): List of product ASINs affected by the disruption.
    """

    supplier_id: str = ""
    disruption_type: str = ""
    details: str = ""
    expected_duration: Optional[int] = None
    affected_products: List[str] = field(default_factory=list)

    def __post_init__(self):
        """
        Validates the attributes of the `SupplyChainDisruptionEvent` upon initialization.
        Ensures supplier ID, disruption type, and details are provided.
        """
        super().__post_init__()  # Call base class validation

        # Validate supplier_id: Must be a non-empty string.
        if not self.supplier_id:
            raise ValueError(
                "Supplier ID cannot be empty for SupplyChainDisruptionEvent."
            )

        # Validate disruption_type: Must be a non-empty string.
        if not self.disruption_type:
            raise ValueError(
                "Disruption type cannot be empty for SupplyChainDisruptionEvent."
            )

        # Validate details: Must be a non-empty string.
        if not self.details:
            raise ValueError("Details cannot be empty for SupplyChainDisruptionEvent.")

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `SupplyChainDisruptionEvent` into a concise summary dictionary.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "supplier_id": self.supplier_id,
            "disruption_type": self.disruption_type,
            "details": (
                self.details[:100] + "..." if len(self.details) > 100 else self.details
            ),
            "expected_duration": self.expected_duration,
            "affected_products": self.affected_products,
        }
