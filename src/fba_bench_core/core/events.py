"""Atomic Event Definitions for the FBA Simulation Engine.

This module defines the core event types used throughout the simulation.
All events are immutable Pydantic models with strict typing to ensure
deterministic simulation replay.

Key principles:
- Every event has a unique ID, tick number, and timestamp
- Events are immutable (frozen=True) for deterministic replay
- Events can be serialized to JSON for journal storage
- Concrete event types define specific payload structures

Usage:
    from fba_bench_core.core.events import GameEvent, MarketTickEvent, OrderPlacedEvent
    
    event = OrderPlacedEvent(
        tick=42,
        agent_id="agent-001",
        payload={"sku_id": "ABC123", "quantity": 10, "price": 19.99}
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class EventCategory(str, Enum):
    """Categories of events for routing and filtering."""

    MARKET = "market"
    ORDER = "order"
    INVENTORY = "inventory"
    LOGISTICS = "logistics"
    FINANCE = "finance"
    CUSTOMER = "customer"
    COMPETITOR = "competitor"
    SYSTEM = "system"


class GameEvent(BaseModel):
    """Base class for all simulation events.

    This is the atomic unit of the event-sourcing system. Every state change
    in the simulation is represented as a GameEvent that can be:
    - Written to the journal
    - Replayed to reconstruct state
    - Serialized for debugging/audit

    Attributes:
        event_id: Unique identifier for this event instance.
        tick: Simulation tick when this event occurred (0-indexed).
        timestamp: Wall-clock time when event was created.
        agent_id: Optional ID of the agent that caused this event.
        event_type: Discriminator string for event type.
        category: Category for routing and filtering.
        payload: Event-specific data.
        metadata: Optional additional context.
    """

    model_config = ConfigDict(
        frozen=True,  # Immutable for deterministic replay
        extra="forbid",  # Strict schema
        validate_assignment=True,
    )

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    tick: int = Field(..., ge=0, description="Simulation tick (0-indexed)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Wall-clock time of event creation",
    )
    agent_id: Optional[str] = Field(
        default=None, description="ID of agent that caused event"
    )
    event_type: str = Field(..., description="Event type discriminator")
    category: EventCategory = Field(
        default=EventCategory.SYSTEM, description="Event category"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )

    def to_journal_dict(self) -> Dict[str, Any]:
        """Serialize event for journal storage.

        Returns a dictionary suitable for JSON serialization and database storage.
        """
        return {
            "event_id": str(self.event_id),
            "tick": self.tick,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "category": self.category.value,
            "payload": self.payload,
            "metadata": self.metadata,
        }

    @classmethod
    def from_journal_dict(cls, data: Dict[str, Any]) -> "GameEvent":
        """Reconstruct event from journal storage.

        This is used during replay to recreate events from the journal.
        """
        return cls(
            event_id=UUID(data["event_id"]),
            tick=data["tick"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            agent_id=data.get("agent_id"),
            event_type=data["event_type"],
            category=EventCategory(data["category"]),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# MARKET EVENTS
# =============================================================================


class MarketTickEvent(GameEvent):
    """Emitted at the start of each market simulation tick.

    This event signals that all market-related services should process
    their updates for this tick.
    """

    event_type: Literal["MARKET_TICK"] = "MARKET_TICK"
    category: EventCategory = EventCategory.MARKET

    # Payload fields for market tick
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contains seasonal_factor, weekday_factor, etc.",
    )


class PriceChangeEvent(GameEvent):
    """Emitted when a product price is changed."""

    event_type: Literal["PRICE_CHANGE"] = "PRICE_CHANGE"
    category: EventCategory = EventCategory.MARKET


class SaleCompletedEvent(GameEvent):
    """Emitted when a sale is completed."""

    event_type: Literal["SALE_COMPLETED"] = "SALE_COMPLETED"
    category: EventCategory = EventCategory.MARKET


# =============================================================================
# ORDER EVENTS
# =============================================================================


class OrderPlacedEvent(GameEvent):
    """Emitted when an order is placed with a supplier.

    Payload should contain:
        - sku_id: str
        - quantity: int
        - price: float
        - supplier_id: str
    """

    event_type: Literal["ORDER_PLACED"] = "ORDER_PLACED"
    category: EventCategory = EventCategory.ORDER


class OrderReceivedEvent(GameEvent):
    """Emitted when an order is received from supplier."""

    event_type: Literal["ORDER_RECEIVED"] = "ORDER_RECEIVED"
    category: EventCategory = EventCategory.ORDER


class OrderCancelledEvent(GameEvent):
    """Emitted when an order is cancelled."""

    event_type: Literal["ORDER_CANCELLED"] = "ORDER_CANCELLED"
    category: EventCategory = EventCategory.ORDER


# =============================================================================
# INVENTORY EVENTS
# =============================================================================


class InventoryAdjustmentEvent(GameEvent):
    """Emitted when inventory levels change.

    Payload should contain:
        - sku_id: str
        - adjustment: int (positive for addition, negative for reduction)
        - reason: str (sale, damage, receipt, adjustment)
        - previous_quantity: int
        - new_quantity: int
    """

    event_type: Literal["INVENTORY_ADJUSTMENT"] = "INVENTORY_ADJUSTMENT"
    category: EventCategory = EventCategory.INVENTORY


class LowStockAlertEvent(GameEvent):
    """Emitted when inventory falls below reorder point."""

    event_type: Literal["LOW_STOCK_ALERT"] = "LOW_STOCK_ALERT"
    category: EventCategory = EventCategory.INVENTORY


class StockoutEvent(GameEvent):
    """Emitted when inventory reaches zero."""

    event_type: Literal["STOCKOUT"] = "STOCKOUT"
    category: EventCategory = EventCategory.INVENTORY


# =============================================================================
# LOGISTICS EVENTS
# =============================================================================


class ShipmentDispatchedEvent(GameEvent):
    """Emitted when a shipment is dispatched from supplier."""

    event_type: Literal["SHIPMENT_DISPATCHED"] = "SHIPMENT_DISPATCHED"
    category: EventCategory = EventCategory.LOGISTICS


class ShipmentArrivedEvent(GameEvent):
    """Emitted when a shipment arrives at warehouse."""

    event_type: Literal["SHIPMENT_ARRIVED"] = "SHIPMENT_ARRIVED"
    category: EventCategory = EventCategory.LOGISTICS


class ShipmentDelayedEvent(GameEvent):
    """Emitted when a shipment is delayed (black swan event)."""

    event_type: Literal["SHIPMENT_DELAYED"] = "SHIPMENT_DELAYED"
    category: EventCategory = EventCategory.LOGISTICS


# =============================================================================
# FINANCE EVENTS
# =============================================================================


class TransactionPostedEvent(GameEvent):
    """Emitted when a ledger transaction is posted.

    Payload should contain:
        - transaction_id: str
        - transaction_type: str
        - debits: List[Dict]
        - credits: List[Dict]
        - total_amount: float
    """

    event_type: Literal["TRANSACTION_POSTED"] = "TRANSACTION_POSTED"
    category: EventCategory = EventCategory.FINANCE


class FeeChargedEvent(GameEvent):
    """Emitted when a fee is charged (storage, fulfillment, referral)."""

    event_type: Literal["FEE_CHARGED"] = "FEE_CHARGED"
    category: EventCategory = EventCategory.FINANCE


class IntegrityCheckEvent(GameEvent):
    """Emitted when ledger integrity verification completes.

    Payload should contain:
        - passed: bool
        - total_assets: float
        - total_liabilities: float
        - total_equity: float
    """

    event_type: Literal["INTEGRITY_CHECK"] = "INTEGRITY_CHECK"
    category: EventCategory = EventCategory.FINANCE


# =============================================================================
# CUSTOMER EVENTS
# =============================================================================


class CustomerVisitEvent(GameEvent):
    """Emitted when a customer views a product listing."""

    event_type: Literal["CUSTOMER_VISIT"] = "CUSTOMER_VISIT"
    category: EventCategory = EventCategory.CUSTOMER


class CustomerPurchaseEvent(GameEvent):
    """Emitted when a customer makes a purchase decision."""

    event_type: Literal["CUSTOMER_PURCHASE"] = "CUSTOMER_PURCHASE"
    category: EventCategory = EventCategory.CUSTOMER


class ReviewPostedEvent(GameEvent):
    """Emitted when a customer posts a review."""

    event_type: Literal["REVIEW_POSTED"] = "REVIEW_POSTED"
    category: EventCategory = EventCategory.CUSTOMER


# =============================================================================
# COMPETITOR EVENTS
# =============================================================================


class CompetitorPriceChangeEvent(GameEvent):
    """Emitted when a competitor changes their price."""

    event_type: Literal["COMPETITOR_PRICE_CHANGE"] = "COMPETITOR_PRICE_CHANGE"
    category: EventCategory = EventCategory.COMPETITOR


class CompetitorLaunchEvent(GameEvent):
    """Emitted when a competitor launches a new product (copycat)."""

    event_type: Literal["COMPETITOR_LAUNCH"] = "COMPETITOR_LAUNCH"
    category: EventCategory = EventCategory.COMPETITOR


class AdAuctionResultEvent(GameEvent):
    """Emitted when an ad auction completes.

    Payload should contain:
        - keyword: str
        - winner_id: str
        - winning_bid: float
        - price_paid: float (second-price auction)
    """

    event_type: Literal["AD_AUCTION_RESULT"] = "AD_AUCTION_RESULT"
    category: EventCategory = EventCategory.COMPETITOR


# =============================================================================
# SYSTEM EVENTS
# =============================================================================


class SimulationStartEvent(GameEvent):
    """Emitted when simulation begins."""

    event_type: Literal["SIMULATION_START"] = "SIMULATION_START"
    category: EventCategory = EventCategory.SYSTEM


class SimulationEndEvent(GameEvent):
    """Emitted when simulation ends."""

    event_type: Literal["SIMULATION_END"] = "SIMULATION_END"
    category: EventCategory = EventCategory.SYSTEM


class DayEndEvent(GameEvent):
    """Emitted at the end of each simulation day.

    Triggers end-of-day processing like fee calculations and integrity checks.
    """

    event_type: Literal["DAY_END"] = "DAY_END"
    category: EventCategory = EventCategory.SYSTEM


# =============================================================================
# TYPE ALIAS FOR ALL EVENTS
# =============================================================================

AnyGameEvent = Union[
    GameEvent,
    MarketTickEvent,
    PriceChangeEvent,
    SaleCompletedEvent,
    OrderPlacedEvent,
    OrderReceivedEvent,
    OrderCancelledEvent,
    InventoryAdjustmentEvent,
    LowStockAlertEvent,
    StockoutEvent,
    ShipmentDispatchedEvent,
    ShipmentArrivedEvent,
    ShipmentDelayedEvent,
    TransactionPostedEvent,
    FeeChargedEvent,
    IntegrityCheckEvent,
    CustomerVisitEvent,
    CustomerPurchaseEvent,
    ReviewPostedEvent,
    CompetitorPriceChangeEvent,
    CompetitorLaunchEvent,
    AdAuctionResultEvent,
    SimulationStartEvent,
    SimulationEndEvent,
    DayEndEvent,
]


# Event type registry for deserialization
EVENT_TYPE_REGISTRY: Dict[str, type] = {
    "MARKET_TICK": MarketTickEvent,
    "PRICE_CHANGE": PriceChangeEvent,
    "SALE_COMPLETED": SaleCompletedEvent,
    "ORDER_PLACED": OrderPlacedEvent,
    "ORDER_RECEIVED": OrderReceivedEvent,
    "ORDER_CANCELLED": OrderCancelledEvent,
    "INVENTORY_ADJUSTMENT": InventoryAdjustmentEvent,
    "LOW_STOCK_ALERT": LowStockAlertEvent,
    "STOCKOUT": StockoutEvent,
    "SHIPMENT_DISPATCHED": ShipmentDispatchedEvent,
    "SHIPMENT_ARRIVED": ShipmentArrivedEvent,
    "SHIPMENT_DELAYED": ShipmentDelayedEvent,
    "TRANSACTION_POSTED": TransactionPostedEvent,
    "FEE_CHARGED": FeeChargedEvent,
    "INTEGRITY_CHECK": IntegrityCheckEvent,
    "CUSTOMER_VISIT": CustomerVisitEvent,
    "CUSTOMER_PURCHASE": CustomerPurchaseEvent,
    "REVIEW_POSTED": ReviewPostedEvent,
    "COMPETITOR_PRICE_CHANGE": CompetitorPriceChangeEvent,
    "COMPETITOR_LAUNCH": CompetitorLaunchEvent,
    "AD_AUCTION_RESULT": AdAuctionResultEvent,
    "SIMULATION_START": SimulationStartEvent,
    "SIMULATION_END": SimulationEndEvent,
    "DAY_END": DayEndEvent,
}


def deserialize_event(data: Dict[str, Any]) -> GameEvent:
    """Deserialize an event from journal storage.

    Uses the event_type field to determine the correct class.

    Args:
        data: Dictionary from journal storage.

    Returns:
        The appropriate GameEvent subclass instance.
    """
    event_type = data.get("event_type")
    event_class = EVENT_TYPE_REGISTRY.get(event_type, GameEvent)
    return event_class.from_journal_dict(data)
