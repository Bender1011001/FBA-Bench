"""Unified CustomerEventService with Money type integration and comprehensive event tracking."""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from money import Money

from fba_bench_core.models.product import Product


class CustomerEventType(Enum):
    """Types of customer events."""

    PURCHASE = "purchase"
    VIEW = "view"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    WISHLIST_ADD = "wishlist_add"
    REVIEW = "review"
    RETURN = "return"
    COMPLAINT = "complaint"
    INQUIRY = "inquiry"
    PRICE_ALERT = "price_alert"


class CustomerSegment(Enum):
    """Customer segments for targeted behavior."""

    PRICE_SENSITIVE = "price_sensitive"
    QUALITY_FOCUSED = "quality_focused"
    CONVENIENCE_FOCUSED = "convenience_focused"
    BRAND_LOYAL = "brand_loyal"
    IMPULSE_BUYER = "impulse_buyer"
    RESEARCHER = "researcher"


@dataclass
class CustomerEvent:
    """Individual customer event with financial and behavioral context."""

    event_id: str
    customer_id: str
    product_id: str
    event_type: CustomerEventType
    timestamp: datetime
    financial_impact: Money
    metadata: Dict[str, Any] = field(default_factory=dict)
    customer_segment: Optional[CustomerSegment] = None
    confidence: float = 1.0


@dataclass
class CustomerBehaviorProfile:
    """Customer behavior profile for simulation."""

    customer_id: str
    segment: CustomerSegment
    price_sensitivity: float  # 0.0 to 1.0
    quality_sensitivity: float  # 0.0 to 1.0
    brand_loyalty: float  # 0.0 to 1.0
    purchase_frequency: float  # Events per day
    average_order_value: Money
    return_rate: float  # 0.0 to 1.0
    review_likelihood: float  # 0.0 to 1.0
    complaint_threshold: float  # 0.0 to 1.0


class CustomerEventService:
    """
    Unified customer event service with Money type integration.

    Combines clean architecture from fba_bench_good_sim with
    comprehensive event tracking and financial accuracy from FBA-bench-main.
    """

    def __init__(self, config: Dict):
        """Initialize customer event service with configuration."""
        self.config = config
        self.events: List[CustomerEvent] = []
        self.customer_profiles: Dict[str, CustomerBehaviorProfile] = {}

        # Event generation parameters
        self.base_event_rate = config.get("base_event_rate", 10.0)  # Events per hour
        self.price_elasticity = config.get("price_elasticity", -1.5)
        self.quality_impact_factor = config.get("quality_impact_factor", 0.3)

        # Customer segment distributions
        self.segment_distribution = config.get(
            "customer_segment_distribution",
            {
                CustomerSegment.PRICE_SENSITIVE.value: 0.25,
                CustomerSegment.QUALITY_FOCUSED.value: 0.20,
                CustomerSegment.CONVENIENCE_FOCUSED.value: 0.15,
                CustomerSegment.BRAND_LOYAL.value: 0.15,
                CustomerSegment.IMPULSE_BUYER.value: 0.15,
                CustomerSegment.RESEARCHER.value: 0.10,
            },
        )

        # Event type probabilities by segment
        self.segment_event_probabilities = self._load_segment_event_probabilities()

        # Financial impact ranges
        self.purchase_value_ranges = config.get(
            "purchase_value_ranges",
            {
                "low": (Money.from_dollars(5.0), Money.from_dollars(25.0)),
                "medium": (Money.from_dollars(25.0), Money.from_dollars(100.0)),
                "high": (Money.from_dollars(100.0), Money.from_dollars(500.0)),
            },
        )

    def _load_segment_event_probabilities(self) -> Dict:
        """Load event type probabilities for each customer segment."""
        return {
            CustomerSegment.PRICE_SENSITIVE: {
                CustomerEventType.VIEW: 0.40,
                CustomerEventType.CART_ADD: 0.15,
                CustomerEventType.PURCHASE: 0.20,
                CustomerEventType.PRICE_ALERT: 0.15,
                CustomerEventType.RETURN: 0.05,
                CustomerEventType.REVIEW: 0.03,
                CustomerEventType.COMPLAINT: 0.02,
            },
            CustomerSegment.QUALITY_FOCUSED: {
                CustomerEventType.VIEW: 0.30,
                CustomerEventType.CART_ADD: 0.20,
                CustomerEventType.PURCHASE: 0.25,
                CustomerEventType.REVIEW: 0.15,
                CustomerEventType.RETURN: 0.05,
                CustomerEventType.INQUIRY: 0.03,
                CustomerEventType.COMPLAINT: 0.02,
            },
            CustomerSegment.CONVENIENCE_FOCUSED: {
                CustomerEventType.VIEW: 0.25,
                CustomerEventType.CART_ADD: 0.25,
                CustomerEventType.PURCHASE: 0.35,
                CustomerEventType.RETURN: 0.08,
                CustomerEventType.REVIEW: 0.05,
                CustomerEventType.COMPLAINT: 0.02,
            },
            CustomerSegment.BRAND_LOYAL: {
                CustomerEventType.VIEW: 0.20,
                CustomerEventType.CART_ADD: 0.15,
                CustomerEventType.PURCHASE: 0.40,
                CustomerEventType.REVIEW: 0.20,
                CustomerEventType.RETURN: 0.03,
                CustomerEventType.COMPLAINT: 0.02,
            },
            CustomerSegment.IMPULSE_BUYER: {
                CustomerEventType.VIEW: 0.35,
                CustomerEventType.CART_ADD: 0.30,
                CustomerEventType.PURCHASE: 0.25,
                CustomerEventType.CART_REMOVE: 0.05,
                CustomerEventType.RETURN: 0.03,
                CustomerEventType.REVIEW: 0.02,
            },
            CustomerSegment.RESEARCHER: {
                CustomerEventType.VIEW: 0.50,
                CustomerEventType.CART_ADD: 0.20,
                CustomerEventType.PURCHASE: 0.15,
                CustomerEventType.REVIEW: 0.08,
                CustomerEventType.INQUIRY: 0.05,
                CustomerEventType.RETURN: 0.02,
            },
        }

    def generate_customer_profile(self, customer_id: str) -> CustomerBehaviorProfile:
        """Generate a realistic customer behavior profile."""
        # Select segment based on distribution
        segments = list(self.segment_distribution.keys())
        weights = list(self.segment_distribution.values())
        segment = CustomerSegment(random.choices(segments, weights=weights)[0])

        # Generate segment-specific characteristics
        if segment == CustomerSegment.PRICE_SENSITIVE:
            profile = CustomerBehaviorProfile(
                customer_id=customer_id,
                segment=segment,
                price_sensitivity=random.uniform(0.8, 1.0),
                quality_sensitivity=random.uniform(0.3, 0.6),
                brand_loyalty=random.uniform(0.1, 0.4),
                purchase_frequency=random.uniform(0.5, 2.0),
                average_order_value=Money.from_dollars(random.uniform(15.0, 50.0)),
                return_rate=random.uniform(0.08, 0.15),
                review_likelihood=random.uniform(0.15, 0.30),
                complaint_threshold=random.uniform(0.6, 0.8),
            )
        elif segment == CustomerSegment.QUALITY_FOCUSED:
            profile = CustomerBehaviorProfile(
                customer_id=customer_id,
                segment=segment,
                price_sensitivity=random.uniform(0.2, 0.5),
                quality_sensitivity=random.uniform(0.8, 1.0),
                brand_loyalty=random.uniform(0.6, 0.9),
                purchase_frequency=random.uniform(0.3, 1.0),
                average_order_value=Money.from_dollars(random.uniform(50.0, 200.0)),
                return_rate=random.uniform(0.03, 0.08),
                review_likelihood=random.uniform(0.40, 0.70),
                complaint_threshold=random.uniform(0.3, 0.5),
            )
        elif segment == CustomerSegment.CONVENIENCE_FOCUSED:
            profile = CustomerBehaviorProfile(
                customer_id=customer_id,
                segment=segment,
                price_sensitivity=random.uniform(0.4, 0.7),
                quality_sensitivity=random.uniform(0.5, 0.8),
                brand_loyalty=random.uniform(0.3, 0.6),
                purchase_frequency=random.uniform(1.0, 3.0),
                average_order_value=Money.from_dollars(random.uniform(25.0, 100.0)),
                return_rate=random.uniform(0.05, 0.12),
                review_likelihood=random.uniform(0.10, 0.25),
                complaint_threshold=random.uniform(0.7, 0.9),
            )
        elif segment == CustomerSegment.BRAND_LOYAL:
            profile = CustomerBehaviorProfile(
                customer_id=customer_id,
                segment=segment,
                price_sensitivity=random.uniform(0.1, 0.4),
                quality_sensitivity=random.uniform(0.7, 0.9),
                brand_loyalty=random.uniform(0.8, 1.0),
                purchase_frequency=random.uniform(0.8, 2.5),
                average_order_value=Money.from_dollars(random.uniform(40.0, 150.0)),
                return_rate=random.uniform(0.02, 0.06),
                review_likelihood=random.uniform(0.50, 0.80),
                complaint_threshold=random.uniform(0.2, 0.4),
            )
        elif segment == CustomerSegment.IMPULSE_BUYER:
            profile = CustomerBehaviorProfile(
                customer_id=customer_id,
                segment=segment,
                price_sensitivity=random.uniform(0.5, 0.8),
                quality_sensitivity=random.uniform(0.3, 0.6),
                brand_loyalty=random.uniform(0.2, 0.5),
                purchase_frequency=random.uniform(1.5, 4.0),
                average_order_value=Money.from_dollars(random.uniform(10.0, 75.0)),
                return_rate=random.uniform(0.10, 0.20),
                review_likelihood=random.uniform(0.05, 0.15),
                complaint_threshold=random.uniform(0.8, 1.0),
            )
        else:  # RESEARCHER
            profile = CustomerBehaviorProfile(
                customer_id=customer_id,
                segment=segment,
                price_sensitivity=random.uniform(0.6, 0.9),
                quality_sensitivity=random.uniform(0.8, 1.0),
                brand_loyalty=random.uniform(0.4, 0.7),
                purchase_frequency=random.uniform(0.2, 0.8),
                average_order_value=Money.from_dollars(random.uniform(30.0, 120.0)),
                return_rate=random.uniform(0.03, 0.07),
                review_likelihood=random.uniform(0.30, 0.60),
                complaint_threshold=random.uniform(0.4, 0.6),
            )

        self.customer_profiles[customer_id] = profile
        return profile

    def simulate_customer_events(
        self, product: Product, market_conditions: Dict, duration_hours: float = 1.0
    ) -> List[CustomerEvent]:
        """
        Simulate customer events for a product over a time period.

        Args:
            product: Product being simulated
            market_conditions: Current market conditions (price, competitors, etc.)
            duration_hours: Simulation duration in hours

        Returns:
            List of generated customer events
        """
        events = []

        # Calculate event rate based on market conditions
        base_rate = self.base_event_rate * duration_hours

        # Adjust rate based on price competitiveness
        our_price = market_conditions.get("our_price", product.current_price)
        competitor_avg_price = market_conditions.get("competitor_avg_price", our_price)

        if competitor_avg_price.cents != 0:
            price_ratio = float(our_price / competitor_avg_price)
            # Apply price elasticity
            price_adjustment = price_ratio**self.price_elasticity
            adjusted_rate = base_rate * price_adjustment
        else:
            adjusted_rate = base_rate

        # Adjust rate based on trust score
        trust_score = market_conditions.get("trust_score", 0.7)
        trust_adjustment = 0.5 + (trust_score * 0.5)  # Scale from 0.5 to 1.0
        final_rate = adjusted_rate * trust_adjustment

        # Generate events
        num_events = max(0, int(np.random.poisson(final_rate)))

        for _ in range(num_events):
            event = self._generate_single_event(product, market_conditions)
            if event:
                events.append(event)

        self.events.extend(events)
        return events

    def _generate_single_event(
        self, product: Product, market_conditions: Dict
    ) -> Optional[CustomerEvent]:
        """Generate a single customer event."""
        # Select or create customer
        customer_id = self._select_customer()
        profile = self.customer_profiles.get(customer_id)

        if not profile:
            profile = self.generate_customer_profile(customer_id)

        # Select event type based on customer segment
        event_type = self._select_event_type(profile)

        # Calculate financial impact
        financial_impact = self._calculate_event_financial_impact(
            event_type, profile, product, market_conditions
        )

        # Generate metadata
        metadata = self._generate_event_metadata(
            event_type, profile, product, market_conditions
        )

        # Calculate confidence based on market conditions
        confidence = self._calculate_event_confidence(event_type, market_conditions)

        return CustomerEvent(
            event_id=f"{customer_id}_{int(datetime.now().timestamp())}_{random.randint(1000, 9999)}",
            customer_id=customer_id,
            product_id=product.product_id,
            event_type=event_type,
            timestamp=datetime.now(),
            financial_impact=financial_impact,
            metadata=metadata,
            customer_segment=profile.segment,
            confidence=confidence,
        )

    def _select_customer(self) -> str:
        """Select an existing customer or create a new one."""
        # 70% chance to use existing customer, 30% chance for new customer
        if self.customer_profiles and random.random() < 0.7:
            return random.choice(list(self.customer_profiles.keys()))
        else:
            return f"customer_{len(self.customer_profiles) + 1}_{random.randint(1000, 9999)}"

    def _select_event_type(self, profile: CustomerBehaviorProfile) -> CustomerEventType:
        """Select event type based on customer profile."""
        probabilities = self.segment_event_probabilities[profile.segment]
        event_types = list(probabilities.keys())
        weights = list(probabilities.values())

        return random.choices(event_types, weights=weights)[0]

    def _calculate_event_financial_impact(
        self,
        event_type: CustomerEventType,
        profile: CustomerBehaviorProfile,
        product: Product,
        market_conditions: Dict,
    ) -> Money:
        """Calculate the financial impact of an event."""
        if event_type == CustomerEventType.PURCHASE:
            # Purchase value based on product price and customer profile
            base_value = market_conditions.get("our_price", product.current_price)

            # Adjust based on customer's average order value
            value_adjustment = float(profile.average_order_value / base_value)
            value_adjustment = max(0.5, min(2.0, value_adjustment))  # Bound adjustment

            return base_value * value_adjustment

        elif event_type == CustomerEventType.RETURN:
            # Return value is typically the purchase price
            return market_conditions.get("our_price", product.current_price) * -1

        elif event_type in [CustomerEventType.VIEW, CustomerEventType.CART_ADD]:
            # These events have potential future value
            conversion_probability = (
                0.05 if event_type == CustomerEventType.VIEW else 0.20
            )
            potential_value = market_conditions.get("our_price", product.current_price)
            return potential_value * conversion_probability

        else:
            # Other events have minimal direct financial impact
            return Money.zero()

    def _generate_event_metadata(
        self,
        event_type: CustomerEventType,
        profile: CustomerBehaviorProfile,
        product: Product,
        market_conditions: Dict,
    ) -> Dict:
        """Generate event-specific metadata."""
        metadata = {
            "customer_segment": profile.segment.value,
            "price_sensitivity": profile.price_sensitivity,
            "quality_sensitivity": profile.quality_sensitivity,
        }

        if event_type == CustomerEventType.PURCHASE:
            metadata.update(
                {
                    "payment_method": random.choice(
                        ["credit_card", "debit_card", "gift_card"]
                    ),
                    "shipping_speed": random.choice(
                        ["standard", "expedited", "overnight"]
                    ),
                    "is_repeat_customer": random.random() < 0.6,
                }
            )

        elif event_type == CustomerEventType.REVIEW:
            # Generate review rating based on quality sensitivity
            base_rating = 3.5
            quality_adjustment = (profile.quality_sensitivity - 0.5) * 2  # -1 to 1
            rating = max(
                1, min(5, base_rating + quality_adjustment + random.uniform(-0.5, 0.5))
            )

            metadata.update(
                {
                    "rating": round(rating, 1),
                    "has_text": random.random() < 0.7,
                    "verified_purchase": random.random() < 0.8,
                }
            )

        elif event_type == CustomerEventType.RETURN:
            reasons = [
                "defective",
                "not_as_described",
                "wrong_size",
                "changed_mind",
                "found_better_price",
            ]
            weights = [0.15, 0.20, 0.25, 0.30, 0.10]

            metadata.update(
                {
                    "return_reason": random.choices(reasons, weights=weights)[0],
                    "days_since_purchase": random.randint(1, 30),
                    "condition": random.choice(["new", "used", "damaged"]),
                }
            )

        elif event_type == CustomerEventType.COMPLAINT:
            complaint_types = [
                "shipping_delay",
                "product_quality",
                "customer_service",
                "pricing",
                "other",
            ]
            metadata.update(
                {
                    "complaint_type": random.choice(complaint_types),
                    "severity": random.choice(["low", "medium", "high"]),
                    "resolution_requested": random.choice(
                        ["refund", "replacement", "explanation", "compensation"]
                    ),
                }
            )

        return metadata

    def _calculate_event_confidence(
        self, event_type: CustomerEventType, market_conditions: Dict
    ) -> float:
        """Calculate confidence level for the event."""
        base_confidence = 0.8

        # Adjust based on market stability
        market_volatility = market_conditions.get("volatility", 0.1)
        volatility_adjustment = 1.0 - (market_volatility * 0.5)

        # Adjust based on trust score
        trust_score = market_conditions.get("trust_score", 0.7)
        trust_adjustment = 0.8 + (trust_score * 0.2)

        confidence = base_confidence * volatility_adjustment * trust_adjustment
        return max(0.1, min(1.0, confidence))

    def get_customer_profile(
        self, customer_id: str
    ) -> Optional[CustomerBehaviorProfile]:
        """Get customer behavior profile."""
        return self.customer_profiles.get(customer_id)

    def get_events_by_type(
        self, event_type: CustomerEventType, hours_back: int = 24
    ) -> List[CustomerEvent]:
        """Get events of a specific type within a time window."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        return [
            event
            for event in self.events
            if event.event_type == event_type and event.timestamp >= cutoff_time
        ]

    def get_customer_events(
        self, customer_id: str, hours_back: int = 24
    ) -> List[CustomerEvent]:
        """Get all events for a specific customer."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        return [
            event
            for event in self.events
            if event.customer_id == customer_id and event.timestamp >= cutoff_time
        ]

    def get_product_events(
        self, product_id: str, hours_back: int = 24
    ) -> List[CustomerEvent]:
        """Get all events for a specific product."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        return [
            event
            for event in self.events
            if event.product_id == product_id and event.timestamp >= cutoff_time
        ]

    def calculate_conversion_metrics(
        self, product_id: str, hours_back: int = 24
    ) -> Dict:
        """Calculate conversion metrics for a product."""
        product_events = self.get_product_events(product_id, hours_back)

        if not product_events:
            return {
                "view_to_cart_rate": 0.0,
                "cart_to_purchase_rate": 0.0,
                "overall_conversion_rate": 0.0,
                "total_views": 0,
                "total_cart_adds": 0,
                "total_purchases": 0,
            }

        # Count events by type
        event_counts = {}
        for event in product_events:
            event_type = event.event_type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        views = event_counts.get(CustomerEventType.VIEW, 0)
        cart_adds = event_counts.get(CustomerEventType.CART_ADD, 0)
        purchases = event_counts.get(CustomerEventType.PURCHASE, 0)

        # Calculate rates
        view_to_cart_rate = (cart_adds / views) if views > 0 else 0.0
        cart_to_purchase_rate = (purchases / cart_adds) if cart_adds > 0 else 0.0
        overall_conversion_rate = (purchases / views) if views > 0 else 0.0

        return {
            "view_to_cart_rate": view_to_cart_rate,
            "cart_to_purchase_rate": cart_to_purchase_rate,
            "overall_conversion_rate": overall_conversion_rate,
            "total_views": views,
            "total_cart_adds": cart_adds,
            "total_purchases": purchases,
        }

    def get_revenue_by_segment(self, hours_back: int = 24) -> Dict:
        """Get revenue breakdown by customer segment."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        segment_revenue = {}

        for event in self.events:
            if (
                event.timestamp >= cutoff_time
                and event.event_type == CustomerEventType.PURCHASE
                and event.customer_segment
            ):
                segment = event.customer_segment.value
                if segment not in segment_revenue:
                    segment_revenue[segment] = Money.zero()

                segment_revenue[segment] += event.financial_impact

        return segment_revenue

    def clear_old_events(self, days_to_keep: int = 30) -> int:
        """Clear events older than specified days."""
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)

        old_count = len(self.events)
        self.events = [event for event in self.events if event.timestamp >= cutoff_time]

        return old_count - len(self.events)

    def get_statistics(self) -> Dict:
        """Get customer event service statistics."""
        if not self.events:
            return {
                "total_events": 0,
                "total_customers": 0,
                "total_revenue": Money.zero(),
                "event_type_distribution": {},
                "segment_distribution": {},
            }

        # Calculate statistics
        total_revenue = sum(
            (
                event.financial_impact
                for event in self.events
                if event.event_type == CustomerEventType.PURCHASE
            ),
            Money.zero(),
        )

        # Event type distribution
        event_type_dist = {}
        for event in self.events:
            event_type = event.event_type.value
            event_type_dist[event_type] = event_type_dist.get(event_type, 0) + 1

        # Segment distribution
        segment_dist = {}
        for profile in self.customer_profiles.values():
            segment = profile.segment.value
            segment_dist[segment] = segment_dist.get(segment, 0) + 1

        return {
            "total_events": len(self.events),
            "total_customers": len(self.customer_profiles),
            "total_revenue": total_revenue,
            "event_type_distribution": event_type_dist,
            "segment_distribution": segment_dist,
            "average_order_value": (
                total_revenue / max(1, event_type_dist.get("purchase", 1))
            ),
        }
