from __future__ import annotations

"""
Centralized shared types for FBA-Bench.

This module provides a single import location for common data structures and
typing interfaces used across agent runners, unified agents, and the event bus.
It is intentionally light to avoid circular dependencies and heavy import-time
side effects.

Exports:
- SimulationState, ToolCall: canonical simulation types used by runners
- AgentObservation: observation type used by unified agents
- TickEvent, SetPriceCommand: structural protocols for event types to break cycles

Design:
- Runtime classes are re-exported from their source modules where possible.
- Event types are provided as Protocols capturing attributes used by dependents,
  allowing code to type-check without importing full event implementations.

Usage:
  from fba_bench.core.types import SimulationState, ToolCall, AgentObservation, TickEvent, SetPriceCommand
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Prefer importing concrete classes from their home modules at runtime.
# If those modules are unavailable in a specific environment, fall back to
# minimal structural definitions to ensure imports don't fail. These fallbacks
# are only used when the source modules cannot be imported.


# Define SimulationState and ToolCall directly to avoid extensive fallback imports
@dataclass
class SimulationState:
    """State of a simulation at a given point in time."""

    tick: int = 0
    simulation_time: Optional[datetime] = None
    products: List[Any] = field(default_factory=list)
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    financial_position: Dict[str, Any] = field(default_factory=dict)
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    agent_state: Dict[str, Any] = field(default_factory=dict)

    def get_product(self, asin: str) -> Any | None:
        """
        Return the product object with the given ASIN if present, else None.

        Supports both object instances exposing an 'asin' attribute and dict-based
        product entries containing an 'asin' key.
        """
        for p in self.products or []:
            try:
                a = getattr(p, "asin", None)
                if a == asin:
                    return p
            except (AttributeError, TypeError):
                pass
            if isinstance(p, dict) and p.get("asin") == asin:
                return p
        return None

    def get_recent_events_since_tick(self, since_tick: int) -> list[dict]:
        """
        Return events whose tick number is greater than the provided since_tick.

        Accepts multiple common tick key variants to be robust across producers:
        - 'tick_number' (preferred)
        - 'tick'
        - 'tick_num'
        """
        out: list[dict] = []
        for e in self.recent_events or []:
            if not isinstance(e, dict):
                continue
            tn = e.get("tick_number")
            if tn is None:
                tn = e.get("tick")
            if tn is None:
                tn = e.get("tick_num")
            if isinstance(tn, int) and tn > since_tick:
                out.append(e)
        return out


@dataclass
class ToolCall:
    """Representation of a tool call made by an agent."""

    tool_name: str
    parameters: Dict[str, Any]
    confidence: float = 1.0
    reasoning: Optional[str] = None
    priority: int = 0

    def __post_init__(self) -> None:
        # Validate tool_name non-empty
        if not isinstance(self.tool_name, str) or not self.tool_name.strip():
            raise ValueError("tool_name must be a non-empty string")
        # Validate parameters is a dict
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dict")
        # Validate confidence in [0, 1]
        try:
            c = float(self.confidence)
        except (TypeError, ValueError) as e:
            raise ValueError(f"confidence must be a number: {e}")
        if c < 0.0 or c > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0 inclusive")
        # Normalize confidence to float
        self.confidence = c


# Define AgentObservation directly to avoid extensive fallback imports
@dataclass
class AgentObservation:
    """Observation made by an agent during simulation."""

    observation_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None


# Structural protocols for events to avoid importing the full fba_events registry.
@runtime_checkable
class TickEvent(Protocol):
    tick_number: int


@runtime_checkable
class SetPriceCommand(Protocol):
    event_id: str
    agent_id: str
    asin: str
    price: float


@runtime_checkable
class PlaceOrderCommand(Protocol):
    """Structural protocol for supply chain order events."""

    event_id: str
    agent_id: str
    supplier_id: str
    asin: str
    quantity: int


# Import Money type for more specific type hints
try:
    from money import Money
except ImportError:
    # Fallback definition if money package is not available
    @dataclass
    class Money:
        """Simple fallback Money class if the money package is not available."""

        amount: float
        currency: str = "USD"


@runtime_checkable
class RunMarketingCampaignCommand(Protocol):
    """Structural protocol for marketing campaign command."""

    event_id: str
    timestamp: datetime
    campaign_type: str
    budget: Money
    duration_days: int


@runtime_checkable
class AdSpendEvent(Protocol):
    """Structural protocol for ad spend event."""

    event_id: str
    timestamp: datetime
    asin: str
    campaign_id: str
    spend: Money
    clicks: int
    impressions: int


@runtime_checkable
class CustomerReviewEvent(Protocol):
    """Structural protocol for a customer product review event."""

    event_id: str
    timestamp: datetime
    asin: str
    rating: int  # 1-5 stars
    comment: str


@runtime_checkable
class RespondToReviewCommand(Protocol):
    """Structural protocol for a respond-to-review command."""

    event_id: str
    timestamp: datetime
    review_id: str
    asin: str
    response_content: str


__all__ = [
    "SimulationState",
    "ToolCall",
    "AgentObservation",
    "TickEvent",
    "SetPriceCommand",
    "PlaceOrderCommand",
    "RunMarketingCampaignCommand",
    "AdSpendEvent",
    "CustomerReviewEvent",
    "RespondToReviewCommand",
]
