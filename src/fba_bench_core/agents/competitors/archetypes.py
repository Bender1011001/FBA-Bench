"""Adversarial Competitor Archetypes.

This module implements three distinct competitor strategies:
1. Price War Bot: Undercuts user price by $0.10 down to a floor
2. Ad Whale Bot: Bids irrationally high on PPC to starve impressions
3. Copycat Bot: Launches similar products after velocity threshold

These bots create realistic competitive pressure that forces agents
to learn proper unit economics and strategic thinking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from fba_bench_core.core.events import (
    AdAuctionResultEvent,
    CompetitorLaunchEvent,
    CompetitorPriceChangeEvent,
    GameEvent,
)

from .base_competitor import BaseCompetitor, WorldStateView


class PriceWarBot(BaseCompetitor):
    """Aggressive price undercutter.
    
    Strategy: Monitor user's price every tick. If User Price < Bot Price,
    Bot sets Price = User Price - $0.10 (down to a floor).
    
    This forces the user to learn:
    - When to stop the price war (margin protection)
    - Value of differentiation over pure price competition
    - Strategic pricing based on costs, not competitors
    """
    
    def __init__(
        self,
        world_state: WorldStateView,
        competitor_id: Optional[str] = None,
        undercut_amount: float = 0.10,
        price_floor: float = 5.00,
        asins: Optional[List[str]] = None,
    ):
        """Initialize Price War Bot.
        
        Args:
            world_state: Read-only market state view.
            competitor_id: Unique identifier.
            undercut_amount: How much to undercut (default $0.10).
            price_floor: Minimum price (won't go below this).
            asins: ASINs to compete on.
        """
        super().__init__(
            world_state=world_state,
            competitor_id=competitor_id,
            name="Price War Bot",
            asins=asins,
        )
        self.undercut_amount = undercut_amount
        self.price_floor = price_floor
        self._current_prices: Dict[str, float] = {}
    
    def decide(self, tick: int) -> List[GameEvent]:
        """Check each ASIN and undercut if needed."""
        events = []
        
        for asin in self.asins:
            # Get user's current price
            user_price = self._world_state.get_product_price(asin)
            if user_price is None:
                continue
            
            # Get our current price (or default to user's price + 1)
            our_price = self._current_prices.get(asin, user_price + 1.0)
            
            # If user is cheaper, undercut them
            if user_price < our_price:
                new_price = max(
                    self.price_floor,
                    user_price - self.undercut_amount
                )
                
                # Only emit event if price actually changes
                if new_price != our_price:
                    self._current_prices[asin] = new_price
                    events.append(self._create_price_change_event(
                        tick=tick,
                        asin=asin,
                        new_price=new_price,
                    ))
        
        return events


class AdWhaleBot(BaseCompetitor):
    """Aggressive PPC bidder that bids irrationally high.
    
    Strategy: Bid 2-3x the reasonable CPC to dominate ad placements.
    This starves competitors of impressions and forces them to either:
    - Outbid (destroying margins)
    - Accept lower organic visibility
    
    Forces user to learn:
    - When to compete vs. when to concede
    - True value of ad impressions
    - Alternative traffic sources
    """
    
    def __init__(
        self,
        world_state: WorldStateView,
        competitor_id: Optional[str] = None,
        bid_multiplier: float = 2.5,
        base_bid: float = 1.00,
        daily_budget: float = 500.00,
        keywords: Optional[List[str]] = None,
    ):
        """Initialize Ad Whale Bot.
        
        Args:
            world_state: Read-only market state view.
            competitor_id: Unique identifier.
            bid_multiplier: How much above market to bid.
            base_bid: Starting bid per click.
            daily_budget: Maximum daily ad spend.
            keywords: Keywords to bid on.
        """
        super().__init__(
            world_state=world_state,
            competitor_id=competitor_id,
            name="Ad Whale Bot",
        )
        self.bid_multiplier = bid_multiplier
        self.base_bid = base_bid
        self.daily_budget = daily_budget
        self.keywords = keywords or []
        self._daily_spend = 0.0
        self._last_day = -1
        
        # Track aggressive bids
        self._statistics["total_ad_spend"] = 0.0
        self._statistics["auctions_won"] = 0
    
    def add_keyword(self, keyword: str) -> None:
        """Add keyword to bid on."""
        if keyword not in self.keywords:
            self.keywords.append(keyword)
    
    def decide(self, tick: int) -> List[GameEvent]:
        """Submit aggressive bids for all keywords."""
        events = []
        
        # Reset daily budget at day boundary (assume 1 day = 24 ticks)
        current_day = tick // 24
        if current_day != self._last_day:
            self._daily_spend = 0.0
            self._last_day = current_day
        
        # Check budget
        if self._daily_spend >= self.daily_budget:
            return events
        
        # Submit bids for each keyword
        for keyword in self.keywords:
            # Calculate aggressive bid
            bid = self.base_bid * self.bid_multiplier
            
            # Create bid event (this would be processed by ad auction system)
            events.append(AdAuctionResultEvent(
                tick=tick,
                agent_id=self.competitor_id,
                payload={
                    "keyword": keyword,
                    "bidder_id": self.competitor_id,
                    "bid_amount": bid,
                    "is_bid_submission": True,  # Flag that this is a bid, not result
                    "competitor_name": self.name,
                }
            ))
        
        return events


class CopycatBot(BaseCompetitor):
    """Product copier that launches similar products after success signals.
    
    Strategy: Monitor user's products for high sales velocity (low BSR).
    When a product hits success threshold, launch a competing product
    after a delay period.
    
    Forces user to learn:
    - First-mover advantage vs. sustainable advantage
    - Importance of brand building and reviews
    - Product differentiation strategies
    """
    
    def __init__(
        self,
        world_state: WorldStateView,
        competitor_id: Optional[str] = None,
        bsr_threshold: int = 10000,
        launch_delay_ticks: int = 30,
        price_discount: float = 0.15,
        asins_to_monitor: Optional[List[str]] = None,
    ):
        """Initialize Copycat Bot.
        
        Args:
            world_state: Read-only market state view.
            competitor_id: Unique identifier.
            bsr_threshold: BSR below which triggers copy.
            launch_delay_ticks: Ticks to wait before launching.
            price_discount: How much cheaper than original (0.15 = 15% off).
            asins_to_monitor: ASINs to watch for success.
        """
        super().__init__(
            world_state=world_state,
            competitor_id=competitor_id,
            name="Copycat Bot",
            asins=asins_to_monitor,
        )
        self.bsr_threshold = bsr_threshold
        self.launch_delay_ticks = launch_delay_ticks
        self.price_discount = price_discount
        
        # Track products being prepared for launch
        self._pending_launches: Dict[str, int] = {}  # asin -> launch_tick
        self._launched_products: List[str] = []
        
        self._statistics["products_copied"] = 0
        self._statistics["products_launched"] = 0
    
    def decide(self, tick: int) -> List[GameEvent]:
        """Monitor products and launch copies."""
        events = []
        
        # Check for new products to copy
        for asin in self.asins:
            if asin in self._launched_products:
                continue  # Already copied
            
            if asin in self._pending_launches:
                continue  # Already scheduled
            
            # Check if product is successful
            bsr = self._world_state.get_product_bsr(asin)
            if bsr is not None and bsr <= self.bsr_threshold:
                # Schedule launch
                launch_tick = tick + self.launch_delay_ticks
                self._pending_launches[asin] = launch_tick
                self._statistics["products_copied"] += 1
        
        # Process pending launches
        launched_asins = []
        for asin, launch_tick in self._pending_launches.items():
            if tick >= launch_tick:
                # Launch the copycat product
                original_price = self._world_state.get_product_price(asin)
                copy_price = (original_price or 20.0) * (1 - self.price_discount)
                
                events.append(CompetitorLaunchEvent(
                    tick=tick,
                    agent_id=self.competitor_id,
                    payload={
                        "original_asin": asin,
                        "copy_asin": f"COPY-{asin}-{uuid4().hex[:6]}",
                        "copy_price": copy_price,
                        "price_discount": self.price_discount,
                        "competitor_id": self.competitor_id,
                        "competitor_name": self.name,
                    }
                ))
                
                self._launched_products.append(asin)
                launched_asins.append(asin)
                self._statistics["products_launched"] += 1
        
        # Clear launched from pending
        for asin in launched_asins:
            del self._pending_launches[asin]
        
        return events


# =============================================================================
# Factory function for creating competitor sets
# =============================================================================

def create_default_competitors(
    world_state: WorldStateView,
    user_asins: List[str],
    keywords: Optional[List[str]] = None,
) -> List[BaseCompetitor]:
    """Create a default set of competitors for simulation.
    
    Args:
        world_state: Read-only market state view.
        user_asins: ASINs the user is selling.
        keywords: Keywords for ad competition.
        
    Returns:
        List of competitor instances.
    """
    competitors = [
        PriceWarBot(
            world_state=world_state,
            asins=user_asins.copy(),
            undercut_amount=0.10,
            price_floor=5.00,
        ),
        AdWhaleBot(
            world_state=world_state,
            keywords=keywords or ["default keyword"],
            bid_multiplier=2.5,
            daily_budget=500.00,
        ),
        CopycatBot(
            world_state=world_state,
            asins_to_monitor=user_asins.copy(),
            bsr_threshold=10000,
            launch_delay_ticks=30,
        ),
    ]
    
    return competitors
