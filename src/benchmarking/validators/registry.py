"""
Validator registries for managing available validators.

This module provides:
- A legacy class-based registry (ValidatorRegistry) to construct class validators
- A function-style registry (register_validator/get_validator/list_validators) that maps keys to callables
  with the interface validate(report: dict, context: dict|None=None) -> dict per the engine contract.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from .base import BaseValidator, ValidatorConfig

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Function-style registry (preferred by Engine)
# ------------------------------------------------------------------------------

_FN_REGISTRY: Dict[
    str, Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]
] = {}


def register_validator(
    key: str, fn: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]
) -> None:
    """
    Register a function-style validator.

    Interface requirement:
      fn(report: dict, context: dict|None=None) -> dict with keys:
        {"issues": list[dict], "summary": dict}
    """
    if not isinstance(key, str) or not key:
        raise ValueError("validator key must be a non-empty string")
    if not callable(fn):
        raise TypeError("validator must be callable")
    _FN_REGISTRY[key] = fn
    logger.debug(f"Registered function-style validator '{key}'")


def get_validator(
    key: str,
) -> Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]:
    """
    Lookup a function-style validator by key. Raises KeyError if not found.
    """
    if key not in _FN_REGISTRY:
        raise KeyError(f"validator_not_found: {key}")
    return _FN_REGISTRY[key]


def list_validators() -> List[str]:
    """
    List all registered function-style validator keys.
    """
    return sorted(_FN_REGISTRY.keys())


@dataclass
class ValidatorRegistration:
    """Information about a registered validator."""

    name: str
    description: str
    category: str
    validator_class: Type[BaseValidator]
    default_config: ValidatorConfig
    tags: List[str] = None  # type: ignore[assignment]
    enabled: bool = True

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class ValidatorRegistry:
    """
    Registry for managing available validators.

    This class provides a centralized way to register, discover, and instantiate
    validators. It supports dynamic registration and categorization of validators.
    """

    def __init__(self):
        """Initialize the legacy class-based validator registry."""
        self._validators: Dict[str, ValidatorRegistration] = {}
        self._categories: Dict[str, List[str]] = {}
        self._tags: Dict[str, List[str]] = {}
        # Legacy path no-op; function-style built-ins are auto-registered at module import below.

    def _register_builtin_validators(self) -> None:
        """Deprecated: kept for backward-compat with older code paths."""
        logger.debug("ValidatorRegistry._register_builtin_validators called (no-op).")

    def register_validator(
        self,
        name: str,
        description: str,
        category: str,
        validator_class: Type[BaseValidator],
        default_config: ValidatorConfig,
        tags: List[str] = None,
        enabled: bool = True,
    ) -> None:
        """
        Register a new validator.

        Args:
            name: Unique name for the validator
            description: Description of the validator
            category: Category of the validator
            validator_class: Class implementing the validator
            default_config: Default configuration for the validator
            tags: List of tags for categorization
            enabled: Whether the validator is enabled by default
        """
        if name in self._validators:
            logger.warning(f"Validator '{name}' already registered, overwriting")

        registration = ValidatorRegistration(
            name=name,
            description=description,
            category=category,
            validator_class=validator_class,
            default_config=default_config,
            tags=tags or [],
            enabled=enabled,
        )

        self._validators[name] = registration

        # Update category index
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)

        # Update tag index
        for tag in registration.tags:
            if tag not in self._tags:
                self._tags[tag] = []
            if name not in self._tags[tag]:
                self._tags[tag].append(name)

        logger.info(f"Registered validator: {name} (category: {category})")

    def unregister_validator(self, name: str) -> bool:
        """
        Unregister a validator.

        Args:
            name: Name of the validator to unregister

        Returns:
            True if successful, False if validator not found
        """
        if name not in self._validators:
            logger.warning(f"Validator '{name}' not found for unregistration")
            return False

        registration = self._validators[name]

        # Remove from category index
        category = registration.category
        if category in self._categories and name in self._categories[category]:
            self._categories[category].remove(name)
            if not self._categories[category]:
                del self._categories[category]

        # Remove from tag index
        for tag in registration.tags:
            if tag in self._tags and name in self._tags[tag]:
                self._tags[tag].remove(name)
                if not self._tags[tag]:
                    del self._tags[tag]

        # Remove from validators
        del self._validators[name]

        logger.info(f"Unregistered validator: {name}")
        return True

    def get_validator(self, name: str) -> Optional[ValidatorRegistration]:
        """
        Get a validator registration by name.

        Args:
            name: Name of the validator

        Returns:
            Validator registration or None if not found
        """
        return self._validators.get(name)

    def create_validator(
        self, name: str, config: ValidatorConfig = None
    ) -> Optional[BaseValidator]:
        """
        Create an instance of a validator.

        Args:
            name: Name of the validator
            config: Configuration for the validator (uses default if None)

        Returns:
            Validator instance or None if not found
        """
        registration = self.get_validator(name)
        if registration is None:
            logger.error(f"Validator '{name}' not found")
            return None

        if config is None:
            config = registration.default_config

        try:
            validator_instance = registration.validator_class(config)
            logger.debug(f"Created validator instance: {name}")
            return validator_instance
        except Exception as e:
            logger.error(f"Error creating validator '{name}': {e}")
            return None

    def list_validators(self, category: str = None, tag: str = None) -> List[str]:
        """
        List available validators.

        Args:
            category: Filter by category (optional)
            tag: Filter by tag (optional)

        Returns:
            List of validator names
        """
        if category is not None:
            return self._categories.get(category, []).copy()

        if tag is not None:
            return self._tags.get(tag, []).copy()

        return list(self._validators.keys())

    def list_categories(self) -> List[str]:
        """
        List all available categories.

        Returns:
            List of category names
        """
        return list(self._categories.keys())

    def list_tags(self) -> List[str]:
        """
        List all available tags.

        Returns:
            List of tag names
        """
        return list(self._tags.keys())

    def get_validators_by_category(
        self, category: str
    ) -> Dict[str, ValidatorRegistration]:
        """
        Get all validators in a specific category.

        Args:
            category: Category name

        Returns:
            Dictionary of validator registrations
        """
        if category not in self._categories:
            return {}

        return {
            name: self._validators[name]
            for name in self._categories[category]
            if name in self._validators
        }

    def get_validators_by_tag(self, tag: str) -> Dict[str, ValidatorRegistration]:
        """
        Get all validators with a specific tag.

        Args:
            tag: Tag name

        Returns:
            Dictionary of validator registrations
        """
        if tag not in self._tags:
            return {}

        return {
            name: self._validators[name]
            for name in self._tags[tag]
            if name in self._validators
        }

    def get_enabled_validators(self) -> Dict[str, ValidatorRegistration]:
        """
        Get all enabled validators.

        Returns:
            Dictionary of enabled validator registrations
        """
        return {
            name: registration
            for name, registration in self._validators.items()
            if registration.enabled
        }

    def enable_validator(self, name: str) -> bool:
        """
        Enable a validator.

        Args:
            name: Name of the validator

        Returns:
            True if successful, False if validator not found
        """
        if name not in self._validators:
            return False

        self._validators[name].enabled = True
        logger.info(f"Enabled validator: {name}")
        return True

    def disable_validator(self, name: str) -> bool:
        """
        Disable a validator.

        Args:
            name: Name of the validator

        Returns:
            True if successful, False if validator not found
        """
        if name not in self._validators:
            return False

        self._validators[name].enabled = False
        logger.info(f"Disabled validator: {name}")
        return True

    def get_validator_info(self, name: str) -> Dict[str, Any]:
        """
        Get detailed information about a validator.

        Args:
            name: Name of the validator

        Returns:
            Dictionary with validator information
        """
        registration = self.get_validator(name)
        if registration is None:
            return {"error": f"Validator '{name}' not found"}

        return {
            "name": registration.name,
            "description": registration.description,
            "category": registration.category,
            "class": registration.validator_class.__name__,
            "module": registration.validator_class.__module__,
            "default_config": {
                "name": registration.default_config.name,
                "description": registration.default_config.description,
                "enabled": registration.default_config.enabled,
            },
            "tags": registration.tags,
            "enabled": registration.enabled,
        }

    def create_validator_suite(
        self, validator_names: List[str], configs: Dict[str, ValidatorConfig] = None
    ) -> Dict[str, BaseValidator]:
        """
        Create a suite of validators.

        Args:
            validator_names: List of validator names to include
            configs: Custom configurations for validators (optional)

        Returns:
            Dictionary of validator instances
        """
        suite = {}
        configs = configs or {}

        for name in validator_names:
            config = configs.get(name)
            validator = self.create_validator(name, config)
            if validator is not None:
                suite[name] = validator

        return suite

    def validate_validator_config(
        self, name: str, config: ValidatorConfig
    ) -> List[str]:
        """
        Validate a validator configuration.

        Args:
            name: Name of the validator
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        registration = self.get_validator(name)
        if registration is None:
            errors.append(f"Unknown validator: {name}")
            return errors

        # Validate required fields
        if not config.name:
            errors.append("Validator name cannot be empty")

        if not config.description:
            errors.append("Validator description cannot be empty")

        return errors

    def get_registry_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the registry.

        Returns:
            Dictionary with registry summary
        """
        enabled_count = sum(1 for r in self._validators.values() if r.enabled)
        disabled_count = len(self._validators) - enabled_count

        return {
            "total_validators": len(self._validators),
            "enabled_validators": enabled_count,
            "disabled_validators": disabled_count,
            "categories": {
                category: len(validators)
                for category, validators in self._categories.items()
            },
            "tags": {tag: len(validators) for tag, validators in self._tags.items()},
        }


# Global registry instance
validator_registry = ValidatorRegistry()
# Auto-register built-in function-style validators on import
# Import modules that call register_validator(...) at import-time.
try:
    from . import (
        determinism_check,  # noqa: F401
        fairness_balance,  # noqa: F401
        outlier_detection,  # noqa: F401
        reproducibility_metadata,  # noqa: F401
        schema_adherence,  # noqa: F401
        structural_consistency,  # noqa: F401
    )
except Exception as _e:
    logger.debug(f"Built-in validators import failed or partial: {_e}")
