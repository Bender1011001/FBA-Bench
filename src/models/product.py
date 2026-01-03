from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

# Single canonical Money base (subclass of fba_bench.money.Money) used across core
try:
    from fba_bench_core.money import (
        Money as CoreMoney,  # canonical subclass over fba_bench.money.Money
    )
except ImportError:  # pragma: no cover
    CoreMoney = None  # type: ignore[misc]

# Fallback legacy repo-local shim (tests force-load it via tests/conftest.py)
try:
    from money import Money as LegacyMoney
except ImportError:  # pragma: no cover
    LegacyMoney = None  # type: ignore[misc]


# Compatibility subclass:
# - Inherits from CoreMoney so isinstance(x, Money-from-tests) remains True
# - Adds numeric-friendly equality so Money == 99.99 passes in legacy tests
_CompatBase = CoreMoney if CoreMoney is not None else object


class _CompatMoney(_CompatBase):  # type: ignore[misc]
    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        # Numeric comparison by dollar value for legacy tests that expect floats
        try:
            if isinstance(other, (int, float)):
                cents = getattr(self, "cents", None)
                if isinstance(cents, int):
                    return float(cents) / 100.0 == float(other)
        except (AttributeError, TypeError):
            pass
        try:
            return super().__eq__(other)  # type: ignore[misc]
        except (AttributeError, TypeError):
            return object.__eq__(self, other)  # fallback


class Product:
    """
    Legacy Product model kept for backward compatibility with legacy unit tests.

    This class accepts either a single mapping positional argument or keyword arguments.
    It preserves Money objects for price/cost when provided, while also accepting numerics.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        payload = dict(data or {})
        payload.update(kwargs)

        # Core fields (all optional in legacy tests)
        self.id: Optional[str] = payload.get("id")
        self.name: Optional[str] = payload.get("name")
        self.category: Optional[str] = payload.get("category")
        # Legacy identifier used across event-based tests
        self.asin: Optional[str] = payload.get("asin")

        # Price and cost: normalize into compat Money so:
        # - isinstance(price, Money) holds for tests using Money type
        # - price == 99.99 holds for tests comparing against numerics
        self.price: Any = self._to_money(payload.get("price"))
        self.cost: Any = self._to_money(payload.get("cost"))

        # Misc/optional fields used by tests/unit/test_models.py
        self.description: Optional[str] = payload.get("description")
        self.features: List[Any] = list(payload.get("features", []) or [])
        self.specifications: Dict[str, Any] = dict(
            payload.get("specifications", {}) or {}
        )
        # Handle both inventory field names for compatibility
        # Prioritize inventory_units if provided, otherwise use inventory
        inventory_value = payload.get("inventory_units")
        if inventory_value is None:
            inventory_value = payload.get("inventory", 0)
        self.inventory_units: int = int(inventory_value or 0)
        self.inventory: int = self.inventory_units  # Alias for backward compatibility
        # Additional fields used by various tests
        self.base_demand: float = float(payload.get("base_demand", 0.0) or 0.0)
        self.bsr: int = int(payload.get("bsr", 100000) or 100000)
        self.trust_score: float = float(payload.get("trust_score", 0.8) or 0.8)
        self.reserved_units: int = int(payload.get("reserved_units", 0) or 0)
        self.sales_velocity: float = float(payload.get("sales_velocity", 0.0) or 0.0)
        self.conversion_rate: float = float(payload.get("conversion_rate", 0.0) or 0.0)
        self.sales_history: List[Dict[str, Any]] = list(
            payload.get("sales_history", []) or []
        )
        self.customer_reviews: List[Dict[str, Any]] = list(
            payload.get("customer_reviews", []) or []
        )
        self.competitors: List[str] = list(payload.get("competitors", []) or [])
        # Optional free-form metadata for per-product hints and extensions
        self.metadata: Dict[str, Any] = dict(payload.get("metadata", {}) or {})

    # ----- Helpers ---------------------------------------------------------
    @staticmethod
    def _money_cents(value: Any) -> Optional[int]:
        try:
            cents = getattr(value, "cents", None)
            return int(cents) if isinstance(cents, int) else None
        except (AttributeError, TypeError):
            return None

    @staticmethod
    def _money_currency(value: Any) -> str:
        try:
            cur = getattr(value, "currency", None)
            return str(cur) if cur else "USD"
        except (AttributeError, TypeError):
            return "USD"

    @staticmethod
    def _as_float(value: Any) -> float:
        for t in (CoreMoney, LegacyMoney):
            if t is not None and isinstance(value, t):  # type: ignore[arg-type]
                c = Product._money_cents(value)
                if c is not None:
                    return float(c) / 100.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _construct_money(amount_dollars: float, currency: str = "USD") -> Any:
        """
        Construct a Money instance using compat subclass if possible,
        else fallback to CoreMoney/LegacyMoney/raw float.
        """
        if CoreMoney is not None:
            try:
                return _CompatMoney(int(round(amount_dollars * 100)), currency)  # type: ignore[misc]
            except (TypeError, AttributeError):
                # Try parent factory, then wrap back to compat
                try:
                    parent = CoreMoney.from_dollars(amount_dollars, currency)  # type: ignore[attr-defined]
                    cents = Product._money_cents(parent) or int(
                        round(amount_dollars * 100)
                    )
                    cur = Product._money_currency(parent)
                    return _CompatMoney(int(cents), cur)  # type: ignore[misc]
                except (TypeError, AttributeError):
                    pass
        if LegacyMoney is not None:
            try:
                return LegacyMoney(int(round(amount_dollars * 100)), currency)  # type: ignore[misc]
            except (TypeError, AttributeError):
                try:
                    return LegacyMoney.from_dollars(amount_dollars, currency)  # type: ignore[attr-defined]
                except (TypeError, AttributeError):
                    pass
        return amount_dollars

    @staticmethod
    def _coerce_to_compat_money_if_needed(value: Any) -> Any:
        """
        If value is a CoreMoney instance but not our compat subclass,
        re-wrap into _CompatMoney to gain numeric-friendly equality.
        """
        if (
            CoreMoney is not None
            and isinstance(value, CoreMoney)
            and not isinstance(value, _CompatMoney)
        ):  # type: ignore[arg-type]
            cents = Product._money_cents(value)
            cur = Product._money_currency(value)
            if cents is not None:
                try:
                    return _CompatMoney(int(cents), cur)  # type: ignore[misc]
                except (TypeError, ValueError):
                    return value
        return value

    @staticmethod
    def _to_money(value: Any) -> Any:
        """
        Normalize various representations to Money, with compat subclass where possible:
        - CoreMoney/LegacyMoney instance: coerce/wrap
        - dict with 'cents' or 'amount' + optional 'currency'
        - numeric or numeric string: treat as dollars
        """
        # Already Money instances
        if CoreMoney is not None and isinstance(value, CoreMoney):  # type: ignore[arg-type]
            return Product._coerce_to_compat_money_if_needed(value)
        if LegacyMoney is not None and isinstance(value, LegacyMoney):  # type: ignore[arg-type]
            cents = Product._money_cents(value)
            cur = Product._money_currency(value)
            if cents is not None:
                return Product._construct_money(cents / 100.0, cur)
            try:
                amt = float(value)
                return Product._construct_money(amt, cur)
            except (TypeError, ValueError):
                return value

        # dict input
        if isinstance(value, dict):
            cur = value.get("currency", "USD")
            cents = value.get("cents", None)
            if isinstance(cents, int):
                return Product._construct_money(cents / 100.0, cur)
            amount = value.get("amount", None)
            if amount is not None:
                try:
                    return Product._construct_money(float(amount), cur)
                except (TypeError, ValueError):
                    return value

        # numeric or string input
        if isinstance(value, (int, float, str)):
            try:
                amt = float(value)
                return Product._construct_money(amt, "USD")
            except (TypeError, ValueError):
                return value

        # Unknown type: return as-is
        return value

    # ----- Conversion ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "cost": self.cost,
            "description": self.description,
            "features": list(self.features),
            "specifications": dict(self.specifications),
            "inventory": self.inventory,
            "sales_history": list(self.sales_history),
            "customer_reviews": list(self.customer_reviews),
            "competitors": list(self.competitors),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Product:
        return cls(data)

    # ----- Mutations -------------------------------------------------------
    def update_price(self, new_price: Union[float, int, Any]) -> None:
        self.price = self._to_money(new_price)

    def update_inventory(self, new_inventory: int) -> None:
        self.inventory = int(new_inventory)

    def add_feature(self, feature: Any) -> None:
        self.features.append(feature)

    def add_sale(self, sale: Dict[str, Any]) -> None:
        self.sales_history.append(dict(sale))

    def add_customer_review(self, review: Dict[str, Any]) -> None:
        self.customer_reviews.append(dict(review))

    def add_competitor(self, competitor_id: str) -> None:
        self.competitors.append(competitor_id)

    # ----- Analytics -------------------------------------------------------
    def calculate_profit_margin(self) -> Optional[float]:
        price = self._as_float(self.price)
        cost = self._as_float(self.cost)
        if price <= 0:
            return None
        # Use round to stable comparison in tests
        return round((price - cost) / price, 2)

    def calculate_average_rating(self) -> Optional[float]:
        ratings = [
            r.get("rating")
            for r in self.customer_reviews
            if isinstance(r, dict) and isinstance(r.get("rating"), (int, float))
        ]
        if not ratings:
            return None
        return round(sum(ratings) / len(ratings), 1)

    def calculate_total_sales(self) -> int:
        total = 0
        for s in self.sales_history:
            try:
                total += int(s.get("quantity", 0) or 0)
            except (TypeError, ValueError, AttributeError):
                pass
        return total

    def calculate_total_revenue(self) -> float:
        total = 0.0
        for s in self.sales_history:
            try:
                total += float(s.get("revenue", 0.0) or 0.0)
            except (TypeError, ValueError, AttributeError):
                pass
        return round(total, 2)

    def get_best_selling_period(self) -> Optional[Dict[str, Any]]:
        if not self.sales_history:
            return None

        def _qty(item: Dict[str, Any]) -> int:
            try:
                return int(item.get("quantity", 0) or 0)
            except (TypeError, ValueError, AttributeError):
                return 0

        best = max(self.sales_history, key=_qty)
        return {"date": best.get("date"), "quantity": _qty(best)}

    # ----- Legacy compatibility helpers --------------------------------------
    def get_profit_margin(self) -> Any:
        """
        Return unit profit (price - cost) as Money.
        Ensures Money type is returned for tests asserting isinstance(x, Money).
        """
        # Primary path: rely on Money arithmetic
        try:
            return self.price - self.cost
        except (TypeError, AttributeError):
            pass

        # Fallback: build via cents if available
        try:
            pc = self._money_cents(self.price) or 0
            cc = self._money_cents(self.cost) or 0
            return self._construct_money(
                (pc - cc) / 100.0, self._money_currency(self.price)
            )
        except (TypeError, AttributeError, ValueError):
            # Final fallback: numeric delta coerced back to Money
            delta = self._as_float(self.price) - self._as_float(self.cost)
            return self._construct_money(delta, self._money_currency(self.price))
