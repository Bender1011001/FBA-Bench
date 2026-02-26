from __future__ import annotations

"""
Compatibility layer for legacy event imports.

This module re-exports canonical classes from fba_events while emitting a
DeprecationWarning on import. Prefer importing directly from fba_events.*
modules or fba_events registry-based exports.

Legacy code that previously imported from various locations can import from
fba_events.compat during the migration period.

Exports:
- BaseEvent
- TickEvent
- SetPriceCommand
- SaleOccurred
- ProductPriceUpdated
- CompetitorPricesUpdated
- CompetitorState
"""

import warnings

warnings.warn(
    "fba_events.compat is deprecated; import from fba_events.* instead",
    DeprecationWarning,
    stacklevel=2,
)

# Try canonical top-level registry exports first, then explicit submodules
# BaseEvent
try:
    from fba_events import BaseEvent as BaseEvent  # type: ignore
except ImportError:
    from fba_events.base import BaseEvent as BaseEvent  # type: ignore

# TickEvent
try:
    from fba_events import TickEvent as TickEvent  # type: ignore
except ImportError:
    from fba_events.time_events import TickEvent as TickEvent  # type: ignore

# SetPriceCommand, ProductPriceUpdated
try:
    from fba_events import SetPriceCommand as SetPriceCommand  # type: ignore
except ImportError:
    from fba_events.pricing import SetPriceCommand as SetPriceCommand  # type: ignore

try:
    from fba_events import ProductPriceUpdated as ProductPriceUpdated  # type: ignore
except ImportError:
    from fba_events.pricing import ProductPriceUpdated as ProductPriceUpdated  # type: ignore

# SaleOccurred
try:
    from fba_events import SaleOccurred as SaleOccurred  # type: ignore
except ImportError:
    from fba_events.sales import SaleOccurred as SaleOccurred  # type: ignore

# CompetitorPricesUpdated, CompetitorState
try:
    from fba_events import CompetitorPricesUpdated as CompetitorPricesUpdated  # type: ignore
except ImportError:
    from fba_events.competitor import (
        CompetitorPricesUpdated as CompetitorPricesUpdated,  # type: ignore
    )

try:
    from fba_events import CompetitorState as CompetitorState  # type: ignore
except ImportError:
    from fba_events.competitor import CompetitorState as CompetitorState  # type: ignore


__all__ = [
    "BaseEvent",
    "TickEvent",
    "SetPriceCommand",
    "SaleOccurred",
    "ProductPriceUpdated",
    "CompetitorPricesUpdated",
    "CompetitorState",
]
