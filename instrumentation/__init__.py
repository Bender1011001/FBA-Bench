"""Instrumentation package shim - redirects to src.instrumentation.

This compatibility layer exists for backward compatibility with code that imports
from 'instrumentation' directly. The canonical location is 'src/instrumentation'.
"""
import os
import warnings

# Issue: Conditionalize warning to prevent spam in logs/tests
if not os.environ.get("FBA_BENCH_SUPPRESS_DEPRECATION"):
    warnings.warn(
        "The 'instrumentation' package shim is deprecated; use direct imports where possible. "
        "Set FBA_BENCH_SUPPRESS_DEPRECATION=1 to suppress this warning.",
        DeprecationWarning,
        stacklevel=2,
    )

# Re-export from the canonical source
from src.instrumentation.agent_tracer import AgentTracer
from src.instrumentation.export_utils import *
from src.instrumentation.simulation_tracer import SimulationTracer
from src.instrumentation.tracer import *

# ClearML is optional
try:
    from src.instrumentation.clearml_tracking import ClearMLTracker
except ImportError:
    ClearMLTracker = None  # type: ignore

__all__ = [
    "AgentTracer",
    "ClearMLTracker",
    "SimulationTracer",
]

# Make submodule imports work (e.g., from instrumentation.clearml_tracking import ...)
# by exposing the modules themselves
from src.instrumentation import clearml_tracking
from src.instrumentation import agent_tracer
from src.instrumentation import simulation_tracer
from src.instrumentation import tracer
from src.instrumentation import export_utils
