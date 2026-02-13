from __future__ import annotations

"""
Legacy compatibility module for older imports.

Prefer importing directly from `fba_events.*`. This exists so code that still
does `from events import ...` keeps working while we migrate.
"""

import warnings

warnings.warn(
    "`events` module is deprecated; import from `fba_events.*` instead",
    DeprecationWarning,
    stacklevel=2,
)

from fba_events.adversarial import AdversarialResponse
from fba_events.competitor import CompetitorPricesUpdated, CompetitorState
from fba_events.inventory import WorldStateSnapshotEvent
from fba_events.pricing import ProductPriceUpdated, SetPriceCommand
from fba_events.sales import SaleOccurred
from fba_events.time_events import TickEvent

__all__ = [
    "AdversarialResponse",
    "CompetitorPricesUpdated",
    "CompetitorState",
    "ProductPriceUpdated",
    "SaleOccurred",
    "SetPriceCommand",
    "TickEvent",
    "WorldStateSnapshotEvent",
]
