"""
Deterministic execution environment for reproducible benchmarking.

This module provides tools for ensuring deterministic execution of benchmarks,
including controlled random seeds, environment isolation, and state management.
"""

import hashlib
import json
import logging
import os
import random
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentState:
    """State of the deterministic environment."""

    random_seed: int
    python_hash_seed: int
    environment_variables: Dict[str, str] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    state_hash: str = ""

    def __post_init__(self):
        """Calculate state hash after initialization."""
        self.state_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calculate hash of the environment state."""
        state_data = {
            "random_seed": self.random_seed,
            "python_hash_seed": self.python_hash_seed,
            "environment_variables": dict(sorted(self.environment_variables.items())),
            "start_time": self.start_time.isoformat(),
        }

        state_str = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()


class DeterministicEnvironment:
    """
    Manages deterministic execution environment for benchmarks.

    This class ensures that benchmark runs are reproducible by controlling
    random seeds, environment variables, and other sources of non-determinism.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the deterministic environment.

        Args:
            seed: Random seed to use (None for random generation)
        """
        self._original_state = None
        self._current_state = None
        self._is_active = False

        # Generate or use provided seed
        self._base_seed = seed if seed is not None else random.randint(0, 2**32 - 1)

        logger.info(
            f"Initialized deterministic environment with seed: {self._base_seed}"
        )

    @property
    def base_seed(self) -> int:
        """Get the base random seed."""
        return self._base_seed

    @property
    def is_active(self) -> bool:
        """Check if deterministic environment is active."""
        return self._is_active

    @property
    def current_state(self) -> Optional[EnvironmentState]:
        """Get the current environment state."""
        return self._current_state

    def activate(
        self, additional_seeds: Optional[Dict[str, int]] = None
    ) -> EnvironmentState:
        """
        Activate the deterministic environment.

        Args:
            additional_seeds: Additional seeds for specific components

        Returns:
            Current environment state
        """
        if self._is_active:
            logger.warning("Deterministic environment already active")
            return self._current_state

        # Store original state
        self._original_state = self._capture_environment_state()

        # Set random seeds
        self._set_random_seeds(additional_seeds)

        # Set environment variables for determinism
        self._set_deterministic_environment()

        # Capture current state
        self._current_state = self._capture_environment_state()
        self._is_active = True

        logger.info(
            f"Activated deterministic environment (state hash: {self._current_state.state_hash})"
        )
        return self._current_state

    def deactivate(self) -> EnvironmentState:
        """
        Deactivate the deterministic environment.

        Returns:
            Environment state before deactivation
        """
        if not self._is_active:
            logger.warning("Deterministic environment not active")
            return None

        # Capture final state
        final_state = self._capture_environment_state()

        # Restore original state
        self._restore_environment_state(self._original_state)

        self._is_active = False
        self._current_state = None

        logger.info("Deactivated deterministic environment")
        return final_state

    @contextmanager
    def context(self, additional_seeds: Optional[Dict[str, int]] = None):
        """
        Context manager for deterministic execution.

        Args:
            additional_seeds: Additional seeds for specific components

        Yields:
            EnvironmentState: Current environment state
        """
        state = self.activate(additional_seeds)
        try:
            yield state
        finally:
            self.deactivate()

    def _capture_environment_state(self) -> EnvironmentState:
        """Capture the current environment state."""
        return EnvironmentState(
            random_seed=random.getstate()[0] if hasattr(random, "getstate") else 0,
            python_hash_seed=os.environ.get("PYTHONHASHSEED", "0"),
            environment_variables=dict(os.environ),
        )

    def _set_random_seeds(
        self, additional_seeds: Optional[Dict[str, int]] = None
    ) -> None:
        """Set random seeds for all random number generators."""
        additional_seeds = additional_seeds or {}

        # Set Python random seed
        random.seed(self._base_seed)

        # Set additional seeds for specific components
        for component, seed in additional_seeds.items():
            if component == "numpy":
                try:
                    import numpy as np

                    np.random.seed(seed)
                except ImportError:
                    logger.warning("NumPy not available, skipping numpy seed")
            elif component == "torch":
                try:
                    import torch

                    torch.manual_seed(seed)
                    if torch.cuda.is_available():
                        torch.cuda.manual_seed_all(seed)
                except ImportError:
                    logger.warning("PyTorch not available, skipping torch seed")
            elif component == "tensorflow":
                try:
                    import tensorflow as tf

                    tf.random.set_seed(seed)
                except ImportError:
                    logger.warning("TensorFlow not available, skipping tensorflow seed")
            else:
                logger.warning(f"Unknown component for seeding: {component}")

    def _set_deterministic_environment(self) -> None:
        """Set environment variables for deterministic execution."""
        # Set Python hash seed
        os.environ["PYTHONHASHSEED"] = str(self._base_seed)

        # Set other deterministic environment variables
        os.environ["PYTHONHASHSEED"] = str(self._base_seed)
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "1" if os.name == "nt" else "0"

    def _restore_environment_state(self, state: EnvironmentState) -> None:
        """Restore environment to a previous state."""
        # Restore environment variables
        os.environ.clear()
        os.environ.update(state.environment_variables)

        # Restore random seed
        random.seed(state.random_seed)

    def generate_derived_seeds(
        self, count: int, base_seed: Optional[int] = None
    ) -> List[int]:
        """
        Generate derived seeds for sub-components.

        Args:
            count: Number of seeds to generate
            base_seed: Base seed to use (None for environment base seed)

        Returns:
            List of derived seeds
        """
        base = base_seed if base_seed is not None else self._base_seed

        # Generate deterministic sequence of seeds
        rng = random.Random(base)
        return [rng.randint(0, 2**32 - 1) for _ in range(count)]

    def validate_reproducibility(
        self, state1: EnvironmentState, state2: EnvironmentState
    ) -> bool:
        """
        Validate if two environment states are equivalent for reproducibility.

        Args:
            state1: First environment state
            state2: Second environment state

        Returns:
            True if states are equivalent
        """
        # Check critical fields
        if state1.random_seed != state2.random_seed:
            logger.warning("Random seeds differ between states")
            return False

        if state1.python_hash_seed != state2.python_hash_seed:
            logger.warning("Python hash seeds differ between states")
            return False

        # Check state hash
        if state1.state_hash != state2.state_hash:
            logger.warning("State hashes differ between states")
            return False

        return True

    def create_reproducible_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a reproducible configuration by adding seed information.

        Args:
            config: Original configuration

        Returns:
            Configuration with reproducibility information
        """
        reproducible_config = config.copy()

        # Add reproducibility information
        reproducible_config["_reproducibility"] = {
            "base_seed": self._base_seed,
            "environment_state": (
                self._current_state.__dict__ if self._current_state else None
            ),
            "timestamp": datetime.now().isoformat(),
        }

        return reproducible_config

    def load_reproducible_config(self, config: Dict[str, Any]) -> bool:
        """
        Load a reproducible configuration and restore environment.

        Args:
            config: Configuration with reproducibility information

        Returns:
            True if successfully loaded and restored
        """
        if "_reproducibility" not in config:
            logger.warning("Configuration does not contain reproducibility information")
            return False

        repro_info = config["_reproducibility"]

        # Extract base seed
        if "base_seed" not in repro_info:
            logger.warning("Reproducibility information missing base_seed")
            return False

        self._base_seed = repro_info["base_seed"]

        # Activate environment with stored seed
        self.activate()

        logger.info("Successfully loaded reproducible configuration")
        return True

    def get_environment_report(self) -> Dict[str, Any]:
        """
        Get a report of the current environment state.

        Returns:
            Dictionary with environment information
        """
        return {
            "base_seed": self._base_seed,
            "is_active": self._is_active,
            "current_state": (
                self._current_state.__dict__ if self._current_state else None
            ),
            "original_state": (
                self._original_state.__dict__ if self._original_state else None
            ),
            "python_version": os.sys.version,
            "platform": os.sys.platform,
            "environment_variables": dict(os.environ),
        }


class DeterministicContext:
    """
    Helper class for managing multiple deterministic contexts.

    This class provides a way to manage nested deterministic contexts
    with different seeds while maintaining reproducibility.
    """

    def __init__(self, base_seed: Optional[int] = None):
        """
        Initialize the deterministic context manager.

        Args:
            base_seed: Base seed for all contexts
        """
        self._base_seed = (
            base_seed if base_seed is not None else random.randint(0, 2**32 - 1)
        )
        self._context_stack = []
        self._environment = DeterministicEnvironment(self._base_seed)

    @property
    def base_seed(self) -> int:
        """Get the base seed."""
        return self._base_seed

    def push_context(self, context_name: str, seed: Optional[int] = None) -> int:
        """
        Push a new deterministic context.

        Args:
            context_name: Name of the context
            seed: Seed for this context (None for derived seed)

        Returns:
            Seed used for this context
        """
        # Generate derived seed if not provided
        if seed is None:
            seed = self._generate_context_seed(context_name)

        # Create context info
        context_info = {
            "name": context_name,
            "seed": seed,
            "parent_seed": (
                self._context_stack[-1]["seed"]
                if self._context_stack
                else self._base_seed
            ),
        }

        # Push to stack
        self._context_stack.append(context_info)

        # Activate environment with context seed
        self._environment.activate({"context": seed})

        logger.info(f"Pushed deterministic context: {context_name} (seed: {seed})")
        return seed

    def pop_context(self) -> Optional[Dict[str, Any]]:
        """
        Pop the current deterministic context.

        Returns:
            Context information or None if no context active
        """
        if not self._context_stack:
            logger.warning("No deterministic context to pop")
            return None

        # Pop context
        context_info = self._context_stack.pop()

        # Deactivate environment
        self._environment.deactivate()

        # Reactivate with parent context if exists
        if self._context_stack:
            parent_context = self._context_stack[-1]
            self._environment.activate({"context": parent_context["seed"]})

        logger.info(f"Popped deterministic context: {context_info['name']}")
        return context_info

    @contextmanager
    def context(self, context_name: str, seed: Optional[int] = None):
        """
        Context manager for deterministic contexts.

        Args:
            context_name: Name of the context
            seed: Seed for this context (None for derived seed)

        Yields:
            int: Seed used for this context
        """
        context_seed = self.push_context(context_name, seed)
        try:
            yield context_seed
        finally:
            self.pop_context()

    def _generate_context_seed(self, context_name: str) -> int:
        """
        Generate a deterministic seed for a context.

        Args:
            context_name: Name of the context

        Returns:
            Generated seed
        """
        # Use hash of context name and parent seed
        parent_seed = (
            self._context_stack[-1]["seed"] if self._context_stack else self._base_seed
        )

        # Create deterministic seed from context name
        name_hash = hashlib.md5(f"{parent_seed}_{context_name}".encode(), usedforsecurity=False).hexdigest()
        return int(name_hash[:8], 16)  # Use first 8 hex characters as seed

    def get_current_context(self) -> Optional[Dict[str, Any]]:
        """Get the current context information."""
        return self._context_stack[-1] if self._context_stack else None

    def get_context_stack(self) -> List[Dict[str, Any]]:
        """Get the entire context stack."""
        return self._context_stack.copy()

    def get_environment_report(self) -> Dict[str, Any]:
        """Get environment report with context information."""
        report = self._environment.get_environment_report()
        report["context_stack"] = self.get_context_stack()
        report["current_context"] = self.get_current_context()
        return report
