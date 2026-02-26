"""
Configuration Schema Manager for FBA-Bench.

This module provides a centralized way to manage configuration schemas
for all components in the FBA-Bench system.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

from ..registry.global_registry import GlobalRegistry, RegistryType
from .pydantic_config import (
    AgentConfig,
    BaseConfig,
    BenchmarkConfig,
    CrewConfig,
    ExecutionConfig,
    LLMConfig,
    MemoryConfig,
    MetricsCollectionConfig,
    ScenarioConfig,
)

logger = logging.getLogger(__name__)


class SchemaValidationError(Exception):
    """Exception raised when schema validation fails."""


class SchemaManager:
    """
    Manager for configuration schemas in FBA-Bench.

    This class provides a centralized way to register, validate, and manage
    configuration schemas for all components in the system.
    """

    def __init__(self, registry: Optional[GlobalRegistry] = None):
        """
        Initialize the schema manager.

        Args:
            registry: Global registry instance (uses global instance if None)
        """
        self.registry = registry or GlobalRegistry()
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._validator_cache: Dict[str, Any] = {}

        # Register built-in schemas
        self._register_builtin_schemas()

        logger.info("SchemaManager initialized")

    def _register_builtin_schemas(self) -> None:
        """Register all built-in configuration schemas."""
        # Register LLMConfig schema
        self.register_schema(
            name="llm_config",
            schema_class=LLMConfig,
            description="LLM configuration schema",
            category="llm",
            tags=["llm", "configuration", "model"],
        )

        # Register AgentConfig schema
        self.register_schema(
            name="agent_config",
            schema_class=AgentConfig,
            description="Agent configuration schema",
            category="agent",
            tags=["agent", "configuration"],
        )

        # Register MemoryConfig schema
        self.register_schema(
            name="memory_config",
            schema_class=MemoryConfig,
            description="Memory configuration schema",
            category="memory",
            tags=["memory", "configuration"],
        )

        # Register CrewConfig schema
        self.register_schema(
            name="crew_config",
            schema_class=CrewConfig,
            description="Crew configuration schema",
            category="crew",
            tags=["crew", "configuration", "crewai"],
        )

        # Register ExecutionConfig schema
        self.register_schema(
            name="execution_config",
            schema_class=ExecutionConfig,
            description="Execution configuration schema",
            category="execution",
            tags=["execution", "configuration"],
        )

        # Register MetricsCollectionConfig schema
        self.register_schema(
            name="metrics_config",
            schema_class=MetricsCollectionConfig,
            description="Metrics collection configuration schema",
            category="metrics",
            tags=["metrics", "configuration"],
        )

        # Register ScenarioConfig schema
        self.register_schema(
            name="scenario_config",
            schema_class=ScenarioConfig,
            description="Scenario configuration schema",
            category="scenario",
            tags=["scenario", "configuration"],
        )

        # Register BenchmarkConfig schema
        self.register_schema(
            name="benchmark_config",
            schema_class=BenchmarkConfig,
            description="Benchmark configuration schema",
            category="benchmark",
            tags=["benchmark", "configuration"],
        )

        logger.info("Registered built-in configuration schemas")

    def register_schema(
        self,
        name: str,
        schema_class: Type[BaseConfig],
        description: str = "",
        category: str = "general",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Register a configuration schema.

        Args:
            name: Unique name for the schema
            schema_class: Pydantic model class for the schema
            description: Description of the schema
            category: Category of the schema
            tags: List of tags for the schema
            metadata: Additional metadata for the schema

        Raises:
            ValueError: If schema name is already registered
        """
        if name in self._schema_cache:
            raise ValueError(f"Schema '{name}' is already registered")

        # Generate JSON schema from Pydantic model
        json_schema = schema_class.model_json_schema()

        # Store in cache
        self._schema_cache[name] = {
            "class": schema_class,
            "json_schema": json_schema,
            "description": description,
            "category": category,
            "tags": tags or [],
            "metadata": metadata or {},
            "registered_at": datetime.now(),
        }

        # Register in global registry (idempotent)
        from ..registry.global_registry import ServiceRegistryEntry

        reg_name = f"config_schema_{name}"
        existing = self.registry.get(reg_name)
        if existing:
            # Update existing entry metadata and timestamps without re-registering
            self.registry.update(
                reg_name,
                description=f"Configuration schema: {description}",
                metadata={
                    "schema_name": name,
                    "schema_class": schema_class.__name__,
                    "category": category,
                    "tags": tags or [],
                    "metadata": metadata or {},
                },
            )
            logger.info(f"Updated configuration schema in registry: {name}")
        else:
            entry = ServiceRegistryEntry(
                name=reg_name,
                description=f"Configuration schema: {description}",
                metadata={
                    "schema_name": name,
                    "schema_class": schema_class.__name__,
                    "category": category,
                    "tags": tags or [],
                    "metadata": metadata or {},
                },
            )
            self.registry.register(entry)
            logger.info(f"Registered configuration schema: {name}")

    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a configuration schema by name.

        Args:
            name: Name of the schema

        Returns:
            Schema dictionary or None if not found
        """
        return self._schema_cache.get(name)

    def get_schema_class(self, name: str) -> Optional[Type[BaseConfig]]:
        """
        Get a configuration schema class by name.

        Args:
            name: Name of the schema

        Returns:
            Schema class or None if not found
        """
        schema_info = self._schema_cache.get(name)
        return schema_info["class"] if schema_info else None

    def get_json_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a JSON schema by name.

        Args:
            name: Name of the schema

        Returns:
            JSON schema dictionary or None if not found
        """
        schema_info = self._schema_cache.get(name)
        return schema_info["json_schema"] if schema_info else None

    def list_schemas(self, category: Optional[str] = None) -> List[str]:
        """
        List all registered schema names.

        Args:
            category: Optional filter by category

        Returns:
            List of schema names
        """
        if category is None:
            return list(self._schema_cache.keys())

        return [
            name
            for name, info in self._schema_cache.items()
            if info["category"] == category
        ]

    def list_categories(self) -> List[str]:
        """
        List all schema categories.

        Returns:
            List of categories
        """
        categories = set()
        for info in self._schema_cache.values():
            categories.add(info["category"])
        return sorted(list(categories))

    def validate_config(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a configuration against a schema.

        Args:
            name: Name of the schema to validate against
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary

        Raises:
            SchemaValidationError: If validation fails
        """
        schema_info = self._schema_cache.get(name)
        if not schema_info:
            raise SchemaValidationError(f"Schema '{name}' not found")

        schema_class = schema_info["class"]

        try:
            # Validate and create config object
            config_obj = schema_class(**config)

            # Convert back to dictionary
            validated_config = config_obj.model_dump()

            logger.debug(f"Validated configuration against schema '{name}'")
            return validated_config

        except Exception as e:
            raise SchemaValidationError(
                f"Configuration validation failed for schema '{name}': {e}"
            ) from e

    def create_config(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Create a configuration using a schema with default values.

        Args:
            name: Name of the schema to use
            **kwargs: Override values for the configuration

        Returns:
            Configuration dictionary

        Raises:
            SchemaValidationError: If schema not found or creation fails
        """
        schema_info = self._schema_cache.get(name)
        if not schema_info:
            raise SchemaValidationError(f"Schema '{name}' not found")

        schema_class = schema_info["class"]

        try:
            # Create config object with provided kwargs
            config_obj = schema_class(**kwargs)

            # Convert to dictionary
            config_dict = config_obj.model_dump()

            logger.debug(f"Created configuration using schema '{name}'")
            return config_dict

        except Exception as e:
            raise SchemaValidationError(
                f"Configuration creation failed for schema '{name}': {e}"
            ) from e

    def merge_configs(self, name: str, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configurations using a schema.

        Args:
            name: Name of the schema to use for validation
            *configs: Configuration dictionaries to merge

        Returns:
            Merged configuration dictionary

        Raises:
            SchemaValidationError: If schema not found or merge fails
        """
        if not configs:
            return self.create_config(name)

        # Start with an empty config
        merged_config = {}

        # Merge configs in order (later configs override earlier ones)
        for config in configs:
            if isinstance(config, dict):
                merged_config.update(config)

        # Validate the merged config
        return self.validate_config(name, merged_config)

    def export_schemas(self, output_path: Union[str, Path]) -> None:
        """
        Export all schemas to a JSON file.

        Args:
            output_path: Path to the output JSON file
        """
        output_path = Path(output_path)

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_schemas": len(self._schema_cache),
            "schemas": {},
        }

        for name, schema_info in self._schema_cache.items():
            export_data["schemas"][name] = {  # type: ignore[index]
                "description": schema_info["description"],
                "category": schema_info["category"],
                "tags": schema_info["tags"],
                "metadata": schema_info["metadata"],
                "json_schema": schema_info["json_schema"],
                "registered_at": schema_info["registered_at"].isoformat(),
            }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported {len(self._schema_cache)} schemas to {output_path}")

    def import_schemas(self, input_path: Union[str, Path]) -> None:
        """
        Import schemas from a JSON file.

        Args:
            input_path: Path to the input JSON file
        """
        input_path = Path(input_path)

        with open(input_path) as f:
            import_data = json.load(f)

        imported_count = 0
        for name, schema_data in import_data.get("schemas", {}).items():
            # Note: We can't import the actual schema class from JSON,
            # so we just store the JSON schema for reference
            self._schema_cache[name] = {
                "json_schema": schema_data["json_schema"],
                "description": schema_data["description"],
                "category": schema_data["category"],
                "tags": schema_data["tags"],
                "metadata": schema_data["metadata"],
                "registered_at": datetime.fromisoformat(schema_data["registered_at"]),
                "class": None,  # Class not available in import
            }
            imported_count += 1

        logger.info(f"Imported {imported_count} schemas from {input_path}")

    def get_schema_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a schema.

        Args:
            name: Name of the schema

        Returns:
            Schema information dictionary or None if not found
        """
        schema_info = self._schema_cache.get(name)
        if not schema_info:
            return None

        return {
            "name": name,
            "description": schema_info["description"],
            "category": schema_info["category"],
            "tags": schema_info["tags"],
            "metadata": schema_info["metadata"],
            "has_class": schema_info["class"] is not None,
            "registered_at": schema_info["registered_at"].isoformat(),
        }

    def get_schemas_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all schemas in a specific category.

        Args:
            category: Category name

        Returns:
            Dictionary of schema information
        """
        result = {}
        for name, schema_info in self._schema_cache.items():
            if schema_info["category"] == category:
                result[name] = self.get_schema_info(name)
        return result  # type: ignore[return-value]

    def get_schemas_by_tag(self, tag: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all schemas with a specific tag.

        Args:
            tag: Tag name

        Returns:
            Dictionary of schema information
        """
        result = {}
        for name, schema_info in self._schema_cache.items():
            if tag in schema_info["tags"]:
                result[name] = self.get_schema_info(name)
        return result  # type: ignore[return-value]

    def unregister_schema(self, name: str) -> bool:
        """
        Unregister a schema.

        Args:
            name: Name of the schema to unregister

        Returns:
            True if successful, False if schema not found
        """
        if name not in self._schema_cache:
            logger.warning(f"Schema '{name}' not found for unregistration")
            return False

        # Remove from cache
        del self._schema_cache[name]

        # Remove from validator cache if present
        if name in self._validator_cache:
            del self._validator_cache[name]

        # Remove from global registry
        registry_name = f"config_schema_{name}"
        self.registry.unregister(registry_name)

        logger.info(f"Unregistered configuration schema: {name}")
        return True

    def clear(self) -> None:
        """Clear all registered schemas."""
        self._schema_cache.clear()
        self._validator_cache.clear()

        # Remove from global registry
        for name in list(self.registry.list_names(RegistryType.SERVICE)):
            if name.startswith("config_schema_"):
                self.registry.unregister(name)

        logger.info("Cleared all configuration schemas")

    def get_manager_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the schema manager.

        Returns:
            Dictionary with manager summary
        """
        categories = {}
        for info in self._schema_cache.values():
            category = info["category"]
            if category not in categories:
                categories[category] = 0
            categories[category] += 1

        return {
            "total_schemas": len(self._schema_cache),
            "categories": categories,
            "total_categories": len(categories),
            "schemas_with_classes": sum(
                1 for info in self._schema_cache.values() if info["class"] is not None
            ),
        }


# Lazy global instance of the schema manager to avoid import-time side effects
_schema_manager: Optional[SchemaManager] = None


def get_schema_manager(registry: Optional[GlobalRegistry] = None) -> SchemaManager:
    """
    Lazy initializer returning a singleton SchemaManager.
    Avoids import-time side effects during package installation or test discovery.
    """
    global _schema_manager
    if _schema_manager is None:
        _schema_manager = SchemaManager(registry=registry)
    return _schema_manager


class _LazySchemaManager:
    """
    Backward-compatible proxy that defers instantiation until an attribute is used.
    Importers can continue to use `from benchmarking.config.schema_manager import schema_manager`
    without triggering work at import time.
    """

    def __getattr__(self, name):
        return getattr(get_schema_manager(), name)


# Backward-compatible proxy
schema_manager = _LazySchemaManager()
