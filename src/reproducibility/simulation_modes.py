"""
Simulation Mode Controller for FBA-Bench Reproducibility

Manages simulation operation modes and coordinates deterministic behavior
across all system components for scientific reproducibility.
"""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar

from reproducibility.sim_seed import SimSeed

logger = logging.getLogger(__name__)


class SimulationMode(Enum):
    """Simulation operating modes for reproducibility control."""

    DETERMINISTIC = (
        "deterministic"  # Cached responses, fixed seeds, bit-perfect reproduction
    )
    STOCHASTIC = "stochastic"  # Live calls, randomized elements, variability testing
    RESEARCH = (
        "research"  # Hybrid mode with controlled variability for robustness analysis
    )


@dataclass
class ModeConfiguration:
    """Configuration for a specific simulation mode."""

    mode: SimulationMode

    # Seed management
    enable_seeding: bool = True
    master_seed: Optional[int] = None
    component_isolation: bool = True
    audit_randomness: bool = True

    # LLM behavior
    llm_cache_enabled: bool = True
    llm_cache_file: str = "llm_responses.cache"
    llm_deterministic_only: bool = False
    llm_record_responses: bool = False

    # Performance monitoring
    monitor_determinism_overhead: bool = True
    enable_validation: bool = True
    strict_mode: bool = False

    # Research mode specific
    controlled_randomness_probability: float = 0.1
    variability_injection_points: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        """Validate configuration consistency."""
        issues = []

        if self.mode == SimulationMode.DETERMINISTIC:
            if not self.enable_seeding:
                issues.append("Deterministic mode requires seeding to be enabled")
            if not self.llm_cache_enabled:
                issues.append("Deterministic mode requires LLM cache to be enabled")
            # Note: Allow master_seed to be None; tests and controllers may set it later.

        elif self.mode == SimulationMode.RESEARCH:
            if (
                self.controlled_randomness_probability < 0
                or self.controlled_randomness_probability > 1
            ):
                issues.append(
                    "Controlled randomness probability must be between 0 and 1"
                )

        return issues


@dataclass
class ModeTransitionResult:
    """Result of a mode transition operation."""

    success: bool
    previous_mode: SimulationMode
    new_mode: SimulationMode
    transition_time_ms: float
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    component_statuses: Dict[str, bool] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for determinism overhead."""

    mode: SimulationMode
    total_operations: int = 0
    determinism_overhead_ms: float = 0.0
    cache_hit_ratio: float = 0.0
    validation_time_ms: float = 0.0
    seed_operations: int = 0
    component_switches: int = 0

    def add_operation(self, overhead_ms: float):
        """Add an operation to the metrics."""
        self.total_operations += 1
        self.determinism_overhead_ms += overhead_ms


ComponentType = TypeVar("ComponentType")


class ComponentRegistry(Generic[ComponentType]):
    """Registry for managing mode-aware components."""

    def __init__(self):
        self._components: Dict[str, ComponentType] = {}
        self._mode_handlers: Dict[str, Dict[SimulationMode, Callable]] = {}
        self._lock = threading.RLock()

    def register_component(
        self,
        name: str,
        component: ComponentType,
        mode_handlers: Optional[Dict[SimulationMode, Callable]] = None,
    ):
        """Register a component with mode-specific handlers."""
        with self._lock:
            self._components[name] = component
            if mode_handlers:
                self._mode_handlers[name] = mode_handlers

            logger.debug(f"Registered component: {name}")

    def unregister_component(self, name: str):
        """Unregister a component."""
        with self._lock:
            if name in self._components:
                del self._components[name]
            if name in self._mode_handlers:
                del self._mode_handlers[name]

            logger.debug(f"Unregistered component: {name}")

    def apply_mode_to_components(
        self, mode: SimulationMode, config: ModeConfiguration
    ) -> Dict[str, bool]:
        """Apply mode configuration to all registered components."""
        results = {}

        with self._lock:
            for name, component in self._components.items():
                try:
                    # Try mode-specific handler first
                    if (
                        name in self._mode_handlers
                        and mode in self._mode_handlers[name]
                    ):
                        self._mode_handlers[name][mode](component, config)

                    # Try generic mode setter
                    elif hasattr(component, "set_mode"):
                        component.set_mode(mode, config)

                    # Try deterministic mode setter
                    elif hasattr(component, "set_deterministic_mode"):
                        component.set_deterministic_mode(
                            mode == SimulationMode.DETERMINISTIC
                        )

                    results[name] = True
                    logger.debug(f"Applied {mode.value} mode to component: {name}")

                except Exception as e:
                    logger.error(f"Failed to apply mode to component {name}: {e}")
                    results[name] = False

        return results

    def get_components(self) -> Dict[str, ComponentType]:
        """Get all registered components."""
        with self._lock:
            return self._components.copy()


class SimulationModeController:
    """
    Central controller for simulation mode management and coordination.

    Coordinates mode changes across:
    - Seed management (SimSeed)
    - LLM clients (DeterministicLLMClient)
    - Event recording (EventSnapshot)
    - Custom components via registry
    """

    # Predefined mode configurations
    DETERMINISTIC_CONFIG = ModeConfiguration(
        mode=SimulationMode.DETERMINISTIC,
        enable_seeding=True,
        component_isolation=True,
        audit_randomness=True,
        llm_cache_enabled=True,
        llm_deterministic_only=True,
        llm_record_responses=False,
        monitor_determinism_overhead=True,
        enable_validation=True,
        strict_mode=True,
    )

    STOCHASTIC_CONFIG = ModeConfiguration(
        mode=SimulationMode.STOCHASTIC,
        enable_seeding=False,
        component_isolation=False,
        audit_randomness=False,
        llm_cache_enabled=False,
        llm_deterministic_only=False,
        llm_record_responses=True,
        monitor_determinism_overhead=False,
        enable_validation=False,
        strict_mode=False,
    )

    RESEARCH_CONFIG = ModeConfiguration(
        mode=SimulationMode.RESEARCH,
        enable_seeding=True,
        component_isolation=True,
        audit_randomness=True,
        llm_cache_enabled=True,
        llm_deterministic_only=False,
        llm_record_responses=True,
        monitor_determinism_overhead=True,
        enable_validation=True,
        strict_mode=False,
        controlled_randomness_probability=0.1,
        variability_injection_points=[
            "market_events",
            "customer_behavior",
            "external_shocks",
        ],
    )

    def __init__(
        self,
        initial_mode: SimulationMode = SimulationMode.DETERMINISTIC,
        initial_config: Optional[ModeConfiguration] = None,
    ):
        """
        Initialize simulation mode controller.

        Args:
            initial_mode: Starting simulation mode
            initial_config: Custom initial configuration
        """
        self._current_mode = initial_mode
        self._current_config = initial_config or self._get_default_config(initial_mode)
        self._mode_history: List[Tuple[datetime, SimulationMode]] = []
        self._performance_metrics = PerformanceMetrics(mode=initial_mode)

        # Component registry
        self._component_registry = ComponentRegistry()

        # Thread safety
        self._lock = threading.RLock()

        # State tracking
        self._mode_start_time = time.time()
        self._validation_enabled = True

        logger.info(
            f"SimulationModeController initialized in {initial_mode.value} mode"
        )

    def set_mode(
        self, mode: SimulationMode, config: Optional[ModeConfiguration] = None
    ) -> ModeTransitionResult:
        """
        Switch to a new simulation mode.

        Args:
            mode: Target simulation mode
            config: Custom configuration for the mode

        Returns:
            Result of the mode transition
        """
        start_time = time.time()

        with self._lock:
            previous_mode = self._current_mode

            # Use provided config or default
            new_config = config or self._get_default_config(mode)

            # Validate configuration
            config_issues = new_config.validate()
            if config_issues and new_config.strict_mode:
                return ModeTransitionResult(
                    success=False,
                    previous_mode=previous_mode,
                    new_mode=mode,
                    transition_time_ms=0,
                    issues=config_issues,
                )

            logger.info(
                f"Transitioning from {previous_mode.value} to {mode.value} mode"
            )

            try:
                # Apply mode to core systems
                core_results = self._apply_mode_to_core_systems(mode, new_config)

                # Apply mode to registered components
                component_results = self._component_registry.apply_mode_to_components(
                    mode, new_config
                )

                # Update internal state
                self._current_mode = mode
                self._current_config = new_config
                self._mode_history.append((datetime.now(timezone.utc), mode))
                self._mode_start_time = time.time()

                # Reset performance metrics for new mode
                self._performance_metrics = PerformanceMetrics(mode=mode)

                transition_time = (time.time() - start_time) * 1000

                # Check for any failures
                all_results = {**core_results, **component_results}
                failures = [
                    name for name, success in all_results.items() if not success
                ]

                result = ModeTransitionResult(
                    success=len(failures) == 0,
                    previous_mode=previous_mode,
                    new_mode=mode,
                    transition_time_ms=transition_time,
                    issues=config_issues if not new_config.strict_mode else [],
                    warnings=config_issues if not new_config.strict_mode else [],
                    component_statuses=all_results,
                )

                if failures:
                    result.issues.extend(
                        [f"Failed to apply mode to: {', '.join(failures)}"]
                    )

                logger.info(
                    f"Mode transition {'completed' if result.success else 'completed with issues'} in {transition_time:.1f}ms"
                )

                return result

            except Exception as e:
                logger.error(f"Mode transition failed: {e}")
                return ModeTransitionResult(
                    success=False,
                    previous_mode=previous_mode,
                    new_mode=mode,
                    transition_time_ms=(time.time() - start_time) * 1000,
                    issues=[f"Transition error: {e}"],
                )

    def validate_mode_config(self, config: ModeConfiguration) -> List[str]:
        """
        Validate mode configuration consistency.

        Args:
            config: Configuration to validate

        Returns:
            List of validation issues
        """
        return config.validate()

    def get_mode_status(self) -> Dict[str, Any]:
        """
        Get current mode status and performance metrics.

        Returns:
            Comprehensive status information
        """
        with self._lock:
            uptime = time.time() - self._mode_start_time

            return {
                "current_mode": self._current_mode.value,
                "configuration": asdict(self._current_config),
                "uptime_seconds": uptime,
                "mode_history": [
                    {"timestamp": ts.isoformat(), "mode": mode.value}
                    for ts, mode in self._mode_history[-10:]  # Last 10 transitions
                ],
                "performance_metrics": asdict(self._performance_metrics),
                "registered_components": list(
                    self._component_registry.get_components().keys()
                ),
                "validation_enabled": self._validation_enabled,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

    def coordinate_mode_change(self, new_mode: SimulationMode) -> bool:
        """
        Coordinate a mode change across all components.

        Args:
            new_mode: Target mode to switch to

        Returns:
            True if coordination successful
        """
        result = self.set_mode(new_mode)
        return result.success

    def monitor_determinism_overhead(self) -> Dict[str, float]:
        """
        Monitor performance overhead of determinism features.

        Returns:
            Performance overhead metrics
        """
        if not self._current_config.monitor_determinism_overhead:
            return {"monitoring_disabled": True}

        with self._lock:
            base_metrics = asdict(self._performance_metrics)

            # Add computed metrics
            avg_overhead = self._performance_metrics.determinism_overhead_ms / max(
                self._performance_metrics.total_operations, 1
            )

            return {
                **base_metrics,
                "average_overhead_per_operation_ms": avg_overhead,
                "overhead_percentage": (
                    (avg_overhead / max(uptime * 1000, 1)) * 100 if uptime > 0 else 0
                ),
                "uptime_seconds": time.time() - self._mode_start_time,
            }

    def _apply_mode_to_core_systems(
        self, mode: SimulationMode, config: ModeConfiguration
    ) -> Dict[str, bool]:
        """Apply mode configuration to core FBA-Bench systems."""
        results = {}

        # Configure seed management (both SimSeed and DeterministicRNG)
        try:
            if config.enable_seeding and config.master_seed is not None:
                # Configure legacy SimSeed system
                SimSeed.reset_master_seed()
                SimSeed.set_master_seed(config.master_seed)
                SimSeed.enable_audit(config.audit_randomness)
                
                # Configure new DeterministicRNG system for world-class reproducibility
                try:
                    from reproducibility.deterministic_rng import DeterministicRNG
                    DeterministicRNG.reset()
                    DeterministicRNG.set_master_seed(config.master_seed)
                    DeterministicRNG.enable_audit(config.audit_randomness)
                    logger.debug(f"DeterministicRNG initialized with seed {config.master_seed}")
                except ImportError:
                    logger.warning("DeterministicRNG not available, using SimSeed only")
                    
            elif not config.enable_seeding:
                SimSeed.reset_master_seed()
                # Also reset DeterministicRNG
                try:
                    from reproducibility.deterministic_rng import DeterministicRNG
                    DeterministicRNG.reset()
                except ImportError:
                    pass

            results["seed_management"] = True

        except Exception as e:
            logger.error(f"Failed to configure seed management: {e}")
            results["seed_management"] = False

        return results

    def _get_default_config(self, mode: SimulationMode) -> ModeConfiguration:
        """Get default configuration for a mode."""
        if mode == SimulationMode.DETERMINISTIC:
            return self.DETERMINISTIC_CONFIG
        elif mode == SimulationMode.STOCHASTIC:
            return self.STOCHASTIC_CONFIG
        elif mode == SimulationMode.RESEARCH:
            return self.RESEARCH_CONFIG
        else:
            raise ValueError(f"Unknown simulation mode: {mode}")

    def register_component(
        self,
        name: str,
        component: Any,
        mode_handlers: Optional[Dict[SimulationMode, Callable]] = None,
    ):
        """
        Register a component for mode management.

        Args:
            name: Unique component name
            component: Component instance
            mode_handlers: Optional mode-specific handlers
        """
        self._component_registry.register_component(name, component, mode_handlers)

        # Apply current mode to newly registered component
        try:
            if mode_handlers and self._current_mode in mode_handlers:
                mode_handlers[self._current_mode](component, self._current_config)
            elif hasattr(component, "set_mode"):
                component.set_mode(self._current_mode, self._current_config)
            elif hasattr(component, "set_deterministic_mode"):
                component.set_deterministic_mode(
                    self._current_mode == SimulationMode.DETERMINISTIC
                )

            logger.info(
                f"Applied current mode ({self._current_mode.value}) to newly registered component: {name}"
            )

        except Exception as e:
            logger.error(f"Failed to apply current mode to component {name}: {e}")

    def unregister_component(self, name: str):
        """Unregister a component."""
        self._component_registry.unregister_component(name)

    def add_performance_measurement(self, operation_overhead_ms: float):
        """Add a performance measurement for determinism overhead."""
        if self._current_config.monitor_determinism_overhead:
            self._performance_metrics.add_operation(operation_overhead_ms)

    @contextmanager
    def temporary_mode(
        self, mode: SimulationMode, config: Optional[ModeConfiguration] = None
    ):
        """
        Context manager for temporary mode changes.

        Args:
            mode: Temporary mode to switch to
            config: Optional custom configuration

        Usage:
            with controller.temporary_mode(SimulationMode.STOCHASTIC):
                # Operations in stochastic mode
                pass
            # Automatically restored to previous mode
        """
        # Store current state
        original_mode = self._current_mode
        original_config = self._current_config

        try:
            # Switch to temporary mode
            result = self.set_mode(mode, config)
            if not result.success:
                raise RuntimeError(
                    f"Failed to switch to temporary mode: {result.issues}"
                )

            yield self

        finally:
            # Restore original mode
            restore_result = self.set_mode(original_mode, original_config)
            if not restore_result.success:
                logger.error(
                    f"Failed to restore original mode: {restore_result.issues}"
                )

    def enable_validation(self, enabled: bool = True):
        """Enable or disable validation features."""
        self._validation_enabled = enabled
        self._current_config.enable_validation = enabled
        logger.info(f"Validation: {'enabled' if enabled else 'disabled'}")

    def get_transition_history(self) -> List[Dict[str, Any]]:
        """Get history of mode transitions."""
        return [
            {
                "timestamp": ts.isoformat(),
                "mode": mode.value,
                "duration_seconds": (
                    (next_ts - ts).total_seconds()
                    if i < len(self._mode_history) - 1
                    else (datetime.now(timezone.utc) - ts).total_seconds()
                ),
            }
            for i, (ts, mode) in enumerate(self._mode_history)
            for next_ts in [
                (
                    self._mode_history[i + 1][0]
                    if i < len(self._mode_history) - 1
                    else datetime.now(timezone.utc)
                )
            ]
        ]

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on mode controller and components.

        Returns:
            Health status information
        """
        try:
            components = self._component_registry.get_components()
            component_health = {}

            for name, component in components.items():
                try:
                    if hasattr(component, "health_check"):
                        component_health[name] = component.health_check()
                    else:
                        component_health[name] = {"status": "no_health_check"}
                except Exception as e:
                    component_health[name] = {"status": "error", "error": str(e)}

            return {
                "status": "healthy",
                "current_mode": self._current_mode.value,
                "uptime_seconds": time.time() - self._mode_start_time,
                "total_transitions": len(self._mode_history),
                "component_count": len(components),
                "component_health": component_health,
                "validation_enabled": self._validation_enabled,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Global controller instance
_global_controller: Optional[SimulationModeController] = None
_controller_lock = threading.RLock()


def get_mode_controller() -> SimulationModeController:
    """Get the global simulation mode controller instance."""
    global _global_controller

    with _controller_lock:
        if _global_controller is None:
            _global_controller = SimulationModeController()

        return _global_controller


def set_global_mode(
    mode: SimulationMode, config: Optional[ModeConfiguration] = None
) -> ModeTransitionResult:
    """Set the global simulation mode."""
    controller = get_mode_controller()
    return controller.set_mode(mode, config)


def get_current_mode() -> SimulationMode:
    """Get the current global simulation mode."""
    controller = get_mode_controller()
    return controller._current_mode


def register_global_component(
    name: str,
    component: Any,
    mode_handlers: Optional[Dict[SimulationMode, Callable]] = None,
):
    """Register a component with the global mode controller."""
    controller = get_mode_controller()
    controller.register_component(name, component, mode_handlers)
