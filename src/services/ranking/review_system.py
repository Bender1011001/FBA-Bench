"""Review and Ranking System - Sales Velocity → Reviews → Organic Rank.

This module implements the feedback loop between sales velocity, customer reviews,
and organic search ranking (BSR). The flywheel effect:

1. Sales velocity increases
2. More customers = more reviews
3. Better reviews = higher conversion rate
4. Higher conversion = better BSR
5. Better BSR = more organic visibility
6. More visibility = more sales (back to 1)

This creates realistic competitive dynamics where building momentum matters.

Usage:
    from services.ranking.review_system import ReviewSystem
    
    system = ReviewSystem(seed=42)
    system.process_sale(asin="B001", units_sold=5)
    bsr = system.get_bsr("B001")
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ReviewSentiment(str, Enum):
    """Review sentiment classification."""

    POSITIVE = "positive"  # 4-5 stars
    NEUTRAL = "neutral"  # 3 stars
    NEGATIVE = "negative"  # 1-2 stars


@dataclass
class Review:
    """A customer review."""

    review_id: str
    asin: str
    rating: float  # 1.0 to 5.0
    timestamp: datetime
    verified_purchase: bool = True
    helpful_votes: int = 0
    sentiment: ReviewSentiment = ReviewSentiment.NEUTRAL


@dataclass
class ProductRankingState:
    """Ranking state for a product."""

    asin: str
    total_sales: int = 0
    sales_velocity_7d: float = 0.0  # Units per day over last 7 days
    sales_velocity_30d: float = 0.0  # Units per day over last 30 days
    reviews: List[Review] = field(default_factory=list)
    average_rating: float = 0.0
    review_count: int = 0
    bsr: int = 200_000  # Best Seller Rank (lower is better)
    organic_visibility: float = 1.0  # Multiplier for organic traffic
    last_updated_tick: int = 0


class ReviewSystem:
    """Review and ranking system with sales velocity feedback.

    Key mechanics:
    1. Sales trigger probabilistic review generation
    2. Reviews affect average rating and count
    3. Sales velocity affects BSR
    4. BSR affects organic visibility
    5. Organic visibility feeds back to demand

    Attributes:
        review_probability: Chance a sale generates a review (default 3%)
        rating_mean: Average rating for generated reviews
        rating_std: Standard deviation of ratings
        bsr_decay_rate: How quickly BSR decays without sales
        velocity_smoothing: Exponential smoothing factor for velocity
    """

    # Review generation parameters
    DEFAULT_REVIEW_PROBABILITY = 0.03  # 3% of buyers leave reviews
    DEFAULT_RATING_MEAN = 4.2
    DEFAULT_RATING_STD = 0.8

    # BSR parameters
    MAX_BSR = 2_000_000
    MIN_BSR = 1
    BSR_DECAY_RATE = 0.02  # Daily decay towards max

    def __init__(
        self,
        seed: Optional[int] = None,
        review_probability: float = DEFAULT_REVIEW_PROBABILITY,
        rating_mean: float = DEFAULT_RATING_MEAN,
        rating_std: float = DEFAULT_RATING_STD,
    ):
        """Initialize the review system.

        Args:
            seed: Random seed for deterministic behavior.
            review_probability: Chance each sale generates a review.
            rating_mean: Mean rating for generated reviews.
            rating_std: Standard deviation of ratings.
        """
        self._seed = seed
        self._rng = random.Random(seed)
        self._review_probability = review_probability
        self._rating_mean = rating_mean
        self._rating_std = rating_std

        # Product states
        self._products: Dict[str, ProductRankingState] = {}

        # Sales history for velocity calculation (asin -> list of (tick, units))
        self._sales_history: Dict[str, List[tuple[int, int]]] = {}

        # Current tick
        self._current_tick = 0

        # Statistics
        self._stats = {
            "total_reviews_generated": 0,
            "total_sales_processed": 0,
            "average_rating_overall": 0.0,
        }

    def get_or_create_product(self, asin: str) -> ProductRankingState:
        """Get or create a product ranking state."""
        if asin not in self._products:
            self._products[asin] = ProductRankingState(asin=asin)
        return self._products[asin]

    def process_sale(
        self,
        asin: str,
        units_sold: int,
        tick: Optional[int] = None,
    ) -> List[Review]:
        """Process a sale and potentially generate reviews.

        Args:
            asin: Product ASIN.
            units_sold: Number of units sold.
            tick: Current simulation tick.

        Returns:
            List of reviews generated from this sale.
        """
        if tick is not None:
            self._current_tick = tick

        product = self.get_or_create_product(asin)
        product.total_sales += units_sold
        product.last_updated_tick = self._current_tick

        # Record sales for velocity calculation
        if asin not in self._sales_history:
            self._sales_history[asin] = []
        self._sales_history[asin].append((self._current_tick, units_sold))

        # Prune old sales history (keep last 30 "days")
        cutoff = self._current_tick - 30
        self._sales_history[asin] = [
            (t, u) for t, u in self._sales_history[asin] if t > cutoff
        ]

        # Update velocity
        self._update_velocity(asin)

        # Update BSR based on velocity
        self._update_bsr(asin)

        self._stats["total_sales_processed"] += units_sold

        # Generate reviews probabilistically
        reviews = self._generate_reviews(asin, units_sold)

        return reviews

    def _generate_reviews(
        self,
        asin: str,
        units_sold: int,
    ) -> List[Review]:
        """Generate reviews based on sales."""
        reviews = []
        product = self._products[asin]

        for _ in range(units_sold):
            if self._rng.random() < self._review_probability:
                # Generate rating from truncated normal distribution
                rating = self._rng.gauss(self._rating_mean, self._rating_std)
                rating = max(1.0, min(5.0, rating))
                rating = round(rating * 2) / 2  # Round to nearest 0.5

                # Determine sentiment
                if rating >= 4.0:
                    sentiment = ReviewSentiment.POSITIVE
                elif rating >= 3.0:
                    sentiment = ReviewSentiment.NEUTRAL
                else:
                    sentiment = ReviewSentiment.NEGATIVE

                review = Review(
                    review_id=f"review_{asin}_{len(product.reviews)}_{self._current_tick}",
                    asin=asin,
                    rating=rating,
                    timestamp=datetime.now(),
                    verified_purchase=True,
                    sentiment=sentiment,
                )

                product.reviews.append(review)
                reviews.append(review)
                self._stats["total_reviews_generated"] += 1

        # Update average rating
        if product.reviews:
            product.review_count = len(product.reviews)
            product.average_rating = sum(r.rating for r in product.reviews) / len(
                product.reviews
            )

            # Update overall stats
            all_ratings = [r.rating for p in self._products.values() for r in p.reviews]
            if all_ratings:
                self._stats["average_rating_overall"] = sum(all_ratings) / len(
                    all_ratings
                )

        return reviews

    def _update_velocity(self, asin: str) -> None:
        """Update sales velocity metrics."""
        product = self._products[asin]
        history = self._sales_history.get(asin, [])

        # 7-day velocity
        cutoff_7d = self._current_tick - 7
        sales_7d = sum(u for t, u in history if t > cutoff_7d)
        product.sales_velocity_7d = sales_7d / 7.0

        # 30-day velocity
        cutoff_30d = self._current_tick - 30
        sales_30d = sum(u for t, u in history if t > cutoff_30d)
        product.sales_velocity_30d = sales_30d / 30.0

    def _update_bsr(self, asin: str) -> None:
        """Update BSR based on sales velocity.

        Higher velocity = lower (better) BSR.
        BSR is relative to maximum possible rank.
        """
        product = self._products[asin]

        # Use 7-day velocity as primary signal
        velocity = product.sales_velocity_7d

        if velocity <= 0:
            # Decay BSR towards max
            product.bsr = min(
                self.MAX_BSR, int(product.bsr * (1 + self.BSR_DECAY_RATE))
            )
        else:
            # Calculate BSR from velocity
            # High velocity = low BSR
            # velocity of 100/day = BSR ~1, velocity of 1/day = BSR ~10,000
            target_bsr = max(self.MIN_BSR, int(10000 / (velocity + 0.1)))

            # Smooth towards target
            product.bsr = int(product.bsr * 0.7 + target_bsr * 0.3)
            product.bsr = max(self.MIN_BSR, min(self.MAX_BSR, product.bsr))

        # Update organic visibility based on BSR
        # BSR 1-100 = 2.0x visibility, BSR 100,000+ = 0.5x visibility
        if product.bsr <= 100:
            product.organic_visibility = 2.0
        elif product.bsr <= 1000:
            product.organic_visibility = 1.5
        elif product.bsr <= 10000:
            product.organic_visibility = 1.2
        elif product.bsr <= 100000:
            product.organic_visibility = 1.0
        else:
            product.organic_visibility = 0.5

    def process_tick(self, tick: int) -> None:
        """Process tick updates (decay BSR for inactive products)."""
        self._current_tick = tick

        for asin, product in self._products.items():
            # Decay BSR if no recent sales
            ticks_since_sale = tick - product.last_updated_tick
            if ticks_since_sale > 0:
                decay_factor = (1 + self.BSR_DECAY_RATE) ** min(ticks_since_sale, 7)
                product.bsr = min(self.MAX_BSR, int(product.bsr * decay_factor))

    def get_bsr(self, asin: str) -> int:
        """Get current BSR for a product."""
        product = self._products.get(asin)
        return product.bsr if product else self.MAX_BSR

    def get_organic_visibility(self, asin: str) -> float:
        """Get organic visibility multiplier."""
        product = self._products.get(asin)
        return product.organic_visibility if product else 1.0

    def get_average_rating(self, asin: str) -> float:
        """Get average rating for a product."""
        product = self._products.get(asin)
        return product.average_rating if product else 0.0

    def get_review_count(self, asin: str) -> int:
        """Get review count for a product."""
        product = self._products.get(asin)
        return product.review_count if product else 0

    def get_product_state(self, asin: str) -> Optional[ProductRankingState]:
        """Get full product ranking state."""
        return self._products.get(asin)

    def get_statistics(self) -> Dict[str, Any]:
        """Return system statistics."""
        return {
            **self._stats,
            "products_tracked": len(self._products),
            "current_tick": self._current_tick,
        }

    def simulate_review_injection(
        self,
        asin: str,
        rating: float,
        count: int = 1,
    ) -> List[Review]:
        """Manually inject reviews (for testing or initial state).

        Args:
            asin: Product ASIN.
            rating: Rating to inject (1.0-5.0).
            count: Number of reviews to inject.

        Returns:
            List of injected reviews.
        """
        product = self.get_or_create_product(asin)
        reviews = []

        rating = max(1.0, min(5.0, rating))
        if rating >= 4.0:
            sentiment = ReviewSentiment.POSITIVE
        elif rating >= 3.0:
            sentiment = ReviewSentiment.NEUTRAL
        else:
            sentiment = ReviewSentiment.NEGATIVE

        for i in range(count):
            review = Review(
                review_id=f"injected_{asin}_{len(product.reviews)}_{i}",
                asin=asin,
                rating=rating,
                timestamp=datetime.now(),
                verified_purchase=False,  # Mark as not verified
                sentiment=sentiment,
            )
            product.reviews.append(review)
            reviews.append(review)

        # Update average
        product.review_count = len(product.reviews)
        product.average_rating = sum(r.rating for r in product.reviews) / len(
            product.reviews
        )

        return reviews
