"""
Lightweight metrics package API.

This package exposes both:
- Legacy class-based registry via `metrics_registry`
- New function-style registry helpers: register_metric/get_metric/list_metrics

Built-in function-style metrics auto-register on registry import.
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Export helpers for function-style metrics
from .registry import (  # noqa: E402
    get_metric,
    list_metrics,
    metrics_registry,  # legacy class-based registry
    register_metric,
)


def metric_keys() -> List[str]:
    """
    Return the list of registered function-style metric keys.

    Clickable references:
    - [`python.def list_metrics()`](benchmarking/metrics/registry.py:1)
    """
    return list_metrics()


__all__ = [
    "register_metric",
    "get_metric",
    "list_metrics",
    "metric_keys",
    "metrics_registry",
]
