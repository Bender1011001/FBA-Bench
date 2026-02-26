"""
Benchmark results management.

This module provides classes for storing, analyzing, and reporting benchmark results.
"""

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class MetricResult:
    """Result for a single metric calculation."""

    name: str
    value: float
    unit: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert MetricResult to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricResult":
        """Create MetricResult from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            unit=data["unit"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentRunResult:
    """Result for a single agent run in a scenario."""

    agent_id: str
    scenario_name: str
    run_number: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    metrics: List[MetricResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert AgentRunResult to dictionary."""
        return {
            "agent_id": self.agent_id,
            "scenario_name": self.scenario_name,
            "run_number": self.run_number,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "errors": self.errors,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRunResult":
        """Create AgentRunResult from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            scenario_name=data["scenario_name"],
            run_number=data["run_number"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            duration_seconds=data["duration_seconds"],
            metrics=[
                MetricResult.from_dict(metric_data)
                for metric_data in data.get("metrics", [])
            ],
            errors=data.get("errors", []),
            success=data.get("success", True),
        )

    def get_metric_value(self, metric_name: str) -> Optional[float]:
        """Get the value of a specific metric."""
        for metric in self.metrics:
            if metric.name == metric_name:
                return metric.value
        return None

    def get_metrics_by_category(self, category: str) -> List[MetricResult]:
        """Get all metrics for a specific category."""
        return [metric for metric in self.metrics if metric.name.startswith(category)]


@dataclass
class ScenarioResult:
    """Result for a scenario across all agents and runs."""

    scenario_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    agent_results: List[AgentRunResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert ScenarioResult to dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "agent_results": [result.to_dict() for result in self.agent_results],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioResult":
        """Create ScenarioResult from dictionary."""
        return cls(
            scenario_name=data["scenario_name"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            duration_seconds=data["duration_seconds"],
            agent_results=[
                AgentRunResult.from_dict(result_data)
                for result_data in data.get("agent_results", [])
            ],
        )

    def get_agent_results(self, agent_id: str) -> List[AgentRunResult]:
        """Get all results for a specific agent."""
        return [result for result in self.agent_results if result.agent_id == agent_id]

    def calculate_aggregate_metrics(self) -> Dict[str, Dict[str, float]]:
        """Calculate aggregate statistics for all metrics."""
        aggregate_metrics = {}

        # Group metrics by name
        metric_groups = {}  # type: ignore[var-annotated]
        for agent_result in self.agent_results:
            for metric in agent_result.metrics:
                if metric.name not in metric_groups:
                    metric_groups[metric.name] = []
                metric_groups[metric.name].append(metric.value)

        # Calculate statistics for each metric
        for metric_name, values in metric_groups.items():
            if values:
                aggregate_metrics[metric_name] = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }

        return aggregate_metrics


@dataclass
class BenchmarkResult:
    """Complete benchmark result across all scenarios and agents."""

    benchmark_name: str
    config_hash: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    scenario_results: List[ScenarioResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert BenchmarkResult to dictionary."""
        return {
            "benchmark_name": self.benchmark_name,
            "config_hash": self.config_hash,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "scenario_results": [result.to_dict() for result in self.scenario_results],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        """Create BenchmarkResult from dictionary."""
        return cls(
            benchmark_name=data["benchmark_name"],
            config_hash=data["config_hash"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            duration_seconds=data["duration_seconds"],
            scenario_results=[
                ScenarioResult.from_dict(result_data)
                for result_data in data.get("scenario_results", [])
            ],
            metadata=data.get("metadata", {}),
        )

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save BenchmarkResult to JSON file."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> "BenchmarkResult":
        """Load BenchmarkResult from JSON file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Result file not found: {file_path}")

        with open(file_path) as f:
            data = json.load(f)

        return cls.from_dict(data)

    def get_scenario_result(self, scenario_name: str) -> Optional[ScenarioResult]:
        """Get result for a specific scenario."""
        for result in self.scenario_results:
            if result.scenario_name == scenario_name:
                return result
        return None

    def get_agent_results(self, agent_id: str) -> List[AgentRunResult]:
        """Get all results for a specific agent across all scenarios."""
        agent_results = []
        for scenario_result in self.scenario_results:
            agent_results.extend(scenario_result.get_agent_results(agent_id))
        return agent_results

    def calculate_summary_statistics(self) -> Dict[str, Any]:
        """Calculate summary statistics for the entire benchmark."""
        summary = {
            "total_scenarios": len(self.scenario_results),
            "total_agent_runs": sum(
                len(scenario_result.agent_results)
                for scenario_result in self.scenario_results
            ),
            "successful_runs": 0,
            "failed_runs": 0,
            "total_duration_seconds": self.duration_seconds,
            "average_scenario_duration": 0.0,
            "agent_performance": {},
        }

        if self.scenario_results:
            summary["average_scenario_duration"] = sum(
                scenario_result.duration_seconds
                for scenario_result in self.scenario_results
            ) / len(self.scenario_results)

        # Count successful and failed runs
        for scenario_result in self.scenario_results:
            for agent_result in scenario_result.agent_results:
                if agent_result.success:
                    summary["successful_runs"] += 1  # type: ignore[operator]
                else:
                    summary["failed_runs"] += 1  # type: ignore[operator]

        # Calculate agent performance summary
        agent_performance = {}
        for scenario_result in self.scenario_results:
            for agent_result in scenario_result.agent_results:
                agent_id = agent_result.agent_id
                if agent_id not in agent_performance:
                    agent_performance[agent_id] = {
                        "total_runs": 0,
                        "successful_runs": 0,
                        "failed_runs": 0,
                        "average_duration": 0.0,
                        "metrics": {},
                    }

                agent_performance[agent_id]["total_runs"] += 1  # type: ignore[operator]
                if agent_result.success:
                    agent_performance[agent_id]["successful_runs"] += 1  # type: ignore[operator]
                else:
                    agent_performance[agent_id]["failed_runs"] += 1  # type: ignore[operator]

                # Aggregate metrics
                for metric in agent_result.metrics:
                    if metric.name not in agent_performance[agent_id]["metrics"]:  # type: ignore[operator]
                        agent_performance[agent_id]["metrics"][metric.name] = []  # type: ignore[index]
                    agent_performance[agent_id]["metrics"][metric.name].append(  # type: ignore[index]
                        metric.value
                    )

        # Calculate averages for each agent
        for agent_id, performance in agent_performance.items():
            if performance["total_runs"] > 0:  # type: ignore[operator]
                # Calculate average duration
                total_duration = sum(
                    result.duration_seconds
                    for scenario_result in self.scenario_results
                    for result in scenario_result.get_agent_results(agent_id)
                )
                performance["average_duration"] = (
                    total_duration / performance["total_runs"]  # type: ignore[operator]
                )

                # Calculate metric averages
                for metric_name, values in performance["metrics"].items():  # type: ignore[attr-defined]
                    if values:
                        performance["metrics"][metric_name] = {  # type: ignore[index]
                            "mean": statistics.mean(values),
                            "median": statistics.median(values),
                            "std_dev": (
                                statistics.stdev(values) if len(values) > 1 else 0.0
                            ),
                        }

        summary["agent_performance"] = agent_performance
        return summary
