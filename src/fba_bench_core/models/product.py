from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

# Import canonical Money (re-exported shim ensures single implementation)
from money import Money
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class Product(BaseModel):
    """
    Canonical Product model used in simulation and tests.

    This model is intentionally permissive to maintain compatibility with existing tests.
    It accepts common legacy fields (asin, base_demand, inventory_units, etc.) while
    preserving strong typing for monetary fields.

    Key compatibility behaviors:
    - If sku is missing but asin is provided, sku defaults to asin.
    - If name is missing, name defaults to asin or sku.
    - If weight_kg is missing but `weight` is provided, weight_kg is derived from `weight`.
    - Extra/unknown fields are allowed and set as attributes for ease-of-use in tests.

    Physical Properties (for logistics calculations):
    - width_cm, height_cm, depth_cm: Product dimensions in centimeters
    - weight_kg: Product weight in kilograms
    - fragility_score: Breakage probability factor (0.0 = indestructible, 1.0 = fragile)
    - volume_m3: Computed cubic meter volume
    - dimensional_weight: Computed logistics dimensional weight
    """

    # Canonical identifiers
    id: UUID = Field(default_factory=uuid4)
    sku: Optional[str] = Field(default=None, description="Stock Keeping Unit")
    asin: Optional[str] = Field(default=None, description="Amazon ASIN identifier")
    name: Optional[str] = Field(default=None, description="Product display name")

    # Domain attributes
    category: Optional[str] = Field(default="general")
    price: Money
    cost: Money

    # Optional analytics/metadata expected by tests
    base_demand: Optional[float] = Field(default=0.0, ge=0)
    inventory_units: Optional[int] = Field(default=0, ge=0)
    bsr: Optional[int] = Field(default=100000, ge=1)
    trust_score: Optional[float] = Field(default=0.8, ge=0.0, le=1.0)
    size: Optional[str] = Field(default="small")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Physical dimensions for logistics (Phase 3: Physics of Stuff)
    width_cm: Optional[float] = Field(
        default=None, gt=0, description="Product width in centimeters"
    )
    height_cm: Optional[float] = Field(
        default=None, gt=0, description="Product height in centimeters"
    )
    depth_cm: Optional[float] = Field(
        default=None, gt=0, description="Product depth in centimeters"
    )
    weight_kg: Optional[float] = Field(
        default=None, gt=0, description="Product weight in kilograms"
    )
    fragility_score: Optional[float] = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Breakage probability factor (0=indestructible, 1=fragile)",
    )

    # -------------------------
    # Normalizers and validators
    # -------------------------
    @field_validator("price", "cost", mode="before")
    def ensure_money_type(cls, v):
        """
        Normalize various inputs to canonical Money:
        - Money instance: passthrough
        - dict with 'cents' or 'amount' (dollars) + optional 'currency'
        - numeric/string: interpreted as dollars
        """
        if isinstance(v, Money):
            return v
        if isinstance(v, dict):
            currency = v.get("currency", "USD")
            cents = v.get("cents", None)
            if isinstance(cents, int):
                return Money(int(cents), currency)
            amount = v.get("amount", None)
            if amount is not None:
                return Money.from_dollars(amount, currency)
            # Fallback if unrecognized dict keys: treat as zero dollars
            return Money.zero(currency)
        # Numeric or string: treat as dollars
        if isinstance(v, (int, float, str)):
            return Money.from_dollars(v)
        # Unknown type: let pydantic raise a validation error downstream
        return v

    @model_validator(mode="before")
    def _coerce_legacy_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-process legacy/alternate field names and derive sensible defaults.
        - sku <- asin when sku missing
        - name <- asin or sku when name missing
        - weight_kg <- weight if provided
        """
        asin = values.get("asin")
        sku = values.get("sku")
        if not sku and asin:
            values["sku"] = asin

        if not values.get("name"):
            values["name"] = asin or sku or "unnamed"

        # Map legacy 'weight' to 'weight_kg' (assumed already in kg in tests)
        if values.get("weight_kg") is None and "weight" in values:
            try:
                w = float(values.get("weight"))
                if w > 0:
                    values["weight_kg"] = w
            except (TypeError, ValueError):
                pass

        return values

    # -------------------------
    # Convenience methods
    # -------------------------
    def get_profit_margin(self) -> Money:
        """
        Return the unit profit margin as Money (price - cost).
        """
        try:
            return self.price - self.cost
        except (TypeError, AttributeError):
            # Fallback: compute via cents if direct subtraction not supported
            try:
                return Money(int(self.price.cents) - int(self.cost.cents))
            except (TypeError, AttributeError, ValueError):
                return Money.zero()

    # -------------------------
    # Logistics computed properties
    # -------------------------
    @computed_field
    @property
    def volume_m3(self) -> float:
        """Compute product volume in cubic meters.

        Used by freight engine for container packing calculations.
        Returns 0.0 if dimensions are not specified.
        """
        if all([self.width_cm, self.height_cm, self.depth_cm]):
            # Convert cm³ to m³ (divide by 1,000,000)
            return (self.width_cm * self.height_cm * self.depth_cm) / 1_000_000
        return 0.0

    @computed_field
    @property
    def dimensional_weight(self) -> float:
        """Compute dimensional weight in kg using standard logistics formula.

        Dimensional weight = Volume (m³) × 167 kg/m³
        This is the industry standard divisor for ocean freight.

        Carriers charge based on max(actual_weight, dimensional_weight).
        """
        return self.volume_m3 * 167.0

    @computed_field
    @property
    def chargeable_weight(self) -> float:
        """Compute chargeable weight for freight billing.

        The chargeable weight is the greater of:
        - Actual weight (weight_kg)
        - Dimensional weight

        This is what carriers use to calculate shipping costs.
        """
        actual = self.weight_kg or 0.0
        dimensional = self.dimensional_weight
        return max(actual, dimensional)

    def calculate_breakage_probability(self, handling_events: int = 5) -> float:
        """Estimate breakage probability during shipping.

        Based on fragility score and number of handling events
        (loading, unloading, transfers, etc.).

        Args:
            handling_events: Number of times the product will be handled.

        Returns:
            Probability of breakage (0.0 to 1.0).
        """
        if self.fragility_score is None:
            return 0.0
        # Compound probability: each handling event has a chance of damage
        per_event_risk = self.fragility_score * 0.02  # 2% per event at max fragility
        return 1.0 - ((1.0 - per_event_risk) ** handling_events)

    # Pydantic v2 model configuration
    model_config = ConfigDict(
        frozen=False,
        arbitrary_types_allowed=True,  # Allow canonical Money type
        title="Canonical Product Model",
        extra="allow",  # Accept extra fields used by some tests
    )
