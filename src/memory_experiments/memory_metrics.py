"""
Memory Metrics

Memory-specific evaluation metrics that integrate with FBA-Bench's existing
MetricSuite system to measure memory effectiveness and consolidation quality.
"""

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .memory_enforcer import MemoryEnforcer

logger = logging.getLogger(__name__)


@dataclass
class MemoryMetricResult:
    """Result from a memory metric calculation."""

    metric_name: str
    value: float
    timestamp: datetime
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class MemoryMetrics:
    """
    Memory-specific metrics for evaluating dual-memory system performance.

    Integrates with FBA-Bench's existing MetricSuite to provide comprehensive
    memory effectiveness evaluation alongside traditional performance metrics.
    """

    def __init__(self, memory_enforcer: Optional[MemoryEnforcer] = None):
        """
        Allow initialization without a provided MemoryEnforcer for unit tests.
        When not provided, construct a minimal stub with the attributes used by metrics.
        """
        if memory_enforcer is None:

            class _StubStore:
                async def size(self) -> int:
                    return 0

                async def get_all(self):
                    return []

                async def retrieve(self, *a, **k):
                    return []

                async def clear(self):
                    return True

            class _StubManager:
                def __init__(self):
                    self.short_term_store = _StubStore()
                    self.long_term_store = _StubStore()
                    self.config = type(
                        "Cfg",
                        (),
                        {
                            "short_term_capacity": 0,
                            "long_term_capacity": 0,
                            "memory_domains": [],
                        },
                    )()
                    self.agent_id = "test"

            class _StubEnforcer:
                def __init__(self):
                    self.memory_manager = _StubManager()
                    self.reflection_module = None
                    self.memory_injection_history = []
                    self.total_memory_retrievals = 0

            memory_enforcer = _StubEnforcer()  # type: ignore[assignment]

        self.memory_enforcer = memory_enforcer  # type: ignore[assignment]
        self.memory_manager = memory_enforcer.memory_manager  # type: ignore[union-attr]
        self.reflection_module = getattr(memory_enforcer, "reflection_module", None)

        # Metric history for trend analysis
        self.metric_history: List[MemoryMetricResult] = []

        # Cache for expensive calculations
        self._metric_cache: Dict[str, Tuple[datetime, float]] = {}
        self._cache_ttl = timedelta(minutes=5)

        # Back-compat for tests expecting a _metrics container
        self._metrics: Dict[str, MemoryMetricResult] = {}

        logger.info(
            f"MemoryMetrics initialized for agent {self.memory_manager.agent_id}"
        )

    async def calculate_all_metrics(self) -> Dict[str, MemoryMetricResult]:
        """Calculate all memory metrics and return as a dictionary."""

        current_time = datetime.now()
        results = {}

        # Memory utilization metrics
        results["memory_utilization"] = await self.calculate_memory_utilization()
        results["memory_efficiency"] = await self.calculate_memory_efficiency()
        results["retrieval_precision"] = await self.calculate_retrieval_precision()

        # Memory quality metrics
        results["memory_relevance"] = await self.calculate_memory_relevance()
        results["temporal_coherence"] = await self.calculate_temporal_coherence()
        results["domain_coverage"] = await self.calculate_domain_coverage()

        # Consolidation metrics (if reflection enabled)
        if self.reflection_module:
            results["consolidation_quality"] = (
                await self.calculate_consolidation_quality()
            )
            results["reflection_effectiveness"] = (
                await self.calculate_reflection_effectiveness()
            )
            results["memory_promotion_rate"] = (
                await self.calculate_memory_promotion_rate()
            )

        # Memory vs. performance correlation
        results["memory_performance_correlation"] = (
            await self.calculate_memory_performance_correlation()
        )
        results["forgetting_cost"] = await self.calculate_forgetting_cost()

        # Advanced metrics
        results["memory_diversity"] = await self.calculate_memory_diversity()
        results["access_pattern_analysis"] = (
            await self.calculate_access_pattern_analysis()
        )

        # Store results in history
        for result in results.values():
            self.metric_history.append(result)

        # Keep only recent history
        cutoff_time = current_time - timedelta(hours=24)
        self.metric_history = [
            metric for metric in self.metric_history if metric.timestamp > cutoff_time
        ]

        return results

    async def calculate_memory_utilization(self) -> MemoryMetricResult:
        """Calculate how effectively memory capacity is being used."""

        short_term_size = await self.memory_manager.short_term_store.size()
        long_term_size = await self.memory_manager.long_term_store.size()

        total_capacity = (
            self.memory_manager.config.short_term_capacity
            + self.memory_manager.config.long_term_capacity
        )
        total_used = short_term_size + long_term_size

        utilization = total_used / total_capacity if total_capacity > 0 else 0.0

        return MemoryMetricResult(
            metric_name="memory_utilization",
            value=utilization,
            timestamp=datetime.now(),
            metadata={
                "short_term_used": short_term_size,
                "long_term_used": long_term_size,
                "total_capacity": total_capacity,
                "utilization_breakdown": {
                    "short_term": short_term_size
                    / self.memory_manager.config.short_term_capacity,
                    "long_term": long_term_size
                    / self.memory_manager.config.long_term_capacity,
                },
            },
        )

    async def calculate_memory_efficiency(self) -> MemoryMetricResult:
        """Calculate memory efficiency as useful retrievals per memory stored."""

        total_retrievals = self.memory_enforcer.total_memory_retrievals  # type: ignore[union-attr]
        total_memories = (
            await self.memory_manager.short_term_store.size()
            + await self.memory_manager.long_term_store.size()
        )

        efficiency = total_retrievals / total_memories if total_memories > 0 else 0.0

        return MemoryMetricResult(
            metric_name="memory_efficiency",
            value=efficiency,
            timestamp=datetime.now(),
            metadata={
                "total_retrievals": total_retrievals,
                "total_memories": total_memories,
                "retrieval_rate": total_retrievals / max(1, total_memories),
            },
        )

    async def calculate_retrieval_precision(self) -> MemoryMetricResult:
        """Calculate precision of memory retrieval based on access patterns."""

        # Get recent injection history
        recent_injections = self.memory_enforcer.memory_injection_history[-10:]  # type: ignore[union-attr]

        if not recent_injections:
            return MemoryMetricResult(
                metric_name="retrieval_precision",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_recent_retrievals"},
            )

        # Calculate average relevance based on whether memories fit in budget
        precision_scores = []
        for injection in recent_injections:
            if injection["within_budget"]:
                # Assume higher precision if memories fit budget (proxy metric)
                precision_scores.append(0.8)
            else:
                precision_scores.append(0.4)

        precision = statistics.mean(precision_scores) if precision_scores else 0.0

        return MemoryMetricResult(
            metric_name="retrieval_precision",
            value=precision,
            timestamp=datetime.now(),
            metadata={
                "recent_injections": len(recent_injections),
                "avg_memories_per_retrieval": (
                    statistics.mean(
                        [inj["retrieved_memories"] for inj in recent_injections]
                    )
                    if recent_injections
                    else 0
                ),
                "budget_fit_rate": sum(
                    1 for inj in recent_injections if inj["within_budget"]
                )
                / len(recent_injections),
            },
        )

    async def calculate_memory_relevance(self) -> MemoryMetricResult:
        """Calculate average relevance of stored memories."""

        short_term_memories = await self.memory_manager.short_term_store.get_all()
        long_term_memories = await self.memory_manager.long_term_store.get_all()
        all_memories = short_term_memories + long_term_memories

        if not all_memories:
            return MemoryMetricResult(
                metric_name="memory_relevance",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_memories"},
            )

        # Calculate relevance based on importance scores and access patterns
        relevance_scores = []
        current_time = datetime.now()

        for memory in all_memories:
            base_relevance = memory.importance_score

            # Boost relevance for recently accessed memories
            if memory.last_accessed:
                hours_since_access = (
                    current_time - memory.last_accessed
                ).total_seconds() / 3600
                access_boost = max(
                    0, 0.2 * (1 - hours_since_access / 168)
                )  # Decay over a week
                base_relevance += access_boost

            # Boost for frequently accessed memories
            frequency_boost = min(0.3, memory.access_count * 0.05)
            base_relevance += frequency_boost

            relevance_scores.append(min(1.0, base_relevance))

        avg_relevance = statistics.mean(relevance_scores)

        return MemoryMetricResult(
            metric_name="memory_relevance",
            value=avg_relevance,
            timestamp=datetime.now(),
            metadata={
                "total_memories": len(all_memories),
                "avg_importance_score": statistics.mean(
                    [m.importance_score for m in all_memories]
                ),
                "avg_access_count": statistics.mean(
                    [m.access_count for m in all_memories]
                ),
                "accessed_memories": len(
                    [m for m in all_memories if m.access_count > 0]
                ),
            },
        )

    async def calculate_temporal_coherence(self) -> MemoryMetricResult:
        """Calculate how well memories are distributed across time."""

        all_memories = (
            await self.memory_manager.short_term_store.get_all()
            + await self.memory_manager.long_term_store.get_all()
        )

        if len(all_memories) < 2:
            return MemoryMetricResult(
                metric_name="temporal_coherence",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "insufficient_memories"},
            )

        # Calculate time distribution
        timestamps = [memory.timestamp for memory in all_memories]
        timestamps.sort()

        # Calculate time gaps between consecutive memories
        time_gaps = []
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600  # in hours
            time_gaps.append(gap)

        # Coherence is higher when memories are more evenly distributed
        if not time_gaps:
            coherence = 0.0
        else:
            gap_variance = statistics.variance(time_gaps) if len(time_gaps) > 1 else 0
            mean_gap = statistics.mean(time_gaps)
            # Normalize coherence (lower variance = higher coherence)
            coherence = 1.0 / (1.0 + gap_variance / max(1, mean_gap))

        return MemoryMetricResult(
            metric_name="temporal_coherence",
            value=coherence,
            timestamp=datetime.now(),
            metadata={
                "time_span_hours": (timestamps[-1] - timestamps[0]).total_seconds()
                / 3600,
                "avg_gap_hours": statistics.mean(time_gaps) if time_gaps else 0,
                "gap_variance": gap_variance if len(time_gaps) > 1 else 0,
                "memory_count": len(all_memories),
            },
        )

    async def calculate_domain_coverage(self) -> MemoryMetricResult:
        """Calculate coverage across different memory domains."""

        all_memories = (
            await self.memory_manager.short_term_store.get_all()
            + await self.memory_manager.long_term_store.get_all()
        )

        if not all_memories:
            return MemoryMetricResult(
                metric_name="domain_coverage",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_memories"},
            )

        # Count memories per domain
        domain_counts = {}  # type: ignore[var-annotated]
        for memory in all_memories:
            domain = memory.domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Calculate coverage as entropy (higher entropy = better coverage)
        total_memories = len(all_memories)
        entropy = 0.0

        for count in domain_counts.values():
            if count > 0:
                probability = count / total_memories
                entropy -= (
                    probability * math.log2(probability) if probability > 0 else 0
                )

        # Normalize entropy by maximum possible entropy
        max_domains = len(self.memory_manager.config.memory_domains)
        max_entropy = math.log2(max_domains) if max_domains > 1 else 1.0
        coverage = entropy / max_entropy if max_entropy > 0 else 0.0

        return MemoryMetricResult(
            metric_name="domain_coverage",
            value=coverage,
            timestamp=datetime.now(),
            metadata={
                "domain_counts": domain_counts,
                "unique_domains": len(domain_counts),
                "total_domains": len(self.memory_manager.config.memory_domains),
                "entropy": entropy,
            },
        )

    async def calculate_consolidation_quality(self) -> MemoryMetricResult:
        """Calculate quality of memory consolidation process."""

        if not self.reflection_module:
            return MemoryMetricResult(
                metric_name="consolidation_quality",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "reflection_disabled"},
            )

        reflection_stats = self.reflection_module.get_reflection_statistics()

        if reflection_stats["total_reflections"] == 0:
            return MemoryMetricResult(
                metric_name="consolidation_quality",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_reflections"},
            )

        # Use the composite quality score from reflection statistics
        quality = reflection_stats.get("avg_quality_score", 0.0)

        return MemoryMetricResult(
            metric_name="consolidation_quality",
            value=quality,
            timestamp=datetime.now(),
            metadata={
                "total_reflections": reflection_stats["total_reflections"],
                "avg_promotion_rate": reflection_stats["avg_promotion_rate"],
                "total_promotions": reflection_stats["total_memories_promoted"],
            },
        )

    async def calculate_reflection_effectiveness(self) -> MemoryMetricResult:
        """Calculate effectiveness of the reflection process."""

        if not self.reflection_module:
            return MemoryMetricResult(
                metric_name="reflection_effectiveness",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "reflection_disabled"},
            )

        reflection_stats = self.reflection_module.get_reflection_statistics()

        # Effectiveness based on promotion rate and quality metrics
        promotion_rate = reflection_stats.get("avg_promotion_rate", 0.0)
        quality_score = reflection_stats.get("avg_quality_score", 0.0)

        # Combine promotion rate and quality (not too high, not too low promotion rate is ideal)
        ideal_promotion_rate = 0.3  # 30% promotion rate is considered optimal
        rate_score = 1.0 - abs(promotion_rate - ideal_promotion_rate)

        effectiveness = rate_score * 0.6 + quality_score * 0.4

        return MemoryMetricResult(
            metric_name="reflection_effectiveness",
            value=effectiveness,
            timestamp=datetime.now(),
            metadata={
                "promotion_rate": promotion_rate,
                "quality_score": quality_score,
                "rate_score": rate_score,
                "ideal_promotion_rate": ideal_promotion_rate,
            },
        )

    async def calculate_memory_promotion_rate(self) -> MemoryMetricResult:
        """Calculate rate of memory promotion from short-term to long-term storage."""

        if not self.reflection_module:
            return MemoryMetricResult(
                metric_name="memory_promotion_rate",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "reflection_disabled"},
            )

        reflection_stats = self.reflection_module.get_reflection_statistics()
        promotion_rate = reflection_stats.get("avg_promotion_rate", 0.0)

        return MemoryMetricResult(
            metric_name="memory_promotion_rate",
            value=promotion_rate,
            timestamp=datetime.now(),
            metadata=reflection_stats,
        )

    async def calculate_memory_performance_correlation(self) -> MemoryMetricResult:
        """Calculate correlation between memory usage and performance."""

        injection_history = self.memory_enforcer.memory_injection_history  # type: ignore[union-attr]

        if len(injection_history) < 5:
            return MemoryMetricResult(
                metric_name="memory_performance_correlation",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "insufficient_data"},
            )

        # Extract memory usage and performance indicators from injection history
        recent_history = injection_history[
            -20:
        ]  # Use last 20 injections for better statistical significance

        # Memory usage metrics
        memory_usage = [inj.get("memory_tokens", 0) for inj in recent_history]
        memories_retrieved = [
            inj.get("retrieved_memories", 0) for inj in recent_history
        ]

        # Performance indicators (proxy metrics since we don't have direct performance data)
        # 1. Budget efficiency (higher is better)
        budget_efficiency = [
            1.0 if inj.get("within_budget", False) else 0.0 for inj in recent_history
        ]

        # 2. Memory utilization efficiency (optimal range is 0.6-0.8)
        utilization_efficiency = []
        for inj in recent_history:
            memory_ratio = inj.get("memory_tokens", 0) / max(
                1, inj.get("token_budget", 1000)
            )
            if 0.6 <= memory_ratio <= 0.8:
                utilization_efficiency.append(1.0)
            else:
                # Score decreases as utilization moves away from optimal range
                utilization_efficiency.append(
                    max(0.0, 1.0 - abs(memory_ratio - 0.7) * 2)
                )

        # 3. Memory diversity score (based on variety of memories retrieved)
        diversity_scores = []
        for inj in recent_history:
            # Use retrieved memories count as a proxy for diversity
            diversity = min(
                1.0, inj.get("retrieved_memories", 0) / 10.0
            )  # Normalize by expected max
            diversity_scores.append(diversity)

        # Calculate composite performance score
        performance_scores = []
        for i in range(len(recent_history)):
            # Weighted combination of performance indicators
            perf_score = (
                budget_efficiency[i] * 0.4  # 40% weight for budget efficiency
                + utilization_efficiency[i]
                * 0.4  # 40% weight for utilization efficiency
                + diversity_scores[i] * 0.2  # 20% weight for diversity
            )
            performance_scores.append(perf_score)

        # Calculate correlations between memory metrics and performance
        correlations = {}

        # Memory usage vs performance correlation
        if len(set(memory_usage)) > 1 and len(set(performance_scores)) > 1:
            try:
                usage_perf_corr = statistics.correlation(
                    memory_usage, performance_scores
                )
                correlations["usage_performance"] = usage_perf_corr
            except statistics.StatisticsError:
                correlations["usage_performance"] = 0.0

        # Memory count vs performance correlation
        if len(set(memories_retrieved)) > 1 and len(set(performance_scores)) > 1:
            try:
                count_perf_corr = statistics.correlation(
                    memories_retrieved, performance_scores
                )
                correlations["count_performance"] = count_perf_corr
            except statistics.StatisticsError:
                correlations["count_performance"] = 0.0

        # Calculate overall correlation score (weighted average of individual correlations)
        overall_correlation = 0.0
        if correlations:
            weights = {"usage_performance": 0.7, "count_performance": 0.3}
            for corr_name, weight in weights.items():
                if corr_name in correlations:
                    overall_correlation += correlations[corr_name] * weight

        return MemoryMetricResult(
            metric_name="memory_performance_correlation",
            value=overall_correlation,
            timestamp=datetime.now(),
            metadata={
                "sample_size": len(recent_history),
                "correlations": correlations,
                "avg_memory_usage": (
                    statistics.mean(memory_usage) if memory_usage else 0.0
                ),
                "avg_performance_score": (
                    statistics.mean(performance_scores) if performance_scores else 0.0
                ),
                "performance_distribution": {
                    "min": min(performance_scores) if performance_scores else 0.0,
                    "max": max(performance_scores) if performance_scores else 0.0,
                    "std_dev": (
                        statistics.stdev(performance_scores)
                        if len(performance_scores) > 1
                        else 0.0
                    ),
                },
            },
        )

    async def calculate_forgetting_cost(self) -> MemoryMetricResult:
        """Calculate the cost of forgetting (performance impact of memory limitations)."""

        # Estimate forgetting cost based on failed memory retrievals and truncations
        injection_history = self.memory_enforcer.memory_injection_history  # type: ignore[union-attr]

        if not injection_history:
            return MemoryMetricResult(
                metric_name="forgetting_cost",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_retrieval_history"},
            )

        # Calculate cost based on budget overruns (truncated memories)
        total_retrievals = len(injection_history)
        budget_failures = sum(
            1 for inj in injection_history if not inj["within_budget"]
        )

        forgetting_cost = (
            budget_failures / total_retrievals if total_retrievals > 0 else 0.0
        )

        return MemoryMetricResult(
            metric_name="forgetting_cost",
            value=forgetting_cost,
            timestamp=datetime.now(),
            metadata={
                "total_retrievals": total_retrievals,
                "budget_failures": budget_failures,
                "failure_rate": forgetting_cost,
            },
        )

    async def calculate_memory_diversity(self) -> MemoryMetricResult:
        """Calculate diversity of memory content and types."""

        all_memories = (
            await self.memory_manager.short_term_store.get_all()
            + await self.memory_manager.long_term_store.get_all()
        )

        if not all_memories:
            return MemoryMetricResult(
                metric_name="memory_diversity",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_memories"},
            )

        # Calculate diversity across multiple dimensions
        event_types = set(memory.event_type for memory in all_memories)
        domains = set(memory.domain for memory in all_memories)

        # Temporal diversity (memories spread across time)
        timestamps = [memory.timestamp for memory in all_memories]
        time_span = (
            (max(timestamps) - min(timestamps)).total_seconds() / 3600
            if len(timestamps) > 1
            else 0
        )

        # Combine diversity measures
        type_diversity = len(event_types) / 10.0  # Normalize by expected max types
        domain_diversity = len(domains) / len(self.memory_manager.config.memory_domains)
        temporal_diversity = min(1.0, time_span / 168)  # Normalize by week

        overall_diversity = (type_diversity + domain_diversity + temporal_diversity) / 3

        return MemoryMetricResult(
            metric_name="memory_diversity",
            value=overall_diversity,
            timestamp=datetime.now(),
            metadata={
                "event_types": len(event_types),
                "domains": len(domains),
                "time_span_hours": time_span,
                "type_diversity": type_diversity,
                "domain_diversity": domain_diversity,
                "temporal_diversity": temporal_diversity,
            },
        )

    async def calculate_access_pattern_analysis(self) -> MemoryMetricResult:
        """Analyze memory access patterns for optimization insights."""

        all_memories = (
            await self.memory_manager.short_term_store.get_all()
            + await self.memory_manager.long_term_store.get_all()
        )

        if not all_memories:
            return MemoryMetricResult(
                metric_name="access_pattern_analysis",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_memories"},
            )

        # Analyze access patterns
        accessed_memories = [m for m in all_memories if m.access_count > 0]

        if not accessed_memories:
            return MemoryMetricResult(
                metric_name="access_pattern_analysis",
                value=0.0,
                timestamp=datetime.now(),
                metadata={"reason": "no_accessed_memories"},
            )

        # Calculate access pattern metrics
        access_rates = [m.access_count for m in accessed_memories]
        avg_access_rate = statistics.mean(access_rates)
        access_variance = (
            statistics.variance(access_rates) if len(access_rates) > 1 else 0
        )

        # Higher score for consistent access patterns (lower variance relative to mean)
        pattern_score = 1.0 / (1.0 + access_variance / max(1, avg_access_rate))

        return MemoryMetricResult(
            metric_name="access_pattern_analysis",
            value=pattern_score,
            timestamp=datetime.now(),
            metadata={
                "total_memories": len(all_memories),
                "accessed_memories": len(accessed_memories),
                "access_rate": len(accessed_memories) / len(all_memories),
                "avg_access_count": avg_access_rate,
                "access_variance": access_variance,
            },
        )

    def get_metric_trends(self, metric_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get trend analysis for a specific metric."""

        cutoff_time = datetime.now() - timedelta(hours=hours)
        metric_history = [
            metric
            for metric in self.metric_history
            if metric.metric_name == metric_name and metric.timestamp > cutoff_time
        ]

        if len(metric_history) < 2:
            return {"trend": "insufficient_data", "values": []}

        values = [metric.value for metric in metric_history]
        timestamps = [metric.timestamp for metric in metric_history]

        # Calculate trend
        if len(values) >= 3:
            # Simple linear trend calculation
            x = list(range(len(values)))
            y = values
            n = len(x)

            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))

            slope = (
                (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
                if (n * sum_x2 - sum_x**2) != 0
                else 0
            )

            if slope > 0.01:
                trend = "increasing"
            elif slope < -0.01:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "values": values,
            "timestamps": [ts.isoformat() for ts in timestamps],
            "latest_value": values[-1] if values else 0.0,
            "min_value": min(values) if values else 0.0,
            "max_value": max(values) if values else 0.0,
            "avg_value": statistics.mean(values) if values else 0.0,
        }

    def get_comprehensive_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of all memory metrics."""

        # Get latest values for each metric type
        latest_metrics = {}
        for metric in reversed(self.metric_history):
            if metric.metric_name not in latest_metrics:
                latest_metrics[metric.metric_name] = metric.value

        return {
            "summary_timestamp": datetime.now().isoformat(),
            "memory_system_health": self._calculate_system_health_score(latest_metrics),
            "latest_metrics": latest_metrics,
            "metric_count": len(self.metric_history),
            "recommendations": self._generate_recommendations(latest_metrics),
        }

    def _calculate_system_health_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall memory system health score."""

        # Weight different metrics by importance
        weights = {
            "memory_efficiency": 0.2,
            "retrieval_precision": 0.2,
            "memory_relevance": 0.15,
            "consolidation_quality": 0.15,
            "temporal_coherence": 0.1,
            "domain_coverage": 0.1,
            "memory_diversity": 0.1,
        }

        weighted_score = 0.0
        total_weight = 0.0

        for metric_name, weight in weights.items():
            if metric_name in metrics:
                weighted_score += metrics[metric_name] * weight
                total_weight += weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def _generate_recommendations(self, metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations based on metric values."""

        recommendations = []

        # Memory utilization recommendations
        if metrics.get("memory_utilization", 0) < 0.3:
            recommendations.append(
                "Consider reducing memory capacity or increasing retention period"
            )
        elif metrics.get("memory_utilization", 0) > 0.9:
            recommendations.append(
                "Memory utilization is high - consider increasing capacity"
            )

        # Efficiency recommendations
        if metrics.get("memory_efficiency", 0) < 0.5:
            recommendations.append(
                "Low memory efficiency - review retrieval patterns and memory relevance"
            )

        # Consolidation recommendations
        if metrics.get("consolidation_quality", 0) < 0.5:
            recommendations.append(
                "Poor consolidation quality - consider adjusting consolidation algorithm"
            )

        # Diversity recommendations
        if metrics.get("domain_coverage", 0) < 0.6:
            recommendations.append(
                "Limited domain coverage - ensure balanced memory collection across domains"
            )

        return (
            recommendations
            if recommendations
            else ["Memory system operating within normal parameters"]
        )
