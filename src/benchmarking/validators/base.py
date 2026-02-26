"""
Base classes for all validator types in the FBA-Bench benchmarking framework.

This module defines the abstract base `BaseValidator` class that all specific
validator implementations (e.g., deterministic, statistical) must inherit from.
It also includes the `ValidatorConfig` dataclass for configuring validators.
"""

import abc
from dataclasses import dataclass
from typing import Any, Dict

from ..core.validation import ValidationResult


@dataclass
class ValidatorConfig:
    """Configuration for a validator."""

    name: str
    description: str
    enabled: bool = True
    parameters: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class BaseValidator(abc.ABC):
    """
    Abstract base class for all validators.

    This class defines the interface that all validators must implement,
    including methods for validation logic and reporting.
    """

    def __init__(self, config: ValidatorConfig):
        """
        Initialize the validator.

        Args:
            config: Validator configuration
        """
        self.config = config

    @abc.abstractmethod
    def validate(self, data: Any, **kwargs) -> ValidationResult:
        """
        Perform validation on a given data set.

        Args:
            data: The data to validate. Can be any structure (e.g., simulation results, events).
            **kwargs: Additional parameters required for validation (e.g., golden master, schema).

        Returns:
            A ValidationResult object indicating if validation passed and any errors/warnings.
        """

    @abc.abstractmethod
    def get_validation_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive report of the validation process.

        Returns:
            A dictionary containing key metrics, findings, and summaries of the validation.
        """

    @abc.abstractmethod
    def reset(self) -> None:
        """
        Reset the validator's internal state (e.g., accumulated errors, metrics)
        for a new validation run.
        """
