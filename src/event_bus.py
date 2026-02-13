"""
Legacy compatibility shim for older imports.

Historically, parts of the codebase and tests imported event bus primitives from a
top-level `event_bus` module:
  - from event_bus import EventBus, get_event_bus, set_event_bus
  - from event_bus import AsyncioQueueBackend, DistributedBackend

The canonical implementation now lives under `fba_bench_core.event_bus` (bridging
to the concrete bus under `fba_events.*`). This module re-exports the public API
to keep legacy imports working.
"""

from fba_bench_core.event_bus import (  # noqa: F401
    AsyncioQueueBackend,
    BaseEvent,
    DistributedBackend,
    EventBus,
    InMemoryEventBus,
    get_event_bus,
    set_event_bus,
)

__all__ = [
    "AsyncioQueueBackend",
    "BaseEvent",
    "DistributedBackend",
    "EventBus",
    "InMemoryEventBus",
    "get_event_bus",
    "set_event_bus",
]
