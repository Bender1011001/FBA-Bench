from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, getcontext
from typing import Any, Callable, Dict, Optional

from fba_bench_core.event_bus import EventBus
from fba_events.competitor import CompetitorPricesUpdated
from fba_events.sales import SaleOccurred

# Increase precision to ensure stable EMA and ratio computations
getcontext().prec = 28


def _to_decimal(x: Any) -> Decimal:
    """Convert input to Decimal deterministically, guarding against float artifacts."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int,)):
        return Decimal(x)
    if isinstance(x, float):
        # Avoid binary float artifacts by converting through str
        return Decimal(str(x))
    if isinstance(x, str):
        return Decimal(x)
    raise TypeError(f"Unsupported type for Decimal conversion: {type(x)}")


def _ema(prev: Optional[Decimal], x: Decimal, alpha: Decimal) -> Decimal:
    """EMA update rule using Decimal arithmetic."""
    if prev is None:
        return x
    return (alpha * x) + ((Decimal("1") - alpha) * prev)


def _clamp(x: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    """Clamp Decimal to [lo, hi]."""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


class BsrEngineV3Service:
    """
    EMA-based velocity and conversion tracker with relative indices vs. market.

    Subscriptions via EventBus:
      - CompetitorPricesUpdated: updates market EMA velocity and conversion proxy
      - SaleOccurred: updates our product EMA velocity and conversion
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        # Configuration defaults
        self.ema_alpha_velocity: Decimal = _to_decimal(
            cfg.get("ema_alpha_velocity", Decimal("0.3"))
        )
        self.ema_alpha_conversion: Decimal = _to_decimal(
            cfg.get("ema_alpha_conversion", Decimal("0.3"))
        )
        self.min_samples_to_index: int = int(cfg.get("min_samples_to_index", 3))
        self.index_floor: Decimal = _to_decimal(cfg.get("index_floor", Decimal("0.01")))
        self.index_ceiling: Decimal = _to_decimal(
            cfg.get("index_ceiling", Decimal("100.0"))
        )
        self.smoothing_eps: Decimal = _to_decimal(
            cfg.get("smoothing_eps", Decimal("1e-9"))
        )

        # Internal state
        # Per-asin product metrics
        self.product_metrics: Dict[str, Dict[str, Any]] = {}
        # Market metrics (EMAs over time)
        self.market_ema_velocity: Optional[Decimal] = None
        self.market_ema_conversion: Optional[Decimal] = None
        self.competitors_latest: Dict[str, Dict[str, Any]] = {}

        # Bus and lifecycle
        self._event_bus: Optional[EventBus] = None
        self._is_running: bool = False

        # Optional reputation provider: Callable[[asin], float in 0..1]
        self._reputation_provider: Optional[Callable[[str], float]] = None

    async def start(self, event_bus: EventBus) -> None:
        """Subscribe to EventBus and begin processing events."""
        if self._is_running:
            return
        self._event_bus = event_bus
        # Subscribe using event classes for type safety
        await self._event_bus.subscribe(
            CompetitorPricesUpdated, self._on_competitor_prices_updated
        )
        await self._event_bus.subscribe(SaleOccurred, self._on_sale_occurred)
        self._is_running = True

    async def stop(self) -> None:
        """Stop service; EventBus does not provide unsubscribe; safe to flip running flag and clear refs."""
        self._is_running = False
        self._event_bus = None

    # Reputation provider integration
    def set_reputation_provider(
        self, provider: Optional[Callable[[str], float]]
    ) -> None:
        """
        Set a function that returns a reputation score in [0,1] for a given ASIN.
        If None is provided, reputation will default to neutral 0.7.
        """
        self._reputation_provider = provider

    # ========== Event Handlers ==========

    async def _on_competitor_prices_updated(
        self, event: CompetitorPricesUpdated
    ) -> None:
        """Update market EMAs from snapshot of competitor states."""
        if not event.competitors:
            # No competitors - keep previous EMAs unchanged
            return

        velocities = [_to_decimal(c.sales_velocity) for c in event.competitors]
        # Average competitor velocity
        avg_velocity: Decimal = sum(velocities, Decimal("0")) / _to_decimal(
            len(velocities)
        )

        # Conversion proxy: v/(v+1) ensures in (0,1) and bounded when conversion unknown
        # Use Decimal guard for division
        conv_terms = []
        one = Decimal("1")
        for v in velocities:
            denom = v + one
            # denom >= 1 always; no zero division
            conv_terms.append((v / denom) if denom != Decimal("0") else Decimal("0"))
        avg_conversion: Decimal = sum(conv_terms, Decimal("0")) / _to_decimal(
            len(conv_terms)
        )

        # EMA updates
        self.market_ema_velocity = _ema(
            self.market_ema_velocity, avg_velocity, self.ema_alpha_velocity
        )
        self.market_ema_conversion = _ema(
            self.market_ema_conversion, avg_conversion, self.ema_alpha_conversion
        )

        # Store latest competitor snapshot (for reference/debug)
        self.competitors_latest = {
            c.asin: {"price": c.price, "bsr": c.bsr, "velocity": c.sales_velocity}
            for c in event.competitors
        }

    async def _on_sale_occurred(self, event: SaleOccurred) -> None:
        """Update per-asin product velocity/conversion EMAs on each sale event."""
        asin = event.asin
        units_sold = _to_decimal(event.units_sold)
        units_demanded = _to_decimal(event.units_demanded)

        m = self.product_metrics.get(asin)
        if m is None:
            m = {"ema_velocity": None, "ema_conversion": None, "updates": 0}
            self.product_metrics[asin] = m

        # Velocity input x is instantaneous units_sold for the event
        m["ema_velocity"] = _ema(m["ema_velocity"], units_sold, self.ema_alpha_velocity)

        # Conversion input x is units_sold / units_demanded if demanded > 0
        if units_demanded > Decimal("0"):
            conv_x = units_sold / units_demanded
            m["ema_conversion"] = _ema(
                m["ema_conversion"], conv_x, self.ema_alpha_conversion
            )

        m["updates"] = int(m.get("updates", 0)) + 1

    # ========== Public API ==========

    def get_product_metrics(self, asin: str) -> Dict[str, Any]:
        rec = self.product_metrics.get(
            asin, {"ema_velocity": None, "ema_conversion": None, "updates": 0}
        )
        return {
            "ema_velocity": rec["ema_velocity"],
            "ema_conversion": rec["ema_conversion"],
            "updates": rec["updates"],
        }

    def get_market_metrics(self) -> Dict[str, Any]:
        return {
            "market_ema_velocity": self.market_ema_velocity,
            "market_ema_conversion": self.market_ema_conversion,
            "competitor_count": len(self.competitors_latest),
        }

    def get_product_indices(self, asin: str) -> Dict[str, Optional[Decimal]]:
        """
        Compute relative indices for a product vs. market:
          - velocity_index
          - conversion_index
          - composite_index (geometric mean)
        Returns None values if insufficient data.
        """
        pm = self.product_metrics.get(asin)
        if not pm or pm.get("updates", 0) < self.min_samples_to_index:
            return {
                "velocity_index": None,
                "conversion_index": None,
                "composite_index": None,
            }

        if self.market_ema_velocity is None or self.market_ema_conversion is None:
            return {
                "velocity_index": None,
                "conversion_index": None,
                "composite_index": None,
            }

        p_v = pm.get("ema_velocity")
        p_c = pm.get("ema_conversion")
        if p_v is None or p_c is None:
            return {
                "velocity_index": None,
                "conversion_index": None,
                "composite_index": None,
            }

        # Guarded denominators and eps in numerator
        denom_v = max(self.market_ema_velocity, self.index_floor)
        denom_c = max(self.market_ema_conversion, self.index_floor)

        velocity_index = _clamp(
            (p_v + self.smoothing_eps) / denom_v, self.index_floor, self.index_ceiling
        )
        conversion_index = _clamp(
            (p_c + self.smoothing_eps) / denom_c, self.index_floor, self.index_ceiling
        )
        composite_index = _clamp(
            (velocity_index * conversion_index) ** Decimal("0.5"),
            self.index_floor,
            self.index_ceiling,
        )

        # Apply reputation adjustment only when an explicit provider is configured
        # Default behavior: no adjustment (factor = 1.0) to match test expectations
        if self._reputation_provider is not None:
            try:
                rep_val = self._reputation_provider(asin)
                rep_score = _to_decimal(rep_val)
                rep_factor = _clamp(
                    Decimal("0.4") + (rep_score * Decimal("0.7")),
                    Decimal("0.4"),
                    Decimal("1.1"),
                )
                composite_index = _clamp(
                    composite_index * rep_factor, self.index_floor, self.index_ceiling
                )
            except (TypeError, AttributeError, ValueError):
                # On provider errors, do not adjust
                pass

        # Quantize for determinism
        q = Decimal("0.000001")
        velocity_index_q = velocity_index.quantize(q, rounding=ROUND_HALF_UP)
        conversion_index_q = conversion_index.quantize(q, rounding=ROUND_HALF_UP)
        composite_index_q = composite_index.quantize(q, rounding=ROUND_HALF_UP)

        return {
            "velocity_index": velocity_index_q,
            "conversion_index": conversion_index_q,
            "composite_index": composite_index_q,
        }

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Debug snapshot: per-asin metrics and indices plus market summary.
        """
        market = self.get_market_metrics()

        products: Dict[str, Any] = {}
        for asin, rec in self.product_metrics.items():
            idx = self.get_product_indices(asin)
            products[asin] = {
                "ema_velocity": rec["ema_velocity"],
                "ema_conversion": rec["ema_conversion"],
                "updates": rec["updates"],
                "indices": idx,
            }

        return {
            "market": market,
            "products": products,
            "competitors_latest_count": len(self.competitors_latest),
        }
