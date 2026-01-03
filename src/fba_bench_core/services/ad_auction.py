"""Second-Price Ad Auction for PPC Competition.

This module implements a Vickrey (second-price) auction for sponsored product placements.
In a second-price auction, the highest bidder wins but pays the second-highest bid price.

Why second-price?
- Encourages truthful bidding (bid your true value)
- Used by Google Ads, Amazon PPC
- Prevents winner's curse
- Creates realistic competitive dynamics

Usage:
    from fba_bench_core.services.ad_auction import AdAuctionService
    
    auction = AdAuctionService()
    result = auction.run_auction(keyword="yoga mat", bids)
    print(f"Winner: {result.winner_id} pays ${result.price_paid}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class AdBid:
    """A bid in an ad auction."""
    bidder_id: str
    bid_amount: float      # Maximum CPC the bidder is willing to pay
    quality_score: float = 1.0  # 0.1-2.0, affects ad rank
    asin: Optional[str] = None  # Product being advertised


@dataclass
class AuctionResult:
    """Result of an ad auction."""
    keyword: str
    winner_id: Optional[str]
    winning_bid: float      # What winner bid
    price_paid: float       # What winner actually pays (second price)
    ad_rank: float          # Winner's ad rank score
    impressions: int        # Estimated impressions won
    position: int           # Ad position (1 = top)
    runner_up_id: Optional[str] = None
    all_participants: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuctionSlot:
    """A slot in the ad auction (position 1, 2, 3, etc.)."""
    position: int
    winner_id: str
    price_paid: float
    ad_rank: float
    impressions: int


class AdAuctionService:
    """Second-price auction for sponsored product placements.
    
    Key mechanics:
    1. Bidders submit bids (max CPC willing to pay)
    2. Ad Rank = Bid × Quality Score
    3. Highest Ad Rank wins
    4. Winner pays: (Second Ad Rank / Winner Quality Score) + $0.01
    5. Multiple slots available (top 3 positions typical)
    
    Attributes:
        min_bid: Minimum bid amount.
        min_increment: Minimum second-price increment.
        slots_per_keyword: Number of ad positions available.
        base_impressions: Base impressions for top slot.
        impression_decay: Decay factor for lower positions.
    """
    
    def __init__(
        self,
        min_bid: float = 0.10,
        min_increment: float = 0.01,
        slots_per_keyword: int = 3,
        base_impressions: int = 1000,
        impression_decay: float = 0.6,
    ):
        """Initialize the ad auction service.
        
        Args:
            min_bid: Minimum allowed bid.
            min_increment: Increment added to second price.
            slots_per_keyword: Number of ad positions per keyword.
            base_impressions: Impressions for position 1.
            impression_decay: Multiplier for each lower position.
        """
        self.min_bid = min_bid
        self.min_increment = min_increment
        self.slots_per_keyword = slots_per_keyword
        self.base_impressions = base_impressions
        self.impression_decay = impression_decay
        
        # Track auction history
        self._auction_history: List[AuctionResult] = []
        self._statistics = {
            "total_auctions": 0,
            "total_revenue": 0.0,
            "avg_winning_bid": 0.0,
            "avg_participants": 0.0,
        }
    
    def run_auction(
        self,
        keyword: str,
        bids: List[AdBid],
        apply_quality_score: bool = True,
    ) -> AuctionResult:
        """Run a second-price auction for a keyword.
        
        Args:
            keyword: The keyword being auctioned.
            bids: List of bids from advertisers.
            apply_quality_score: Whether to factor in quality scores.
            
        Returns:
            AuctionResult with winner and price paid.
        """
        if not bids:
            return AuctionResult(
                keyword=keyword,
                winner_id=None,
                winning_bid=0.0,
                price_paid=0.0,
                ad_rank=0.0,
                impressions=0,
                position=0,
            )
        
        # Filter valid bids
        valid_bids = [b for b in bids if b.bid_amount >= self.min_bid]
        if not valid_bids:
            return AuctionResult(
                keyword=keyword,
                winner_id=None,
                winning_bid=0.0,
                price_paid=0.0,
                ad_rank=0.0,
                impressions=0,
                position=0,
                all_participants=[b.bidder_id for b in bids],
            )
        
        # Calculate ad rank for each bid
        ranked_bids = []
        for bid in valid_bids:
            quality = bid.quality_score if apply_quality_score else 1.0
            ad_rank = bid.bid_amount * quality
            ranked_bids.append((ad_rank, bid))
        
        # Sort by ad rank descending
        ranked_bids.sort(key=lambda x: x[0], reverse=True)
        
        # Winner is highest ad rank
        winner_rank, winner_bid = ranked_bids[0]
        
        # Calculate price paid (second-price)
        if len(ranked_bids) >= 2:
            second_rank, second_bid = ranked_bids[1]
            # Price = (Second Ad Rank / Winner QS) + increment
            winner_qs = winner_bid.quality_score if apply_quality_score else 1.0
            price_paid = (second_rank / winner_qs) + self.min_increment
        else:
            # Only one bidder - pay minimum bid
            price_paid = self.min_bid
        
        # Cap at winning bid (can't pay more than you bid)
        price_paid = min(price_paid, winner_bid.bid_amount)
        
        # Calculate impressions for position 1
        impressions = self.base_impressions
        
        result = AuctionResult(
            keyword=keyword,
            winner_id=winner_bid.bidder_id,
            winning_bid=winner_bid.bid_amount,
            price_paid=round(price_paid, 2),
            ad_rank=winner_rank,
            impressions=impressions,
            position=1,
            runner_up_id=ranked_bids[1][1].bidder_id if len(ranked_bids) >= 2 else None,
            all_participants=[b.bidder_id for b in bids],
        )
        
        # Update statistics
        self._record_result(result)
        
        return result
    
    def run_multi_slot_auction(
        self,
        keyword: str,
        bids: List[AdBid],
        apply_quality_score: bool = True,
    ) -> List[AuctionSlot]:
        """Run auction for multiple ad slots.
        
        Awards positions 1 through N (slots_per_keyword).
        Each slot winner pays the price to beat the next slot.
        
        Args:
            keyword: The keyword being auctioned.
            bids: List of bids from advertisers.
            apply_quality_score: Whether to factor in quality scores.
            
        Returns:
            List of AuctionSlot results, one per filled position.
        """
        if not bids:
            return []
        
        # Calculate ad rank for each bid
        ranked_bids = []
        for bid in bids:
            if bid.bid_amount < self.min_bid:
                continue
            quality = bid.quality_score if apply_quality_score else 1.0
            ad_rank = bid.bid_amount * quality
            ranked_bids.append((ad_rank, bid))
        
        # Sort by ad rank descending
        ranked_bids.sort(key=lambda x: x[0], reverse=True)
        
        slots = []
        for position, (rank, bid) in enumerate(ranked_bids[:self.slots_per_keyword], 1):
            # Price paid is based on next bidder's rank
            if position < len(ranked_bids):
                next_rank, _ = ranked_bids[position]
                winner_qs = bid.quality_score if apply_quality_score else 1.0
                price = (next_rank / winner_qs) + self.min_increment
                price = min(price, bid.bid_amount)
            else:
                price = self.min_bid
            
            # Impressions decay by position
            impressions = int(
                self.base_impressions * (self.impression_decay ** (position - 1))
            )
            
            slots.append(AuctionSlot(
                position=position,
                winner_id=bid.bidder_id,
                price_paid=round(price, 2),
                ad_rank=rank,
                impressions=impressions,
            ))
        
        return slots
    
    def _record_result(self, result: AuctionResult) -> None:
        """Record auction result for statistics."""
        self._auction_history.append(result)
        self._statistics["total_auctions"] += 1
        
        if result.winner_id:
            self._statistics["total_revenue"] += result.price_paid
            
            # Update running averages
            n = self._statistics["total_auctions"]
            self._statistics["avg_winning_bid"] = (
                (self._statistics["avg_winning_bid"] * (n - 1) + result.winning_bid) / n
            )
            self._statistics["avg_participants"] = (
                (self._statistics["avg_participants"] * (n - 1) + len(result.all_participants)) / n
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Return auction statistics."""
        return {
            **self._statistics,
            "history_size": len(self._auction_history),
        }
    
    def get_recent_history(self, limit: int = 100) -> List[AuctionResult]:
        """Get recent auction results."""
        return self._auction_history[-limit:]
    
    def estimate_cost(
        self,
        keyword: str,
        target_position: int,
        historical_bids: Optional[List[AdBid]] = None,
    ) -> float:
        """Estimate cost to win a specific position.
        
        Args:
            keyword: Target keyword.
            target_position: Desired ad position (1 = top).
            historical_bids: Historical bid data for estimation.
            
        Returns:
            Estimated CPC for the target position.
        """
        if not historical_bids:
            # Default estimate based on position
            base_estimate = 1.00
            position_factor = 1.5 ** (4 - min(target_position, 4))
            return base_estimate * position_factor
        
        # Calculate from historical data
        ranked = sorted(
            historical_bids,
            key=lambda b: b.bid_amount * b.quality_score,
            reverse=True
        )
        
        if target_position > len(ranked):
            return self.min_bid
        
        # Need to beat the bid at target position
        target_bid = ranked[target_position - 1]
        return target_bid.bid_amount + self.min_increment
    
    def clear_history(self) -> None:
        """Clear auction history (for testing)."""
        self._auction_history.clear()
        self._statistics = {
            "total_auctions": 0,
            "total_revenue": 0.0,
            "avg_winning_bid": 0.0,
            "avg_participants": 0.0,
        }
