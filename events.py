"""
Compatibility shim module for legacy imports:

Tests and legacy code often use:
    from events import TickEvent, SaleOccurred, CompetitorPricesUpdated, ...

This shim re-exports the canonical event definitions from src/fba_events
so that all components (tests, services, orchestrator) reference the same classes.
It imports CONCRETE symbols from their defining modules to guarantee single-class identity.
"""

# Core base and bus (import from canonical package to ensure single-class identity)
from fba_events.base import BaseEvent
from fba_events.bus import EventBus, InMemoryEventBus

# Competitor/pricing/inventory frequently used in services
from fba_events.competitor import (
    CompetitorPricesUpdated,
    CompetitorState,
)
from fba_events.pricing import (
    ProductPriceUpdated,
    SetPriceCommand,
)
from fba_events.sales import SaleOccurred

# Time and sales events
from fba_events.time_events import TickEvent

# Inventory/budget (some tests/modules import these from events)
try:
    from fba_events.inventory import (  # type: ignore
        InventoryUpdate,
        LowInventoryEvent,
        WorldStateSnapshotEvent,
    )
except ImportError:
    pass

try:
    from fba_events.budget import (  # type: ignore
        BudgetExceeded,
        BudgetWarning,
        ConstraintViolation,
    )
except ImportError:
    pass

# Marketing/common convenience re-exports (+ legacy alias)
try:
    from fba_events.marketing import (  # type: ignore
        AdClickEvent,
        CustomerAcquisitionEvent,
        MarketTrendEvent,
        VisitEvent,
    )

    # Legacy alias used by some tests/fixtures
    MarketChangeEvent = MarketTrendEvent
except ImportError:
    pass

# Adversarial event family (needed by redteam and tests)
try:
    from fba_events.adversarial import (  # type: ignore
        AdversarialEvent,
        AdversarialResponse,
        ComplianceTrapEvent,
        MarketManipulationEvent,
        PhishingEvent,
    )
except ImportError:
    pass

# Customer events (messaging/complaints)
try:
    from fba_events.customer import (  # type: ignore
        ComplaintEvent,
        CustomerMessageReceived,
        NegativeReviewEvent,
        RespondToCustomerMessageCommand,
    )
except ImportError:
    pass

# Reporting events (profit/loss summaries)
try:
    from fba_events.reporting import (  # type: ignore
        LossEvent,
        ProfitReport,
    )
except ImportError:
    pass

__all__ = [
    # Base/Bus
    "BaseEvent",
    "EventBus",
    "InMemoryEventBus",
    # Time/Sales
    "TickEvent",
    "SaleOccurred",
    # Competitor/Pricing
    "CompetitorPricesUpdated",
    "CompetitorState",
    "SetPriceCommand",
    "ProductPriceUpdated",
    # Inventory/Budget
    "InventoryUpdate",
    "LowInventoryEvent",
    "WorldStateSnapshotEvent",
    "BudgetWarning",
    "BudgetExceeded",
    "ConstraintViolation",
    # Marketing
    "AdClickEvent",
    "CustomerAcquisitionEvent",
    "VisitEvent",
    "MarketTrendEvent",
    "MarketChangeEvent",
    # Adversarial
    "AdversarialEvent",
    "AdversarialResponse",
    "ComplianceTrapEvent",
    "MarketManipulationEvent",
    "PhishingEvent",
    # Customer
    "CustomerMessageReceived",
    "NegativeReviewEvent",
    "ComplaintEvent",
    "RespondToCustomerMessageCommand",
    # Reporting
    "ProfitReport",
    "LossEvent",
]
