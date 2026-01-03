"""
Compatibility shim: agent_runners.runner_factory

This module provides a minimal RunnerFactory facade used by tests and legacy
code paths. It delegates to agent_runners.registry for the actual logic.
"""

from __future__ import annotations

from typing import Any, List


def _get_registry():
    """
    Resolve the registry module dynamically at call-time to avoid stale imports
    in test environments and during lazy package initialization.
    """
    try:
        # Direct submodule import path
        from agent_runners import registry as reg  # type: ignore

        return reg
    except (ImportError, AttributeError):
        # Fallback to importlib if needed
        try:
            import importlib

            return importlib.import_module("agent_runners.registry")
        except (ImportError, AttributeError):
            return None


class RunnerFactory:
    @staticmethod
    def register_runner(name: str, runner_cls: Any, metadata: Any = None) -> None:
        reg = _get_registry()
        if reg and hasattr(reg, "register_runner"):
            return reg.register_runner(name, runner_cls, metadata)
        raise ImportError("agent_runners.registry.register_runner unavailable")

    @staticmethod
    def create_runner(framework: str, agent_id: str, config: Any) -> Any:
        reg = _get_registry()
        if reg and hasattr(reg, "create_runner"):
            try:
                # Prefer new signature that accepts agent_id kw
                return reg.create_runner(framework, config, agent_id=agent_id)
            except TypeError:
                # Fallback to older signature without agent_id
                return reg.create_runner(framework, config)
        raise ImportError("agent_runners.registry.create_runner unavailable")

    @staticmethod
    def get_all_frameworks() -> List[str]:
        reg = _get_registry()
        if reg and hasattr(reg, "supported_runners"):
            try:
                return list(reg.supported_runners())
            except (AttributeError, TypeError):
                return []
        if reg and hasattr(reg, "get_all_frameworks"):
            try:
                return list(reg.get_all_frameworks())
            except (AttributeError, TypeError):
                return []
        return []

    @staticmethod
    def get_framework_info(name: str) -> dict:
        reg = _get_registry()
        if reg and hasattr(reg, "get_framework_info"):
            try:
                return reg.get_framework_info(name)
            except (AttributeError, TypeError):
                return {"name": name, "available": False}
        return {"name": name, "available": False}

    @staticmethod
    def is_framework_available(name: str) -> bool:
        reg = _get_registry()
        if reg and hasattr(reg, "is_framework_available"):
            try:
                return bool(reg.is_framework_available(name))
            except (AttributeError, TypeError):
                return False
        return False

    @staticmethod
    def validate_config(framework: str, cfg: Any) -> Any:
        reg = _get_registry()
        if reg and hasattr(reg, "validate_config"):
            # Propagate validation errors (e.g., AgentRunnerError) as tests expect
            return reg.validate_config(framework, cfg)
        return cfg
