"""Events compatibility shim.

- Re-exports EventBus/get_event_bus from the production event_bus module and
  provides convenience wrappers (publish/subscribe/unsubscribe).
- Defines core event types used across the system to avoid circular imports.

Note on EventBus usage:
The underlying EventBus accepts any hashable as the event key. Callers may use
either string event names or the event class itself as the key.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from event_bus import EventBus, get_event_bus
from fba_events.adversarial import AdversarialResponse
from fba_events.compat import (
    BaseEvent,
    CompetitorPricesUpdated,
    CompetitorState,
    ProductPriceUpdated,
    SaleOccurred,
    SetPriceCommand,
)

__all__ = [
    "EventBus",
    "get_event_bus",
    "publish",
    "subscribe",
    "unsubscribe",
    "AdversarialResponse",
    "TickEvent",
    "BudgetWarning",
    "BudgetExceeded",
    "BaseEvent",
    "CompetitorPricesUpdated",
    "CompetitorState",
    "ProductPriceUpdated",
    "SaleOccurred",
    "SetPriceCommand",
]


# ---------------------------
# Core Event Types
# ---------------------------

@dataclass(frozen=True)
class TickEvent:
    """Simulation tick event used to signal end/start of each tick."""
    event_id: str
    timestamp: datetime


@dataclass(frozen=True)
class BudgetWarning:
    """Warning when usage crosses a configured threshold but is not exceeded."""
    event_id: str
    timestamp: datetime
    agent_id: str
    budget_type: str
    current_usage: int
    limit: int
    reason: str


@dataclass(frozen=True)
class BudgetExceeded:
    """Budget constraint exceeded event; may be hard-fail or soft depending on config."""
    event_id: str
    timestamp: datetime
    agent_id: str
    budget_type: str
    current_usage: int
    limit: int
    reason: str
    severity: str  # "soft" or "hard_fail"


# ---------------------------
# Convenience wrappers
# ---------------------------

def publish(event_name: Any, payload: Any) -> None:
    """Publish an event on the global EventBus.

    Args:
        event_name: The event's name/type (string or class).
        payload: The event payload to dispatch to subscribers.
    """
    get_event_bus().publish(event_name, payload)


def subscribe(event_name: Any, handler: Callable[[Any], None]) -> None:
    """Subscribe a handler to an event on the global EventBus.

    Args:
        event_name: The event name/type (string or class) to subscribe to.
        handler: A callable that accepts the event payload.
    """
    get_event_bus().subscribe(event_name, handler)


def unsubscribe(event_name: Any, handler: Callable[[Any], None]) -> None:
    """Unsubscribe a handler from an event on the global EventBus.

    Args:
        event_name: The event name/type (string or class) to unsubscribe from.
        handler: The handler previously registered for this event.
    """
    get_event_bus().unsubscribe(event_name, handler)
