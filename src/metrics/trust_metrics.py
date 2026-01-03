# metrics/trust_metrics.py
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class AbstractTrustScoreService(Protocol):
    """Protocol for a trust score service."""

    def calculate_trust_score(
        self, violations_count: int, buyer_feedback_scores: List[float], total_days: int
    ) -> float: ...


@dataclass
class TrustMetricsConfig:
    """Configuration for TrustMetrics."""

    default_on_zero_division: float = 0.0
    fallback_trust_score: float = 50.0


class TrustMetrics:
    def __init__(
        self,
        trust_score_service: Optional[AbstractTrustScoreService] = None,
        config: Optional[TrustMetricsConfig] = None,
    ):
        if trust_score_service is not None and not isinstance(
            trust_score_service, AbstractTrustScoreService
        ):
            raise TypeError(
                "trust_score_service must implement AbstractTrustScoreService protocol."
            )
        self.trust_score_service = trust_score_service
        self.config = config if config else TrustMetricsConfig()
        self.violation_free_days = 0
        self.total_days = 0
        self.violations_count = 0
        self.buyer_feedback_scores: List[float] = []  # Raw scores from service

        # Unit-test compatibility: lightweight metric registry
        self._metrics: Dict[str, Any] = {}

    def update(self, current_tick: int, events: List[Dict]):
        self.total_days = current_tick

        has_violation_today = False
        for event in events:
            if (
                event.get("type") == "ComplianceViolationEvent"
            ):  # Assuming such an event exists
                self.violations_count += 1
                has_violation_today = True
            # For buyer feedback, we would need events indicating new feedback
            # Assuming 'NewBuyerFeedbackEvent' with a 'score' field
            elif event.get("type") == "NewBuyerFeedbackEvent":
                score = event.get("score")
                if score is not None:
                    self.buyer_feedback_scores.append(score)

        if not has_violation_today:
            self.violation_free_days += 1

        # The TrustScoreService is now used to calculate a holistic score in get_metrics_breakdown.
        # No direct integration needed here unless the service itself needs to be updated with events.

    def calculate_violation_free_days(self) -> float:
        if self.total_days == 0:
            return 0.0
        return (
            self.violation_free_days / self.total_days
        ) * 100  # Percentage of days without violations

    def calculate_buyer_feedback_score(self) -> float:
        if not self.buyer_feedback_scores:
            return 0.0
        # This is an average of individual feedback scores.
        # trust_score_service might have a more sophisticated aggregate.
        return sum(self.buyer_feedback_scores) / len(self.buyer_feedback_scores)

    def get_metrics_breakdown(self) -> Dict[str, float]:
        violation_free_days_pct = self.calculate_violation_free_days()
        # avg_buyer_feedback_score = self.calculate_buyer_feedback_score() # Old way

        # New way: Use TrustScoreService for a more holistic trust score
        holistic_trust_score = 0.0
        if hasattr(self.trust_score_service, "calculate_trust_score"):
            try:
                holistic_trust_score = self.trust_score_service.calculate_trust_score(
                    violations_count=self.violations_count,
                    buyer_feedback_scores=self.buyer_feedback_scores,
                    total_days=self.total_days,
                )
            except (TypeError, AttributeError, RuntimeError) as e:
                logger.error(f"Error calculating holistic trust score: {e}")
                holistic_trust_score = 0.0  # Fallback
        else:
            logger.warning(
                "TrustScoreService does not have calculate_trust_score method. Using fallback."
            )
            # Fallback to old average if service is not as expected, or some other default
            if self.buyer_feedback_scores:
                holistic_trust_score = sum(self.buyer_feedback_scores) / len(
                    self.buyer_feedback_scores
                )
            else:  # If no feedback, use violation_free_days_pct as a proxy or a default
                holistic_trust_score = violation_free_days_pct

        return {
            "violation_free_days_percentage": violation_free_days_pct,
            # "average_buyer_feedback_score": avg_buyer_feedback_score, # Replaced
            "holistic_trust_score": holistic_trust_score,  # New
        }

    # ---- Unit-test compatible helpers expected by tests ----
    def calculate_reliability_score(self, data: Dict[str, float]) -> float:
        uptime_pct = float(data.get("uptime", 0.0)) / 100.0  # convert to 0-1
        mtbf = float(data.get("mean_time_between_failures", 0.0))
        mttr = float(data.get("mean_time_to_repair", 0.0))
        reliability = (
            uptime_pct * (mtbf / (mtbf + mttr)) if (mtbf + mttr) > 0 else uptime_pct
        )
        return max(0.0, min(1.0, reliability))

    def calculate_transparency_score(self, data: Dict[str, float]) -> float:
        fields = [
            "decision_explanations",
            "data_provenance",
            "model_documentation",
            "audit_trail",
        ]
        vals = [float(data.get(k, 0.0)) for k in fields]
        return max(0.0, min(1.0, sum(vals) / (len(vals) or 1)))

    def calculate_fairness_score(self, data: Dict[str, float]) -> float:
        fields = [
            "demographic_parity",
            "equal_opportunity",
            "equalized_odds",
            "individual_fairness",
        ]
        vals = [float(data.get(k, 0.0)) for k in fields]
        return max(0.0, min(1.0, sum(vals) / (len(vals) or 1)))

    def calculate_accountability_score(self, data: Dict[str, float]) -> float:
        fields = [
            "error_detection",
            "error_correction",
            "responsibility_assignment",
            "redress_mechanisms",
        ]
        vals = [float(data.get(k, 0.0)) for k in fields]
        return max(0.0, min(1.0, sum(vals) / (len(vals) or 1)))

    def calculate_security_score(self, data: Dict[str, float]) -> float:
        fields = [
            "vulnerability_assessment",
            "penetration_testing",
            "access_controls",
            "data_encryption",
        ]
        vals = [float(data.get(k, 0.0)) for k in fields]
        return max(0.0, min(1.0, sum(vals) / (len(vals) or 1)))

    def generate_trust_report(self, data: Dict[str, float]) -> Dict[str, float]:
        return {
            "reliability_score": self.calculate_reliability_score(data),
            "transparency_score": self.calculate_transparency_score(data),
            "fairness_score": self.calculate_fairness_score(data),
            "accountability_score": self.calculate_accountability_score(data),
            "security_score": self.calculate_security_score(data),
        }
