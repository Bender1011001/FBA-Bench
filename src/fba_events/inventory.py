"""
Event definitions related to inventory management and world state snapshots in the FBA-Bench simulation.

This module defines `InventoryUpdate` to track changes in product quantities,
`LowInventoryEvent` to signal when stock levels are critical, and
`WorldStateSnapshotEvent` for periodic comprehensive captures of the simulation's
overall state. These events are essential for operational oversight,
replenishment decisions, and historical analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fba_bench_core.money import Money

from .base import BaseEvent


@dataclass
class InventoryUpdate(BaseEvent):
    """
    Signals a change in a product's canonical inventory quantity.

    This event is published by the `WorldStore` whenever the official
    inventory count for a product is updated. This typically occurs as a
    result of sales, customer returns, or the arrival of inbound shipments.
    It provides a real-time view of stock adjustments within the simulation.

    Attributes:
        event_id (str): Unique identifier for this inventory update event. Inherited from `BaseEvent`.
        timestamp (datetime): The UTC datetime when the inventory was officially updated. Inherited from `BaseEvent`.
        asin (str): The Amazon Standard Identification Number of the product whose inventory was updated.
        new_quantity (int): The canonical new inventory quantity after this update.
        previous_quantity (int): The canonical inventory quantity immediately before this update.
        change_reason (str): The reason for the inventory change,
                             e.g., "sale", "return", "inbound_shipment", "adjustment".
        agent_id (Optional[str]): The ID of the agent (if any) that triggered this inventory change.
                                  Useful for attributing actions like placing orders.
        command_id (Optional[str]): The event ID of the command (e.g., `PlaceOrderCommand`) that
                                    caused this inventory update, providing traceability.
    """

    asin: str
    new_quantity: int
    previous_quantity: int
    change_reason: str
    agent_id: Optional[str] = None
    command_id: Optional[str] = None
    # Optional unit cost basis at time of inventory update (e.g., purchase cost per unit)
    cost_basis: Optional[Money] = None

    def __post_init__(self):
        """
        Validates the attributes of the `InventoryUpdate` event upon initialization.
        Ensures ASIN and change reason are provided, and quantities are non-negative.
        """
        super().__post_init__()  # Call base class validation

        # Validate ASIN: Must be a non-empty string.
        if not self.asin or not isinstance(self.asin, str):
            raise ValueError("ASIN must be a non-empty string for InventoryUpdate.")

        # Validate quantities: Both new and previous quantities must be non-negative.
        if self.new_quantity < 0 or self.previous_quantity < 0:
            raise ValueError(
                f"New quantity ({self.new_quantity}) and previous quantity ({self.previous_quantity}) must be non-negative for InventoryUpdate."
            )

        # Validate change_reason: Must be a non-empty string.
        if not self.change_reason or not isinstance(self.change_reason, str):
            raise ValueError(
                "Change reason must be a non-empty string for InventoryUpdate."
            )

    def get_quantity_change(self) -> int:
        """
        Calculates the net change in inventory quantity as a result of this update.

        Returns:
            int: The difference between `new_quantity` and `previous_quantity`.
                 A positive value indicates an increase, a negative value a decrease.
        """
        return self.new_quantity - self.previous_quantity

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `InventoryUpdate` event into a concise summary dictionary.
        This is useful for logging, debugging, and high-level monitoring of stock movements.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "asin": self.asin,
            "new_quantity": self.new_quantity,
            "previous_quantity": self.previous_quantity,
            "quantity_change": self.get_quantity_change(),
            "change_reason": self.change_reason,
            "agent_id": self.agent_id,
            "command_id": self.command_id,
            "cost_basis": (
                str(self.cost_basis) if isinstance(self.cost_basis, Money) else None
            ),
        }


@dataclass
class LowInventoryEvent(BaseEvent):
    """
    Signals that a product's inventory level has fallen below a critical reorder point.

    This event is intended to trigger inventory management skills in agents,
    prompting them to consider placing new orders to replenish stock and
    avoid potential stockouts.

    Attributes:
        event_id (str): Unique identifier for this low inventory event. Inherited from `BaseEvent`.
        timestamp (datetime): When the low inventory condition was detected. Inherited from `BaseEvent`.
        asin (str): The product ASIN with low inventory.
        current_level (int): The current actual inventory level of the product.
        reorder_point (int): The predefined threshold at which a reorder is typically recommended.
        days_remaining (float): Estimated number of days remaining until current stock is depleted,
                                based on recent sales velocity.
        urgency_level (str): Categorical urgency of the situation,
                             e.g., "low", "medium", "high", "critical".
        recommended_order_quantity (int): A suggested quantity to order to bring inventory
                                          back to optimal levels. Defaults to 0.
    """

    asin: str
    current_level: int
    reorder_point: int
    days_remaining: float
    urgency_level: str
    recommended_order_quantity: int = 0

    def __post_init__(self):
        """
        Validates the attributes of the `LowInventoryEvent` upon initialization.
        Ensures ASIN is provided, levels are non-negative, and urgency level is valid.
        """
        super().__post_init__()  # Call base class validation

        # Validate ASIN: Must be a non-empty string.
        if not self.asin:
            raise ValueError("ASIN cannot be empty for LowInventoryEvent.")

        # Validate current_level and reorder_point: Must be non-negative.
        if self.current_level < 0 or self.reorder_point < 0:
            raise ValueError(
                f"Inventory levels (current_level: {self.current_level}, reorder_point: {self.reorder_point}) must be non-negative for LowInventoryEvent."
            )

        # Validate urgency_level: Must be one of the predefined categories.
        if self.urgency_level not in ["low", "medium", "high", "critical"]:
            raise ValueError(
                f"Urgency level must be 'low', 'medium', 'high', or 'critical', but got '{self.urgency_level}' for LowInventoryEvent."
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `LowInventoryEvent` into a concise summary dictionary.
        This is useful for quick assessments of inventory health and response prioritization.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "asin": self.asin,
            "current_level": self.current_level,
            "reorder_point": self.reorder_point,
            "days_remaining": round(self.days_remaining, 1),
            "urgency_level": self.urgency_level,
            "recommended_order_quantity": self.recommended_order_quantity,
        }


@dataclass
class WorldStateSnapshotEvent(BaseEvent):
    """
    Represents a comprehensive snapshot of the simulation's entire world state.

    This event is published periodically by the `WorldStore` or a dedicated
    snapshot service. It provides a consistent, global view of the simulation
    at a specific point in time, useful for debugging, analysis,
    and potentially for saving/restoring simulation states.

    Attributes:
        event_id (str): Unique identifier for this world state snapshot event. Inherited from `BaseEvent`.
        timestamp (datetime): When this snapshot was taken. Inherited from `BaseEvent`.
        snapshot_id (str): A unique identifier for this specific snapshot instance.
        tick_number (int): The simulation tick number at which this snapshot was captured.
        product_count (int): The total number of distinct products currently managed in the simulation.
        summary_metrics (Dict[str, Any]): A dictionary containing aggregated high-level metrics
                                         of the world state, e.g., 'total_revenue_overall',
                                         'average_inventory_level', 'active_agent_count'.
    """

    snapshot_id: str
    tick_number: int
    product_count: int
    summary_metrics: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Validates the attributes of the `WorldStateSnapshotEvent` upon initialization.
        Ensures snapshot ID is provided, and counts/metrics are valid.
        """
        super().__post_init__()  # Call base class validation

        # Validate snapshot_id: Must be a non-empty string.
        if not self.snapshot_id:
            raise ValueError("Snapshot ID cannot be empty for WorldStateSnapshotEvent.")

        # Validate tick_number: Must be non-negative.
        if self.tick_number < 0:
            raise ValueError(
                f"Tick number must be non-negative, but got {self.tick_number} for WorldStateSnapshotEvent."
            )

        # Validate product_count: Must be non-negative.
        if self.product_count < 0:
            raise ValueError(
                f"Product count must be non-negative, but got {self.product_count} for WorldStateSnapshotEvent."
            )

        # Validate summary_metrics: Must be a dictionary.
        if not isinstance(self.summary_metrics, dict):
            raise TypeError(
                f"Summary metrics must be a dictionary, but got {type(self.summary_metrics)} for WorldStateSnapshotEvent."
            )

    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the `WorldStateSnapshotEvent` into a concise summary dictionary.
        Returns a copy of `summary_metrics` to prevent external modification.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "snapshot_id": self.snapshot_id,
            "tick_number": self.tick_number,
            "product_count": self.product_count,
            "summary_metrics": self.summary_metrics.copy(),  # Return a copy to prevent external modification
        }
