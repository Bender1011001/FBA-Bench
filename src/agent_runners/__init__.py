"""
Framework-agnostic agent runner abstraction layer for FBA-Bench.

This package intentionally uses lazy exports to prevent heavy import-time side
effects and circular imports with benchmarking.* modules.

Key Concepts (resolved lazily on attribute access):
- AgentRunner API and errors
- SimulationState and ToolCall data structures
- RunnerFactory for framework registration/creation
- AgentManager/AgentRegistry integration layer
- Dependency management utilities
- Typed configuration helpers
"""

from __future__ import annotations

import importlib
from typing import Any, List

# Public API surface (names will be resolved lazily)
__all__: List[str] = [
    # Core interfaces and data
    "AgentRunner",
    "AgentRunnerStatus",
    "AgentRunnerError",
    "AgentRunnerInitializationError",
    "AgentRunnerDecisionError",
    "AgentRunnerCleanupError",
    "AgentRunnerTimeoutError",
    "SimulationState",
    "ToolCall",
    # Registry helper
    "create_runner",
    "supported_runners",
    "RunnerFactory",
    # Integration
    "AgentManager",
    "AgentRegistry",
    # Dependency management
    "DependencyManager",
    "dependency_manager",
    "check_framework_availability",
    "get_available_frameworks",
    "install_framework",
    # Utilities
    "get_framework_status",
    # Builder/config helpers (back-compat for tests)
    "create_agent_builder",
    "DIYConfig",
    "validate_config",
    "AgentRunnerConfig",
]

# Candidate submodules to search when resolving attributes lazily.
# Order matters: light/leaf modules should come first to minimize side effects.
_CANDIDATE_MODULES = [
    "agent_runners.base_runner",
    "agent_runners.registry",
    "agent_runners.dependency_manager",
    "agent_runners.agent_registry",
    "agent_runners.runner_factory",
    "agent_runners.configs.framework_configs",
    "agent_runners.configs.config_schema",
    "agent_runners.agent_manager",  # kept last to reduce circular import risk
]


def __getattr__(name: str) -> Any:
    """
    Lazily resolve attributes from submodules to avoid import-time cycles.
    """
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    for module_name in _CANDIDATE_MODULES:
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, name):
                attr = getattr(mod, name)
                # Cache the attribute on the module to avoid repeated lookups
                globals()[name] = attr
                return attr
        except (ImportError, AttributeError):
            continue

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
