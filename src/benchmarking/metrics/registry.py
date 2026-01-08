"""
Minimal metrics registry compatible with unit tests.

This module provides a simple MetricsRegistry class with the exact API
expected by tests:
- __init__() -> starts empty (no auto-registered metrics)
- register(name, metric)
- get(name) -> BaseMetric | None
- get_all_metrics() -> dict[str, BaseMetric]
- unregister(name) -> raises ValueError if not found
- clear()
- list_metrics() -> list[str]

Additionally, it exposes a function-style registry for optional use:
- register_metric(key, fn)
- get_metric(key)
- list_function_metrics()
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .base import BaseMetric


class MetricRegistry:
    """
    A minimal in-memory registry for BaseMetric instances.
    Starts empty and supports CRUD-style operations used in unit tests.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, BaseMetric] = {}

    def register(self, name: str, metric: BaseMetric) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("Metric name must be a non-empty string")
        if name in self._metrics:
            raise ValueError(f"Metric '{name}' already registered")
        if not isinstance(metric, BaseMetric):
            # Allow mocks with BaseMetric spec in tests
            # but still enforce presence of 'name' attribute for sanity
            if not hasattr(metric, "name"):
                raise TypeError(
                    "Metric must be a BaseMetric or a compatible mock with 'name'"
                )
        self._metrics[name] = metric

    def get(self, name: str) -> Optional[BaseMetric]:
        return self._metrics.get(name)

    # Legacy/test API: allow creating/returning a metric instance by name.
    # Tests monkeypatch MetricRegistry.create_metric(self, name, config=None),
    # so we provide this symbol for compatibility.
    def create_metric(
        self, name: str, config: Optional[dict] = None
    ) -> Optional[BaseMetric]:
        # In this minimal registry we store instances directly, so just return it if present.
        # The test will monkeypatch this to return custom stubs as needed.
        return self._metrics.get(name)

    def get_all_metrics(self) -> Dict[str, BaseMetric]:
        # Return a shallow copy to prevent external mutation
        return dict(self._metrics)

    def unregister(self, name: str) -> None:
        if name not in self._metrics:
            raise ValueError(f"Metric '{name}' not found")
        del self._metrics[name]

    def clear(self) -> None:
        self._metrics.clear()

    def list_metrics(self) -> List[str]:
        return list(self._metrics.keys())

    def get_metrics_by_category(self, category: str) -> Dict[str, BaseMetric]:
        """
        Get all metrics belonging to a specific category.
        This provides a dictionary-like view expected by the benchmark engine.
        """
        return {
            name: metric
            for name, metric in self._metrics.items()
            if getattr(metric, "category", None) == category
            or getattr(getattr(metric, "metadata", None), "category", None) == category
        }


# Backwards-compat class alias expected by tests
MetricsRegistry = MetricRegistry


# -----------------------------------------------------------------------------
# Optional function-style registry (kept minimal and decoupled from tests)
# -----------------------------------------------------------------------------
_FN_METRICS: Dict[str, Callable[[dict, dict | None], dict]] = {}


def register_metric(key: str, fn: Callable[[dict, dict | None], dict]) -> None:
    """
    Register a function-style metric.

    Args:
        key: Unique metric key
        fn: Callable evaluate(run: dict, context: dict|None=None) -> dict
    """
    if not isinstance(key, str) or not key:
        raise ValueError("Metric key must be a non-empty string")
    if not callable(fn):
        raise TypeError("Metric function must be callable")
    _FN_METRICS[key] = fn


def get_metric(key: str) -> Callable[[dict, dict | None], dict]:
    """
    Lookup a function-style metric by key.

    Raises:
        KeyError if not found.
    """
    try:
        return _FN_METRICS[key]
    except KeyError as exc:
        available = ", ".join(sorted(_FN_METRICS.keys()))
        raise KeyError(
            f"Unknown metric '{key}'. Available metrics: [{available}]. "
            "Ensure the metric is registered."
        ) from exc


def list_function_metrics() -> List[str]:
    """List function-style metric keys."""
    return sorted(_FN_METRICS.keys())


# Back-compat function alias expected by benchmarking.metrics.__init__
def list_metrics() -> List[str]:
    """Alias to list_function_metrics for compatibility."""
    return list_function_metrics()


# Global registry instance expected by benchmarking.metrics.__init__
metrics_registry = MetricRegistry()


# Auto-register built-in function metrics so list_metrics() returns expected keys
def _auto_register_builtin_function_metrics() -> None:
    modules = [
        "benchmarking.metrics.technical_performance_v2",
        "benchmarking.metrics.accuracy_score",
        "benchmarking.metrics.keyword_coverage",
        "benchmarking.metrics.policy_compliance",
        "benchmarking.metrics.robustness",
        "benchmarking.metrics.cost_efficiency",
        "benchmarking.metrics.completeness",
        "benchmarking.metrics.custom_scriptable",
    ]
    for mod in modules:
        try:
            __import__(mod)
        except Exception:
            # Optional modules should not break import-time behavior
            pass


# Perform auto-registration at import time
_auto_register_builtin_function_metrics()
