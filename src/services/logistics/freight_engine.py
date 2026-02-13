"""Freight Engine - Container/LCL Pricing Calculator.

This module handles the physics of international freight shipping:
- LCL (Less than Container Load): Per-CBM pricing, expensive per unit
- FCL (Full Container Load): Fixed container cost, cheaper per unit at scale

The freight engine determines:
1. Whether to use LCL or FCL based on volume threshold
2. Bin packing estimates for container utilization
3. Total shipping cost including dimensional weight calculations

Usage:
    from services.logistics.freight_engine import FreightEngine
    from fba_bench_core.models.product import Product
    
    engine = FreightEngine()
    cost = engine.calculate_shipping_cost(products, quantities)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from money import Money


class ShippingMode(str, Enum):
    """Freight shipping modes."""

    LCL = "lcl"  # Less than Container Load
    FCL_20 = "fcl_20"  # 20-foot container
    FCL_40 = "fcl_40"  # 40-foot container
    FCL_40HC = "fcl_40hc"  # 40-foot high cube container
    AIR = "air"  # Air freight (expensive, fast)


@dataclass
class ContainerSpec:
    """Container specifications."""

    name: str
    mode: ShippingMode
    internal_volume_m3: float
    max_weight_kg: float
    base_cost_usd: float
    usable_volume_ratio: float = 0.85  # Account for pallets, dunnage

    @property
    def usable_volume_m3(self) -> float:
        """Actual usable volume after pallet/dunnage overhead."""
        return self.internal_volume_m3 * self.usable_volume_ratio


# Standard container specifications
CONTAINERS = {
    ShippingMode.FCL_20: ContainerSpec(
        name="20ft Standard",
        mode=ShippingMode.FCL_20,
        internal_volume_m3=33.2,
        max_weight_kg=28200,
        base_cost_usd=2500.0,
    ),
    ShippingMode.FCL_40: ContainerSpec(
        name="40ft Standard",
        mode=ShippingMode.FCL_40,
        internal_volume_m3=67.7,
        max_weight_kg=26700,
        base_cost_usd=4000.0,
    ),
    ShippingMode.FCL_40HC: ContainerSpec(
        name="40ft High Cube",
        mode=ShippingMode.FCL_40HC,
        internal_volume_m3=76.3,
        max_weight_kg=26500,
        base_cost_usd=4200.0,
    ),
}


@dataclass
class ShipmentQuote:
    """Freight shipping quote result."""

    mode: ShippingMode
    total_volume_m3: float
    total_weight_kg: float
    chargeable_weight_kg: float
    base_cost: Money
    surcharges: Money
    total_cost: Money
    cost_per_unit: Money
    unit_count: int
    containers_needed: int = 1
    utilization_pct: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class FreightEngine:
    """Calculate freight costs for shipments.

    Determines optimal shipping mode (LCL vs FCL) based on volume and
    calculates costs including dimensional weight adjustments.

    Attributes:
        fcl_threshold_m3: Volume above which FCL is cheaper.
        lcl_rate_per_cbm: Cost per cubic meter for LCL.
        dimensional_weight_factor: kg/m³ for dimensional weight calc.
    """

    # Default thresholds and rates
    DEFAULT_FCL_THRESHOLD_M3 = 15.0
    DEFAULT_LCL_RATE_PER_CBM = 85.0  # USD per cubic meter
    DEFAULT_DIMENSIONAL_WEIGHT_FACTOR = 167.0  # kg/m³

    def __init__(
        self,
        fcl_threshold_m3: float = DEFAULT_FCL_THRESHOLD_M3,
        lcl_rate_per_cbm: float = DEFAULT_LCL_RATE_PER_CBM,
        dimensional_weight_factor: float = DEFAULT_DIMENSIONAL_WEIGHT_FACTOR,
    ):
        """Initialize freight engine.

        Args:
            fcl_threshold_m3: Volume threshold for FCL consideration.
            lcl_rate_per_cbm: LCL rate per cubic meter.
            dimensional_weight_factor: Factor for dimensional weight.
        """
        self.fcl_threshold_m3 = fcl_threshold_m3
        self.lcl_rate_per_cbm = lcl_rate_per_cbm
        self.dimensional_weight_factor = dimensional_weight_factor

    def calculate_shipping_cost(
        self,
        products: List[Any],  # List of Product objects
        quantities: Dict[str, int],
        origin: str = "CN",
        destination: str = "US",
    ) -> ShipmentQuote:
        """Calculate optimal shipping cost for a shipment.

        Automatically selects LCL or FCL based on volume.

        Args:
            products: List of Product objects with volume_m3 property.
            quantities: Dict mapping SKU to quantity.
            origin: Origin country code.
            destination: Destination country code.

        Returns:
            ShipmentQuote with cost breakdown.
        """
        # Calculate total volume and weight
        total_volume = 0.0
        total_weight = 0.0
        total_units = 0

        for product in products:
            sku = getattr(product, "sku", None) or getattr(
                product, "asin", str(id(product))
            )
            qty = quantities.get(sku, 0)
            if qty <= 0:
                continue

            # Get volume - try property first, then calculate
            volume = getattr(product, "volume_m3", None)
            if volume is None or volume == 0:
                # Try to calculate from dimensions
                w = getattr(product, "width_cm", None)
                h = getattr(product, "height_cm", None)
                d = getattr(product, "depth_cm", None)
                if all([w, h, d]):
                    volume = (w * h * d) / 1_000_000
                else:
                    volume = 0.001  # Default 1 liter if no dimensions

            weight = getattr(product, "weight_kg", None) or 0.5  # Default 0.5kg

            total_volume += volume * qty
            total_weight += weight * qty
            total_units += qty

        if total_units == 0:
            return ShipmentQuote(
                mode=ShippingMode.LCL,
                total_volume_m3=0,
                total_weight_kg=0,
                chargeable_weight_kg=0,
                base_cost=Money.zero(),
                surcharges=Money.zero(),
                total_cost=Money.zero(),
                cost_per_unit=Money.zero(),
                unit_count=0,
            )

        # Calculate chargeable weight
        dimensional_weight = total_volume * self.dimensional_weight_factor
        chargeable_weight = max(total_weight, dimensional_weight)

        # Determine optimal mode
        if total_volume >= self.fcl_threshold_m3:
            return self._calculate_fcl_cost(
                total_volume, total_weight, chargeable_weight, total_units
            )
        else:
            return self._calculate_lcl_cost(
                total_volume, total_weight, chargeable_weight, total_units
            )

    def _calculate_lcl_cost(
        self,
        total_volume: float,
        total_weight: float,
        chargeable_weight: float,
        total_units: int,
    ) -> ShipmentQuote:
        """Calculate LCL (Less than Container Load) costs."""

        # LCL charged by volume (CBM) or weight, whichever is greater
        volume_cost = total_volume * self.lcl_rate_per_cbm
        weight_cost = chargeable_weight * 0.15  # $0.15/kg as baseline

        base_cost_usd = max(volume_cost, weight_cost)

        # Add LCL-specific surcharges (handling, consolidation)
        surcharge_pct = 0.15  # 15% for LCL handling
        surcharges_usd = base_cost_usd * surcharge_pct

        total_cost = Money.from_dollars(base_cost_usd + surcharges_usd)
        cost_per_unit = Money.from_dollars(
            (base_cost_usd + surcharges_usd) / total_units
        )

        return ShipmentQuote(
            mode=ShippingMode.LCL,
            total_volume_m3=total_volume,
            total_weight_kg=total_weight,
            chargeable_weight_kg=chargeable_weight,
            base_cost=Money.from_dollars(base_cost_usd),
            surcharges=Money.from_dollars(surcharges_usd),
            total_cost=total_cost,
            cost_per_unit=cost_per_unit,
            unit_count=total_units,
            containers_needed=0,
            utilization_pct=0,
            details={
                "pricing_method": "per_cbm",
                "rate_per_cbm": self.lcl_rate_per_cbm,
                "volume_cost": volume_cost,
                "weight_cost": weight_cost,
            },
        )

    def _calculate_fcl_cost(
        self,
        total_volume: float,
        total_weight: float,
        chargeable_weight: float,
        total_units: int,
    ) -> ShipmentQuote:
        """Calculate FCL (Full Container Load) costs."""

        # Determine best container type
        container = self._select_optimal_container(total_volume, total_weight)

        # Calculate containers needed
        containers_needed = self._calculate_containers_needed(
            total_volume, total_weight, container
        )

        # Base cost is container cost * number of containers
        base_cost_usd = container.base_cost_usd * containers_needed

        # FCL has lower surcharges (no consolidation)
        surcharge_pct = 0.08  # 8% for documentation, handling
        surcharges_usd = base_cost_usd * surcharge_pct

        # Calculate utilization
        utilization = min(
            1.0, total_volume / (container.usable_volume_m3 * containers_needed)
        )

        total_cost = Money.from_dollars(base_cost_usd + surcharges_usd)
        cost_per_unit = Money.from_dollars(
            (base_cost_usd + surcharges_usd) / total_units
        )

        return ShipmentQuote(
            mode=container.mode,
            total_volume_m3=total_volume,
            total_weight_kg=total_weight,
            chargeable_weight_kg=chargeable_weight,
            base_cost=Money.from_dollars(base_cost_usd),
            surcharges=Money.from_dollars(surcharges_usd),
            total_cost=total_cost,
            cost_per_unit=cost_per_unit,
            unit_count=total_units,
            containers_needed=containers_needed,
            utilization_pct=utilization * 100,
            details={
                "container_type": container.name,
                "container_volume_m3": container.usable_volume_m3,
                "container_cost": container.base_cost_usd,
            },
        )

    def _select_optimal_container(
        self,
        total_volume: float,
        total_weight: float,
    ) -> ContainerSpec:
        """Select the most cost-effective container type."""

        # Start with 20ft, upgrade if needed
        candidates = [
            CONTAINERS[ShippingMode.FCL_20],
            CONTAINERS[ShippingMode.FCL_40],
            CONTAINERS[ShippingMode.FCL_40HC],
        ]

        best_container = candidates[0]
        best_cost_per_cbm = float("inf")

        for container in candidates:
            # Check if shipment fits
            containers_needed = self._calculate_containers_needed(
                total_volume, total_weight, container
            )

            total_container_cost = container.base_cost_usd * containers_needed
            total_capacity = container.usable_volume_m3 * containers_needed

            # Cost per CBM of cargo
            cost_per_cbm = total_container_cost / max(total_volume, 0.1)

            if cost_per_cbm < best_cost_per_cbm:
                best_cost_per_cbm = cost_per_cbm
                best_container = container

        return best_container

    def _calculate_containers_needed(
        self,
        total_volume: float,
        total_weight: float,
        container: ContainerSpec,
    ) -> int:
        """Calculate number of containers needed."""
        import math

        # Containers needed by volume
        by_volume = math.ceil(total_volume / container.usable_volume_m3)

        # Containers needed by weight
        by_weight = math.ceil(total_weight / container.max_weight_kg)

        return max(1, by_volume, by_weight)

    def compare_shipping_modes(
        self,
        products: List[Any],
        quantities: Dict[str, int],
    ) -> Dict[str, ShipmentQuote]:
        """Get quotes for all shipping modes for comparison.

        Returns:
            Dict mapping mode name to quote.
        """
        # Calculate totals
        total_volume = 0.0
        total_weight = 0.0
        total_units = 0

        for product in products:
            sku = getattr(product, "sku", None) or str(id(product))
            qty = quantities.get(sku, 0)
            volume = getattr(product, "volume_m3", 0.001) or 0.001
            weight = getattr(product, "weight_kg", 0.5) or 0.5

            total_volume += volume * qty
            total_weight += weight * qty
            total_units += qty

        dimensional_weight = total_volume * self.dimensional_weight_factor
        chargeable_weight = max(total_weight, dimensional_weight)

        quotes = {}

        # LCL quote
        quotes["LCL"] = self._calculate_lcl_cost(
            total_volume, total_weight, chargeable_weight, total_units
        )

        # FCL quotes for each container type
        for mode, container in CONTAINERS.items():
            quotes[container.name] = self._calculate_fcl_cost(
                total_volume, total_weight, chargeable_weight, total_units
            )

        return quotes

    def get_breakeven_volume(
        self,
        container: ContainerSpec = None,
    ) -> float:
        """Calculate volume at which FCL becomes cheaper than LCL.

        Returns:
            Breakeven volume in cubic meters.
        """
        if container is None:
            container = CONTAINERS[ShippingMode.FCL_20]

        # LCL cost at volume V = V * lcl_rate * 1.15 (with surcharges)
        # FCL cost = container_base_cost * 1.08 (with surcharges)
        # Breakeven: V * lcl_rate * 1.15 = container_base_cost * 1.08

        lcl_with_surcharge = self.lcl_rate_per_cbm * 1.15
        fcl_with_surcharge = container.base_cost_usd * 1.08

        breakeven = fcl_with_surcharge / lcl_with_surcharge
        return breakeven
