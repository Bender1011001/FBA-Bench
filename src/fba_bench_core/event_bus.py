from __future__ import annotations

"""
Legacy event_bus compatibility shim.

This module preserves the historical import path:
  - from event_bus import EventBus, get_event_bus, set_event_bus
  - from event_bus import AsyncioQueueBackend, DistributedBackend

It bridges to the concrete implementations in fba_events.bus to avoid broad refactors.
"""

from typing import Optional

# Public aliases to maintain backwards compatibility in code/tests
from fba_events.base import (
    BaseEvent as _BaseEvent,  # Direct import after confirming its existence and structure
)
from fba_events.bus import (
    EventBus as _BaseEventBus,
    InMemoryEventBus as _InMemoryEventBus,
)


class EventBus(_InMemoryEventBus):
    """
    compat: concrete EventBus that accepts legacy `backend` parameter but uses in-memory backend.

    When constructed with a compat Distributed/Asyncio backend instance (our _CompatBackend),
    this shim will also mirror subscribe/publish through that backend using a dict-shaped event:
      { 'event_type', 'event_data', 'target_partition', 'timestamp' }.

    This preserves typed semantics for regular subscribers while enabling
    distributed tests expecting dict payloads via the backend.
    """

    def __init__(self, *args, **kwargs) -> None:
        # Detect legacy backend if provided positionally or by keyword
        self._compat_backend = None
        backend = None
        if args:
            backend = args[0]
        if backend is None:
            backend = kwargs.get("backend")
        super().__init__()
        try:
            if isinstance(backend, _CompatBackend):
                self._compat_backend = backend
        except (TypeError, AttributeError):
            self._compat_backend = None

    async def subscribe(self, event_type, handler):  # type: ignore[override]
        """
        Subscribe handler.

        Behavior:
        - Register only with the typed base bus so handlers receive typed event objects.
        - Do not double-register to the compat backend to avoid duplicate deliveries.
        """
        return await super().subscribe(event_type, handler)

    async def publish(self, event) -> None:  # type: ignore[override]
        """
        Publish a typed event to the in-memory bus.

        Note:
        - Do NOT mirror to the compat backend here to avoid duplicate deliveries when
          tests subscribe by string event name. Distributed/dict-shaped usage should
          explicitly use the compat backend in those test paths.
        """
        await super().publish(event)

    def get_stats(self) -> dict:
        """
        Return basic operational statistics for observability and tests.
        Keys:
            - started: whether the bus is started
            - events_published: number of events accepted via publish()
            - events_processed: number of events dequeued and dispatched
            - subscribers: total registered handler count
        """
        try:
            subs = sum(len(v) for v in getattr(self, "_subscribers", {}).values())
        except (TypeError, AttributeError):
            subs = 0
        return {
            "started": bool(getattr(self, "_started", False)),
            "events_published": int(getattr(self, "_events_published", 0)),
            "events_processed": int(getattr(self, "_events_processed", 0)),
            "subscribers": int(subs),
        }


InMemoryEventBus = _InMemoryEventBus
BaseEvent = _BaseEvent


class _CompatBackend(_InMemoryEventBus):
    """
    Legacy backend adapter that accepts arbitrary constructor args but
    always initializes an in-memory event bus backend.

    Additionally, it provides a dict-oriented API compatible with historical
    'DistributedEventBus' usage in tests:
      - publish_event(event_type: str, event_data: dict, target_partition: Optional[str])
      - subscribe_to_event(event_type: str, handler)
    Handlers receive a dictionary payload with keys:
      { 'event_type', 'event_data', 'target_partition', 'timestamp' }.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self._subs: dict[str, list] = {}
        self._started: bool = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False
        # Do not leak handlers across tests
        self._subs.clear()

    async def publish_event(
        self,
        event_type: str,
        event_data: dict | None = None,
        *,
        target_partition: str | None = None,
    ) -> bool:
        from datetime import datetime, timezone

        msg = {
            "event_type": event_type,
            "event_data": dict(event_data or {}),
            "target_partition": target_partition,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Deliver to specific subscribers and wildcard '*'
        handlers = list(self._subs.get(event_type, [])) + list(self._subs.get("*", []))
        for h in handlers:
            try:
                res = h(msg)
                # Support async handlers
                if hasattr(res, "__await__"):
                    await res  # type: ignore[func-returns-value]
            except (TypeError, AttributeError, RuntimeError):
                # Swallow handler errors to avoid breaking publisher in tests
                pass
        return True

    async def subscribe_to_event(self, event_type: str, handler) -> bool:
        self._subs.setdefault(event_type, []).append(handler)
        return True


# Historical backends used in tests; mapped to a compat implementation
AsyncioQueueBackend = _CompatBackend
DistributedBackend = _CompatBackend

# Singleton holder used by legacy code paths
_bus_singleton: Optional[_BaseEventBus] = None


def get_event_bus() -> _BaseEventBus:
    """
    Return a process-local singleton EventBus instance.

    Historically this returned a configured backend. To keep behavior stable,
    we provide an InMemoryEventBus when no bus has been set explicitly.
    """
    global _bus_singleton
    if _bus_singleton is None:
        _bus_singleton = _InMemoryEventBus()
    return _bus_singleton


def set_event_bus(bus: _BaseEventBus) -> None:
    """
    Explicitly set the process-local EventBus singleton.
    Useful for tests or embedding in other runtimes.
    """
    global _bus_singleton
    _bus_singleton = bus
