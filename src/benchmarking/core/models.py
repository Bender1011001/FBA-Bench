"""
Core models for benchmarking in FBA-Bench.

Pydantic models for benchmark results, experiments, and configurations.
Used in test_engine_new_api.py and benchmarking workflows.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .results import ScenarioResult


class MetricsAggregationMode(Enum):
    """
    Enum for metrics aggregation modes in benchmarking.
    """

    AVERAGE = "average"
    SUM = "sum"
    MAX = "max"
    MIN = "min"


class RunStatus(Enum):
    """
    Enum for run status in benchmarking.
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ValidationMode(Enum):
    """Validation modes for benchmark execution/verification."""

    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"


class BenchmarkResult(BaseModel):
    """
    Model for a single benchmark result.
    """

    experiment_id: str = Field(..., description="Unique ID for the experiment")
    metric_name: str = Field(
        ..., description="Name of the metric (e.g., 'profit_margin')"
    )
    value: float = Field(..., description="The measured value")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the result was recorded"
    )
    agent_type: str = Field(..., description="Type of agent used")
    scenario_tier: str = Field(..., description="Scenario tier (e.g., 'tier_0')")


class ExperimentConfig(BaseModel):
    """
    Configuration for a benchmarking experiment.
    """

    experiment_id: str = Field(..., description="Unique ID for the experiment")
    scenario_path: str = Field(..., description="Path to scenario YAML")
    agent_config: Dict[str, Any] = Field(
        default_factory=dict, description="Agent configuration"
    )
    iterations: int = Field(1, ge=1, description="Number of iterations")
    metrics: List[str] = Field(default_factory=list, description="Metrics to track")


class BenchmarkSummary(BaseModel):
    """
    Summary of benchmark results.
    """

    experiment_id: str
    average_metrics: Dict[str, float] = Field(default_factory=dict)
    std_metrics: Dict[str, float] = Field(default_factory=dict)
    total_time: float = Field(0.0)
    success_rate: float = Field(1.0, ge=0.0, le=1.0)


__all__ = [
    "MetricsAggregationMode",
    "RunStatus",
    "ValidationMode",
    "BenchmarkResult",
    "ExperimentConfig",
    "BenchmarkSummary",
    "ScenarioResult",
]
