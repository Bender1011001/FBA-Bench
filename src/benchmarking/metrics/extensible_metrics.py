"""
Extensible Metrics and Validation Framework for FBA-Bench.

This module provides a clear and well-documented API for users to define and register custom metrics,
and abstracts validation logic to allow easy integration of user-defined checks.
"""

import abc
import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from statistics import mean, median, stdev
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


class MetricValueType(str, Enum):
    """Types of metric values."""

    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    STRING = "string"
    LIST = "list"
    DICT = "dict"
    PERCENTAGE = "percentage"
    DURATION = "duration"
    CURRENCY = "currency"


class AggregationMethod(str, Enum):
    """Methods for aggregating metric values."""

    MEAN = "mean"
    MEDIAN = "median"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    STD_DEV = "std_dev"
    COUNT = "count"
    CUSTOM = "custom"


@dataclass
class MetricMetadata:
    """Metadata for a metric definition."""

    name: str
    description: str
    value_type: MetricValueType
    unit: str = ""
    tags: Set[str] = field(default_factory=set)
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    aggregation_methods: List[AggregationMethod] = field(
        default_factory=lambda: [AggregationMethod.MEAN]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "value_type": self.value_type.value,
            "unit": self.unit,
            "tags": list(self.tags),
            "version": self.version,
            "author": self.author,
            "category": self.category,
            "aggregation_methods": [
                method.value for method in self.aggregation_methods
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricMetadata":
        """Create metadata from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            value_type=MetricValueType(data["value_type"]),
            unit=data.get("unit", ""),
            tags=set(data.get("tags", [])),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            category=data.get("category", "general"),
            aggregation_methods=[
                AggregationMethod(method)
                for method in data.get("aggregation_methods", ["mean"])
            ],
        )


@dataclass
class MetricResult:
    """Result of a metric calculation."""

    name: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricResult":
        """Create result from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            context=data.get("context", {}),
        )


@dataclass
class MetricValidationResult:
    """Result of a metric validation."""

    metric_name: str
    is_valid: bool
    validation_score: float = 0.0  # 0.0 to 1.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "metric_name": self.metric_name,
            "is_valid": self.is_valid,
            "validation_score": self.validation_score,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricValidationResult":
        """Create validation result from dictionary."""
        return cls(
            metric_name=data["metric_name"],
            is_valid=data["is_valid"],
            validation_score=data.get("validation_score", 0.0),
            message=data.get("message", ""),
            details=data.get("details", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class BaseMetric(abc.ABC):
    """Base class for all metrics."""

    def __init__(self, metadata: MetricMetadata):
        """Initialize the metric."""
        self.metadata = metadata
        self._is_initialized = False

    @property
    def name(self) -> str:
        """Get the metric name."""
        return self.metadata.name

    @property
    def value_type(self) -> MetricValueType:
        """Get the metric value type."""
        return self.metadata.value_type

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the metric with configuration."""
        self._is_initialized = True

    @abc.abstractmethod
    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        """Calculate the metric value."""

    async def validate(self, result: MetricResult) -> MetricValidationResult:
        """Validate a metric result."""
        # Default validation - just check if value is not None
        is_valid = result.value is not None
        return MetricValidationResult(
            metric_name=self.name,
            is_valid=is_valid,
            validation_score=1.0 if is_valid else 0.0,
            message="Valid" if is_valid else "Value is None",
        )

    def aggregate(
        self,
        results: List[MetricResult],
        method: AggregationMethod = AggregationMethod.MEAN,
    ) -> Any:
        """Aggregate multiple metric results."""
        if not results:
            return None

        values = [r.value for r in results if r.value is not None]

        if not values:
            return None

        if method == AggregationMethod.MEAN:
            return mean(values)
        elif method == AggregationMethod.MEDIAN:
            return median(values)
        elif method == AggregationMethod.SUM:
            return sum(values)
        elif method == AggregationMethod.MIN:
            return min(values)
        elif method == AggregationMethod.MAX:
            return max(values)
        elif method == AggregationMethod.STD_DEV:
            return stdev(values) if len(values) > 1 else 0.0
        elif method == AggregationMethod.COUNT:
            return len(values)
        else:
            # For custom aggregation, return all values
            return values


class NumericMetric(BaseMetric):
    """Base class for numeric metrics."""

    def __init__(
        self,
        metadata: MetricMetadata,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ):
        """Initialize the numeric metric."""
        super().__init__(metadata)
        self.min_value = min_value
        self.max_value = max_value

    async def validate(self, result: MetricResult) -> MetricValidationResult:
        """Validate a numeric metric result."""
        if not isinstance(result.value, (int, float)):
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Expected numeric value, got {type(result.value)}",
            )

        value = float(result.value)

        # Check min/max bounds
        if self.min_value is not None and value < self.min_value:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Value {value} is below minimum {self.min_value}",
            )

        if self.max_value is not None and value > self.max_value:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Value {value} is above maximum {self.max_value}",
            )

        return MetricValidationResult(
            metric_name=self.name,
            is_valid=True,
            validation_score=1.0,
            message="Valid numeric value",
        )


class BooleanMetric(BaseMetric):
    """Base class for boolean metrics."""

    async def validate(self, result: MetricResult) -> MetricValidationResult:
        """Validate a boolean metric result."""
        if not isinstance(result.value, bool):
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Expected boolean value, got {type(result.value)}",
            )

        return MetricValidationResult(
            metric_name=self.name,
            is_valid=True,
            validation_score=1.0 if result.value else 0.0,
            message="Valid boolean value",
        )


class StringMetric(BaseMetric):
    """Base class for string metrics."""

    def __init__(
        self,
        metadata: MetricMetadata,
        allowed_values: Optional[List[str]] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ):
        """Initialize the string metric."""
        super().__init__(metadata)
        self.allowed_values = allowed_values
        self.min_length = min_length
        self.max_length = max_length

    async def validate(self, result: MetricResult) -> MetricValidationResult:
        """Validate a string metric result."""
        if not isinstance(result.value, str):
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Expected string value, got {type(result.value)}",
            )

        value = str(result.value)

        # Check allowed values
        if self.allowed_values and value not in self.allowed_values:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Value '{value}' not in allowed values: {self.allowed_values}",
            )

        # Check length constraints
        if self.min_length is not None and len(value) < self.min_length:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"String length {len(value)} is below minimum {self.min_length}",
            )

        if self.max_length is not None and len(value) > self.max_length:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"String length {len(value)} is above maximum {self.max_length}",
            )

        return MetricValidationResult(
            metric_name=self.name,
            is_valid=True,
            validation_score=1.0,
            message="Valid string value",
        )


class ListMetric(BaseMetric):
    """Base class for list metrics."""

    def __init__(
        self,
        metadata: MetricMetadata,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        element_type: Optional[Type] = None,
    ):
        """Initialize the list metric."""
        super().__init__(metadata)
        self.min_length = min_length
        self.max_length = max_length
        self.element_type = element_type

    async def validate(self, result: MetricResult) -> MetricValidationResult:
        """Validate a list metric result."""
        if not isinstance(result.value, list):
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Expected list value, got {type(result.value)}",
            )

        value_list = result.value

        # Check length constraints
        if self.min_length is not None and len(value_list) < self.min_length:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"List length {len(value_list)} is below minimum {self.min_length}",
            )

        if self.max_length is not None and len(value_list) > self.max_length:
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"List length {len(value_list)} is above maximum {self.max_length}",
            )

        # Check element types
        if self.element_type:
            invalid_elements = [
                elem for elem in value_list if not isinstance(elem, self.element_type)
            ]
            if invalid_elements:
                return MetricValidationResult(
                    metric_name=self.name,
                    is_valid=False,
                    validation_score=0.0,
                    message=f"Found {len(invalid_elements)} elements of wrong type",
                )

        return MetricValidationResult(
            metric_name=self.name,
            is_valid=True,
            validation_score=1.0,
            message="Valid list value",
        )


class CustomMetric(BaseMetric):
    """Custom metric with user-defined calculation and validation logic."""

    def __init__(
        self,
        metadata: MetricMetadata,
        calculation_func: Callable[[Dict[str, Any]], Any],
        validation_func: Optional[
            Callable[[MetricResult], MetricValidationResult]
        ] = None,
    ):
        """Initialize the custom metric."""
        super().__init__(metadata)
        self.calculation_func = calculation_func
        self.validation_func = validation_func

    async def calculate(self, context: Dict[str, Any]) -> MetricResult:
        """Calculate the metric using the custom function."""
        try:
            if inspect.iscoroutinefunction(self.calculation_func):
                value = await self.calculation_func(context)
            else:
                value = self.calculation_func(context)

            return MetricResult(name=self.name, value=value, context=context)
        except Exception as e:
            logger.error(f"Error calculating custom metric {self.name}: {e}")
            return MetricResult(
                name=self.name, value=None, context=context, metadata={"error": str(e)}
            )

    async def validate(self, result: MetricResult) -> MetricValidationResult:
        """Validate the metric using the custom function or default validation."""
        if self.validation_func:
            try:
                if inspect.iscoroutinefunction(self.validation_func):
                    return await self.validation_func(result)
                else:
                    return self.validation_func(result)
            except Exception as e:
                logger.error(f"Error validating custom metric {self.name}: {e}")
                return MetricValidationResult(
                    metric_name=self.name,
                    is_valid=False,
                    validation_score=0.0,
                    message=f"Validation error: {e!s}",
                )
        else:
            # Use default validation
            return await super().validate(result)


class MetricRegistry:
    """Registry for managing metric definitions."""

    def __init__(self):
        """Initialize the registry."""
        self._metrics: Dict[str, BaseMetric] = {}
        self._metric_types: Dict[str, Type[BaseMetric]] = {
            "numeric": NumericMetric,  # type: ignore[type-abstract]
            "boolean": BooleanMetric,  # type: ignore[type-abstract]
            "string": StringMetric,  # type: ignore[type-abstract]
            "list": ListMetric,  # type: ignore[type-abstract]
            "custom": CustomMetric,
        }

    def register(self, metric: BaseMetric) -> None:
        """Register a metric."""
        self._metrics[metric.name] = metric
        logger.info(f"Registered metric: {metric.name}")

    def register_custom_metric(
        self,
        name: str,
        description: str,
        value_type: MetricValueType,
        calculation_func: Callable[[Dict[str, Any]], Any],
        validation_func: Optional[
            Callable[[MetricResult], MetricValidationResult]
        ] = None,
        **kwargs,
    ) -> CustomMetric:
        """Register a custom metric with a function."""
        metadata = MetricMetadata(
            name=name, description=description, value_type=value_type, **kwargs
        )

        metric = CustomMetric(metadata, calculation_func, validation_func)
        self.register(metric)
        return metric

    def get(self, name: str) -> Optional[BaseMetric]:
        """Get a metric by name."""
        return self._metrics.get(name)

    def list_metrics(self) -> List[str]:
        """List all registered metric names."""
        return list(self._metrics.keys())

    def get_metrics_by_category(self, category: str) -> List[BaseMetric]:
        """Get metrics by category."""
        return [
            metric
            for metric in self._metrics.values()
            if metric.metadata.category == category
        ]

    def get_metrics_by_tag(self, tag: str) -> List[BaseMetric]:
        """Get metrics by tag."""
        return [
            metric for metric in self._metrics.values() if tag in metric.metadata.tags
        ]

    def create_metric(
        self, metric_type: str, metadata: MetricMetadata, **kwargs
    ) -> BaseMetric:
        """Create a metric of the specified type."""
        if metric_type not in self._metric_types:
            raise ValueError(f"Unknown metric type: {metric_type}")

        metric_class = self._metric_types[metric_type]
        return metric_class(metadata, **kwargs)


class MetricSuite:
    """Collection of metrics for comprehensive evaluation."""

    def __init__(self, name: str, description: str = ""):
        """Initialize the metric suite."""
        self.name = name
        self.description = description
        self.metrics: Dict[str, BaseMetric] = {}
        self.metric_weights: Dict[str, float] = {}
        self._is_initialized = False

    def add_metric(self, metric: BaseMetric, weight: float = 1.0) -> None:
        """Add a metric to the suite."""
        self.metrics[metric.name] = metric
        self.metric_weights[metric.name] = weight
        logger.debug(
            f"Added metric {metric.name} to suite {self.name} with weight {weight}"
        )

    def remove_metric(self, metric_name: str) -> None:
        """Remove a metric from the suite."""
        if metric_name in self.metrics:
            del self.metrics[metric_name]
            del self.metric_weights[metric_name]
            logger.debug(f"Removed metric {metric_name} from suite {self.name}")

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize all metrics in the suite."""
        init_tasks = []
        for metric in self.metrics.values():
            init_tasks.append(metric.initialize(config))

        await asyncio.gather(*init_tasks)
        self._is_initialized = True
        logger.info(
            f"Initialized metric suite {self.name} with {len(self.metrics)} metrics"
        )

    async def calculate_all(self, context: Dict[str, Any]) -> Dict[str, MetricResult]:
        """Calculate all metrics in the suite."""
        if not self._is_initialized:
            raise RuntimeError(f"Metric suite {self.name} not initialized")

        results = {}
        calculation_tasks = []

        for metric in self.metrics.values():
            calculation_tasks.append(metric.calculate(context))

        metric_results = await asyncio.gather(
            *calculation_tasks, return_exceptions=True
        )

        for metric, result in zip(self.metrics.values(), metric_results):
            if isinstance(result, Exception):
                logger.error(f"Error calculating metric {metric.name}: {result}")
                results[metric.name] = MetricResult(
                    name=metric.name,
                    value=None,
                    context=context,
                    metadata={"error": str(result)},
                )
            else:
                results[metric.name] = result  # type: ignore[assignment]

        return results

    async def validate_all(
        self, results: Dict[str, MetricResult]
    ) -> Dict[str, MetricValidationResult]:
        """Validate all metric results."""
        validation_results = {}
        validation_tasks = []

        for metric_name, result in results.items():
            if metric_name in self.metrics:
                validation_tasks.append(self.metrics[metric_name].validate(result))
            else:
                logger.warning(f"No metric found for result: {metric_name}")

        validation_results_list = await asyncio.gather(
            *validation_tasks, return_exceptions=True
        )

        for metric_name, validation_result in zip(
            results.keys(), validation_results_list
        ):
            if isinstance(validation_result, Exception):
                logger.error(
                    f"Error validating metric {metric_name}: {validation_result}"
                )
                validation_results[metric_name] = MetricValidationResult(
                    metric_name=metric_name,
                    is_valid=False,
                    validation_score=0.0,
                    message=f"Validation error: {validation_result!s}",
                )
            else:
                validation_results[metric_name] = validation_result  # type: ignore[assignment]

        return validation_results

    def calculate_overall_score(
        self, validation_results: Dict[str, MetricValidationResult]
    ) -> float:
        """Calculate overall score from validation results."""
        if not validation_results:
            return 0.0

        total_weight = 0.0
        weighted_score = 0.0

        for metric_name, validation_result in validation_results.items():
            weight = self.metric_weights.get(metric_name, 1.0)
            total_weight += weight
            weighted_score += weight * validation_result.validation_score

        if total_weight == 0.0:
            return 0.0

        return weighted_score / total_weight

    def get_summary(
        self,
        results: Dict[str, MetricResult],
        validation_results: Dict[str, MetricValidationResult],
    ) -> Dict[str, Any]:
        """Get a summary of metric results."""
        summary = {
            "suite_name": self.name,
            "total_metrics": len(self.metrics),
            "valid_metrics": sum(1 for v in validation_results.values() if v.is_valid),
            "overall_score": self.calculate_overall_score(validation_results),
            "metrics": {},
        }

        for metric_name in self.metrics:
            if metric_name in results and metric_name in validation_results:
                summary["metrics"][metric_name] = {  # type: ignore[index]
                    "value": results[metric_name].value,
                    "is_valid": validation_results[metric_name].is_valid,
                    "validation_score": validation_results[
                        metric_name
                    ].validation_score,
                    "message": validation_results[metric_name].message,
                }

        return summary


class ValidationRule(abc.ABC):
    """Base class for validation rules."""

    def __init__(self, name: str, description: str = ""):
        """Initialize the validation rule."""
        self.name = name
        self.description = description

    @abc.abstractmethod
    async def validate(self, context: Dict[str, Any]) -> MetricValidationResult:
        """Validate the context."""


class ThresholdValidationRule(ValidationRule):
    """Validation rule that checks if a value is within a threshold."""

    def __init__(
        self,
        name: str,
        metric_name: str,
        min_threshold: Optional[float] = None,
        max_threshold: Optional[float] = None,
        description: str = "",
    ):
        """Initialize the threshold validation rule."""
        super().__init__(name, description)
        self.metric_name = metric_name
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold

    async def validate(self, context: Dict[str, Any]) -> MetricValidationResult:
        """Validate the metric value against thresholds."""
        if self.metric_name not in context:
            return MetricValidationResult(
                metric_name=self.metric_name,
                is_valid=False,
                validation_score=0.0,
                message=f"Metric {self.metric_name} not found in context",
            )

        value = context[self.metric_name]

        if not isinstance(value, (int, float)):
            return MetricValidationResult(
                metric_name=self.metric_name,
                is_valid=False,
                validation_score=0.0,
                message=f"Expected numeric value for {self.metric_name}, got {type(value)}",
            )

        value = float(value)

        if self.min_threshold is not None and value < self.min_threshold:
            return MetricValidationResult(
                metric_name=self.metric_name,
                is_valid=False,
                validation_score=0.0,
                message=f"Value {value} is below minimum threshold {self.min_threshold}",
            )

        if self.max_threshold is not None and value > self.max_threshold:
            return MetricValidationResult(
                metric_name=self.metric_name,
                is_valid=False,
                validation_score=0.0,
                message=f"Value {value} is above maximum threshold {self.max_threshold}",
            )

        return MetricValidationResult(
            metric_name=self.metric_name,
            is_valid=True,
            validation_score=1.0,
            message=f"Value {value} is within thresholds",
        )


class CustomValidationRule(ValidationRule):
    """Custom validation rule with user-defined logic."""

    def __init__(
        self,
        name: str,
        validation_func: Callable[[Dict[str, Any]], MetricValidationResult],
        description: str = "",
    ):
        """Initialize the custom validation rule."""
        super().__init__(name, description)
        self.validation_func = validation_func

    async def validate(self, context: Dict[str, Any]) -> MetricValidationResult:
        """Validate using the custom function."""
        try:
            if inspect.iscoroutinefunction(self.validation_func):
                return await self.validation_func(context)
            else:
                return self.validation_func(context)
        except Exception as e:
            logger.error(f"Error in custom validation rule {self.name}: {e}")
            return MetricValidationResult(
                metric_name=self.name,
                is_valid=False,
                validation_score=0.0,
                message=f"Validation error: {e!s}",
            )


class ValidationEngine:
    """Engine for running validation rules."""

    def __init__(self):
        """Initialize the validation engine."""
        self.rules: Dict[str, ValidationRule] = {}

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        self.rules[rule.name] = rule
        logger.debug(f"Added validation rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> None:
        """Remove a validation rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.debug(f"Removed validation rule: {rule_name}")

    async def validate_all(
        self, context: Dict[str, Any]
    ) -> Dict[str, MetricValidationResult]:
        """Run all validation rules."""
        results = {}
        validation_tasks = []

        for rule in self.rules.values():
            validation_tasks.append(rule.validate(context))

        rule_results = await asyncio.gather(*validation_tasks, return_exceptions=True)

        for rule, result in zip(self.rules.values(), rule_results):
            if isinstance(result, Exception):
                logger.error(f"Error in validation rule {rule.name}: {result}")
                results[rule.name] = MetricValidationResult(
                    metric_name=rule.name,
                    is_valid=False,
                    validation_score=0.0,
                    message=f"Rule error: {result!s}",
                )
            else:
                results[rule.name] = result  # type: ignore[assignment]

        return results


# Global instances
metric_registry = MetricRegistry()
validation_engine = ValidationEngine()
