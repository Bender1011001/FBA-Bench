from __future__ import annotations

"""
agent_runners.compat - Temporary event compatibility layer.

This module provides thin passthroughs to event types used by some code paths and tests,
without importing deprecated monolithic modules. If the canonical fba_events package is
available, its definitions are re-exported. Otherwise, structural Protocol fallbacks are
declared to satisfy type-checking and runtime attribute access.

Exports:
- TickEvent
- SetPriceCommand
"""

from typing import Any, Protocol, runtime_checkable

# Prefer canonical-first via fba_events.compat (emits DeprecationWarning) to maintain legacy paths temporarily.
# Resolve concrete types once, avoiding multiple re-bindings that confuse type checkers.


def _resolve_TickEvent() -> type[Any]:
    try:
        from fba_events.compat import TickEvent as T

        return T
    except (ImportError, AttributeError):
        try:
            from fba_events import TickEvent as T

            return T
        except (ImportError, AttributeError):
            try:
                from fba_events.time_events import TickEvent as T

                return T
            except (ImportError, AttributeError):

                @runtime_checkable
                class _TickEvent(Protocol):
                    """Minimal structural protocol for a simulation tick event."""

                    tick_number: int
                    # Optional fields sometimes accessed by callers
                    # timestamp: datetime
                    # event_type: str

                return _TickEvent


def _resolve_SetPriceCommand() -> type[Any]:
    try:
        from fba_events.compat import SetPriceCommand as C

        return C
    except (ImportError, AttributeError):
        try:
            from fba_events import SetPriceCommand as C

            return C
        except (ImportError, AttributeError):
            try:
                from fba_events.pricing import SetPriceCommand as C

                return C
            except (ImportError, AttributeError):

                @runtime_checkable
                class _SetPriceCommand(Protocol):
                    """Minimal structural protocol for a SetPriceCommand used in tests."""

                    event_id: str
                    agent_id: str
                    asin: str
                    new_price: Any  # Can be Money or float depending on caller context
                    # Optional fields sometimes present
                    # timestamp: datetime
                    # reason: str

                return _SetPriceCommand


# Single final bindings with explicit type to satisfy mypy
TickEvent: type[Any] = _resolve_TickEvent()
SetPriceCommand: type[Any] = _resolve_SetPriceCommand()
