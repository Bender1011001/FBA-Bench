"""
Enhanced Evaluation Framework for FBA-Bench.

This module provides a comprehensive evaluation framework for multi-dimensional assessment
of agent performance, including task completion, efficiency, creativity, safety, and other
critical dimensions of agent capabilities.
"""

import asyncio
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from scipy import stats
from sklearn.cluster import DBSCAN

from ..core.results import AgentRunResult, ScenarioResult
from ..metrics.comparative_analysis import ComparativeAnalysisEngine

logger = logging.getLogger(__name__)


class EvaluationDimension(Enum):
    """Dimensions of agent evaluation."""

    TASK_COMPLETION = "task_completion"
    EFFICIENCY = "efficiency"
    CREATIVITY = "creativity"
    SAFETY = "safety"
    ADAPTABILITY = "adaptability"
    ROBUSTNESS = "robustness"
    COLLABORATION = "collaboration"
    DECISION_QUALITY = "decision_quality"
    LEARNING_RATE = "learning_rate"
    RESOURCE_UTILIZATION = "resource_utilization"


class EvaluationGranularity(Enum):
    """Granularity levels for evaluation."""

    COARSE = "coarse"  # High-level overview
    MEDIUM = "medium"  # Balanced detail
    FINE = "fine"  # Detailed analysis
    COMPREHENSIVE = "comprehensive"  # Maximum detail


@dataclass
class DimensionWeight:
    """Weight configuration for evaluation dimensions."""

    dimension: EvaluationDimension
    weight: float
    importance: str  # "low", "medium", "high", "critical"
    description: str = ""


@dataclass
class EvaluationConfig:
    """Configuration for the evaluation framework."""

    name: str
    description: str
    dimensions: List[DimensionWeight]
    granularity: EvaluationGranularity
    include_comparative_analysis: bool = True
    include_trend_analysis: bool = True
    include_statistical_significance: bool = True
    include_benchmark_comparison: bool = True
    custom_metrics: List[str] = field(default_factory=list)
    scenario_weights: Dict[str, float] = field(default_factory=dict)
    baseline_agent_id: Optional[str] = None
    evaluation_timeout_seconds: int = 300


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    dimension: EvaluationDimension
    score: float
    confidence: float
    details: Dict[str, Any]
    trend: str  # "improving", "declining", "stable"
    significance: float  # Statistical significance


@dataclass
class MultiDimensionalEvaluation:
    """Multi-dimensional evaluation result."""

    agent_id: str
    scenario_name: str
    timestamp: datetime
    overall_score: float
    dimension_scores: List[DimensionScore]
    comparative_performance: Dict[str, float]
    trend_analysis: Dict[str, Any]
    statistical_significance: Dict[str, float]
    benchmark_comparison: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "scenario_name": self.scenario_name,
            "timestamp": self.timestamp.isoformat(),
            "overall_score": self.overall_score,
            "dimension_scores": [
                {
                    "dimension": ds.dimension.value,
                    "score": ds.score,
                    "confidence": ds.confidence,
                    "details": ds.details,
                    "trend": ds.trend,
                    "significance": ds.significance,
                }
                for ds in self.dimension_scores
            ],
            "comparative_performance": self.comparative_performance,
            "trend_analysis": self.trend_analysis,
            "statistical_significance": self.statistical_significance,
            "benchmark_comparison": self.benchmark_comparison,
            "metadata": self.metadata,
        }


@dataclass
class EvaluationProfile:
    """Comprehensive evaluation profile for an agent."""

    agent_id: str
    evaluations: List[MultiDimensionalEvaluation]
    profile_created: datetime
    last_updated: datetime
    performance_summary: Dict[str, Any]
    strengths: List[EvaluationDimension]
    weaknesses: List[EvaluationDimension]
    improvement_areas: List[str]
    overall_trend: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "evaluations": [eval.to_dict() for eval in self.evaluations],
            "profile_created": self.profile_created.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "performance_summary": self.performance_summary,
            "strengths": [s.value for s in self.strengths],
            "weaknesses": [w.value for w in self.weaknesses],
            "improvement_areas": self.improvement_areas,
            "overall_trend": self.overall_trend,
        }


class EnhancedEvaluationFramework:
    """
    Enhanced evaluation framework for multi-dimensional agent assessment.

    This framework provides comprehensive evaluation capabilities including:
    - Multi-dimensional performance assessment
    - Comparative analysis between agents
    - Trend analysis over time
    - Statistical significance testing
    - Benchmark comparison
    - Performance profiling
    """

    def __init__(self, config: EvaluationConfig):
        """Initialize the evaluation framework."""
        self.config = config
        self.comparative_engine = ComparativeAnalysisEngine()
        self.evaluation_history: Dict[str, List[MultiDimensionalEvaluation]] = {}
        self.agent_profiles: Dict[str, EvaluationProfile] = {}
        self.benchmark_data: Dict[str, Any] = {}

        # Validate dimension weights
        total_weight = sum(dw.weight for dw in config.dimensions)
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Dimension weights must sum to 1.0, got {total_weight}")

        logger.info(
            f"Initialized EnhancedEvaluationFramework with {len(config.dimensions)} dimensions"
        )

    async def evaluate_agent(
        self,
        agent_id: str,
        scenario_result: ScenarioResult,
        context: Dict[str, Any] = None,
    ) -> MultiDimensionalEvaluation:
        """
        Evaluate an agent's performance across multiple dimensions.

        Args:
            agent_id: ID of the agent to evaluate
            scenario_result: Scenario result containing agent performance data
            context: Additional context for evaluation

        Returns:
            Multi-dimensional evaluation result
        """
        logger.info(
            f"Evaluating agent {agent_id} on scenario {scenario_result.scenario_name}"
        )

        if context is None:
            context = {}

        # Get agent results
        agent_results = scenario_result.get_agent_results(agent_id)
        if not agent_results:
            logger.warning(
                f"No results found for agent {agent_id} in scenario {scenario_result.scenario_name}"
            )
            return self._create_empty_evaluation(
                agent_id, scenario_result.scenario_name
            )

        # Calculate dimension scores
        dimension_scores = await self._calculate_dimension_scores(
            agent_id, agent_results, context
        )

        # Calculate overall score
        overall_score = self._calculate_overall_score(dimension_scores)

        # Perform comparative analysis if enabled
        comparative_performance = {}
        if self.config.include_comparative_analysis:
            comparative_performance = await self._perform_comparative_analysis(
                agent_id, scenario_result, dimension_scores
            )

        # Perform trend analysis if enabled
        trend_analysis = {}
        if self.config.include_trend_analysis:
            trend_analysis = await self._perform_trend_analysis(
                agent_id, dimension_scores
            )

        # Calculate statistical significance if enabled
        statistical_significance = {}
        if self.config.include_statistical_significance:
            statistical_significance = await self._calculate_statistical_significance(
                agent_id, agent_results, dimension_scores
            )

        # Perform benchmark comparison if enabled
        benchmark_comparison = {}
        if self.config.include_benchmark_comparison and self.config.baseline_agent_id:
            benchmark_comparison = await self._perform_benchmark_comparison(
                agent_id, scenario_result, dimension_scores
            )

        # Create evaluation result
        evaluation = MultiDimensionalEvaluation(
            agent_id=agent_id,
            scenario_name=scenario_result.scenario_name,
            timestamp=datetime.now(),
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            comparative_performance=comparative_performance,
            trend_analysis=trend_analysis,
            statistical_significance=statistical_significance,
            benchmark_comparison=benchmark_comparison,
            metadata={
                "granularity": self.config.granularity.value,
                "evaluation_config": self.config.name,
                "num_runs": len(agent_results),
            },
        )

        # Store evaluation in history
        if agent_id not in self.evaluation_history:
            self.evaluation_history[agent_id] = []
        self.evaluation_history[agent_id].append(evaluation)

        # Update agent profile
        await self._update_agent_profile(agent_id)

        logger.info(
            f"Completed evaluation for agent {agent_id}: overall score {overall_score:.3f}"
        )
        return evaluation

    async def evaluate_multiple_agents(
        self,
        agent_ids: List[str],
        scenario_result: ScenarioResult,
        context: Dict[str, Any] = None,
    ) -> Dict[str, MultiDimensionalEvaluation]:
        """
        Evaluate multiple agents on the same scenario.

        Args:
            agent_ids: List of agent IDs to evaluate
            scenario_result: Scenario result containing agent performance data
            context: Additional context for evaluation

        Returns:
            Dictionary mapping agent IDs to evaluation results
        """
        logger.info(
            f"Evaluating {len(agent_ids)} agents on scenario {scenario_result.scenario_name}"
        )

        # Evaluate all agents in parallel
        evaluation_tasks = []
        for agent_id in agent_ids:
            task = self.evaluate_agent(agent_id, scenario_result, context)
            evaluation_tasks.append(task)

        evaluations = await asyncio.gather(*evaluation_tasks, return_exceptions=True)

        # Process results
        results = {}
        for agent_id, evaluation in zip(agent_ids, evaluations):
            if isinstance(evaluation, Exception):
                logger.error(f"Error evaluating agent {agent_id}: {evaluation}")
                results[agent_id] = self._create_empty_evaluation(
                    agent_id, scenario_result.scenario_name
                )
            else:
                results[agent_id] = evaluation  # type: ignore[assignment]

        return results

    async def create_agent_profile(
        self, agent_id: str, include_history: bool = True
    ) -> EvaluationProfile:
        """
        Create a comprehensive profile for an agent.

        Args:
            agent_id: ID of the agent
            include_history: Whether to include historical evaluations

        Returns:
            Agent evaluation profile
        """
        logger.info(f"Creating profile for agent {agent_id}")

        # Get evaluation history
        evaluations = self.evaluation_history.get(agent_id, [])
        if not evaluations:
            logger.warning(f"No evaluation history found for agent {agent_id}")
            return self._create_empty_profile(agent_id)

        # Calculate performance summary
        performance_summary = self._calculate_performance_summary(evaluations)

        # Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(evaluations)

        # Identify improvement areas
        improvement_areas = self._identify_improvement_areas(evaluations)

        # Determine overall trend
        overall_trend = self._determine_overall_trend(evaluations)

        # Create profile
        profile = EvaluationProfile(
            agent_id=agent_id,
            evaluations=evaluations if include_history else [],
            profile_created=datetime.now(),
            last_updated=datetime.now(),
            performance_summary=performance_summary,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_areas=improvement_areas,
            overall_trend=overall_trend,
        )

        # Store profile
        self.agent_profiles[agent_id] = profile

        logger.info(
            f"Created profile for agent {agent_id} with {len(evaluations)} evaluations"
        )
        return profile

    async def generate_evaluation_report(
        self,
        agent_ids: List[str],
        format_type: str = "json",
        include_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive evaluation report.

        Args:
            agent_ids: List of agent IDs to include in the report
            format_type: Output format ("json", "html", "markdown")
            include_recommendations: Whether to include improvement recommendations

        Returns:
            Evaluation report data
        """
        logger.info(f"Generating evaluation report for {len(agent_ids)} agents")

        # Create or get agent profiles
        profiles = {}
        for agent_id in agent_ids:
            if agent_id in self.agent_profiles:
                profiles[agent_id] = self.agent_profiles[agent_id]
            else:
                profiles[agent_id] = await self.create_agent_profile(agent_id)

        # Generate comparative analysis
        comparative_analysis = await self._generate_comparative_report(profiles)

        # Generate recommendations if requested
        recommendations = {}
        if include_recommendations:
            recommendations = await self._generate_recommendations(profiles)

        # Create report structure
        report = {
            "report_generated": datetime.now().isoformat(),
            "report_config": {
                "name": self.config.name,
                "description": self.config.description,
                "dimensions": [dw.dimension.value for dw in self.config.dimensions],
                "granularity": self.config.granularity.value,
            },
            "agent_profiles": {aid: p.to_dict() for aid, p in profiles.items()},
            "comparative_analysis": comparative_analysis,
            "recommendations": recommendations,
            "summary_statistics": self._generate_summary_statistics(profiles),
        }

        logger.info(f"Generated evaluation report with {len(agent_ids)} agents")
        return report

    async def _calculate_dimension_scores(
        self,
        agent_id: str,
        agent_results: List[AgentRunResult],
        context: Dict[str, Any],
    ) -> List[DimensionScore]:
        """Calculate scores for each evaluation dimension."""
        dimension_scores = []

        for dim_weight in self.config.dimensions:
            dimension = dim_weight.dimension

            # Calculate dimension score based on available metrics
            score, confidence, details = await self._calculate_single_dimension_score(
                dimension, agent_results, context
            )

            # Determine trend
            trend = self._determine_dimension_trend(agent_id, dimension, score)

            # Calculate statistical significance
            significance = self._calculate_dimension_significance(
                dimension, agent_results, score
            )

            dimension_scores.append(
                DimensionScore(
                    dimension=dimension,
                    score=score,
                    confidence=confidence,
                    details=details,
                    trend=trend,
                    significance=significance,
                )
            )

        return dimension_scores

    async def _calculate_single_dimension_score(
        self,
        dimension: EvaluationDimension,
        agent_results: List[AgentRunResult],
        context: Dict[str, Any],
    ) -> Tuple[float, float, Dict[str, Any]]:
        """Calculate score for a single dimension."""
        # Extract relevant metrics for this dimension
        relevant_metrics = self._get_relevant_metrics(dimension)

        if not relevant_metrics:
            logger.warning(f"No relevant metrics found for dimension {dimension.value}")
            return 0.5, 0.0, {"error": "No relevant metrics"}

        # Collect metric values
        metric_values = []
        metric_details = {}  # type: ignore[var-annotated]

        for agent_result in agent_results:
            for metric in agent_result.metrics:
                if metric.name in relevant_metrics:
                    metric_values.append(metric.value)
                    if metric.name not in metric_details:
                        metric_details[metric.name] = []
                    metric_details[metric.name].append(metric.value)

        if not metric_values:
            logger.warning(f"No metric values found for dimension {dimension.value}")
            return 0.5, 0.0, {"error": "No metric values"}

        # Calculate dimension score
        score = self._aggregate_metric_values(metric_values, dimension)

        # Calculate confidence based on consistency and number of values
        confidence = self._calculate_dimension_confidence(metric_values, metric_details)

        # Add detailed breakdown
        details = {
            "metric_count": len(metric_values),
            "relevant_metrics": relevant_metrics,
            "metric_statistics": {
                name: {
                    "mean": statistics.mean(values),
                    "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "min": min(values),
                    "max": max(values),
                }
                for name, values in metric_details.items()
            },
        }

        return score, confidence, details

    def _get_relevant_metrics(self, dimension: EvaluationDimension) -> List[str]:
        """Get metrics relevant to a dimension."""
        # Mapping of dimensions to relevant metrics
        dimension_metrics = {
            EvaluationDimension.TASK_COMPLETION: [
                "task_success_rate",
                "completion_time",
                "accuracy",
                "quality_score",
            ],
            EvaluationDimension.EFFICIENCY: [
                "resource_usage",
                "time_efficiency",
                "cost_efficiency",
                "throughput",
            ],
            EvaluationDimension.CREATIVITY: [
                "novelty_score",
                "innovation_index",
                "solution_diversity",
                "creative_thinking",
            ],
            EvaluationDimension.SAFETY: [
                "safety_score",
                "risk_assessment",
                "compliance_score",
                "harm_prevention",
            ],
            EvaluationDimension.ADAPTABILITY: [
                "adaptation_speed",
                "flexibility_score",
                "generalization_ability",
                "learning_rate",
            ],
            EvaluationDimension.ROBUSTNESS: [
                "error_resilience",
                "stability_score",
                "fault_tolerance",
                "recovery_time",
            ],
            EvaluationDimension.COLLABORATION: [
                "teamwork_score",
                "communication_effectiveness",
                "coordination_efficiency",
            ],
            EvaluationDimension.DECISION_QUALITY: [
                "decision_accuracy",
                "judgment_score",
                "optimal_choice_rate",
                "strategic_thinking",
            ],
            EvaluationDimension.LEARNING_RATE: [
                "learning_speed",
                "knowledge_acquisition",
                "skill_improvement",
                "adaptation_rate",
            ],
            EvaluationDimension.RESOURCE_UTILIZATION: [
                "resource_efficiency",
                "utilization_rate",
                "optimization_score",
                "waste_reduction",
            ],
        }

        return dimension_metrics.get(dimension, [])

    def _aggregate_metric_values(
        self, values: List[float], dimension: EvaluationDimension
    ) -> float:
        """Aggregate metric values into a dimension score."""
        if not values:
            return 0.0

        # Different aggregation methods based on dimension
        if dimension in [
            EvaluationDimension.TASK_COMPLETION,
            EvaluationDimension.SAFETY,
        ]:
            # For these dimensions, use minimum to ensure no critical failures
            return min(values)
        elif dimension in [
            EvaluationDimension.EFFICIENCY,
            EvaluationDimension.RESOURCE_UTILIZATION,
        ]:
            # For efficiency, use harmonic mean to penalize extreme inefficiencies
            return len(values) / sum(1.0 / (v + 1e-6) for v in values)
        elif dimension in [
            EvaluationDimension.CREATIVITY,
            EvaluationDimension.ADAPTABILITY,
        ]:
            # For creativity and adaptability, use maximum to highlight peak performance
            return max(values)
        else:
            # For other dimensions, use mean
            return statistics.mean(values)

    def _calculate_dimension_confidence(
        self, values: List[float], metric_details: Dict[str, List[float]]
    ) -> float:
        """Calculate confidence score for a dimension."""
        if not values:
            return 0.0

        # Base confidence on number of data points
        data_points_confidence = min(1.0, len(values) / 10.0)

        # Base confidence on consistency (inverse of variance)
        if len(values) > 1:
            variance = statistics.variance(values)
            max_possible_variance = (
                max((v - 0.5) ** 2 for v in values) if values else 0.25
            )
            consistency_confidence = 1.0 - (variance / (max_possible_variance + 1e-6))
            consistency_confidence = max(0.0, min(1.0, consistency_confidence))
        else:
            consistency_confidence = 0.5

        # Base confidence on metric coverage
        expected_metrics = 3  # Expected number of metrics per dimension
        metric_coverage_confidence = min(1.0, len(metric_details) / expected_metrics)

        # Combine confidence factors
        overall_confidence = (
            data_points_confidence * 0.4
            + consistency_confidence * 0.4
            + metric_coverage_confidence * 0.2
        )

        return max(0.0, min(1.0, overall_confidence))

    def _determine_dimension_trend(
        self, agent_id: str, dimension: EvaluationDimension, current_score: float
    ) -> str:
        """Determine trend for a dimension based on historical data."""
        if agent_id not in self.evaluation_history:
            return "insufficient_data"

        historical_evaluations = self.evaluation_history[agent_id]
        if len(historical_evaluations) < 3:
            return "insufficient_data"

        # Get recent scores for this dimension
        recent_scores = []
        for eval in historical_evaluations[-5:]:  # Last 5 evaluations
            for dim_score in eval.dimension_scores:
                if dim_score.dimension == dimension:
                    recent_scores.append(dim_score.score)

        if len(recent_scores) < 3:
            return "insufficient_data"

        # Simple trend analysis
        older_scores = recent_scores[:-1]
        newer_scores = recent_scores[1:]

        older_avg = statistics.mean(older_scores)
        newer_avg = statistics.mean(newer_scores)

        if newer_avg > older_avg * 1.05:  # 5% improvement threshold
            return "improving"
        elif newer_avg < older_avg * 0.95:  # 5% decline threshold
            return "declining"
        else:
            return "stable"

    def _calculate_dimension_significance(
        self,
        dimension: EvaluationDimension,
        agent_results: List[AgentRunResult],
        score: float,
    ) -> float:
        """Calculate statistical significance of a dimension score."""
        if len(agent_results) < 3:
            return 0.0

        # Extract metric values for this dimension
        relevant_metrics = self._get_relevant_metrics(dimension)
        all_values = []

        for agent_result in agent_results:
            for metric in agent_result.metrics:
                if metric.name in relevant_metrics:
                    all_values.append(metric.value)

        if len(all_values) < 3:
            return 0.0

        # Calculate standard error
        std_dev = statistics.stdev(all_values)
        std_error = std_dev / (len(all_values) ** 0.5)

        # Calculate significance as 1 - (standard error / score)
        # Higher values indicate more significant results
        if score > 0:
            significance = min(1.0, 1.0 - (std_error / score))
        else:
            significance = 0.0

        return max(0.0, significance)

    def _calculate_overall_score(self, dimension_scores: List[DimensionScore]) -> float:
        """Calculate overall score from dimension scores."""
        if not dimension_scores:
            return 0.0

        # Use weighted average based on dimension weights
        weighted_sum = 0.0
        total_weight = 0.0

        for dim_score in dimension_scores:
            # Find the weight for this dimension
            weight = 0.0
            for dim_weight in self.config.dimensions:
                if dim_weight.dimension == dim_score.dimension:
                    weight = dim_weight.weight
                    break

            weighted_sum += dim_score.score * weight
            total_weight += weight

        if total_weight == 0:
            return statistics.mean([ds.score for ds in dimension_scores])

        return weighted_sum / total_weight

    async def _perform_comparative_analysis(
        self,
        agent_id: str,
        scenario_result: ScenarioResult,
        dimension_scores: List[DimensionScore],
    ) -> Dict[str, float]:
        """Perform comparative analysis against other agents."""
        # Get all agent IDs from the scenario
        all_agent_ids = set()
        for agent_result in scenario_result.agent_results:
            all_agent_ids.add(agent_result.agent_id)

        if len(all_agent_ids) <= 1:
            return {}

        # Create performance data for comparison
        agent_performance = {  # noqa: F841
            dim_score.dimension.value: dim_score.score for dim_score in dimension_scores
        }

        # For simplicity, we'll compare against average performance
        # In a real implementation, this would use the comparative engine
        comparative_performance = {}

        for dim_score in dimension_scores:
            dim_name = dim_score.dimension.value
            # Normalize to 0-1 scale where 0.5 is average
            normalized_score = dim_score.score
            comparative_performance[dim_name] = normalized_score

        return comparative_performance

    async def _perform_trend_analysis(
        self, agent_id: str, dimension_scores: List[DimensionScore]
    ) -> Dict[str, Any]:
        """Perform trend analysis for agent performance."""
        if agent_id not in self.evaluation_history:
            return {"status": "insufficient_data"}

        historical_evaluations = self.evaluation_history[agent_id]
        if len(historical_evaluations) < 3:
            return {"status": "insufficient_data"}

        trend_analysis = {}

        for dim_score in dimension_scores:
            dimension = dim_score.dimension

            # Get historical scores for this dimension
            historical_scores = []
            for eval in historical_evaluations:
                for hist_dim_score in eval.dimension_scores:
                    if hist_dim_score.dimension == dimension:
                        historical_scores.append(hist_dim_score.score)

            if len(historical_scores) < 3:
                trend_analysis[dimension.value] = {"status": "insufficient_data"}
                continue

            # Calculate trend using linear regression
            x = list(range(len(historical_scores)))
            y = historical_scores

            # Simple linear regression
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi**2 for xi in x)

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)

            # Determine trend direction and strength
            if abs(slope) < 0.01:
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "improving"
            else:
                trend_direction = "declining"

            trend_strength = min(1.0, abs(slope) * 10)  # Scale to 0-1

            trend_analysis[dimension.value] = {
                "direction": trend_direction,
                "strength": trend_strength,  # type: ignore[dict-item]
                "slope": slope,  # type: ignore[dict-item]
                "historical_scores": historical_scores[-10:],  # Last 10 scores  # type: ignore[dict-item]
            }

        return trend_analysis

    async def _calculate_statistical_significance(
        self,
        agent_id: str,
        agent_results: List[AgentRunResult],
        dimension_scores: List[DimensionScore],
    ) -> Dict[str, float]:
        """Calculate statistical significance of results."""
        significance_results = {}

        for dim_score in dimension_scores:
            dimension = dim_score.dimension

            # Get relevant metrics for this dimension
            relevant_metrics = self._get_relevant_metrics(dimension)

            # Collect all metric values
            all_values = []
            for agent_result in agent_results:
                for metric in agent_result.metrics:
                    if metric.name in relevant_metrics:
                        all_values.append(metric.value)

            if len(all_values) < 3:
                significance_results[dimension.value] = 0.0
                continue

            # Calculate statistical significance using t-test against expected value
            expected_value = 0.7  # Expected performance level
            t_statistic, p_value = stats.ttest_1samp(all_values, expected_value)

            # Convert p-value to significance score (lower p-value = higher significance)
            significance = max(0.0, 1.0 - p_value)
            significance_results[dimension.value] = significance

        return significance_results

    async def _perform_benchmark_comparison(
        self,
        agent_id: str,
        scenario_result: ScenarioResult,
        dimension_scores: List[DimensionScore],
    ) -> Dict[str, Any]:
        """Perform comparison against baseline/benchmark agent."""
        if not self.config.baseline_agent_id:
            return {}

        # Get baseline agent results
        baseline_results = scenario_result.get_agent_results(
            self.config.baseline_agent_id
        )
        if not baseline_results:
            return {}

        # Calculate baseline dimension scores
        baseline_scores = await self._calculate_dimension_scores(
            self.config.baseline_agent_id, baseline_results, {}
        )

        # Compare scores
        comparison = {}
        for dim_score in dimension_scores:
            dimension = dim_score.dimension

            # Find corresponding baseline score
            baseline_score = None
            for base_score in baseline_scores:
                if base_score.dimension == dimension:
                    baseline_score = base_score.score
                    break

            if baseline_score is None:
                comparison[dimension.value] = {"status": "no_baseline_data"}
                continue

            # Calculate relative performance
            if baseline_score > 0:
                relative_performance = dim_score.score / baseline_score
            else:
                relative_performance = 1.0

            # Determine comparison result
            if relative_performance > 1.2:
                comparison_result = "significantly_better"
            elif relative_performance > 1.05:
                comparison_result = "better"
            elif relative_performance > 0.95:
                comparison_result = "similar"
            elif relative_performance > 0.8:
                comparison_result = "worse"
            else:
                comparison_result = "significantly_worse"

            comparison[dimension.value] = {
                "agent_score": dim_score.score,  # type: ignore[dict-item]
                "baseline_score": baseline_score,  # type: ignore[dict-item]
                "relative_performance": relative_performance,  # type: ignore[dict-item]
                "comparison_result": comparison_result,
                "improvement_needed": max(0, baseline_score - dim_score.score),  # type: ignore[dict-item]
            }

        return comparison

    def _create_empty_evaluation(
        self, agent_id: str, scenario_name: str
    ) -> MultiDimensionalEvaluation:
        """Create an empty evaluation result."""
        return MultiDimensionalEvaluation(
            agent_id=agent_id,
            scenario_name=scenario_name,
            timestamp=datetime.now(),
            overall_score=0.0,
            dimension_scores=[],
            comparative_performance={},
            trend_analysis={},
            statistical_significance={},
            benchmark_comparison={},
            metadata={"status": "no_data"},
        )

    async def _update_agent_profile(self, agent_id: str) -> None:
        """Update agent profile with latest evaluation."""
        if agent_id not in self.evaluation_history:
            return

        evaluations = self.evaluation_history[agent_id]
        if not evaluations:
            return

        # Calculate performance summary
        performance_summary = self._calculate_performance_summary(evaluations)

        # Identify strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(evaluations)

        # Identify improvement areas
        improvement_areas = self._identify_improvement_areas(evaluations)

        # Determine overall trend
        overall_trend = self._determine_overall_trend(evaluations)

        # Create or update profile
        profile = EvaluationProfile(
            agent_id=agent_id,
            evaluations=evaluations,
            profile_created=datetime.now(),
            last_updated=datetime.now(),
            performance_summary=performance_summary,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_areas=improvement_areas,
            overall_trend=overall_trend,
        )

        self.agent_profiles[agent_id] = profile

    def _calculate_performance_summary(
        self, evaluations: List[MultiDimensionalEvaluation]
    ) -> Dict[str, Any]:
        """Calculate performance summary from evaluations."""
        if not evaluations:
            return {}

        # Overall statistics
        overall_scores = [eval.overall_score for eval in evaluations]

        # Dimension statistics
        dimension_stats = {}
        for dimension in EvaluationDimension:
            scores = []
            for eval in evaluations:
                for dim_score in eval.dimension_scores:
                    if dim_score.dimension == dimension:
                        scores.append(dim_score.score)

            if scores:
                dimension_stats[dimension.value] = {
                    "mean": statistics.mean(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
                    "min": min(scores),
                    "max": max(scores),
                    "trend": self._determine_overall_dimension_trend(scores),
                }

        return {
            "total_evaluations": len(evaluations),
            "overall_performance": {
                "mean": statistics.mean(overall_scores),
                "std_dev": (
                    statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0.0
                ),
                "min": min(overall_scores),
                "max": max(overall_scores),
                "trend": self._determine_overall_trend(evaluations),
            },
            "dimension_performance": dimension_stats,
            "recent_performance": {
                "last_5": [eval.overall_score for eval in evaluations[-5:]],
                "last_10": [eval.overall_score for eval in evaluations[-10:]],
            },
        }

    def _identify_strengths_weaknesses(
        self, evaluations: List[MultiDimensionalEvaluation]
    ) -> Tuple[List[EvaluationDimension], List[EvaluationDimension]]:
        """Identify agent strengths and weaknesses."""
        if not evaluations:
            return [], []

        # Calculate average scores for each dimension
        dimension_scores = {}
        for dimension in EvaluationDimension:
            scores = []
            for eval in evaluations:
                for dim_score in eval.dimension_scores:
                    if dim_score.dimension == dimension:
                        scores.append(dim_score.score)

            if scores:
                dimension_scores[dimension] = statistics.mean(scores)

        # Sort dimensions by score
        sorted_dimensions = sorted(
            dimension_scores.items(), key=lambda x: x[1], reverse=True
        )

        # Identify top 3 as strengths, bottom 3 as weaknesses
        strengths = [dim for dim, score in sorted_dimensions[:3]]
        weaknesses = [dim for dim, score in sorted_dimensions[-3:]]

        return strengths, weaknesses

    def _identify_improvement_areas(
        self, evaluations: List[MultiDimensionalEvaluation]
    ) -> List[str]:
        """Identify areas for improvement."""
        if not evaluations:
            return []

        improvement_areas = []

        # Check for declining trends
        for dimension in EvaluationDimension:
            trend = self._determine_dimension_trend_from_evaluations(
                evaluations, dimension
            )
            if trend == "declining":
                improvement_areas.append(f"improve_{dimension.value}")

        # Check for low scores
        latest_eval = evaluations[-1]
        for dim_score in latest_eval.dimension_scores:
            if dim_score.score < 0.6:  # Below 60% threshold
                improvement_areas.append(f"enhance_{dim_score.dimension.value}")

        # Check for low confidence
        for dim_score in latest_eval.dimension_scores:
            if dim_score.confidence < 0.5:  # Below 50% confidence
                improvement_areas.append(f"stabilize_{dim_score.dimension.value}")

        return improvement_areas

    def _determine_overall_trend(
        self, evaluations: List[MultiDimensionalEvaluation]
    ) -> str:
        """Determine overall performance trend."""
        if len(evaluations) < 3:
            return "insufficient_data"

        # Get overall scores
        scores = [eval.overall_score for eval in evaluations]

        # Simple trend analysis
        older_scores = scores[:-1]
        newer_scores = scores[1:]

        older_avg = statistics.mean(older_scores)
        newer_avg = statistics.mean(newer_scores)

        if newer_avg > older_avg * 1.05:  # 5% improvement threshold
            return "improving"
        elif newer_avg < older_avg * 0.95:  # 5% decline threshold
            return "declining"
        else:
            return "stable"

    def _determine_overall_dimension_trend(self, scores: List[float]) -> str:
        """Determine trend for a dimension's scores."""
        if len(scores) < 3:
            return "insufficient_data"

        older_scores = scores[:-1]
        newer_scores = scores[1:]

        older_avg = statistics.mean(older_scores)
        newer_avg = statistics.mean(newer_scores)

        if newer_avg > older_avg * 1.05:
            return "improving"
        elif newer_avg < older_avg * 0.95:
            return "declining"
        else:
            return "stable"

    def _determine_dimension_trend_from_evaluations(
        self,
        evaluations: List[MultiDimensionalEvaluation],
        dimension: EvaluationDimension,
    ) -> str:
        """Determine trend for a specific dimension from evaluations."""
        if len(evaluations) < 3:
            return "insufficient_data"

        # Get scores for this dimension
        scores = []
        for eval in evaluations:
            for dim_score in eval.dimension_scores:
                if dim_score.dimension == dimension:
                    scores.append(dim_score.score)

        if len(scores) < 3:
            return "insufficient_data"

        return self._determine_overall_dimension_trend(scores)

    def _create_empty_profile(self, agent_id: str) -> EvaluationProfile:
        """Create an empty agent profile."""
        return EvaluationProfile(
            agent_id=agent_id,
            evaluations=[],
            profile_created=datetime.now(),
            last_updated=datetime.now(),
            performance_summary={},
            strengths=[],
            weaknesses=[],
            improvement_areas=[],
            overall_trend="no_data",
        )

    async def _generate_comparative_report(
        self, profiles: Dict[str, EvaluationProfile]
    ) -> Dict[str, Any]:
        """Generate comparative analysis report."""
        if len(profiles) < 2:
            return {"status": "insufficient_agents"}

        # Extract overall performance data
        agent_performance = {}
        for agent_id, profile in profiles.items():
            if profile.evaluations:
                latest_eval = profile.evaluations[-1]
                agent_performance[agent_id] = latest_eval.overall_score
            else:
                agent_performance[agent_id] = 0.0

        # Rank agents
        ranked_agents = sorted(
            agent_performance.items(), key=lambda x: x[1], reverse=True
        )

        # Calculate performance gaps
        best_score = ranked_agents[0][1] if ranked_agents else 0.0
        performance_gaps = {}
        for agent_id, score in agent_performance.items():
            if best_score > 0:
                gap = (best_score - score) / best_score
            else:
                gap = 0.0
            performance_gaps[agent_id] = gap

        # Cluster agents by performance
        agent_ids = list(agent_performance.keys())
        performance_matrix = []
        for agent_id in agent_ids:
            profile = profiles[agent_id]
            if profile.evaluations:
                latest_eval = profile.evaluations[-1]
                dimension_scores = [
                    dim_score.score for dim_score in latest_eval.dimension_scores
                ]
                performance_matrix.append(dimension_scores)
            else:
                performance_matrix.append([0.0] * len(EvaluationDimension))

        # Perform clustering
        if len(performance_matrix) > 1:
            clustering = DBSCAN(eps=0.3, min_samples=1).fit(performance_matrix)
            clusters = {}  # type: ignore[var-annotated]
            for i, agent_id in enumerate(agent_ids):
                cluster_id = clustering.labels_[i]
                if cluster_id not in clusters:
                    clusters[cluster_id] = []
                clusters[cluster_id].append(agent_id)
        else:
            clusters = {0: agent_ids}

        return {
            "agent_rankings": ranked_agents,
            "performance_gaps": performance_gaps,
            "performance_clusters": clusters,
            "best_performer": ranked_agents[0][0] if ranked_agents else None,
            "performance_distribution": {
                "mean": statistics.mean(agent_performance.values()),
                "std_dev": (
                    statistics.stdev(agent_performance.values())
                    if len(agent_performance) > 1
                    else 0.0
                ),
                "min": min(agent_performance.values()),
                "max": max(agent_performance.values()),
            },
        }

    async def _generate_recommendations(
        self, profiles: Dict[str, EvaluationProfile]
    ) -> Dict[str, List[str]]:
        """Generate improvement recommendations for agents."""
        recommendations = {}

        for agent_id, profile in profiles.items():
            agent_recommendations = []

            # Add recommendations based on weaknesses
            for weakness in profile.weaknesses:
                agent_recommendations.append(
                    f"Focus on improving {weakness.value} capabilities"
                )

            # Add recommendations based on improvement areas
            for area in profile.improvement_areas:
                agent_recommendations.append(
                    f"Implement strategies to {area.replace('_', ' ')}"
                )

            # Add trend-based recommendations
            if profile.overall_trend == "declining":
                agent_recommendations.append(
                    "Review and update agent strategies to address performance decline"
                )
            elif profile.overall_trend == "stable":
                agent_recommendations.append(
                    "Explore optimization opportunities to enhance performance"
                )

            # Add dimension-specific recommendations
            if profile.evaluations:
                latest_eval = profile.evaluations[-1]
                for dim_score in latest_eval.dimension_scores:
                    if dim_score.score < 0.5:  # Poor performance
                        agent_recommendations.append(
                            f"Urgently address {dim_score.dimension.value} performance (current: {dim_score.score:.2f})"
                        )
                    elif dim_score.confidence < 0.5:  # Low confidence
                        agent_recommendations.append(
                            f"Stabilize {dim_score.dimension.value} performance to improve confidence"
                        )

            recommendations[agent_id] = agent_recommendations

        return recommendations

    def _generate_summary_statistics(
        self, profiles: Dict[str, EvaluationProfile]
    ) -> Dict[str, Any]:
        """Generate summary statistics for the report."""
        if not profiles:
            return {}

        # Collect all evaluation data
        all_evaluations = []
        for profile in profiles.values():
            all_evaluations.extend(profile.evaluations)

        if not all_evaluations:
            return {"status": "no_evaluation_data"}

        # Overall statistics
        overall_scores = [eval.overall_score for eval in all_evaluations]

        # Dimension statistics
        dimension_stats = {}
        for dimension in EvaluationDimension:
            scores = []
            for eval in all_evaluations:
                for dim_score in eval.dimension_scores:
                    if dim_score.dimension == dimension:
                        scores.append(dim_score.score)

            if scores:
                dimension_stats[dimension.value] = {
                    "mean": statistics.mean(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
                    "min": min(scores),
                    "max": max(scores),
                }

        # Agent statistics
        agent_stats = {}
        for agent_id, profile in profiles.items():
            if profile.evaluations:
                scores = [eval.overall_score for eval in profile.evaluations]
                agent_stats[agent_id] = {
                    "mean": statistics.mean(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
                    "min": min(scores),
                    "max": max(scores),
                    "trend": profile.overall_trend,
                }

        return {
            "total_evaluations": len(all_evaluations),
            "total_agents": len(profiles),
            "overall_statistics": {
                "mean": statistics.mean(overall_scores),
                "std_dev": (
                    statistics.stdev(overall_scores) if len(overall_scores) > 1 else 0.0
                ),
                "min": min(overall_scores),
                "max": max(overall_scores),
            },
            "dimension_statistics": dimension_stats,
            "agent_statistics": agent_stats,
            "evaluation_timeframe": {
                "earliest": min(eval.timestamp for eval in all_evaluations).isoformat(),
                "latest": max(eval.timestamp for eval in all_evaluations).isoformat(),
            },
        }
