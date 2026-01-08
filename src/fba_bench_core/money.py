from __future__ import annotations

# Canonical Money compatibility shim.
# - Uses fba_bench.money as the single source of truth (integer cents, performant)
# - Accepts legacy constructor kwargs used in Pydantic-oriented code:
#     Money(amount="12.34", currency="USD")  -> Money(1234, "USD")
#     Money(cents=1234, currency="USD")      -> Money(1234, "USD")
# Ensures instances created via this module are instances of this subclass,
# satisfying Pydantic's `is_instance_of` checks.
import decimal
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fba_bench.money import (
    EUR_ZERO,
    GBP_ZERO,
    MAX_MONEY_CENTS,
    USD_ZERO,
    Money as _Money,  # type: ignore
    max_money,
    min_money,
    sum_money,
)


class Money(_Money):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any):
        """
        Back-compat constructor:
        - Supports Money(amount="12.34", currency="USD") by converting to integer cents
        - Supports Money(cents=1234, currency="USD")
        - Falls back to canonical cents[, currency] positional args
        """
        if kwargs and ("amount" in kwargs or "cents" in kwargs):
            currency = kwargs.get("currency", "USD")
            if "cents" in kwargs and isinstance(kwargs["cents"], int):
                cents = int(kwargs["cents"])
            else:
                amount = kwargs.get("amount", 0)
                try:
                    d = Decimal(str(amount))
                    cents = int(
                        (d * Decimal("100")).quantize(
                            Decimal("1"), rounding=ROUND_HALF_UP
                        )
                    )
                except (decimal.InvalidOperation, ValueError, TypeError):
                    cents = 0
            super().__init__(cents, currency)
        else:
            super().__init__(*args, **kwargs)

    @classmethod
    def zero(cls, currency: str = "USD") -> Money:
        return cls(0, currency)

    @classmethod
    def from_dollars(cls, amount: Any, currency: str = "USD") -> Money:
        try:
            d = Decimal(str(amount))
            cents = int(
                (d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        except (decimal.InvalidOperation, ValueError, TypeError):
            cents = 0
        return cls(cents, currency)

    def _wrap(self, other: Any) -> Money:
        """Ensure arithmetic returns this subclass."""
        if isinstance(other, _Money):
            return Money(int(other.cents), getattr(other, "currency", "USD"))
        raise TypeError("Unsupported operand result type")

    def __add__(self, other: Any) -> Money:
        return self._wrap(super().__add__(other))

    def __sub__(self, other: Any) -> Money:
        return self._wrap(super().__sub__(other))

    def __mul__(self, other: Any) -> Money:
        return self._wrap(super().__mul__(other))

    def __rmul__(self, other: Any) -> Money:
        return self.__mul__(other)

    def __truediv__(self, other: Any) -> Money:
        return self._wrap(super().__truediv__(other))

    def __eq__(self, other: Any) -> bool:  # type: ignore[override]
        """
        Extend equality to support numeric comparison with dollars for legacy tests:
        Money(9999, 'USD') == 99.99 -> True
        """
        try:
            if isinstance(other, (int, float)):
                return float(self.cents) / 100.0 == float(other)
        except (TypeError, AttributeError):
            pass
        try:
            return super().__eq__(other)  # type: ignore[misc]
        except (TypeError, AttributeError):
            return False

    def __req__(self, other: Any) -> bool:
        # For symmetry when float is on the left-hand side
        return self.__eq__(other)

    def __float__(self) -> float:
        try:
            return float(self.cents) / 100.0
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def to_float(self) -> float:
        """
        Compatibility helper used by some event summary serializers.
        Returns the dollar value as float.
        """
        try:
            return float(self.cents) / 100.0
        except (TypeError, ValueError, AttributeError):
            return 0.0

    @property
    def amount(self) -> Decimal:
        """
        Back-compat property expected by contract tests.
        Returns Decimal dollar amount with 2dp using HALF_UP rounding.
        """
        try:
            return (Decimal(self.cents) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except (decimal.InvalidOperation, ValueError, TypeError):
            # Safe fallback without quantization if Decimal math fails
            return Decimal(str(float(self.cents) / 100.0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    def abs(self) -> Money:
        """Return a new Money instance with the absolute value of cents."""
        return Money(abs(self.cents), getattr(self, "currency", "USD"))

    def __abs__(self) -> Money:
        """Support the built-in abs() function."""
        return self.abs()


__all__ = [
    "Money",
    "sum_money",
    "max_money",
    "min_money",
    "USD_ZERO",
    "EUR_ZERO",
    "GBP_ZERO",
    "MAX_MONEY_CENTS",
]
