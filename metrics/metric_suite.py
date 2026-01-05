"""
Metric Suite for FBA-Bench.
Calculates scores across 7 domains with weighted final score.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

STANDARD_WEIGHTS = {
    "finance": 0.25,
    "ops": 0.15,
    "marketing": 0.15,
    "trust": 0.15,
    "cognitive": 0.10,
    "stress_recovery": 0.10,
    "cost": 0.10,
}

@dataclass
class FinalScores:
    """Final scores with breakdown."""
    score: float
    breakdown: Dict[str, float]

class MetricSuite:
    """
    Core metric calculation suite for FBA-Bench.
    Computes 7-domain scores from events.
    """

    def __init__(
        self,
        tier: str,
        financial_audit_service: Any = None,
        sales_service: Any = None,
        trust_score_service: Any = None,
        weights: Dict[str, float] = STANDARD_WEIGHTS,
    ):
        self.tier = tier
        self.weights = weights
        self.financial_audit_service = financial_audit_service
        self.sales_service = sales_service
        self.trust_score_service = trust_score_service
        self.events_subscribed = False

    def subscribe_to_events(self, event_bus: Any):
        """Subscribe to event bus for real-time metric collection."""
        self.events_subscribed = True
        # In full impl, register listeners here
        logger.info("MetricSuite subscribed to events")

    def calculate_final_score(self, events: List[Dict[str, Any]]) -> FinalScores:
        """
        Calculate final score from event list.

        Args:
            events: List of event dicts

        Returns:
            FinalScores with score and breakdown
        """
        if not events:
            return FinalScores(score=0.0, breakdown={k: 0.0 for k in self.weights})

        # Stub calculations: average domain scores based on event count
        num_events = len(events)
        breakdown = {}
        total_weighted = 0.0

        for domain, weight in self.weights.items():
            # Simple stub: score based on events (in real, domain-specific logic)
            domain_score = min(100.0, num_events * 5.0)  # Cap at 100
            breakdown[domain] = domain_score
            total_weighted += domain_score * weight

        final_score = total_weighted

        logger.info(f"Calculated scores for {len(events)} events: final={final_score:.2f}")
        return FinalScores(score=final_score, breakdown=breakdown)
