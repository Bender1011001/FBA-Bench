"""Base Competitor Interface for Adversarial AI.

This module defines the foundation for adversarial competitor bots that
compete against the user's agent. Competitors:
- Have read-only access to public WorldState (price, BSR, review count)
- Cannot see private data (inventory levels, margins, costs)
- Make decisions based on observable market signals

Usage:
    from fba_bench_core.agents.competitors.base_competitor import BaseCompetitor
    
    class MyBot(BaseCompetitor):
        def decide(self, tick: int) -> List[BaseEvent]:
            # Implement strategy
            pass
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4

from fba_bench_core.core.events import (
    CompetitorPriceChangeEvent,
    GameEvent,
)


@dataclass(frozen=True)
class PublicProductInfo:
    """Read-only view of publicly observable product information.
    
    This is what competitors can "scrape" from the marketplace.
    Private data like cost, margins, and inventory levels are NOT included.
    """
    asin: str
    price: float              # Current listing price
    bsr: int                  # Best Seller Rank
    review_count: int         # Number of reviews
    review_rating: float      # Average rating (1.0-5.0)
    shipping_days: int        # Estimated shipping time
    is_prime: bool            # FBA/Prime badge
    seller_id: str            # Seller identifier
    category: str             # Product category
    title: Optional[str] = None


class WorldStateView(Protocol):
    """Protocol defining read-only access to public WorldState.
    
    Competitors receive this interface, which exposes only public data.
    """
    
    def get_product_price(self, asin: str) -> Optional[float]:
        """Get current listing price for a product."""
        ...
    
    def get_product_bsr(self, asin: str) -> Optional[int]:
        """Get Best Seller Rank for a product."""
        ...
    
    def get_product_reviews(self, asin: str) -> tuple[int, float]:
        """Get (review_count, average_rating) for a product."""
        ...
    
    def get_competitors_for_asin(self, asin: str) -> List[PublicProductInfo]:
        """Get all competitor listings for an ASIN."""
        ...
    
    def get_current_tick(self) -> int:
        """Get current simulation tick."""
        ...
    
    def get_category_average_price(self, category: str) -> float:
        """Get average price for a product category."""
        ...


class BaseCompetitor(ABC):
    """Abstract base class for adversarial AI competitors.
    
    Competitors implement strategies to compete with the user's agent.
    They observe public market data and emit events (price changes, 
    ad bids, product launches) that affect the simulation.
    
    Attributes:
        competitor_id: Unique identifier for this competitor.
        name: Human-readable name (e.g., "Price War Bot").
        asins: List of ASINs this competitor is active on.
        enabled: Whether competitor is active in simulation.
    """
    
    def __init__(
        self,
        world_state: WorldStateView,
        competitor_id: Optional[str] = None,
        name: str = "Competitor",
        asins: Optional[List[str]] = None,
    ):
        """Initialize competitor.
        
        Args:
            world_state: Read-only view of public world state.
            competitor_id: Unique ID (generated if not provided).
            name: Human-readable competitor name.
            asins: ASINs this competitor competes on.
        """
        self._world_state = world_state
        self.competitor_id = competitor_id or f"competitor-{uuid4().hex[:8]}"
        self.name = name
        self.asins = asins or []
        self.enabled = True
        self._last_tick = -1
        self._statistics: Dict[str, Any] = {
            "decisions_made": 0,
            "events_emitted": 0,
        }
    
    @property
    def world_state(self) -> WorldStateView:
        """Read-only access to public world state."""
        return self._world_state
    
    @abstractmethod
    def decide(self, tick: int) -> List[GameEvent]:
        """Make decisions for this tick.
        
        Called once per tick. Returns list of events to emit
        (price changes, ad bids, etc.).
        
        Args:
            tick: Current simulation tick.
            
        Returns:
            List of events representing competitor actions.
        """
        pass
    
    def on_tick(self, tick: int) -> List[GameEvent]:
        """Process a tick (wraps decide with state tracking).
        
        This method handles:
        - Avoiding duplicate processing
        - Statistics tracking
        - Enabling/disabling
        
        Args:
            tick: Current simulation tick.
            
        Returns:
            List of events from decide().
        """
        if not self.enabled:
            return []
        
        if tick <= self._last_tick:
            return []  # Already processed
        
        self._last_tick = tick
        events = self.decide(tick)
        
        self._statistics["decisions_made"] += 1
        self._statistics["events_emitted"] += len(events)
        
        return events
    
    def get_statistics(self) -> Dict[str, Any]:
        """Return competitor statistics."""
        return {
            "competitor_id": self.competitor_id,
            "name": self.name,
            "enabled": self.enabled,
            "asins": self.asins,
            "last_tick": self._last_tick,
            **self._statistics,
        }
    
    def add_asin(self, asin: str) -> None:
        """Add an ASIN to compete on."""
        if asin not in self.asins:
            self.asins.append(asin)
    
    def remove_asin(self, asin: str) -> None:
        """Remove an ASIN from competition."""
        if asin in self.asins:
            self.asins.remove(asin)
    
    def _create_price_change_event(
        self,
        tick: int,
        asin: str,
        new_price: float,
    ) -> CompetitorPriceChangeEvent:
        """Helper to create a price change event."""
        return CompetitorPriceChangeEvent(
            tick=tick,
            agent_id=self.competitor_id,
            payload={
                "asin": asin,
                "new_price": new_price,
                "competitor_id": self.competitor_id,
                "competitor_name": self.name,
            }
        )


class CompetitorRegistry:
    """Registry for managing active competitors."""
    
    def __init__(self):
        self._competitors: Dict[str, BaseCompetitor] = {}
    
    def register(self, competitor: BaseCompetitor) -> None:
        """Register a competitor."""
        self._competitors[competitor.competitor_id] = competitor
    
    def unregister(self, competitor_id: str) -> None:
        """Unregister a competitor."""
        self._competitors.pop(competitor_id, None)
    
    def get(self, competitor_id: str) -> Optional[BaseCompetitor]:
        """Get competitor by ID."""
        return self._competitors.get(competitor_id)
    
    def get_all(self) -> List[BaseCompetitor]:
        """Get all registered competitors."""
        return list(self._competitors.values())
    
    def get_enabled(self) -> List[BaseCompetitor]:
        """Get all enabled competitors."""
        return [c for c in self._competitors.values() if c.enabled]
    
    def process_tick(self, tick: int) -> List[GameEvent]:
        """Process tick for all enabled competitors."""
        events = []
        for competitor in self.get_enabled():
            events.extend(competitor.on_tick(tick))
        return events
