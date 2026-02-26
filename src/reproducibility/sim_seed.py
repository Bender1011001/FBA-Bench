import asyncio
import hashlib
import logging
import random
import threading
import traceback
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RNGSourceInfo:
    """Information about a registered RNG source."""

    name: str
    source_type: str
    instance: Any
    component: str
    registered_at: str
    last_used: Optional[str] = None
    usage_count: int = 0


@dataclass
class SeedAuditEntry:
    """Audit entry for seed usage tracking."""

    timestamp: str
    component: str
    operation: str
    seed_value: int
    call_stack: str
    thread_id: str
    task_id: Optional[str] = None


@dataclass
class DeterminismValidationResult:
    """Result of determinism validation."""

    is_deterministic: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    unregistered_sources: List[str] = field(default_factory=list)
    seed_conflicts: List[str] = field(default_factory=list)


class SimSeed:
    """
    Enhanced seed management system for deterministic reproducibility
    across multi-threaded, multi-component simulations.

    Features:
    - Thread-safe seeding across asyncio tasks and threads
    - Component isolation with separate seed streams
    - Comprehensive audit trail of all RNG usage
    - Validation and detection of uncontrolled randomness
    - Real-time monitoring of determinism violations
    """

    _master_seed: Optional[int] = None
    _component_seeds: Dict[str, int] = {}
    _registered_sources: Dict[str, RNGSourceInfo] = {}
    _audit_trail: List[SeedAuditEntry] = []
    _seed_lock = threading.RLock()
    _audit_enabled: bool = True
    _thread_local = threading.local()
    _task_seeds: Dict[str, int] = {}
    _unregistered_calls: Set[str] = set()

    @classmethod
    def set_master_seed(cls, seed: int):
        """
        Sets the global master seed with enhanced thread safety and auditing.
        This should be called once at the start of a deterministic simulation run.
        """
        with cls._seed_lock:
            if cls._master_seed is not None:
                raise RuntimeError(
                    "Master seed already set. Cannot re-seed during a run."
                )

            cls._master_seed = seed
            cls._component_seeds.clear()
            cls._task_seeds.clear()
            cls._audit_trail.clear()
            cls._unregistered_calls.clear()

            # Initialize Python's random module
            random.seed(seed)

            # Initialize NumPy's random number generator
            np.random.seed(seed)

            # Create audit entry
            cls._add_audit_entry("master", "set_master_seed", seed)

            logger.info(f"Master seed set to: {seed}")

    @classmethod
    def get_master_seed(cls) -> Optional[int]:
        """
        Returns the current master seed.
        """
        return cls._master_seed

    @classmethod
    def derive_seed(cls, salt: Union[str, int]) -> int:
        """
        Derives a new deterministic seed from the master seed and a given salt.
        This ensures different components get isolated, yet reproducible, streams.
        """
        with cls._seed_lock:
            if cls._master_seed is None:
                raise RuntimeError("Master seed not set. Call set_master_seed() first.")

            # Use a combination of the master seed and salt to create a deterministic sub-seed
            combined_string = f"{cls._master_seed}-{salt}"
            derived_seed = int(
                hashlib.sha256(combined_string.encode()).hexdigest(), 16
            ) % (2**32 - 1)

            # Create audit entry
            cls._add_audit_entry(
                "derived", "derive_seed", derived_seed, f"salt: {salt}"
            )

            return derived_seed

    @classmethod
    def get_component_seed(cls, component_name: str) -> int:
        """
        Get or create an isolated seed for a specific component.

        Args:
            component_name: Name of the component requesting a seed

        Returns:
            Deterministic seed specific to the component
        """
        with cls._seed_lock:
            if component_name not in cls._component_seeds:
                if cls._master_seed is None:
                    raise RuntimeError(
                        "Master seed not set. Call set_master_seed() first."
                    )

                # Create component-specific seed
                component_seed = cls.derive_seed(f"component_{component_name}")
                cls._component_seeds[component_name] = component_seed

                logger.debug(
                    f"Created component seed for '{component_name}': {component_seed}"
                )

            cls._add_audit_entry(
                component_name,
                "get_component_seed",
                cls._component_seeds[component_name],
            )
            return cls._component_seeds[component_name]

    @classmethod
    def register_rng_source(
        cls,
        source_name: str,
        rng_instance: Any,
        component: str,
        source_type: str = "unknown",
    ):
        """
        Register an RNG source for tracking and validation.

        Args:
            source_name: Unique name for the RNG source
            rng_instance: The RNG instance (e.g., random.Random(), numpy.random.Generator)
            component: Component that owns this RNG
            source_type: Type of RNG (random, numpy, custom, etc.)
        """
        with cls._seed_lock:
            if source_name in cls._registered_sources:
                logger.warning(
                    f"RNG source '{source_name}' already registered, updating..."
                )

            cls._registered_sources[source_name] = RNGSourceInfo(
                name=source_name,
                source_type=source_type,
                instance=rng_instance,
                component=component,
                registered_at=datetime.now(timezone.utc).isoformat(),
            )

            # Seed the registered RNG with component-specific seed
            component_seed = cls.get_component_seed(component)  # noqa: F841

            try:
                # Attempt to seed the RNG instance
                if hasattr(rng_instance, "seed"):
                    # Derive a specific seed for this RNG source
                    rng_seed = cls.derive_seed(f"{component}_{source_name}")
                    rng_instance.seed(rng_seed)

                    cls._add_audit_entry(
                        component,
                        "register_rng_source",
                        rng_seed,
                        f"source: {source_name}, type: {source_type}",
                    )

                    logger.debug(
                        f"Registered and seeded RNG '{source_name}' for component '{component}'"
                    )
                else:
                    logger.warning(
                        f"RNG instance '{source_name}' does not have a 'seed' method"
                    )

            except Exception as e:
                logger.error(f"Failed to seed RNG '{source_name}': {e}")

    @classmethod
    def audit_randomness_sources(cls) -> List[str]:
        """
        Audit all known randomness sources and detect unregistered usage.

        Returns:
            List of potential issues or unregistered sources
        """
        issues = []

        with cls._seed_lock:
            # Check if any unregistered calls were detected
            if cls._unregistered_calls:
                issues.extend(
                    [
                        f"Unregistered RNG call: {call}"
                        for call in cls._unregistered_calls
                    ]
                )

            # Check for RNG sources that haven't been used
            unused_sources = [
                name
                for name, info in cls._registered_sources.items()
                if info.usage_count == 0
            ]

            if unused_sources:
                issues.append(f"Registered but unused RNG sources: {unused_sources}")

            # Check for potential threading issues
            thread_usage = defaultdict(int)  # type: ignore[var-annotated]
            for entry in cls._audit_trail:
                thread_usage[entry.thread_id] += 1

            if len(thread_usage) > 1:
                issues.append(
                    f"RNG usage detected across {len(thread_usage)} threads: {dict(thread_usage)}"
                )

            logger.info(
                f"Randomness audit completed. Found {len(issues)} potential issues."
            )

        return issues

    @classmethod
    def ensure_thread_safety(cls) -> bool:
        """
        Ensure that thread-safe seeding is properly configured.

        Returns:
            True if thread safety is ensured, False if issues detected
        """
        with cls._seed_lock:
            current_thread = threading.current_thread().ident

            # Get or create thread-local RNG state
            if not hasattr(cls._thread_local, "rng_state"):
                if cls._master_seed is None:
                    logger.error("Cannot ensure thread safety: master seed not set")
                    return False

                # Create thread-specific seed
                thread_seed = cls.derive_seed(f"thread_{current_thread}")
                cls._thread_local.rng_state = random.Random(thread_seed)
                cls._thread_local.np_rng = np.random.Generator(
                    np.random.PCG64(thread_seed)
                )

                cls._add_audit_entry(
                    "thread_safety",
                    "ensure_thread_safety",
                    thread_seed,
                    f"thread_id: {current_thread}",
                )

                logger.debug(
                    f"Thread-local RNG state created for thread {current_thread}"
                )

            return True

    @classmethod
    def get_thread_local_rng(cls) -> Tuple[random.Random, np.random.Generator]:
        """
        Get thread-local RNG instances.

        Returns:
            Tuple of (Python Random instance, NumPy Generator instance)
        """
        if not cls.ensure_thread_safety():
            raise RuntimeError("Failed to ensure thread safety")

        return cls._thread_local.rng_state, cls._thread_local.np_rng

    @classmethod
    def validate_determinism(
        cls, simulation_run: Any = None
    ) -> DeterminismValidationResult:
        """
        Validate that the simulation maintains determinism.

        Args:
            simulation_run: Optional simulation run data for validation

        Returns:
            Validation result with detected issues
        """
        result = DeterminismValidationResult(is_deterministic=True)

        with cls._seed_lock:
            # Check master seed is set
            if cls._master_seed is None:
                result.is_deterministic = False
                result.issues.append("Master seed not set")

            # Check for unregistered RNG usage
            unregistered = cls.audit_randomness_sources()
            if unregistered:
                result.unregistered_sources = unregistered
                if any("Unregistered RNG call" in issue for issue in unregistered):
                    result.is_deterministic = False
                    result.issues.extend(unregistered)
                else:
                    result.warnings.extend(unregistered)

            # Check for seed conflicts (same seed used by multiple components)
            seed_usage = defaultdict(list)
            for component, seed in cls._component_seeds.items():
                seed_usage[seed].append(component)

            conflicts = {
                seed: components
                for seed, components in seed_usage.items()
                if len(components) > 1
            }
            if conflicts:
                result.seed_conflicts = [
                    f"Seed {seed} used by: {components}"
                    for seed, components in conflicts.items()
                ]
                result.warnings.extend(result.seed_conflicts)

            # Check audit trail for anomalies
            if cls._audit_enabled and len(cls._audit_trail) == 0:
                result.warnings.append(
                    "No audit trail entries found - possible tracking issue"
                )

            # Validate thread usage patterns
            threads_in_audit = set(entry.thread_id for entry in cls._audit_trail)
            if len(threads_in_audit) > 10:  # Arbitrary threshold
                result.warnings.append(
                    f"High thread count detected: {len(threads_in_audit)} threads"
                )

            logger.info(
                f"Determinism validation: {'PASSED' if result.is_deterministic else 'FAILED'}"
            )

        return result

    @classmethod
    def _add_audit_entry(
        cls, component: str, operation: str, seed_value: int, details: str = ""
    ):
        """Add an entry to the audit trail."""
        if not cls._audit_enabled:
            return

        # Get current thread and task information
        thread_id = str(threading.current_thread().ident)
        task_id = None

        try:
            # Try to get current asyncio task
            if asyncio.current_task():
                task_id = str(id(asyncio.current_task()))
        except RuntimeError:
            pass  # Not in an asyncio context

        # Get call stack for debugging (limited depth)
        call_stack = "->".join(
            [
                f"{frame.filename}:{frame.lineno}:{frame.name}"
                for frame in traceback.extract_stack()[-3:-1]  # Skip current frame
            ]
        )

        entry = SeedAuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            component=component,
            operation=f"{operation}({details})" if details else operation,
            seed_value=seed_value,
            call_stack=call_stack,
            thread_id=thread_id,
            task_id=task_id,
        )

        cls._audit_trail.append(entry)

        # Limit audit trail size to prevent memory issues
        if len(cls._audit_trail) > 10000:
            cls._audit_trail = cls._audit_trail[-5000:]  # Keep recent half

    @classmethod
    def get_audit_trail(cls) -> List[SeedAuditEntry]:
        """Get copy of the audit trail."""
        with cls._seed_lock:
            return cls._audit_trail.copy()

    @classmethod
    def export_audit_trail(cls, filepath: str) -> bool:
        """
        Export audit trail to file for analysis.

        Args:
            filepath: Path to export file

        Returns:
            True if successful, False otherwise
        """
        try:
            import json

            with cls._seed_lock:
                audit_data = {
                    "master_seed": cls._master_seed,
                    "component_seeds": cls._component_seeds,
                    "registered_sources": {
                        name: {
                            "name": info.name,
                            "source_type": info.source_type,
                            "component": info.component,
                            "registered_at": info.registered_at,
                            "last_used": info.last_used,
                            "usage_count": info.usage_count,
                        }
                        for name, info in cls._registered_sources.items()
                    },
                    "audit_trail": [
                        {
                            "timestamp": entry.timestamp,
                            "component": entry.component,
                            "operation": entry.operation,
                            "seed_value": entry.seed_value,
                            "call_stack": entry.call_stack,
                            "thread_id": entry.thread_id,
                            "task_id": entry.task_id,
                        }
                        for entry in cls._audit_trail
                    ],
                }

            with open(filepath, "w") as f:
                json.dump(audit_data, f, indent=2, separators=(",", ": "))

            logger.info(f"Audit trail exported to: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export audit trail: {e}")
            return False

    @classmethod
    def enable_audit(cls, enabled: bool = True):
        """Enable or disable audit trail recording."""
        cls._audit_enabled = enabled
        logger.info(f"Audit trail: {'enabled' if enabled else 'disabled'}")

    @classmethod
    @contextmanager
    def component_context(cls, component_name: str):
        """
        Context manager for component-scoped RNG operations.

        Args:
            component_name: Name of the component

        Usage:
            with SimSeed.component_context("market_simulation"):
                # All RNG operations in this block use component-specific seeds
                value = random.random()
        """
        # Store original state
        original_state = random.getstate()
        original_np_state = np.random.get_state()

        try:
            # Set component-specific seeds
            component_seed = cls.get_component_seed(component_name)
            random.seed(component_seed)
            np.random.seed(component_seed)

            cls._add_audit_entry(component_name, "context_enter", component_seed)

            yield component_seed

        finally:
            # Restore original state
            random.setstate(original_state)
            np.random.set_state(original_np_state)

            cls._add_audit_entry(component_name, "context_exit", component_seed)

    @classmethod
    def reset_master_seed(cls):
        """
        Resets the master seed, allowing it to be set again.
        Use with caution, typically only for testing or between simulation runs.
        """
        with cls._seed_lock:
            cls._master_seed = None
            cls._component_seeds.clear()
            cls._registered_sources.clear()
            cls._task_seeds.clear()
            cls._unregistered_calls.clear()

            # Clear audit trail
            cls._audit_trail.clear()

            # Reset standard libraries to non-deterministic state
            random.seed(None)
            np.random.seed(None)

            logger.info("Master seed and all tracking data reset")

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """Get comprehensive statistics about seed usage."""
        with cls._seed_lock:
            return {
                "master_seed": cls._master_seed,
                "component_count": len(cls._component_seeds),
                "registered_sources": len(cls._registered_sources),
                "audit_entries": len(cls._audit_trail),
                "unregistered_calls": len(cls._unregistered_calls),
                "audit_enabled": cls._audit_enabled,
                "thread_count": len(set(entry.thread_id for entry in cls._audit_trail)),
                "components": list(cls._component_seeds.keys()),
                "source_types": list(
                    set(info.source_type for info in cls._registered_sources.values())
                ),
            }


# Initialize the master seed to a non-deterministic state by default on module load
# This ensures that if set_master_seed is not called, we don't accidentally get
# pseudo-deterministic behavior from uninitialized state.
SimSeed.reset_master_seed()
