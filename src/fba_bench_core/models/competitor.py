"""Competitor model compatible with both legacy dict-based construction and
newer explicit keyword-based construction used by integration tests.

This class intentionally supports two initialization modes to avoid breaking
existing call sites:
- Legacy: Competitor(data: Dict[str, Any])
- Explicit: Competitor(asin="...", price=Money(...), sales_velocity=..., bsr=..., strategy="...", trust_score=...)

In explicit mode, attributes commonly used in event-driven flows (asin, price,
bsr, sales_velocity, strategy, trust_score) are set. In legacy mode, the original
fields (id, name, market_share, strengths, weaknesses, products, pricing_strategy,
market_position, recent_activities) are populated exactly as before.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from money import Money


class Competitor:
    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs: Any):
        """
        Initialize a Competitor either from a dictionary (legacy) or explicit kwargs.

        Legacy mode (preserved for unit tests):
            Competitor({"id": "...", "name": "...", "market_share": 0.1, ...})

        Explicit mode (used by integration tests):
            Competitor(
                asin="B001",
                price=Money.from_dollars(18.99),
                sales_velocity=1.2,
                bsr=5000,
                strategy="aggressive",
                trust_score=0.85,
                persona=<optional>
            )
        """
        if data is not None and not kwargs:
            # ---- Legacy dict-based initialization (unchanged behavior) ----
            # Basic identity and position
            self.id: str = data.get("id", "")
            self.name: str = data.get("name", "")
            self.market_share: float = float(data.get("market_share", 0.0))

            # Qualitative attributes
            self.strengths: List[str] = list(data.get("strengths", []))
            self.weaknesses: List[str] = list(data.get("weaknesses", []))

            # Products owned by competitor (list of product IDs)
            self.products: List[str] = list(data.get("products", []))

            # Strategy and position
            self.pricing_strategy: str = data.get("pricing_strategy", "")
            self.market_position: str = data.get("market_position", "")

            # Recent activities log
            self.recent_activities: List[str] = list(data.get("recent_activities", []))
            # For compatibility with explicit mode consumers, also expose asin when possible.
            try:
                self.asin: str = str(data.get("asin") or data.get("id") or "")
            except (TypeError, ValueError):
                self.asin = ""
            # Optional fields used by some flows; provide neutral defaults
            self.price = Money.zero()
            self.sales_velocity = 0.0
            self.bsr = 100000
            self.strategy = data.get("strategy", "") or data.get("pricing_strategy", "")
            try:
                self.trust_score = float(data.get("trust_score", 0.0))
            except (TypeError, ValueError):
                self.trust_score = 0.0
        else:
            # ---- Explicit keyword-based initialization (integration tests) ----
            asin = kwargs.get("asin") or kwargs.get("id") or ""
            self.asin: str = str(asin)
            # Maintain `id` as an alias for asin if not provided
            self.id: str = str(kwargs.get("id", self.asin))

            # Optional human-readable name for completeness
            self.name: str = str(kwargs.get("name", ""))

            # Price handling with safe coercion to Money
            price = kwargs.get("price", Money.zero())
            if not isinstance(price, Money):
                try:
                    price = Money.from_dollars(price)
                except (TypeError, ValueError):
                    price = Money.zero()
            self.price: Money = price

            # Core quantitative attributes
            try:
                self.sales_velocity: float = float(kwargs.get("sales_velocity", 0.0))
            except (TypeError, ValueError):
                self.sales_velocity = 0.0

            try:
                self.bsr: int = int(kwargs.get("bsr", 100000))
            except (TypeError, ValueError):
                self.bsr = 100000

            self.strategy: str = str(kwargs.get("strategy", "adaptive"))
            try:
                self.trust_score: float = float(kwargs.get("trust_score", 0.8))
            except (TypeError, ValueError):
                self.trust_score = 0.8

            # Legacy-centric attributes preserved with benign defaults
            self.market_share: float = 0.0
            self.strengths: List[str] = []
            self.weaknesses: List[str] = []
            self.products: List[str] = []
            self.pricing_strategy: str = self.strategy or ""
            self.market_position: str = ""
            self.recent_activities: List[str] = []

            # Pass-through any optional fields used by flows (e.g., persona)
            if "persona" in kwargs:
                self.persona = kwargs["persona"]

            # Inventory tracking for War Games (finite resources)
            try:
                self.inventory: int = int(kwargs.get("inventory", 5000))
            except (TypeError, ValueError):
                self.inventory = 5000

    @property
    def is_out_of_stock(self) -> bool:
        return self.inventory <= 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "market_share": self.market_share,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "products": list(self.products),
            "pricing_strategy": self.pricing_strategy,
            "market_position": self.market_position,
            "recent_activities": list(self.recent_activities),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Competitor:
        return cls(data)

    # Mutators used by tests
    def update_market_share(self, new_share: float) -> None:
        self.market_share = float(new_share)

    def add_strength(self, strength: str) -> None:
        if strength not in self.strengths:
            self.strengths.append(strength)

    def add_weakness(self, weakness: str) -> None:
        if weakness not in self.weaknesses:
            self.weaknesses.append(weakness)

    def add_product(self, product_id: str) -> None:
        if product_id not in self.products:
            self.products.append(product_id)

    def add_recent_activity(self, activity: str) -> None:
        self.recent_activities.append(activity)

    # Analytics helpers (tests only check bounds / type)
    def calculate_threat_level(self) -> float:
        """
        Calculate a simple normalized threat level in [0,1].
        Heuristic: baseline = market_share (0..1); adjust by strengths/weaknesses.
        """
        base = max(0.0, min(1.0, float(self.market_share)))
        adjusted = base + 0.05 * len(self.strengths) - 0.03 * len(self.weaknesses)
        return max(0.0, min(1.0, adjusted))

    def get_competitive_advantage(self) -> List[str]:
        """
        Return list of areas of advantage. For unit tests we can return strengths.
        """
        return list(self.strengths) if self.strengths else []
