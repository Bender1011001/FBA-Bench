from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Union


def _parse_date(d: Any) -> Optional[datetime]:
    try:
        if isinstance(d, datetime):
            return d
        if isinstance(d, str):
            # Expect format "YYYY-MM-DD" per tests
            return datetime.strptime(d, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return None


class SalesResult:
    """
    Legacy SalesResult model to satisfy legacy unit tests in tests/unit/test_models.py.

    Accepts a single mapping positional argument or keyword arguments. Provides simple
    dictionary-backed storage with convenience methods and derived calculations used by tests.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        payload = dict(data or {})
        payload.update(kwargs)

        # Core identity and linkage
        self.id: Optional[str] = payload.get("id")
        self.product_id: Optional[str] = payload.get("product_id")
        self.sales_agent_id: Optional[str] = payload.get("sales_agent_id")
        self.customer_id: Optional[str] = payload.get("customer_id")

        # Quantities and pricing
        self.quantity: int = int(payload.get("quantity", 0) or 0)
        self.unit_price: float = float(payload.get("unit_price", 0.0) or 0.0)
        # total_price is tracked explicitly but normalized by helpers when quantity/price change
        self.total_price: float = float(
            payload.get("total_price", self.quantity * self.unit_price) or 0.0
        )
        self.discount: float = float(
            payload.get("discount", 0.0) or 0.0
        )  # percentage (0-100)

        # Dates and channels (expose exact attributes expected by legacy tests)
        self.sale_date: Any = payload.get("sale_date")
        self.delivery_date: Any = payload.get("delivery_date")
        self.sale_channel: Optional[str] = payload.get("sale_channel")
        self.payment_method: Optional[str] = payload.get("payment_method")
        self.shipping_address: Optional[str] = payload.get("shipping_address")
        self.order_status: Optional[str] = payload.get("order_status")

        # Customer feedback
        self.customer_feedback: Optional[str] = payload.get("customer_feedback")

        # Commission
        self.commission_rate: float = float(payload.get("commission_rate", 0.0) or 0.0)
        self.commission_amount: float = float(
            payload.get("commission_amount", 0.0) or 0.0
        )

        # Normalize initial totals if not explicitly provided
        if "total_price" not in payload:
            self._recalculate_total_price()

    # ------------------------- Internal helpers -------------------------
    def _recalculate_total_price(self) -> None:
        self.total_price = round(self.quantity * self.unit_price, 2)

    # ------------------------- Conversions ------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "sales_agent_id": self.sales_agent_id,
            "customer_id": self.customer_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "discount": self.discount,
            "sale_date": self.sale_date,
            "sale_channel": self.sale_channel,
            "payment_method": self.payment_method,
            "shipping_address": self.shipping_address,
            "order_status": self.order_status,
            "delivery_date": self.delivery_date,
            "customer_feedback": self.customer_feedback,
            "commission_rate": self.commission_rate,
            "commission_amount": self.commission_amount,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SalesResult:
        return cls(data)

    # ------------------------- Mutations --------------------------------
    def update_quantity(self, new_quantity: Union[int, float]) -> None:
        self.quantity = int(new_quantity)
        self._recalculate_total_price()

    def update_unit_price(self, new_unit_price: Union[int, float]) -> None:
        self.unit_price = float(new_unit_price)
        self._recalculate_total_price()

    def apply_discount(self, percent: Union[int, float]) -> None:
        """
        Apply a percentage discount to the current total_price.
        E.g., 10.0 means 10% off -> total_price *= 0.9
        """
        self.discount = float(percent)
        self.total_price = round(
            self.total_price * max(0.0, 1.0 - self.discount / 100.0), 2
        )

    def update_order_status(self, new_status: str) -> None:
        self.order_status = new_status

    def update_delivery_date(self, new_date: Any) -> None:
        self.delivery_date = new_date

    def add_customer_feedback(self, feedback: str) -> None:
        self.customer_feedback = feedback

    # ------------------------- Calculations -----------------------------
    def calculate_commission(self) -> float:
        """
        Commission computed as commission_rate * total_price
        """
        return round(self.total_price * float(self.commission_rate or 0.0), 2)

    def calculate_profit(self, cost_per_unit: Union[int, float]) -> float:
        """
        Profit = (unit_price - cost_per_unit) * quantity
        """
        return round((self.unit_price - float(cost_per_unit)) * self.quantity, 2)

    def calculate_delivery_time(self) -> Optional[int]:
        """
        Return number of days between sale_date and delivery_date.
        If dates are missing or invalid, return None.
        """
        sd = _parse_date(self.sale_date)
        dd = _parse_date(self.delivery_date)
        if sd is None or dd is None:
            return None
        delta = dd - sd
        try:
            return int(delta.days)
        except (ValueError, TypeError, AttributeError):
            return None
