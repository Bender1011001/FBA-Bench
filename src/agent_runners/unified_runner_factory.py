"""
Deprecation shim: agent_runners.unified_runner_factory

Historically provided a separate "unified runner factory". To preserve legacy imports,
we forward to the registry-based creation while emitting deprecation warnings.

Prefer:
    from agent_runners.registry import create_runner, supported_runners
or the AgentManager with unified agents when appropriate.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Union

from agent_runners import registry as _registry

logger = logging.getLogger(__name__)


class UnifiedRunnerFactory:
    """
    Deprecated compatibility wrapper.

    Method signatures are aligned with older code that passed (agent_type, agent_id, config).
    We forward 'agent_type' to the registry key and ensure 'agent_id' is present in config.
    """

    def __init__(self) -> None:
        logger.warning(
            "UnifiedRunnerFactory is deprecated; use AgentManager or agent_runners.registry instead."
        )

    def create_runner(
        self, agent_type: str, agent_id: str, config: Union[Dict[str, Any], Any, Any]
    ) -> Any:
        cfg: Dict[str, Any] = dict(config or {})
        cfg.setdefault("agent_id", agent_id)
        return _registry.create_runner(agent_type, cfg)

    def get_available_agent_types(self) -> List[str]:
        return _registry.supported_runners()

    # Legacy adapter APIs are not applicable; return empty or false
    def get_available_adapter_types(self) -> List[str]:
        return []

    def is_agent_type_registered(self, agent_type: str) -> bool:
        return agent_type in set(_registry.supported_runners())

    def is_adapter_type_registered(self, adapter_type: str) -> bool:
        return False


def create_unified_runner(
    agent_type: str, agent_id: str, config: Union[Dict[str, Any], Any, Any]
) -> Any:
    """
    Legacy function. Prefer agent_runners.registry.create_runner.
    """
    return UnifiedRunnerFactory().create_runner(agent_type, agent_id, config)
