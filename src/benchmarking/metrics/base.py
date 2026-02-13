"""
Base classes for multi-dimensional evaluation metrics.

This module provides the foundation for all benchmarking metrics, including
abstract base classes and concrete implementations for cognitive, business,
technical, and ethical metrics.

It also provides a legacy-compatible API expected by tests:
- BaseMetric(name, description, category)
- MetricResult(name, score, confidence, details, metadata, timestamp)
- Concrete metrics: CognitiveMetrics, BusinessMetrics, TechnicalMetrics, EthicalMetrics
  with .name in {"cognitive","business","technical","ethical"} and .category in MetricCategory.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# -----------------------------------------------------------------------------
# Legacy/test-facing MetricResult (distinct from benchmarking.core.results.MetricResult)
# -----------------------------------------------------------------------------
@dataclass
class MetricResult:
    """
    Result container for metric evaluation compatible with unit tests.

    Fields:
      - name: metric identifier
      - score: normalized score in [0, 1]
      - confidence: confidence in [0, 1]
      - details: nested dictionary with metric-specific details
      - metadata: free-form key/value metadata
      - timestamp: creation time (UTC)
    """

    name: str
    score: float
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "confidence": self.confidence,
            "details": self.details,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    def is_valid(self) -> bool:
        try:
            s = float(self.score)
            c = float(self.confidence)
        except Exception:
            return False
        return 0.0 <= s <= 1.0 and 0.0 <= c <= 1.0


# -----------------------------------------------------------------------------
# Optional configuration structure (used by the extended registry path)
# -----------------------------------------------------------------------------
@dataclass
class MetricConfig:
    """Configuration for a metric."""

    name: str
    description: str
    unit: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    target_value: Optional[float] = None
    weight: float = 1.0
    enabled: bool = True


class MetricCategory(str, Enum):
    # Canonical lowercase members
    cognitive = "cognitive"
    business = "business"
    technical = "technical"
    ethical = "ethical"
    # Uppercase aliases for test/back-compat
    COGNITIVE = "cognitive"
    BUSINESS = "business"
    TECHNICAL = "technical"
    ETHICAL = "ethical"


# -----------------------------------------------------------------------------
# Base class (legacy-compatible)
# -----------------------------------------------------------------------------
class BaseMetric(abc.ABC):
    """
    Abstract base class for all metrics (legacy-compatible interface).

    Two initialization modes:
      - Test/legacy mode:
          BaseMetric(name="...", description="...", category=MetricCategory.COGNITIVE)
      - Registry/config mode:
          BaseMetric(config=MetricConfig(...))  # category should then be provided by subclass
    """

    def __init__(
        self,
        config: Optional[MetricConfig] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[MetricCategory] = None,
    ):
        if config is not None and any(
            v is not None for v in (name, description, category)
        ):
            raise TypeError(
                "Provide either config or (name, description, category), not both"
            )

        if config is not None:
            # Config-driven init (primarily for the extended registry path)
            # Preserve a reference to config for tests that access .config.*
            self.config = config
            self.name = config.name
            self.description = config.description
            # Subclass may set category explicitly in this mode (optional for some tests)
            self.category = category
        else:
            # Legacy/test-driven init
            if not isinstance(name, str) or not name:
                raise TypeError("name must be a non-empty string")
            if not isinstance(description, str) or not description:
                raise TypeError("description must be a non-empty string")
            if category is None:
                raise TypeError("category must be provided")
            self.name = name
            self.description = description
            self.category = category
            # Synthesize a minimal config so attributes like .unit and .config.* exist
            self.config = MetricConfig(
                name=self.name,
                description=self.description,
                unit="score",
            )

    @property
    def unit(self) -> str:
        """
        Unit label for this metric. Defaults to 'score' when not configured.
        """
        try:
            return self.config.unit  # populated in both legacy and config init paths
        except Exception:
            return "score"

    def validate_context(self, context: Any) -> tuple[bool, List[str]]:
        """
        Minimal context validation required by tests.

        Returns:
          (True, []) if context is a dict. Otherwise (False, [error messages]).
        """
        if not isinstance(context, dict):
            return False, ["Context must be a dict"]
        return True, []

    @abc.abstractmethod
    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        """
        Calculate the metric result from context.
        Must return a MetricResult(name, score in [0,1], confidence in [0,1]).
        """
        raise NotImplementedError


# -----------------------------------------------------------------------------
# Concrete metrics (legacy-compatible)
# -----------------------------------------------------------------------------
class CognitiveMetrics(BaseMetric):
    """
    Metrics for evaluating cognitive capabilities of agents.

    The calculation turns event counts into a normalized [0,1] score and reports
    details for reasoning/planning/memory.
    """

    def __init__(self):
        super().__init__(
            name="cognitive",
            description="Cognitive capability evaluation (reasoning, planning, memory)",
            category=MetricCategory.COGNITIVE,
        )

    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        events: List[Dict[str, Any]] = list(context.get("events", []))

        reasoning = sum(1 for e in events if e.get("type") == "AgentDecisionEvent")
        planning = sum(1 for e in events if e.get("type") == "AgentPlannedGoalEvent")
        # Heuristic: consider completed goals as memory utilization proxy
        memory = sum(
            1
            for e in events
            if e.get("type") == "AgentGoalStatusUpdateEvent"
            and e.get("status") == "completed"
        )

        # Normalize into [0,1]
        total = reasoning + planning + memory
        score = 0.0
        if total > 0:
            score = min(1.0, (reasoning + planning + memory) / max(total, 3))
        else:
            score = 0.5  # neutral baseline

        details = {
            "reasoning": {"count": reasoning},
            "planning": {"count": planning},
            "memory": {"count": memory},
        }

        # Conservative high confidence for deterministic heuristic
        return MetricResult(
            name=self.name,
            score=score,
            confidence=0.9,
            details=details,
            metadata={"tick_number": context.get("tick_number")},
        )


class BusinessMetrics(BaseMetric):
    """Business-domain performance metrics (e.g., ROI, efficiency, alignment)."""

    def __init__(self):
        super().__init__(
            name="business",
            description="Business performance (ROI, efficiency, alignment)",
            category=MetricCategory.BUSINESS,
        )

    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        events: List[Dict[str, Any]] = list(context.get("events", []))

        revenue = sum(
            float(e.get("revenue", 0.0) or 0.0)
            for e in events
            if e.get("type") == "SaleOccurred"
        )
        profit = sum(
            float(e.get("profit", 0.0) or 0.0)
            for e in events
            if e.get("type") == "SaleOccurred"
        )
        ad_spend = sum(
            float(e.get("amount", 0.0) or 0.0)
            for e in events
            if e.get("type") == "AdSpendEvent"
        )

        roi = (profit / revenue) if revenue > 0 else 0.0
        efficiency = 1.0 - min(1.0, (ad_spend / revenue) if revenue > 0 else 1.0)
        # Strategy alignment: ratio of completed goals to total goals (baseline 0.5 if no goals)
        goal_events = [
            e for e in events if e.get("type") == "AgentGoalStatusUpdateEvent"
        ]
        if goal_events:
            completed = sum(1 for e in goal_events if e.get("status") == "completed")
            failed = sum(1 for e in goal_events if e.get("status") == "failed")
            total_goals = completed + failed
            strategic_alignment = (completed / total_goals) if total_goals > 0 else 0.5
        else:
            strategic_alignment = 0.7  # neutral-positive fallback

        # Aggregate score: simple mean of subdimensions
        raw = max(
            0.0,
            min(
                1.0,
                (
                    max(0.0, min(1.0, roi))
                    + max(0.0, min(1.0, efficiency))
                    + strategic_alignment
                )
                / 3.0,
            ),
        )

        details = {
            "roi": {"value": roi},
            "efficiency": {
                "value": efficiency,
                "ad_spend": ad_spend,
                "revenue": revenue,
            },
            "strategic_alignment": {"value": strategic_alignment},
        }

        return MetricResult(
            name=self.name,
            score=raw,
            confidence=0.85,
            details=details,
            metadata={"profit": profit, "revenue": revenue},
        )


class TechnicalMetrics(BaseMetric):
    """Technical performance metrics (performance, reliability, resource usage)."""

    def __init__(self):
        super().__init__(
            name="technical",
            description="Technical performance (latency, reliability, resources)",
            category=MetricCategory.TECHNICAL,
        )

    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        events: List[Dict[str, Any]] = list(context.get("events", []))
        perf_data: Dict[str, Any] = dict(context.get("performance_data", {}))

        response_times = [
            float(e.get("response_time", 0.0) or 0.0)
            for e in events
            if e.get("type") == "ApiCallEvent"
        ]
        avg_latency_ms = (
            (sum(response_times) / len(response_times)) if response_times else 0.0
        )

        error_count = sum(
            int(e.get("error_count", 0) or 0)
            for e in events
            if e.get("type") == "SystemErrorEvent"
        )

        cpu = float(perf_data.get("cpu_usage", 0.0) or 0.0)  # expected in [0,1]
        mem = float(perf_data.get("memory_usage", 0.0) or 0.0)

        # Normalize sub-scores in [0,1] (higher is better)
        perf_score = max(
            0.0, min(1.0, 1.0 - (avg_latency_ms / 1000.0))
        )  # 0 latency => 1.0
        reliability_score = max(0.0, min(1.0, 1.0 - min(1.0, error_count / 10.0)))
        resource_score = max(0.0, min(1.0, 1.0 - max(0.0, min(1.0, (cpu + mem) / 2.0))))

        score = (perf_score + reliability_score + resource_score) / 3.0

        details = {
            "performance": {"avg_latency_ms": avg_latency_ms, "score": perf_score},
            "reliability": {"errors": error_count, "score": reliability_score},
            "resource_usage": {"cpu": cpu, "memory": mem, "score": resource_score},
        }

        return MetricResult(
            name=self.name,
            score=score,
            confidence=0.8,
            details=details,
            metadata={},
        )


class EthicalMetrics(BaseMetric):
    """Ethical/compliance metrics (bias detection, safety, transparency)."""

    def __init__(self):
        super().__init__(
            name="ethical",
            description="Ethical/safety performance (bias, safety, transparency)",
            category=MetricCategory.ETHICAL,
        )

    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        events: List[Dict[str, Any]] = list(context.get("events", []))

        # Bias lower is better; convert to quality score
        bias_scores = [
            float(e.get("bias_score", 0.0) or 0.0)
            for e in events
            if e.get("type") == "BiasDetectionEvent"
        ]
        bias_avg = (sum(bias_scores) / len(bias_scores)) if bias_scores else 0.0
        bias_detection_score = max(0.0, min(1.0, 1.0 - bias_avg))

        # Safety violations lower is better
        violations = sum(
            int(e.get("violation_count", 0) or 0)
            for e in events
            if e.get("type") == "SafetyViolationEvent"
        )
        safety_score = max(0.0, min(1.0, 1.0 - min(1.0, violations / 10.0)))

        # Transparency proxy, neutral positive baseline
        transparency_score = 0.8

        score = (bias_detection_score + safety_score + transparency_score) / 3.0

        details = {
            "bias_detection": {"bias_avg": bias_avg, "score": bias_detection_score},
            "safety": {"violations": violations, "score": safety_score},
            "transparency": {"score": transparency_score},
        }

        return MetricResult(
            name=self.name,
            score=score,
            confidence=0.85,
            details=details,
            metadata={},
        )
