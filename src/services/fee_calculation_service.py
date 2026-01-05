"""Unified FeeCalculationService with Money type integration and comprehensive fee calculations."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal
from enum import Enum
from typing import Dict, List

from money import Money

from fba_bench_core.models.product import Product


class FeeType(Enum):
    """Types of fees in the FBA system."""

    REFERRAL = "referral"
    FBA = "fba"
    STORAGE = "storage"
    REMOVAL = "removal"
    RETURN_PROCESSING = "return_processing"
    PREP = "prep"
    LABELING = "labeling"
    ADVERTISING = "advertising"
    PENALTY = "penalty"
    SURCHARGE = "surcharge"
    SUBSCRIPTION = "subscription"


@dataclass
class FeeCalculation:
    """Detailed fee calculation result."""

    fee_type: FeeType
    base_amount: Money
    rate: float
    calculated_amount: Money
    description: str
    calculation_details: Dict
    timestamp: datetime


@dataclass
class ComprehensiveFeeBreakdown:
    """Complete fee breakdown for a transaction."""

    product_id: str
    sale_price: Money
    individual_fees: List[FeeCalculation]
    total_fees: Money
    net_proceeds: Money
    profit_margin_percent: float
    timestamp: datetime


class FeeCalculationService:
    """
    Unified fee calculation service with Money type integration.

    Combines comprehensive fee calculations from FBA-bench-main with
    clean architecture from fba_bench_good_sim.
    """

    def __init__(self, config: Dict):
        """Initialize fee calculation service with configuration."""
        self.config = config

        # Fee rate configuration
        self.fee_rates = config.get("fee_rates", {})
        self._load_default_fee_rates()

        # Size tier configuration
        self.size_tiers = config.get(
            "size_tiers",
            {
                "small_standard": {
                    "max_weight_oz": 16,
                    "max_dimensions_inches": [15, 12, 0.75],
                },
                "large_standard": {
                    "max_weight_oz": 160,
                    "max_dimensions_inches": [18, 14, 8],
                },
                "small_oversize": {
                    "max_weight_oz": 1120,
                    "max_dimensions_inches": [60, 30, 30],
                },
                "medium_oversize": {
                    "max_weight_oz": 1120,
                    "max_dimensions_inches": [108, 30, 30],
                },
                "large_oversize": {
                    "max_weight_oz": 2240,
                    "max_dimensions_inches": [108, 30, 30],
                },
                "special_oversize": {
                    "max_weight_oz": float("inf"),
                    "max_dimensions_inches": [float("inf"), float("inf"), float("inf")],
                },
            },
        )

        # Category-specific referral rates
        self.category_referral_rates = config.get("category_referral_rates", {})
        self._load_default_category_rates()

        # Storage rates (per cubic foot per month)
        self.storage_rates = config.get(
            "storage_rates",
            {
                "standard_jan_sep": Money.from_dollars(0.87),
                "standard_oct_dec": Money.from_dollars(2.40),
                "oversize_jan_sep": Money.from_dollars(0.56),
                "oversize_oct_dec": Money.from_dollars(1.40),
            },
        )

        # Dimensional weight divisor (default 139)
        self.dim_divisor = self._to_decimal(
            self.config.get("dimensional_weight_divisor", 139)
        )

        # Surcharges configuration
        self.surcharges = self.config.get("surcharges", {})
        self._load_default_surcharges()

        # Penalties configuration
        self.penalties = self.config.get("penalties", {})
        self._load_default_penalties()

    def _load_default_fee_rates(self) -> None:
        """Load default fee rates if not provided in config."""
        defaults = {
            "referral_base_rate": 0.15,  # 15% default referral fee
            "fba_small_standard": Money.from_dollars(3.22),
            "fba_large_standard_1lb": Money.from_dollars(4.09),
            "fba_large_standard_additional_lb": Money.from_dollars(0.42),
            "fba_small_oversize": Money.from_dollars(9.73),
            "fba_medium_oversize": Money.from_dollars(18.41),
            "fba_large_oversize": Money.from_dollars(89.98),
            "fba_special_oversize": Money.from_dollars(158.49),
            "return_processing_rate": 0.20,  # 20% of item price
            "prep_fee": Money.from_dollars(0.55),
            "labeling_fee": Money.from_dollars(0.55),
            "removal_fee_standard": Money.from_dollars(0.50),
            "removal_fee_oversize": Money.from_dollars(0.60),
        }

        for key, value in defaults.items():
            if key not in self.fee_rates:
                self.fee_rates[key] = value

    def _load_default_category_rates(self) -> None:
        """Load default category-specific referral rates."""
        defaults = {
            "electronics": 0.08,
            "computers": 0.06,
            "books": 0.15,
            "clothing": 0.17,
            "home_garden": 0.15,
            "sports_outdoors": 0.15,
            "toys_games": 0.15,
            "automotive": 0.12,
            "health_personal_care": 0.15,
            "grocery": 0.08,
        }

        for category, rate in defaults.items():
            if category not in self.category_referral_rates:
                self.category_referral_rates[category] = rate

    # Helper conversions and geometry
    def _to_decimal(self, value) -> Decimal:
        """Convert int/float/str/Decimal to Decimal safely (no float math leakage)."""
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            return Decimal(str(value))
        return Decimal(str(value))

    def _compute_cubic_feet(self, dimensions_inches) -> Decimal:
        """Compute cubic feet from dimensions in inches using Decimal math."""
        dims = dimensions_inches
        # Allow string format like "LxWxH"
        if isinstance(dims, str) and "x" in dims.lower():
            parts = [p.strip() for p in dims.lower().split("x")]
            if len(parts) == 3:
                dims = parts
        if not dims or len(dims) != 3:
            dims = [12, 8, 1]
        L, W, H = (self._to_decimal(d) for d in dims)
        cubic_inches = L * W * H
        return (cubic_inches / Decimal(1728)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    def _compute_billable_weight_lb(self, product: Product) -> Decimal:
        """
        Compute billable weight per carrier practice (2025 fidelity):
        - actual_weight_lb = weight_oz / 16 (Decimal)
        - dim_weight_lb = (L * W * H) / dim_divisor
        - billable = max(actual, dim), rounded up to nearest 0.1 lb
        """
        # Actual weight
        weight_oz = getattr(product, "weight_oz", 16)
        actual_lb = self._to_decimal(weight_oz) / Decimal(16)

        # Dimensions
        dimensions = getattr(product, "dimensions_inches", None)
        if dimensions is None:
            dim_str = getattr(product, "dimensions", None)
            if isinstance(dim_str, str) and "x" in dim_str.lower():
                parts = [p.strip() for p in dim_str.lower().split("x")]
                if len(parts) == 3:
                    dimensions = parts
        if not dimensions:
            dimensions = [12, 8, 1]
        L, W, H = (self._to_decimal(d) for d in dimensions)
        dim_weight_lb = (L * W * H) / self.dim_divisor

        billable = dim_weight_lb if dim_weight_lb > actual_lb else actual_lb
        return billable.quantize(Decimal("0.1"), rounding=ROUND_UP)

    def _load_default_surcharges(self) -> None:
        """Load default surcharges config."""
        defaults = {
            "peak_season_pct_on_fba": 0.0,  # Decimal fraction, e.g., 0.08 for 8%
            "fuel_pct_on_fba": 0.0,
            "remote_area_flat": Money.zero(),
            "hazardous_flat": Money.zero(),
        }
        for k, v in defaults.items():
            if k not in self.surcharges:
                self.surcharges[k] = v

    def _load_default_penalties(self) -> None:
        """Load default penalties config."""
        defaults = {
            "ltsf_monthly_per_cu_ft": Money.zero(),
            "low_price_threshold": Money.zero(),
            "low_price_fee_flat": Money.zero(),
        }
        for k, v in defaults.items():
            if k not in self.penalties:
                self.penalties[k] = v

    def calculate_comprehensive_fees(
        self, product: Product, sale_price: Money, additional_context: Dict = None
    ) -> ComprehensiveFeeBreakdown:
        """
        Calculate comprehensive fee breakdown for a sale.

        Args:
            product: Product being sold
            sale_price: Sale price of the product
            additional_context: Additional context like storage duration, prep requirements, etc.

        Returns:
            Complete fee breakdown
        """
        if additional_context is None:
            additional_context = {}

        individual_fees: List[FeeCalculation] = []

        # Calculate referral fee
        referral_fee = self._calculate_referral_fee(product, sale_price)
        individual_fees.append(referral_fee)

        # Calculate FBA fulfillment fee
        fba_fee = self._calculate_fba_fee(product)
        individual_fees.append(fba_fee)

        # Surcharges applied off FBA fee
        # Determine peak season: Oct-Dec, unless overridden by additional_context
        peak_override = additional_context.get("peak_season", None)
        current_month = datetime.now().month
        is_peak_season = (
            (current_month in [10, 11, 12])
            if peak_override is None
            else bool(peak_override)
        )

        # Percent surcharges on FBA
        peak_pct = (
            self._to_decimal(self.surcharges.get("peak_season_pct_on_fba", 0.0))
            if is_peak_season
            else Decimal("0")
        )
        fuel_pct = self._to_decimal(self.surcharges.get("fuel_pct_on_fba", 0.0))

        if peak_pct > 0:
            peak_amount = fba_fee.calculated_amount * peak_pct
            individual_fees.append(
                FeeCalculation(
                    fee_type=FeeType.SURCHARGE,
                    base_amount=fba_fee.calculated_amount,
                    rate=float(peak_pct),
                    calculated_amount=peak_amount,
                    description="Peak season surcharge on FBA fee",
                    calculation_details={
                        "basis": "fba",
                        "percent": float(peak_pct),
                        "is_peak_season": is_peak_season,
                    },
                    timestamp=datetime.now(),
                )
            )

        if fuel_pct > 0:
            fuel_amount = fba_fee.calculated_amount * fuel_pct
            individual_fees.append(
                FeeCalculation(
                    fee_type=FeeType.SURCHARGE,
                    base_amount=fba_fee.calculated_amount,
                    rate=float(fuel_pct),
                    calculated_amount=fuel_amount,
                    description="Fuel surcharge on FBA fee",
                    calculation_details={"basis": "fba", "percent": float(fuel_pct)},
                    timestamp=datetime.now(),
                )
            )

        # Flat surcharges
        if additional_context.get("is_remote_area", False):
            remote_flat = self.surcharges.get("remote_area_flat", Money.zero())
            if isinstance(remote_flat, Money) and remote_flat.cents != 0:
                individual_fees.append(
                    FeeCalculation(
                        fee_type=FeeType.SURCHARGE,
                        base_amount=remote_flat,
                        rate=1.0,
                        calculated_amount=remote_flat,
                        description="Remote area flat surcharge",
                        calculation_details={"type": "remote_area_flat"},
                        timestamp=datetime.now(),
                    )
                )

        if additional_context.get("is_hazmat", False):
            haz_flat = self.surcharges.get("hazardous_flat", Money.zero())
            if isinstance(haz_flat, Money) and haz_flat.cents != 0:
                individual_fees.append(
                    FeeCalculation(
                        fee_type=FeeType.SURCHARGE,
                        base_amount=haz_flat,
                        rate=1.0,
                        calculated_amount=haz_flat,
                        description="Hazardous materials flat surcharge",
                        calculation_details={"type": "hazardous_flat"},
                        timestamp=datetime.now(),
                    )
                )

        # Calculate storage fee if applicable
        storage_duration_days = additional_context.get("storage_duration_days", 0)
        if storage_duration_days > 0:
            storage_fee = self._calculate_storage_fee(product, storage_duration_days)
            individual_fees.append(storage_fee)

        # Calculate prep fees if applicable
        if additional_context.get("requires_prep", False):
            prep_fee = self._calculate_prep_fee(product)
            individual_fees.append(prep_fee)

        # Calculate labeling fees if applicable
        if additional_context.get("requires_labeling", False):
            labeling_fee = self._calculate_labeling_fee(product)
            individual_fees.append(labeling_fee)

        # Calculate return processing fee if applicable
        if additional_context.get("is_return", False):
            return_fee = self._calculate_return_processing_fee(sale_price)
            individual_fees.append(return_fee)

        # Calculate advertising fees if applicable
        ad_spend = additional_context.get("advertising_spend", Money.zero())
        if ad_spend.cents != 0:
            ad_fee = self._calculate_advertising_fee(ad_spend)
            individual_fees.append(ad_fee)

        # Calculate penalty fees if applicable (direct input)
        penalty_amount = additional_context.get("penalty_amount", Money.zero())
        if penalty_amount.cents != 0:
            penalty_fee = self._calculate_penalty_fee(
                penalty_amount, additional_context.get("penalty_reason", "unknown")
            )
            individual_fees.append(penalty_fee)

        # Configurable penalties:
        # Long-term storage penalty (LTSF) - months_in_storage >= 12
        months_in_storage = int(additional_context.get("months_in_storage", 0) or 0)
        ltsf_rate: Money = self.penalties.get("ltsf_monthly_per_cu_ft", Money.zero())
        if (
            months_in_storage >= 12
            and isinstance(ltsf_rate, Money)
            and ltsf_rate.cents > 0
        ):
            cf = self._compute_cubic_feet(
                getattr(product, "dimensions_inches", [12, 8, 1])
            )
            # Money * int -> Money; Money * Decimal -> Money
            ltsf_amount = (ltsf_rate * months_in_storage) * cf
            individual_fees.append(
                FeeCalculation(
                    fee_type=FeeType.PENALTY,
                    base_amount=ltsf_rate,
                    rate=float(cf),
                    calculated_amount=ltsf_amount,
                    description=f"Long-term storage penalty ({months_in_storage} months)",
                    calculation_details={
                        "months_in_storage": months_in_storage,
                        "cubic_feet": float(cf),
                        "monthly_rate": ltsf_rate,
                    },
                    timestamp=datetime.now(),
                )
            )

        # Low-price penalty
        low_price_threshold: Money = self.penalties.get(
            "low_price_threshold", Money.zero()
        )
        low_price_fee_flat: Money = self.penalties.get(
            "low_price_fee_flat", Money.zero()
        )
        if (
            isinstance(low_price_threshold, Money)
            and low_price_threshold.cents > 0
            and sale_price < low_price_threshold
        ):
            if isinstance(low_price_fee_flat, Money) and low_price_fee_flat.cents > 0:
                individual_fees.append(
                    FeeCalculation(
                        fee_type=FeeType.PENALTY,
                        base_amount=low_price_threshold,
                        rate=1.0,
                        calculated_amount=low_price_fee_flat,
                        description=f"Low-price penalty (threshold {low_price_threshold})",
                        calculation_details={
                            "threshold": low_price_threshold,
                            "trigger_price": sale_price,
                        },
                        timestamp=datetime.now(),
                    )
                )

        # Calculate totals
        total_fees = sum(
            (fee.calculated_amount for fee in individual_fees), Money.zero()
        )
        net_proceeds = sale_price - total_fees

        # Calculate profit margin
        cost_basis = getattr(product, "cost_basis", Money.zero())
        if cost_basis.cents != 0:
            profit = net_proceeds - cost_basis
            # Compute percentage off cents, avoid Money/Money operations
            profit_margin_percent = (profit.cents / cost_basis.cents) * 100.0
        else:
            profit_margin_percent = 0.0

        return ComprehensiveFeeBreakdown(
            product_id=getattr(
                product, "product_id", getattr(product, "asin", "unknown")
            ),
            sale_price=sale_price,
            individual_fees=individual_fees,
            total_fees=total_fees,
            net_proceeds=net_proceeds,
            profit_margin_percent=profit_margin_percent,
            timestamp=datetime.now(),
        )

    def _calculate_referral_fee(
        self, product: Product, sale_price: Money
    ) -> FeeCalculation:
        """Calculate referral fee based on product category and sale price."""
        category = getattr(product, "category", "default")
        rate_val = self.category_referral_rates.get(
            category, self.fee_rates["referral_base_rate"]
        )
        rate_dec = self._to_decimal(rate_val)

        # Apply minimum and maximum referral fee rules (Decimal-safe)
        calculated_amount = sale_price * rate_dec

        # Some categories have minimum fees
        min_fee = Money.from_dollars(0.30)  # $0.30 minimum for most categories
        if category in ["books", "music", "video"]:
            min_fee = Money.from_dollars(1.00)  # $1.00 minimum for media

        calculated_amount = max(calculated_amount, min_fee)

        # Some categories have maximum fees
        if category == "electronics":
            max_fee = Money.from_dollars(100.00)
            calculated_amount = min(calculated_amount, max_fee)

        return FeeCalculation(
            fee_type=FeeType.REFERRAL,
            base_amount=sale_price,
            rate=float(rate_dec),
            calculated_amount=calculated_amount,
            description=f"Referral fee for {category} category",
            calculation_details={
                "category": category,
                "rate_applied": float(rate_dec),
                "minimum_fee": min_fee,
                "sale_price": sale_price,
            },
            timestamp=datetime.now(),
        )

    def _calculate_fba_fee(self, product: Product) -> FeeCalculation:
        """Calculate FBA fulfillment fee based on product size and billable weight (2025 fidelity)."""
        size_tier = self._determine_size_tier(product)
        billable_weight_lb = self._compute_billable_weight_lb(product)

        if size_tier == "small_standard":
            calculated_amount = self.fee_rates["fba_small_standard"]

        elif size_tier == "large_standard":
            base_fee = self.fee_rates["fba_large_standard_1lb"]
            if billable_weight_lb > Decimal("1.0"):
                additional_weight = billable_weight_lb - Decimal("1.0")
                rate_cents = Decimal(
                    self.fee_rates["fba_large_standard_additional_lb"].cents
                )
                additional_fee_cents = (additional_weight * rate_cents).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                additional_fee = Money(int(additional_fee_cents))
                calculated_amount = base_fee + additional_fee
            else:
                calculated_amount = base_fee

        elif size_tier == "small_oversize":
            calculated_amount = self.fee_rates["fba_small_oversize"]

        elif size_tier == "medium_oversize":
            calculated_amount = self.fee_rates["fba_medium_oversize"]

        elif size_tier == "large_oversize":
            calculated_amount = self.fee_rates["fba_large_oversize"]

        else:  # special_oversize
            calculated_amount = self.fee_rates["fba_special_oversize"]

        return FeeCalculation(
            fee_type=FeeType.FBA,
            base_amount=Money.zero(),
            rate=0.0,
            calculated_amount=calculated_amount,
            description=f"FBA fulfillment fee for {size_tier} item",
            calculation_details={
                "size_tier": size_tier,
                "billable_weight_lb": float(billable_weight_lb),
                "dimensions": getattr(product, "dimensions_inches", [0, 0, 0]),
            },
            timestamp=datetime.now(),
        )

    def _calculate_storage_fee(
        self, product: Product, duration_days: int
    ) -> FeeCalculation:
        """Calculate monthly storage fee prorated for duration (Decimal math)."""
        size_tier = self._determine_size_tier(product)
        is_oversize = "oversize" in size_tier

        # Determine if it's peak season (Oct-Dec)
        current_month = datetime.now().month
        is_peak_season = current_month in [10, 11, 12]

        # Get appropriate rate
        if is_oversize:
            rate_key = "oversize_oct_dec" if is_peak_season else "oversize_jan_sep"
        else:
            rate_key = "standard_oct_dec" if is_peak_season else "standard_jan_sep"

        monthly_rate = self.storage_rates[rate_key]

        # Calculate cubic feet using Decimal math
        dimensions = getattr(product, "dimensions_inches", [12, 8, 1])
        cubic_feet = self._compute_cubic_feet(dimensions)

        # Prorate for actual duration using Decimal(30)
        daily_rate = monthly_rate / Decimal(30)
        calculated_amount = (daily_rate * cubic_feet) * int(duration_days)

        return FeeCalculation(
            fee_type=FeeType.STORAGE,
            base_amount=monthly_rate,
            rate=float(cubic_feet),
            calculated_amount=calculated_amount,
            description=f"Storage fee for {duration_days} days",
            calculation_details={
                "duration_days": duration_days,
                "cubic_feet": float(cubic_feet),
                "monthly_rate": monthly_rate,
                "is_peak_season": is_peak_season,
                "size_tier": size_tier,
            },
            timestamp=datetime.now(),
        )

    def _calculate_prep_fee(self, product: Product) -> FeeCalculation:
        """Calculate prep service fee."""
        calculated_amount = self.fee_rates["prep_fee"]

        return FeeCalculation(
            fee_type=FeeType.PREP,
            base_amount=calculated_amount,
            rate=1.0,
            calculated_amount=calculated_amount,
            description="Prep service fee",
            calculation_details={"service_type": "standard_prep"},
            timestamp=datetime.now(),
        )

    def _calculate_labeling_fee(self, product: Product) -> FeeCalculation:
        """Calculate labeling service fee."""
        calculated_amount = self.fee_rates["labeling_fee"]

        return FeeCalculation(
            fee_type=FeeType.LABELING,
            base_amount=calculated_amount,
            rate=1.0,
            calculated_amount=calculated_amount,
            description="Labeling service fee",
            calculation_details={"service_type": "standard_labeling"},
            timestamp=datetime.now(),
        )

    def _calculate_return_processing_fee(self, sale_price: Money) -> FeeCalculation:
        """Calculate return processing fee with Decimal-safe math."""
        rate_val = self.fee_rates["return_processing_rate"]
        rate_dec = self._to_decimal(rate_val)
        calculated_amount = sale_price * rate_dec

        return FeeCalculation(
            fee_type=FeeType.RETURN_PROCESSING,
            base_amount=sale_price,
            rate=float(rate_dec),
            calculated_amount=calculated_amount,
            description="Return processing fee",
            calculation_details={"original_sale_price": sale_price},
            timestamp=datetime.now(),
        )

    def _calculate_advertising_fee(self, ad_spend: Money) -> FeeCalculation:
        """Calculate advertising fee (pass-through of ad spend)."""
        return FeeCalculation(
            fee_type=FeeType.ADVERTISING,
            base_amount=ad_spend,
            rate=1.0,
            calculated_amount=ad_spend,
            description="Advertising spend",
            calculation_details={"ad_spend": ad_spend},
            timestamp=datetime.now(),
        )

    def _calculate_penalty_fee(
        self, penalty_amount: Money, reason: str
    ) -> FeeCalculation:
        """Calculate penalty fee."""
        return FeeCalculation(
            fee_type=FeeType.PENALTY,
            base_amount=penalty_amount,
            rate=1.0,
            calculated_amount=penalty_amount,
            description=f"Penalty fee: {reason}",
            calculation_details={"penalty_reason": reason},
            timestamp=datetime.now(),
        )

    def _determine_size_tier(self, product: Product) -> str:
        """Determine the size tier for a product."""
        weight_oz = getattr(product, "weight_oz", 16)
        dimensions = getattr(product, "dimensions_inches", [12, 8, 1])

        for tier_name, tier_config in self.size_tiers.items():
            if weight_oz <= tier_config["max_weight_oz"] and all(
                d <= max_d
                for d, max_d in zip(dimensions, tier_config["max_dimensions_inches"])
            ):
                return tier_name

        return "special_oversize"  # Default to largest tier

    def estimate_fees_for_price_point(
        self, product: Product, target_price: Money, context: Dict = None
    ) -> Dict:
        """Estimate fees for a specific price point."""
        if context is None:
            context = {}

        breakdown = self.calculate_comprehensive_fees(product, target_price, context)

        return {
            "sale_price": target_price,
            "total_fees": breakdown.total_fees,
            "net_proceeds": breakdown.net_proceeds,
            "fee_percentage": (breakdown.total_fees.cents / target_price.cents) * 100.0,
            "profit_margin_percent": breakdown.profit_margin_percent,
            "break_even_price": self._calculate_break_even_price(product, context),
        }

    def _calculate_break_even_price(self, product: Product, context: Dict) -> Money:
        """Calculate the break-even price for a product."""
        cost_basis = getattr(product, "cost_basis", Money.zero())
        if cost_basis.cents == 0:
            return Money.zero()

        # Estimate fees at cost basis price to get fee structure
        temp_breakdown = self.calculate_comprehensive_fees(product, cost_basis, context)

        # Calculate break-even price iteratively
        # Start with cost + estimated fees
        estimated_price = cost_basis + temp_breakdown.total_fees

        # Refine estimate (fees change with price due to referral fees)
        for _ in range(3):  # 3 iterations should be sufficient
            refined_breakdown = self.calculate_comprehensive_fees(
                product, estimated_price, context
            )
            estimated_price = cost_basis + refined_breakdown.total_fees

        return estimated_price

    def get_fee_summary_by_type(
        self, breakdowns: List[ComprehensiveFeeBreakdown]
    ) -> Dict:
        """Get summary of fees by type across multiple transactions."""
        fee_totals: Dict[str, Dict[str, Money | int]] = {}

        for breakdown in breakdowns:
            for fee in breakdown.individual_fees:
                fee_type = fee.fee_type.value
                if fee_type not in fee_totals:
                    fee_totals[fee_type] = {
                        "total_amount": Money.zero(),
                        "count": 0,
                        "average_amount": Money.zero(),
                    }

                fee_totals[fee_type]["total_amount"] = (
                    fee_totals[fee_type]["total_amount"] + fee.calculated_amount
                )
                fee_totals[fee_type]["count"] = int(fee_totals[fee_type]["count"]) + 1

        # Calculate averages
        for fee_type, totals in fee_totals.items():
            if totals["count"] > 0:
                totals["average_amount"] = Money(
                    totals["total_amount"].cents // totals["count"]
                )

        return fee_totals
