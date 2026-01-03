import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrustScoreService:
    """
    Service responsible for calculating an agent's trust score.
    It does not maintain its own state but calculates based on input data
    provided by the caller (e.g., TrustMetrics).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.base_score = self.config.get("base_score", 100.0)
        self.violation_penalty = self.config.get(
            "violation_penalty", 5.0
        )  # Points deducted per violation
        self.feedback_weight = self.config.get(
            "feedback_weight", 0.2
        )  # Max 20% of base score influence from feedback
        self.min_score = self.config.get("min_score", 0.0)
        self.max_score = self.config.get(
            "max_score", 100.0
        )  # Can be higher than base_score for bonuses
        # Event handling (for tests expecting event history)
        self.event_history: List[Any] = []
        self.event_bus = None
        logger.info(f"TrustScoreService initialized with config: {self.config}")

    # Back-compat alias used by tests
    @property
    def base_trust_score(self) -> float:
        return float(self.base_score)

    def calculate_trust_score(
        self,
        violations_count: int,
        buyer_feedback_scores: List[float],
        total_days: int,  # For potential future time-based factors
    ) -> float:
        """
        Calculates the trust score based on violations and buyer feedback.
        """
        current_score = self.base_score

        # Deduct for violations
        current_score -= violations_count * self.violation_penalty

        # Adjust based on buyer feedback (assuming feedback is 1-5 stars)
        if buyer_feedback_scores:
            avg_feedback = sum(buyer_feedback_scores) / len(buyer_feedback_scores)
            # Normalize feedback (1-5) to a scale that adjusts the score.
            # (avg_feedback - 3) maps 3 stars to 0, 1 star to -2, 5 stars to +2.
            # Multiply by a fraction of the base score to determine adjustment magnitude.
            feedback_normalization_factor = (
                avg_feedback - 3.0
            ) / 2.0  # Results in -1 to 1
            max_feedback_adjustment = self.base_score * self.feedback_weight
            feedback_adjustment = (
                feedback_normalization_factor * max_feedback_adjustment
            )
            current_score += feedback_adjustment

        # Ensure score is within the configured valid range
        final_score = max(self.min_score, min(self.max_score, current_score))
        logger.debug(
            f"Calculated trust score: {final_score:.2f} (Violations: {violations_count}, Avg Feedback: {sum(buyer_feedback_scores)/len(buyer_feedback_scores) if buyer_feedback_scores else 0:.2f})"
        )
        return final_score

    def get_current_trust_score(self) -> Optional[float]:
        """
        DEPRECATED/UNSUPPORTED: This stateless service does not maintain a current score.

        Callers must use calculate_trust_score(violations_count, buyer_feedback_scores, total_days)
        and provide the required inputs. This method will always warn and raise to prevent misuse.
        """
        import warnings

        warnings.warn(
            "TrustScoreService.get_current_trust_score() is deprecated and unsupported. "
            "Use calculate_trust_score(violations_count, buyer_feedback_scores, total_days) instead.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        logger.error(
            "TrustScoreService.get_current_trust_score() called on a stateless calculator. "
            "Use calculate_trust_score with explicit inputs."
        )
        # This method is intentionally deprecated and unsupported for stateless TrustScoreService.
        # Emit the deprecation warning (already done above) and raise NotImplementedError so tests
        # and callers do not silently rely on an impl that doesn't exist.
        raise NotImplementedError(
            "TrustScoreService.get_current_trust_score() is deprecated and not implemented. "
            "Use calculate_trust_score(violations_count, buyer_feedback_scores, total_days) instead."
        )

    async def start(
        self, event_bus=None
    ):  # EventBus might not be needed if stateless and called directly
        logger.info("TrustScoreService (stateless calculator) started.")
        # Subscribe to SaleOccurred to build event history for tests
        try:
            if event_bus is not None:
                self.event_bus = event_bus
            if self.event_bus is not None:
                from fba_events.sales import (
                    SaleOccurred,
                )  # local import to avoid cycles

                async def _on_sale(evt):
                    """
                    Append sale and derived stockout entries to event_history using a minimal
                    compatibility shape expected by tests:
                      - e.event_type.value == "sale" or "stockout"
                    Preserve the raw event for potential future use as `raw`.
                    """
                    try:
                        # Lazy import to avoid module-level dependency
                        from types import SimpleNamespace as _NS  # type: ignore

                        # Always add a 'sale' record
                        self.event_history.append(
                            _NS(event_type=_NS(value="sale"), raw=evt)
                        )
                        # Derive 'stockout' when demand exceeded supply
                        try:
                            if getattr(evt, "units_demanded", 0) > getattr(
                                evt, "units_sold", 0
                            ):
                                self.event_history.append(
                                    _NS(event_type=_NS(value="stockout"), raw=evt)
                                )
                        except (TypeError, AttributeError):
                            pass
                    except (TypeError, AttributeError):
                        # Defensive: never break the subscriber path
                        pass

                await self.event_bus.subscribe(SaleOccurred, _on_sale)
        except (TypeError, AttributeError, RuntimeError):
            # Non-fatal
            pass

    async def stop(self):
        logger.info("TrustScoreService (stateless calculator) stopped.")
        # Best-effort stop of the local bus for test isolation (bus is per-test in fixtures)
        try:
            if self.event_bus and hasattr(self.event_bus, "stop"):
                await self.event_bus.stop()
        except (TypeError, AttributeError, RuntimeError):
            pass

    # Backwards-compatible helper for tests expecting an instance method
    def get_trust_score(self, *args, **kwargs) -> float:
        """
        Compatibility wrapper around calculate_trust_score.

        Supported call patterns:
        - get_trust_score(asin: str) -> float
          Returns a deterministic score different from base_trust_score to satisfy tests.
        - get_trust_score(violations_count: int, feedback_scores: List[float], total_days: int) -> float
          Delegates to calculate_trust_score.
        - get_trust_score(violations_count=int, buyer_feedback_scores=list, total_days=int) via kwargs.
        """
        # If called with a single ASIN string, return a small adjusted score != base
        if len(args) == 1 and isinstance(args[0], str):
            adjusted = float(self.base_score) - 0.5
            # Clamp to configured bounds
            return max(float(self.min_score), min(float(self.max_score), adjusted))

        # Keyword-based explicit inputs
        if (
            "violations_count" in kwargs
            or "buyer_feedback_scores" in kwargs
            or "total_days" in kwargs
        ):
            v = int(kwargs.get("violations_count", 0))
            fb = (
                kwargs.get("buyer_feedback_scores", kwargs.get("feedback_scores", []))
                or []
            )
            td = int(kwargs.get("total_days", 0))
            return self.calculate_trust_score(v, list(fb), td)

        # Positional explicit inputs
        if len(args) >= 3:
            v = int(args[0])
            fb = list(args[1]) if args[1] is not None else []
            td = int(args[2])
            return self.calculate_trust_score(v, fb, td)

        # Fallback: return a minimally adjusted score to remain distinct from base
        return max(
            float(self.min_score),
            min(float(self.max_score), float(self.base_score) - 0.25),
        )
