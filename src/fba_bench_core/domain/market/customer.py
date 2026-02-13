"""Customer Agent for Utility-Based Market Simulation.

This module defines the Customer class - a virtual shopper that makes
purchasing decisions based on utility functions. Sales are the result
of thousands of micro-decisions, not a macro-formula.

Key behavioral attributes:
- price_sensitivity: How much price affects purchase decisions
- brand_loyalty: Preference for familiar/trusted sellers
- patience: Willingness to wait for slower shipping
- need_urgency: Urgency of purchase (impulse vs. researched)

Usage:
    from fba_bench_core.domain.market.customer import Customer, CustomerPool
    
    customer = Customer.random(seed=42)
    utility = customer.calculate_utility(price=19.99, reviews=4.5, shipping_days=2)
    
    pool = CustomerPool.generate(count=1000, seed=42)
    for customer in pool:
        # Each customer evaluates products and may purchase
        pass
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class CustomerSegment(str, Enum):
    """Customer behavioral segments for market analysis."""

    BARGAIN_HUNTER = "bargain_hunter"  # High price sensitivity
    PRIME_LOYALIST = "prime_loyalist"  # Values fast shipping
    BRAND_SEEKER = "brand_seeker"  # High brand loyalty
    IMPULSE_BUYER = "impulse_buyer"  # High urgency, low patience
    RESEARCHER = "researcher"  # Low urgency, thorough evaluation
    BALANCED = "balanced"  # Moderate on all dimensions


class Customer(BaseModel):
    """Virtual customer agent that makes purchasing decisions.

    Each customer has behavioral attributes that determine their utility
    function when evaluating products on the virtual shelf. The customer
    with the highest utility for a product (above threshold) makes a purchase.

    Attributes:
        customer_id: Unique identifier for this customer instance.
        price_sensitivity: Weight on price in utility function (0.0-1.0).
            High = very price conscious, avoids expensive items.
        brand_loyalty: Preference for established/reviewed products (0.0-1.0).
            High = prefers products with good reviews/history.
        patience: Willingness to wait for shipping (0.0-1.0).
            High = OK with slow shipping, Low = needs fast delivery.
        need_urgency: How urgently they need to purchase (0.0-1.0).
            High = will buy now, Low = may browse and leave.
        budget: Maximum amount customer will spend (optional).
        segment: Customer behavioral segment for analytics.
    """

    model_config = ConfigDict(
        frozen=True,  # Customers are immutable once created
        extra="forbid",
    )

    customer_id: UUID = Field(default_factory=uuid4)
    price_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    brand_loyalty: float = Field(default=0.3, ge=0.0, le=1.0)
    patience: float = Field(default=0.7, ge=0.0, le=1.0)
    need_urgency: float = Field(default=0.5, ge=0.0, le=1.0)
    budget: Optional[float] = Field(default=None, gt=0)
    segment: CustomerSegment = Field(default=CustomerSegment.BALANCED)

    def calculate_utility(
        self,
        price: float,
        reviews: float,
        shipping_days: int,
        review_count: int = 100,
        base_price: float = 20.0,
    ) -> float:
        """Calculate utility score for a product.

        The utility function balances:
        - Price: Lower is better, weighted by price_sensitivity
        - Reviews: Higher is better, weighted by brand_loyalty
        - Shipping: Faster is better, weighted by (1 - patience)

        Args:
            price: Product price in dollars.
            reviews: Average review rating (1.0-5.0).
            shipping_days: Estimated shipping days (1-14+).
            review_count: Number of reviews (affects confidence).
            base_price: Reference price for normalization.

        Returns:
            Utility score (higher = more likely to purchase).
        """
        # Normalize price relative to base (lower is better)
        price_score = max(0, 1.0 - (price / (base_price * 2)))

        # Review score (0-5 normalized to 0-1)
        review_score = reviews / 5.0

        # Review confidence (more reviews = more trust)
        review_confidence = min(1.0, review_count / 100)
        adjusted_review = review_score * (0.5 + 0.5 * review_confidence)

        # Shipping score (faster is better)
        # 1 day = 1.0, 14+ days = 0.0
        shipping_score = max(0, 1.0 - (shipping_days - 1) / 13)

        # Weight the components
        w_price = self.price_sensitivity
        w_reviews = self.brand_loyalty
        w_shipping = 1.0 - self.patience

        # Normalize weights to sum to 1
        total_weight = w_price + w_reviews + w_shipping
        if total_weight > 0:
            w_price /= total_weight
            w_reviews /= total_weight
            w_shipping /= total_weight
        else:
            w_price = w_reviews = w_shipping = 1 / 3

        utility = (
            w_price * price_score
            + w_reviews * adjusted_review
            + w_shipping * shipping_score
        )

        return utility

    def will_purchase(
        self,
        utility: float,
        base_threshold: float = 0.4,
    ) -> bool:
        """Determine if customer will purchase based on utility.

        The purchase threshold is adjusted by need_urgency:
        - High urgency: Lower threshold (more likely to buy)
        - Low urgency: Higher threshold (more selective)

        Args:
            utility: Calculated utility score.
            base_threshold: Base purchase threshold.

        Returns:
            True if customer will purchase.
        """
        # Urgency adjusts threshold: high urgency = lower bar
        threshold = base_threshold * (1.5 - self.need_urgency)
        return utility >= threshold

    def can_afford(self, price: float) -> bool:
        """Check if product is within customer's budget."""
        if self.budget is None:
            return True
        return price <= self.budget

    def evaluate_shelf(
        self,
        products: List[Dict[str, Any]],
        purchase_threshold: float = 0.4,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate all products on shelf and decide what to buy.

        Customer evaluates each product, calculates utility, and
        purchases the one with maximum utility if above threshold.

        Args:
            products: List of product dicts with keys:
                - price: float
                - reviews: float (1.0-5.0)
                - shipping_days: int
                - review_count: int (optional)
                - sku: str
            purchase_threshold: Minimum utility to purchase.

        Returns:
            The product dict customer will buy, or None if no purchase.
        """
        best_product = None
        best_utility = -float("inf")

        for product in products:
            price = product.get("price", 0)

            # Skip if over budget
            if not self.can_afford(price):
                continue

            utility = self.calculate_utility(
                price=price,
                reviews=product.get("reviews", 3.0),
                shipping_days=product.get("shipping_days", 3),
                review_count=product.get("review_count", 50),
            )

            if utility > best_utility:
                best_utility = utility
                best_product = product

        # Check if best product meets threshold
        if best_product and self.will_purchase(best_utility, purchase_threshold):
            return best_product

        return None

    @classmethod
    def random(
        cls,
        seed: Optional[int] = None,
    ) -> "Customer":
        """Generate a random customer with realistic distributions.

        Uses normal distributions centered on typical values with
        some variance to create diverse customer base.
        """
        rng = random.Random(seed)

        # Generate attributes with bounded normal distribution
        def bounded_normal(mean: float, std: float) -> float:
            value = rng.gauss(mean, std)
            return max(0.0, min(1.0, value))

        price_sensitivity = bounded_normal(0.5, 0.2)
        brand_loyalty = bounded_normal(0.4, 0.2)
        patience = bounded_normal(0.6, 0.2)
        need_urgency = bounded_normal(0.5, 0.25)

        # Determine segment based on dominant attribute
        segment = cls._determine_segment(
            price_sensitivity, brand_loyalty, patience, need_urgency
        )

        # Budget: some customers have limits, most don't
        budget = None
        if rng.random() < 0.3:  # 30% have a budget
            budget = rng.gauss(50, 30)
            budget = max(10, budget)  # Minimum $10 budget

        return cls(
            price_sensitivity=price_sensitivity,
            brand_loyalty=brand_loyalty,
            patience=patience,
            need_urgency=need_urgency,
            budget=budget,
            segment=segment,
        )

    @staticmethod
    def _determine_segment(
        price_sensitivity: float,
        brand_loyalty: float,
        patience: float,
        need_urgency: float,
    ) -> CustomerSegment:
        """Determine customer segment based on dominant attributes."""

        # Find dominant attribute
        attrs = {
            CustomerSegment.BARGAIN_HUNTER: price_sensitivity,
            CustomerSegment.BRAND_SEEKER: brand_loyalty,
            CustomerSegment.PRIME_LOYALIST: (1 - patience),  # Wants fast shipping
            CustomerSegment.IMPULSE_BUYER: need_urgency,
            CustomerSegment.RESEARCHER: (1 - need_urgency),
        }

        max_attr = max(attrs.values())

        # Need clear dominance (>0.7) to assign segment
        for segment, value in attrs.items():
            if value == max_attr and value > 0.7:
                return segment

        return CustomerSegment.BALANCED


class CustomerPool:
    """Generator for pools of customer agents.

    Creates deterministic or random pools of customers for market simulation.
    """

    def __init__(self, customers: List[Customer]):
        """Initialize pool with existing customers."""
        self._customers = customers

    def __iter__(self):
        return iter(self._customers)

    def __len__(self):
        return len(self._customers)

    def __getitem__(self, idx: int) -> Customer:
        return self._customers[idx]

    @classmethod
    def generate(
        cls,
        count: int = 1000,
        seed: Optional[int] = None,
    ) -> "CustomerPool":
        """Generate a pool of random customers.

        Args:
            count: Number of customers to generate.
            seed: Random seed for reproducibility.

        Returns:
            CustomerPool with generated customers.
        """
        customers = []
        for i in range(count):
            # Each customer gets deterministic seed based on pool seed
            customer_seed = seed + i if seed is not None else None
            customers.append(Customer.random(seed=customer_seed))

        return cls(customers)

    def get_segment_distribution(self) -> Dict[CustomerSegment, int]:
        """Return count of customers by segment."""
        distribution: Dict[CustomerSegment, int] = {}
        for customer in self._customers:
            segment = customer.segment
            distribution[segment] = distribution.get(segment, 0) + 1
        return distribution

    def filter_by_segment(self, segment: CustomerSegment) -> "CustomerPool":
        """Return a new pool with only customers of specified segment."""
        filtered = [c for c in self._customers if c.segment == segment]
        return CustomerPool(filtered)

    def filter_by_budget(
        self,
        min_budget: Optional[float] = None,
        max_budget: Optional[float] = None,
    ) -> "CustomerPool":
        """Return a new pool filtered by budget range."""
        filtered = []
        for customer in self._customers:
            if customer.budget is None:
                # No budget = unlimited, include if no max specified
                if max_budget is None:
                    filtered.append(customer)
                continue

            if min_budget is not None and customer.budget < min_budget:
                continue
            if max_budget is not None and customer.budget > max_budget:
                continue
            filtered.append(customer)

        return CustomerPool(filtered)
