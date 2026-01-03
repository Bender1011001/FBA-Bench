# mypy: ignore-errors
from __future__ import annotations

"""
Typed registry and explicit helper for agent runner creation.

- Provides a small, testable mapping from runner_key -> concrete runner class
- Validates config using the target runner's Pydantic v2 model when available
- Defers optional third-party imports to runner initialization (soft deps preserved)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Type

# Core base API
from .base_runner import AgentRunner, AgentRunnerError

# Import concrete runners and their config models (safe: these modules only soft-import 3rd parties at runtime)
from .crewai_runner import CrewAIRunner, CrewAIRunnerConfig
from .langchain_runner import LangChainRunner, LangChainRunnerConfig

# DIY is always available and does not have a dedicated Pydantic config model
try:
    from .diy_runner import DIYRunner
except (ImportError, AttributeError):
    DIYRunner = None  # type: ignore

logger = logging.getLogger(__name__)

# Internal registry holds (RunnerClass, Optional[ConfigModelClass])
# Keep imports soft: config models do not import third-party frameworks; runners soft-import at _do_initialize
RUNNER_REGISTRY: Dict[str, Tuple[Type[AgentRunner], Optional[Type[Any]]]] = {}

if DIYRunner is not None:
    RUNNER_REGISTRY["diy"] = (DIYRunner, None)

RUNNER_REGISTRY.update(
    {
        "crewai": (CrewAIRunner, CrewAIRunnerConfig),
        "langchain": (LangChainRunner, LangChainRunnerConfig),
    }
)


def supported_runners() -> List[str]:
    """Return supported runner keys."""
    return sorted(RUNNER_REGISTRY.keys())


def _validate_config(key: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize config for the target runner when a Pydantic model is available."""
    runner_entry = RUNNER_REGISTRY.get(key)
    if not runner_entry:
        return cfg
    _, cfg_model = runner_entry

    # No model provided: accept as-is
    if cfg_model is None:
        return cfg or {}

    # Some tests pass a dict as "metadata" for the config model. Merge it as defaults.
    if isinstance(cfg_model, dict):
        merged = dict(cfg_model)
        merged.update(cfg or {})
        return merged

    # Try Pydantic v2 first
    try:
        model_validate = getattr(cfg_model, "model_validate", None)
        if callable(model_validate):
            validated = model_validate(cfg or {})
            # Prefer model_dump if available
            if hasattr(validated, "model_dump"):
                return validated.model_dump(exclude_none=True)
            # Fallback to dict-like
            try:
                return dict(validated)
            except (TypeError, ValueError, AttributeError):
                return cfg or {}
    except (AttributeError, TypeError, ValueError, RuntimeError):
        # fall through to v1 attempt
        pass

    # Try Pydantic v1 style
    try:
        inst = cfg_model(**(cfg or {}))
        if hasattr(inst, "dict"):
            return inst.dict(exclude_none=True)
        if hasattr(inst, "model_dump"):
            return inst.model_dump(exclude_none=True)
        try:
            return dict(inst)
        except (TypeError, ValueError, AttributeError):
            return cfg or {}
    except (TypeError, ValueError, AttributeError, RuntimeError) as e:
        # Clear error message surfaced to callers, but keep it forgiving for non-pydantic inputs
        raise ValueError(f"Invalid config for runner '{key}': {e}") from e


def create_runner(
    key: str, config: Dict[str, Any], agent_id: Optional[str] = None
) -> AgentRunner:
    """
    Create a runner instance with validation.

    Args:
        key: runner key (e.g., 'crewai', 'langchain', 'diy')
        config: configuration dict for the runner
        agent_id: optional explicit agent id to use when constructing the runner

    Returns:
        AgentRunner instance

    Raises:
        ValueError: when key is unknown or config validation fails
        AgentRunnerInitializationError: if optional dependency is missing during initialization
    """
    if not isinstance(key, str):
        raise ValueError("Runner key must be a string")
    norm_key = key.strip().lower()

    entry = RUNNER_REGISTRY.get(norm_key)
    if entry is None:
        msg = (
            f"Unknown runner key: '{key}'. "
            f"Supported keys: {', '.join(supported_runners()) or '(none)'}"
        )
        logger.error(msg)
        # Normalize to AgentRunnerError expected by tests
        raise AgentRunnerError(msg)

    runner_cls, _ = entry

    # Validate config using the specific model if available
    normalized_cfg = _validate_config(norm_key, config or {})

    # Determine agent identifier
    final_agent_id = (
        agent_id
        or normalized_cfg.get("agent_id")
        or normalized_cfg.get("name")
        or normalized_cfg.get("agent_name")
        or "agent"
    )

    # Instantiate explicitly; AgentRunner __init__ may trigger initialization and optional imports
    # This preserves soft-dependency behavior: import errors happen at instantiation time
    try:
        return runner_cls(final_agent_id, normalized_cfg)
    except (AttributeError, TypeError, ValueError, RuntimeError, AgentRunnerError):
        # Let caller see runner-specific exceptions (e.g., AgentRunnerInitializationError)
        raise


def register_runner(
    name: str, runner_cls: Type[AgentRunner], config_model: Optional[Type[Any]] = None
) -> None:
    """
    Register a runner class at runtime (used by tests to inject mock runners).
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Runner name must be a non-empty string")
    RUNNER_REGISTRY[name.strip().lower()] = (runner_cls, config_model)


def is_framework_available(name: str) -> bool:
    """Return True if a runner is registered under the given name."""
    try:
        return name.strip().lower() in RUNNER_REGISTRY
    except (AttributeError, TypeError):
        return False


def get_all_frameworks() -> List[str]:
    """Return all registered runner keys."""
    return supported_runners()


def get_framework_info(name: str) -> Dict[str, Any]:
    """Return basic information about a registered runner."""
    try:
        nk = name.strip().lower()
    except (AttributeError, TypeError):
        nk = str(name or "").strip().lower()
    entry = RUNNER_REGISTRY.get(nk)
    if not entry:
        return {"name": name, "available": False}
    cls, cfg_model = entry
    return {
        "name": nk,
        "class": getattr(cls, "__name__", str(cls)),
        "available": True,
        "has_config_model": cfg_model is not None,
    }


def validate_config(framework: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Explicit config validation facade exposed for RunnerFactory proxy.
    Adds a small DIY sanity check expected by tests.
    """
    nk = (framework or "").strip().lower()
    if nk == "diy":
        agent_type = (cfg or {}).get("agent_type")
        # Accept common DIY types
        if agent_type not in {"advanced", "baseline", None}:
            from .base_runner import (
                AgentRunnerError,  # local import to avoid cycles at module import
            )

            raise AgentRunnerError(f"Invalid DIY agent_type: {agent_type!r}")
    # Defer to registry-specific validators when available
    return _validate_config(nk, cfg or {})


__all__ = [
    "RUNNER_REGISTRY",
    "create_runner",
    "supported_runners",
    "register_runner",
    "is_framework_available",
    "get_all_frameworks",
    "get_framework_info",
    "validate_config",
]
