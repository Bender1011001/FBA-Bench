"""
Technical performance metrics for FBA-Bench.

This module provides advanced metrics for evaluating technical performance including
scalability under load, resource utilization efficiency, latency and throughput
analysis, error handling, system resilience, performance degradation analysis,
and optimization effectiveness.
"""

import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import BaseMetric, MetricConfig


@dataclass
class LoadTestResult:
    """Results from a load test."""

    concurrent_users: int
    requests_per_second: float
    average_response_time: float
    max_response_time: float
    error_rate: float
    throughput: float
    resource_utilization: Dict[str, float]


@dataclass
class ResourceMetrics:
    """Resource utilization metrics."""

    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_usage: float
    gpu_usage: Optional[float] = None
    energy_consumption: Optional[float] = None


@dataclass
class ErrorAnalysis:
    """Error analysis data."""

    error_count: int
    error_types: Dict[str, int]
    error_severity: Dict[str, float]
    recovery_time: float
    error_patterns: List[str]


class TechnicalPerformanceMetrics(BaseMetric):
    """
    Advanced metrics for evaluating technical performance.

    This class provides comprehensive evaluation of technical performance
    including scalability, resource utilization, latency, throughput, error handling,
    resilience, and optimization effectiveness.
    """

    def __init__(self, config: MetricConfig = None):
        """
        Initialize technical performance metrics.

        Args:
            config: Metric configuration (uses defaults if None)
        """
        if config is None:
            config = MetricConfig(
                name="technical_performance_advanced",
                description="Technical performance score",
                unit="score",
                min_value=0.0,
                max_value=100.0,
                target_value=85.0,
            )

        super().__init__(config)

        # Sub-metric configurations
        self.scalability_config = MetricConfig(
            name="scalability",
            description="Scalability under load",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.resource_utilization_config = MetricConfig(
            name="resource_utilization",
            description="Resource utilization efficiency",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.latency_throughput_config = MetricConfig(
            name="latency_throughput",
            description="Latency and throughput analysis",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.error_handling_config = MetricConfig(
            name="error_handling",
            description="Error handling and recovery capabilities",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.system_resilience_config = MetricConfig(
            name="system_resilience",
            description="System resilience metrics",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.performance_degradation_config = MetricConfig(
            name="performance_degradation",
            description="Performance degradation analysis",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

        self.optimization_effectiveness_config = MetricConfig(
            name="optimization_effectiveness",
            description="Optimization effectiveness measures",
            unit="score",
            min_value=0.0,
            max_value=100.0,
        )

    def calculate(self, data: Dict[str, Any]) -> float:  # type: ignore[override]
        """
        Calculate technical performance score.

        Args:
            data: Data containing technical performance metrics

        Returns:
            Overall technical performance score
        """
        if not isinstance(data, dict):
            return 0.0
        # Calculate sub-metric scores
        scalability = self.calculate_scalability(data)
        resource_utilization = self.calculate_resource_utilization(data)
        latency_throughput = self.calculate_latency_throughput(data)
        error_handling = self.calculate_error_handling(data)
        system_resilience = self.calculate_system_resilience(data)
        performance_degradation = self.calculate_performance_degradation(data)
        optimization_effectiveness = self.calculate_optimization_effectiveness(data)

        # Calculate weighted average
        weights = {
            "scalability": 0.18,
            "resource_utilization": 0.15,
            "latency_throughput": 0.18,
            "error_handling": 0.15,
            "system_resilience": 0.12,
            "performance_degradation": 0.12,
            "optimization_effectiveness": 0.10,
        }

        overall_score = (
            scalability * weights["scalability"]
            + resource_utilization * weights["resource_utilization"]
            + latency_throughput * weights["latency_throughput"]
            + error_handling * weights["error_handling"]
            + system_resilience * weights["system_resilience"]
            + performance_degradation * weights["performance_degradation"]
            + optimization_effectiveness * weights["optimization_effectiveness"]
        )

        return overall_score

    def calculate_scalability(self, data: Dict[str, Any]) -> float:
        """
        Calculate scalability under load score.

        Args:
            data: Data containing scalability metrics

        Returns:
            Scalability score
        """
        load_test_results = data.get("load_test_results", [])
        if not load_test_results:
            return 0.0

        scalability_scores = []

        for result in load_test_results:
            if isinstance(result, dict):
                result = LoadTestResult(
                    concurrent_users=result.get("concurrent_users", 0),
                    requests_per_second=result.get("requests_per_second", 0.0),
                    average_response_time=result.get("average_response_time", 0.0),
                    max_response_time=result.get("max_response_time", 0.0),
                    error_rate=result.get("error_rate", 0.0),
                    throughput=result.get("throughput", 0.0),
                    resource_utilization=result.get("resource_utilization", {}),
                )

            # Evaluate scalability components
            linear_scaling = self._evaluate_linear_scaling(result)
            response_time_stability = self._evaluate_response_time_stability(result)
            throughput_scaling = self._evaluate_throughput_scaling(result)
            error_rate_stability = self._evaluate_error_rate_stability(result)

            # Calculate weighted scalability score
            weights = {
                "linear_scaling": 0.3,
                "response_time_stability": 0.25,
                "throughput_scaling": 0.25,
                "error_rate_stability": 0.2,
            }

            scalability_score = (
                linear_scaling * weights["linear_scaling"]
                + response_time_stability * weights["response_time_stability"]
                + throughput_scaling * weights["throughput_scaling"]
                + error_rate_stability * weights["error_rate_stability"]
            )

            scalability_scores.append(scalability_score)

        return statistics.mean(scalability_scores) * 100

    def calculate_resource_utilization(self, data: Dict[str, Any]) -> float:
        """
        Calculate resource utilization efficiency score.

        Args:
            data: Data containing resource utilization metrics

        Returns:
            Resource utilization score
        """
        resource_metrics = data.get("resource_metrics", [])
        if not resource_metrics:
            return 0.0

        utilization_scores = []

        for metrics in resource_metrics:
            if isinstance(metrics, dict):
                metrics = ResourceMetrics(
                    cpu_usage=metrics.get("cpu_usage", 0.0),
                    memory_usage=metrics.get("memory_usage", 0.0),
                    disk_usage=metrics.get("disk_usage", 0.0),
                    network_usage=metrics.get("network_usage", 0.0),
                    gpu_usage=metrics.get("gpu_usage"),
                    energy_consumption=metrics.get("energy_consumption"),
                )

            # Evaluate resource utilization components
            cpu_efficiency = self._evaluate_cpu_efficiency(metrics)
            memory_efficiency = self._evaluate_memory_efficiency(metrics)
            disk_efficiency = self._evaluate_disk_efficiency(metrics)
            network_efficiency = self._evaluate_network_efficiency(metrics)
            overall_efficiency = self._evaluate_overall_resource_efficiency(metrics)

            # Calculate weighted utilization score
            weights = {
                "cpu_efficiency": 0.25,
                "memory_efficiency": 0.25,
                "disk_efficiency": 0.15,
                "network_efficiency": 0.15,
                "overall_efficiency": 0.20,
            }

            utilization_score = (
                cpu_efficiency * weights["cpu_efficiency"]
                + memory_efficiency * weights["memory_efficiency"]
                + disk_efficiency * weights["disk_efficiency"]
                + network_efficiency * weights["network_efficiency"]
                + overall_efficiency * weights["overall_efficiency"]
            )

            utilization_scores.append(utilization_score)

        return statistics.mean(utilization_scores) * 100

    def calculate_latency_throughput(self, data: Dict[str, Any]) -> float:
        """
        Calculate latency and throughput analysis score.

        Args:
            data: Data containing latency and throughput metrics

        Returns:
            Latency and throughput score
        """
        latency_data = data.get("latency_data", [])
        throughput_data = data.get("throughput_data", [])

        if not latency_data and not throughput_data:
            return 0.0

        # Evaluate latency
        latency_score = 0.0
        if latency_data:
            avg_latency = statistics.mean(latency_data)
            max_latency = max(latency_data)
            latency_variance = (
                statistics.variance(latency_data) if len(latency_data) > 1 else 0.0
            )

            # Lower latency is better
            latency_score = self._calculate_latency_score(
                avg_latency, max_latency, latency_variance
            )

        # Evaluate throughput
        throughput_score = 0.0
        if throughput_data:
            avg_throughput = statistics.mean(throughput_data)
            throughput_variance = (
                statistics.variance(throughput_data)
                if len(throughput_data) > 1
                else 0.0
            )

            # Higher throughput is better
            throughput_score = self._calculate_throughput_score(
                avg_throughput, throughput_variance
            )

        # Combine latency and throughput scores
        if latency_data and throughput_data:
            combined_score = (latency_score + throughput_score) / 2.0
        elif latency_data:
            combined_score = latency_score
        else:
            combined_score = throughput_score

        return combined_score * 100

    def calculate_error_handling(self, data: Dict[str, Any]) -> float:
        """
        Calculate error handling and recovery capabilities score.

        Args:
            data: Data containing error handling metrics

        Returns:
            Error handling score
        """
        error_analyses = data.get("error_analyses", [])
        if not error_analyses:
            return 0.0

        error_scores = []

        for analysis in error_analyses:
            if isinstance(analysis, dict):
                analysis = ErrorAnalysis(
                    error_count=analysis.get("error_count", 0),
                    error_types=analysis.get("error_types", {}),
                    error_severity=analysis.get("error_severity", {}),
                    recovery_time=analysis.get("recovery_time", 0.0),
                    error_patterns=analysis.get("error_patterns", []),
                )

            # Evaluate error handling components
            error_rate = self._evaluate_error_rate(analysis)
            recovery_speed = self._evaluate_recovery_speed(analysis)
            error_classification = self._evaluate_error_classification(analysis)
            prevention_effectiveness = self._evaluate_prevention_effectiveness(analysis)

            # Calculate weighted error handling score
            weights = {
                "error_rate": 0.3,
                "recovery_speed": 0.3,
                "error_classification": 0.2,
                "prevention_effectiveness": 0.2,
            }

            error_score = (
                error_rate * weights["error_rate"]
                + recovery_speed * weights["recovery_speed"]
                + error_classification * weights["error_classification"]
                + prevention_effectiveness * weights["prevention_effectiveness"]
            )

            error_scores.append(error_score)

        return statistics.mean(error_scores) * 100

    def calculate_system_resilience(self, data: Dict[str, Any]) -> float:
        """
        Calculate system resilience metrics score.

        Args:
            data: Data containing system resilience metrics

        Returns:
            System resilience score
        """
        resilience_tests = data.get("resilience_tests", [])
        if not resilience_tests:
            return 0.0

        resilience_scores = []

        for test in resilience_tests:
            # Evaluate resilience components
            fault_tolerance = self._evaluate_fault_tolerance(test)
            recovery_capability = self._evaluate_recovery_capability(test)
            redundancy_effectiveness = self._evaluate_redundancy_effectiveness(test)
            degradation_handling = self._evaluate_degradation_handling(test)

            # Calculate weighted resilience score
            weights = {
                "fault_tolerance": 0.3,
                "recovery_capability": 0.3,
                "redundancy_effectiveness": 0.2,
                "degradation_handling": 0.2,
            }

            resilience_score = (
                fault_tolerance * weights["fault_tolerance"]
                + recovery_capability * weights["recovery_capability"]
                + redundancy_effectiveness * weights["redundancy_effectiveness"]
                + degradation_handling * weights["degradation_handling"]
            )

            resilience_scores.append(resilience_score)

        return statistics.mean(resilience_scores) * 100

    def calculate_performance_degradation(self, data: Dict[str, Any]) -> float:
        """
        Calculate performance degradation analysis score.

        Args:
            data: Data containing performance degradation metrics

        Returns:
            Performance degradation score
        """
        degradation_profiles = data.get("degradation_profiles", [])
        if not degradation_profiles:
            return 0.0

        degradation_scores = []

        for profile in degradation_profiles:
            # Evaluate degradation components
            degradation_rate = self._evaluate_degradation_rate(profile)
            degradation_consistency = self._evaluate_degradation_consistency(profile)
            recovery_from_degradation = self._evaluate_recovery_from_degradation(
                profile
            )
            degradation_prediction = self._evaluate_degradation_prediction(profile)

            # Calculate weighted degradation score (lower degradation is better)
            weights = {
                "degradation_rate": 0.3,
                "degradation_consistency": 0.2,
                "recovery_from_degradation": 0.3,
                "degradation_prediction": 0.2,
            }

            degradation_score = (
                degradation_rate * weights["degradation_rate"]
                + degradation_consistency * weights["degradation_consistency"]
                + recovery_from_degradation * weights["recovery_from_degradation"]
                + degradation_prediction * weights["degradation_prediction"]
            )

            degradation_scores.append(degradation_score)

        return statistics.mean(degradation_scores) * 100

    def calculate_optimization_effectiveness(self, data: Dict[str, Any]) -> float:
        """
        Calculate optimization effectiveness measures score.

        Args:
            data: Data containing optimization effectiveness metrics

        Returns:
            Optimization effectiveness score
        """
        optimization_results = data.get("optimization_results", [])
        if not optimization_results:
            return 0.0

        optimization_scores = []

        for result in optimization_results:
            # Evaluate optimization components
            performance_improvement = self._evaluate_performance_improvement(result)
            resource_reduction = self._evaluate_resource_reduction(result)
            optimization_stability = self._evaluate_optimization_stability(result)
            cost_effectiveness = self._evaluate_optimization_cost_effectiveness(result)

            # Calculate weighted optimization score
            weights = {
                "performance_improvement": 0.35,
                "resource_reduction": 0.25,
                "optimization_stability": 0.2,
                "cost_effectiveness": 0.2,
            }

            optimization_score = (
                performance_improvement * weights["performance_improvement"]
                + resource_reduction * weights["resource_reduction"]
                + optimization_stability * weights["optimization_stability"]
                + cost_effectiveness * weights["cost_effectiveness"]
            )

            optimization_scores.append(optimization_score)

        return statistics.mean(optimization_scores) * 100

    def _evaluate_linear_scaling(self, result: LoadTestResult) -> float:
        """Evaluate linear scaling capability."""
        concurrent_users = result.concurrent_users
        throughput = result.throughput

        # Calculate scaling efficiency
        # Ideally, throughput should scale linearly with concurrent users
        expected_throughput = (
            concurrent_users * 10
        )  # Base assumption: 10 requests per user
        scaling_efficiency = (
            throughput / expected_throughput if expected_throughput > 0 else 0.0
        )

        return min(1.0, scaling_efficiency)

    def _evaluate_response_time_stability(self, result: LoadTestResult) -> float:
        """Evaluate response time stability under load."""
        avg_response_time = result.average_response_time
        max_response_time = result.max_response_time

        # Calculate response time stability
        # Lower ratio of max to average response time indicates better stability
        if avg_response_time > 0:
            stability_ratio = avg_response_time / max_response_time
        else:
            stability_ratio = 1.0

        return stability_ratio

    def _evaluate_throughput_scaling(self, result: LoadTestResult) -> float:
        """Evaluate throughput scaling capability."""
        requests_per_second = result.requests_per_second
        concurrent_users = result.concurrent_users

        # Calculate throughput per user
        throughput_per_user = (
            requests_per_second / concurrent_users if concurrent_users > 0 else 0.0
        )

        # Normalize to expected range (0-20 requests per second per user)
        throughput_score = min(1.0, throughput_per_user / 20.0)

        return throughput_score

    def _evaluate_error_rate_stability(self, result: LoadTestResult) -> float:
        """Evaluate error rate stability under load."""
        error_rate = result.error_rate

        # Lower error rate is better
        error_score = max(0.0, 1.0 - error_rate)

        return error_score

    def _evaluate_cpu_efficiency(self, metrics: ResourceMetrics) -> float:
        """Evaluate CPU utilization efficiency."""
        cpu_usage = metrics.cpu_usage

        # Optimal CPU usage is around 70-80%
        optimal_usage = 0.75
        efficiency = 1.0 - abs(cpu_usage - optimal_usage)

        return max(0.0, efficiency)

    def _evaluate_memory_efficiency(self, metrics: ResourceMetrics) -> float:
        """Evaluate memory utilization efficiency."""
        memory_usage = metrics.memory_usage

        # Optimal memory usage is around 60-70%
        optimal_usage = 0.65
        efficiency = 1.0 - abs(memory_usage - optimal_usage)

        return max(0.0, efficiency)

    def _evaluate_disk_efficiency(self, metrics: ResourceMetrics) -> float:
        """Evaluate disk utilization efficiency."""
        disk_usage = metrics.disk_usage

        # Optimal disk usage is around 50-60%
        optimal_usage = 0.55
        efficiency = 1.0 - abs(disk_usage - optimal_usage)

        return max(0.0, efficiency)

    def _evaluate_network_efficiency(self, metrics: ResourceMetrics) -> float:
        """Evaluate network utilization efficiency."""
        network_usage = metrics.network_usage

        # Optimal network usage is around 40-50%
        optimal_usage = 0.45
        efficiency = 1.0 - abs(network_usage - optimal_usage)

        return max(0.0, efficiency)

    def _evaluate_overall_resource_efficiency(self, metrics: ResourceMetrics) -> float:
        """Evaluate overall resource utilization efficiency."""
        # Calculate balanced resource utilization
        resources = [
            metrics.cpu_usage,
            metrics.memory_usage,
            metrics.disk_usage,
            metrics.network_usage,
        ]

        # Balance is important - no single resource should be overutilized
        max_usage = max(resources)
        avg_usage = statistics.mean(resources)  # noqa: F841

        # Balance score (lower variance is better)
        if len(resources) > 1:
            variance = statistics.variance(resources)
            balance_score = max(0.0, 1.0 - variance * 10)  # Scale variance impact
        else:
            balance_score = 1.0

        # Overall efficiency score
        efficiency_score = (1.0 - max_usage) * 0.5 + balance_score * 0.5

        return max(0.0, efficiency_score)

    def _calculate_latency_score(
        self, avg_latency: float, max_latency: float, variance: float
    ) -> float:
        """Calculate latency score."""
        # Lower latency is better
        # Normalize to 0-1 range based on typical expectations
        max_acceptable_latency = 1000.0  # 1 second
        max_acceptable_variance = 100.0  # 100ms variance

        avg_latency_score = max(0.0, 1.0 - avg_latency / max_acceptable_latency)
        max_latency_score = max(0.0, 1.0 - max_latency / (max_acceptable_latency * 2))
        variance_score = max(0.0, 1.0 - variance / max_acceptable_variance)

        latency_score = (avg_latency_score + max_latency_score + variance_score) / 3.0

        return latency_score

    def _calculate_throughput_score(
        self, avg_throughput: float, variance: float
    ) -> float:
        """Calculate throughput score."""
        # Higher throughput is better
        # Normalize to 0-1 range based on typical expectations
        min_acceptable_throughput = 10.0  # 10 requests per second  # noqa: F841
        max_acceptable_variance = 50.0  # 50 requests variance

        throughput_score = min(
            1.0, avg_throughput / 1000.0
        )  # Normalize to 1000 rps as max
        variance_score = max(0.0, 1.0 - variance / max_acceptable_variance)

        combined_score = (throughput_score + variance_score) / 2.0

        return combined_score

    def _evaluate_error_rate(self, analysis: ErrorAnalysis) -> float:
        """Evaluate error rate."""
        error_count = analysis.error_count
        total_operations = analysis.error_types.get("total_operations", error_count)

        if total_operations == 0:
            return 1.0

        error_rate = error_count / total_operations
        error_score = max(0.0, 1.0 - error_rate * 10)  # Scale error impact

        return error_score

    def _evaluate_recovery_speed(self, analysis: ErrorAnalysis) -> float:
        """Evaluate recovery speed."""
        recovery_time = analysis.recovery_time

        # Faster recovery is better
        max_acceptable_recovery = 300.0  # 5 minutes
        recovery_score = max(0.0, 1.0 - recovery_time / max_acceptable_recovery)

        return recovery_score

    def _evaluate_error_classification(self, analysis: ErrorAnalysis) -> float:
        """Evaluate error classification accuracy."""
        error_types = analysis.error_types
        error_severity = analysis.error_severity

        # Good classification should have detailed type and severity information
        type_coverage = len(error_types) / 10.0  # Assuming 10 major error types
        severity_coverage = len(error_severity) / 5.0  # Assuming 5 severity levels

        classification_score = (
            min(1.0, type_coverage) + min(1.0, severity_coverage)
        ) / 2.0

        return classification_score

    def _evaluate_prevention_effectiveness(self, analysis: ErrorAnalysis) -> float:
        """Evaluate error prevention effectiveness."""
        error_patterns = analysis.error_patterns

        # Prevention effectiveness is demonstrated by identifying and addressing patterns
        pattern_recognition = (
            len(error_patterns) / 10.0
        )  # Normalize by expected patterns
        prevention_score = min(1.0, pattern_recognition)

        return prevention_score

    def _evaluate_fault_tolerance(self, test: Dict[str, Any]) -> float:
        """Evaluate fault tolerance."""
        injected_faults = test.get("injected_faults", 0)
        successful_continuations = test.get("successful_continuations", 0)

        if injected_faults == 0:
            return 1.0

        tolerance_score = successful_continuations / injected_faults

        return min(1.0, tolerance_score)

    def _evaluate_recovery_capability(self, test: Dict[str, Any]) -> float:
        """Evaluate recovery capability."""
        recovery_attempts = test.get("recovery_attempts", 0)
        successful_recoveries = test.get("successful_recoveries", 0)
        avg_recovery_time = test.get("avg_recovery_time", 0.0)

        if recovery_attempts == 0:
            return 1.0

        recovery_success_rate = successful_recoveries / recovery_attempts

        # Consider recovery time
        time_score = max(0.0, 1.0 - avg_recovery_time / 300.0)  # 5 minutes max

        recovery_score = (recovery_success_rate + time_score) / 2.0

        return recovery_score

    def _evaluate_redundancy_effectiveness(self, test: Dict[str, Any]) -> float:
        """Evaluate redundancy effectiveness."""
        redundancy_components = test.get("redundancy_components", 0)
        failed_components = test.get("failed_components", 0)
        service_continuity = test.get("service_continuity", 0.0)

        if redundancy_components == 0:
            return 0.0

        # Redundancy should prevent service disruption
        component_failure_rate = failed_components / redundancy_components
        redundancy_score = service_continuity * (1.0 - component_failure_rate)

        return max(0.0, redundancy_score)

    def _evaluate_degradation_handling(self, test: Dict[str, Any]) -> float:
        """Evaluate graceful degradation handling."""
        degradation_scenarios = test.get("degradation_scenarios", 0)
        graceful_degradations = test.get("graceful_degradations", 0)

        if degradation_scenarios == 0:
            return 1.0

        # Graceful degradation should maintain service quality
        degradation_score = graceful_degradations / degradation_scenarios

        return degradation_score

    def _evaluate_degradation_rate(self, profile: Dict[str, Any]) -> float:
        """Evaluate performance degradation rate."""
        initial_performance = profile.get("initial_performance", 1.0)
        final_performance = profile.get("final_performance", 1.0)
        time_period = profile.get("time_period", 1.0)

        if time_period == 0:
            return 1.0

        # Calculate degradation rate
        degradation_rate = (initial_performance - final_performance) / time_period

        # Lower degradation rate is better
        degradation_score = max(
            0.0, 1.0 - degradation_rate * 10
        )  # Scale degradation impact

        return degradation_score

    def _evaluate_degradation_consistency(self, profile: Dict[str, Any]) -> float:
        """Evaluate degradation consistency."""
        performance_measurements = profile.get("performance_measurements", [])

        if len(performance_measurements) < 2:
            return 1.0

        # Calculate consistency of degradation
        degradation_values = []
        for i in range(1, len(performance_measurements)):
            degradation = performance_measurements[i - 1] - performance_measurements[i]
            degradation_values.append(degradation)

        if not degradation_values:
            return 1.0

        # Lower variance in degradation indicates more consistent behavior
        variance = statistics.variance(degradation_values)
        consistency_score = max(0.0, 1.0 - variance * 5)  # Scale variance impact

        return consistency_score

    def _evaluate_recovery_from_degradation(self, profile: Dict[str, Any]) -> float:
        """Evaluate recovery from degradation."""
        recovery_events = profile.get("recovery_events", [])
        recovery_effectiveness = profile.get("recovery_effectiveness", 0.0)

        if not recovery_events:
            return 0.0

        # Evaluate recovery effectiveness
        recovery_score = recovery_effectiveness / 100.0  # Normalize to 0-1

        return recovery_score

    def _evaluate_degradation_prediction(self, profile: Dict[str, Any]) -> float:
        """Evaluate degradation prediction accuracy."""
        predicted_degradation = profile.get("predicted_degradation", 0.0)
        actual_degradation = profile.get("actual_degradation", 0.0)

        if predicted_degradation == 0:
            return 1.0 if actual_degradation == 0 else 0.0

        # Calculate prediction accuracy
        prediction_error = abs(predicted_degradation - actual_degradation) / abs(
            predicted_degradation
        )
        prediction_score = max(0.0, 1.0 - prediction_error)

        return prediction_score

    def _evaluate_performance_improvement(self, result: Dict[str, Any]) -> float:
        """Evaluate performance improvement from optimization."""
        baseline_performance = result.get("baseline_performance", 0.0)
        optimized_performance = result.get("optimized_performance", 0.0)

        if baseline_performance == 0:
            return 0.0

        # Calculate performance improvement
        improvement_ratio = optimized_performance / baseline_performance
        improvement_score = min(
            1.0, improvement_ratio / 2.0
        )  # Normalize to reasonable range

        return improvement_score

    def _evaluate_resource_reduction(self, result: Dict[str, Any]) -> float:
        """Evaluate resource reduction from optimization."""
        baseline_resources = result.get("baseline_resources", {})
        optimized_resources = result.get("optimized_resources", {})

        if not baseline_resources or not optimized_resources:
            return 0.0

        # Calculate resource reduction
        reduction_scores = []

        for resource, baseline_value in baseline_resources.items():
            if resource in optimized_resources:
                optimized_value = optimized_resources[resource]
                if baseline_value > 0:
                    reduction_ratio = (
                        baseline_value - optimized_value
                    ) / baseline_value
                    reduction_score = max(0.0, reduction_ratio)
                    reduction_scores.append(reduction_score)

        return statistics.mean(reduction_scores) if reduction_scores else 0.0

    def _evaluate_optimization_stability(self, result: Dict[str, Any]) -> float:
        """Evaluate optimization stability."""
        performance_measurements = result.get("performance_measurements", [])

        if len(performance_measurements) < 2:
            return 1.0

        # Calculate stability of optimized performance
        variance = statistics.variance(performance_measurements)
        stability_score = max(0.0, 1.0 - variance * 10)  # Scale variance impact

        return stability_score

    def _evaluate_optimization_cost_effectiveness(
        self, result: Dict[str, Any]
    ) -> float:
        """Evaluate optimization cost effectiveness."""
        optimization_cost = result.get("optimization_cost", 0.0)
        performance_gain = result.get("performance_gain", 0.0)
        resource_savings = result.get("resource_savings", 0.0)

        if optimization_cost == 0:
            return 1.0 if performance_gain > 0 or resource_savings > 0 else 0.0

        # Calculate cost effectiveness
        total_benefit = performance_gain + resource_savings
        cost_effectiveness = total_benefit / optimization_cost
        effectiveness_score = min(
            1.0, cost_effectiveness / 5.0
        )  # Normalize to reasonable range

        return effectiveness_score
