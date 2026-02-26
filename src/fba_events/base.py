"""
Base event and core event-related definitions for the FBA-Bench simulation.

This module provides the `BaseEvent` abstract class, which all concrete
event types throughout the simulation must inherit from. It establishes
fundamental properties and methods common to all events, ensuring a
consistent structure for event handling, traceability, and serialization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass
class BaseEvent(ABC):
    """
    Abstract base class for all events within the FBA-Bench simulation.

    All concrete event types must inherit from this class, ensuring they have
    a unique `event_id` and a `timestamp` for traceability, and implement
    the `to_summary_dict` method for consistent data representation.

    Attributes:
        event_id (str): A unique identifier for this specific event instance.
        timestamp (datetime): The UTC datetime when the event occurred or was generated.
    """

    event_id: str
    timestamp: datetime

    def __post_init__(self):
        """
        Performs basic validation on common event attributes after initialization.
        Ensures `event_id` is not empty and `timestamp` is a `datetime` object.
        """
        # Validate event_id: Must be a non-empty string.
        if not self.event_id:
            raise ValueError("Event ID cannot be empty")
        # Validate timestamp: Must be a datetime object.
        if not isinstance(self.timestamp, datetime):
            raise TypeError("Timestamp must be a datetime object")

    @abstractmethod
    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Converts the event instance into a summary dictionary.

        This method is crucial for logging, debugging, serialization, and
        external systems that need a standardized, concise representation
        of the event's key data. Implementations should convert complex
        objects (like Money or datetime) to string representations,
        and ensure that the output is JSON-serializable.

        Returns:
            Dict[str, Any]: A dictionary containing key attributes of the event.
        """
        raise NotImplementedError("Subclasses must implement to_summary_dict")


import asyncio  # noqa: E402
from typing import Awaitable, Callable, List  # noqa: E402


class EventBus:
    """
    Simple asynchronous event bus for publishing and subscribing to events.

    Supports multiple subscribers per event type. Events are published asynchronously
    and subscribers receive them via callbacks. Designed for the FBA-Bench simulation
    to handle event distribution without blocking.

    Attributes:
        subscribers (Dict[str, List[Callable]]): Mapping of event types to subscriber callbacks.
    """

    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[BaseEvent], Awaitable[None]]]] = {}  # noqa: F821  # type: ignore[name-defined]

    def subscribe(
        self, event_type: str, callback: Callable[[BaseEvent], Awaitable[None]]  # noqa: F821  # type: ignore[name-defined]
    ) -> None:
        """
        Subscribe a callback to receive events of a specific type.

        Args:
            event_type (str): The type of event to subscribe to (e.g., 'TickEvent').
            callback (Callable[[BaseEvent], Awaitable[None]]): Async function to call when an event is published.
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def unsubscribe(
        self, event_type: str, callback: Callable[[BaseEvent], Awaitable[None]]  # noqa: F821  # type: ignore[name-defined]
    ) -> None:
        """
        Unsubscribe a callback from receiving events of a specific type.

        Args:
            event_type (str): The type of event to unsubscribe from.
            callback (Callable[[BaseEvent], Awaitable[None]]): The callback to remove.
        """
        if event_type in self.subscribers:
            self.subscribers[event_type] = [
                cb for cb in self.subscribers[event_type] if cb != callback
            ]
            if not self.subscribers[event_type]:
                del self.subscribers[event_type]

    async def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to all subscribers of its type.

        Args:
            event (BaseEvent): The event to publish.
        """
        event_type = type(event).__name__
        if event_type in self.subscribers:
            tasks = [callback(event) for callback in self.subscribers[event_type]]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
