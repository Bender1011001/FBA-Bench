"""
Data models for WorldStore service.
Defines ProductState and related dataclasses for canonical state representation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from money import Money

logger = logging.getLogger(__name__)


def _money_from_serializable(val: Any) -> Money:
    """
    Coerce serialized money representations into a Money instance.
    Accepts:
      - Money: passthrough
      - int: treated as cents
      - str: "$12.34" or "12.34" -> parsed as dollars
      - Decimal: parsed as dollars
    """
    if isinstance(val, Money):
        return val
    if isinstance(val, int):
        return Money(val)
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("$"):
            s = s[1:]
        return Money.from_dollars(s)
    if isinstance(val, float):
        return Money.from_dollars(val)
    if isinstance(val, Decimal):
        return Money.from_dollars(val)
    raise TypeError(f"Unsupported Money serialization type: {type(val)}")


@dataclass
class ProductState:
    """
    Canonical product state managed by WorldStore.

    Contains the authoritative values for all product attributes
    that can be modified by agents.
    """

    # Back-compat: accept either 'asin' or 'product_id' (tests may use product_id)
    asin: str = ""  # allow construction with product_id alias only
    price: Money = field(default_factory=lambda: Money(0))
    last_updated: datetime = field(default_factory=datetime.utcnow)
    inventory_quantity: int = 0  # Current inventory level
    cost_basis: Money = field(
        default_factory=lambda: Money(0)
    )  # Average cost basis of existing inventory
    last_agent_id: Optional[str] = None
    last_command_id: Optional[str] = None
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Accept product_id as an alias to asin; not serialized
    product_id: Optional[str] = field(default=None, repr=False, compare=False)
    # Back-compat constructor aliases accepted by tests
    inventory: Optional[int] = field(default=None, repr=False, compare=False)
    quality: Optional[float] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        # Normalize asin from product_id when provided
        if (not self.asin) and self.product_id:
            self.asin = str(self.product_id)
        # Normalize price to Money if a primitive was provided
        try:
            if not isinstance(self.price, Money):
                self.price = _money_from_serializable(self.price)
        except (TypeError, AttributeError, ValueError):
            # Fallback to zero if coercion fails
            self.price = Money.zero()
        # Map 'inventory' alias to 'inventory_quantity'
        if self.inventory is not None:
            try:
                self.inventory_quantity = int(self.inventory)
            except (TypeError, ValueError):
                pass
        # Map 'quality' into metadata
        if self.quality is not None:
            try:
                self.metadata["quality"] = float(self.quality)
            except (TypeError, ValueError):
                pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging/serialization."""
        return {
            "asin": self.asin,
            "price": str(self.price),
            "inventory_quantity": self.inventory_quantity,
            "cost_basis": str(self.cost_basis),
            "last_updated": self.last_updated.isoformat(),
            "last_agent_id": self.last_agent_id,
            "last_command_id": self.last_command_id,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductState":
        """Create ProductState from a dictionary."""
        # Accept 'product_id' as alias for asin
        asin_val = data.get("asin") or data.get("product_id")
        return cls(
            asin=str(asin_val),
            price=_money_from_serializable(data["price"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            inventory_quantity=int(data.get("inventory_quantity", 0)),
            cost_basis=_money_from_serializable(data.get("cost_basis", "$0.00")),
            last_agent_id=data.get("last_agent_id"),
            last_command_id=data.get("last_command_id"),
            version=int(data.get("version", 1)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CommandArbitrationResult:
    """Result of command arbitration process."""

    accepted: bool
    reason: str
    final_price: Optional[Money] = None
    arbitration_notes: Optional[str] = None


@dataclass
class SimpleArbitrationResult:
    """Simple arbitration outcome for dict-based commands (used by tests)."""

    winning_command: Dict[str, Any]
    reason: str
