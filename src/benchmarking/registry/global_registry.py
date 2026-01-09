"""
Global Registry System for FBA-Bench.

This module provides a centralized registry system for managing all components
and configurations across the FBA-Bench application.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class RegistryType(str, Enum):
    """Types of registries available in the system."""

    AGENT = "agent"
    SCENARIO = "scenario"
    METRIC = "metric"
    CONFIG = "config"
    SERVICE = "service"
    TOOL = "tool"
    RUNNER = "runner"


@dataclass
class RegistryEntry:
    """Base class for registry entries."""

    name: str
    # entry_type is set by subclasses in their __post_init__, not at construction time.
    entry_type: RegistryType = field(init=False, default=RegistryType.SERVICE)
    description: str = ""
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True

    def __post_init__(self):
        """Validate the registry entry."""
        if not self.name:
            raise ValueError("Registry entry name cannot be empty")
        if not isinstance(self.entry_type, RegistryType):
            raise ValueError(f"Invalid registry type: {self.entry_type}")


@dataclass
class AgentRegistryEntry(RegistryEntry):
    """Registry entry for agents."""

    agent_class: Type[Any] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    framework: str = "unknown"

    def __post_init__(self):
        """Initialize the agent registry entry."""
        self.entry_type = RegistryType.AGENT
        super().__post_init__()


@dataclass
class ScenarioRegistryEntry(RegistryEntry):
    """Registry entry for scenarios."""

    scenario_class: Type[Any] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    duration_ticks: int = 100
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize the scenario registry entry."""
        self.entry_type = RegistryType.SCENARIO
        super().__post_init__()


@dataclass
class MetricRegistryEntry(RegistryEntry):
    """Registry entry for metrics."""

    metric_class: Type[Any] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize the metric registry entry."""
        self.entry_type = RegistryType.METRIC
        super().__post_init__()


@dataclass
class ServiceRegistryEntry(RegistryEntry):
    """Registry entry for services."""

    service_class: Type[Any] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    singleton: bool = True
    dependencies: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize the service registry entry."""
        self.entry_type = RegistryType.SERVICE
        super().__post_init__()


@dataclass
class ToolRegistryEntry(RegistryEntry):
    """Registry entry for tools."""

    tool_class: Type[Any] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize the tool registry entry."""
        self.entry_type = RegistryType.TOOL
        super().__post_init__()


@dataclass
class RunnerRegistryEntry(RegistryEntry):
    """Registry entry for runners."""

    runner_class: Type[Any] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    framework: str = "unknown"

    def __post_init__(self):
        """Initialize the runner registry entry."""
        self.entry_type = RegistryType.RUNNER
        super().__post_init__()


class GlobalRegistry:
    """
    Global registry for managing all components in FBA-Bench.

    This class provides a centralized way to register, discover, and manage
    all components used in the FBA-Bench system.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(GlobalRegistry, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the global registry."""
        if getattr(self, "_initialized", False):
            return

        # Registry storage
        self._entries: Dict[str, RegistryEntry] = {}
        self._type_index: Dict[RegistryType, Dict[str, str]] = {
            registry_type: {} for registry_type in RegistryType
        }
        self._tag_index: Dict[str, List[str]] = {}
        self._dependency_index: Dict[str, List[str]] = {}

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "on_register": [],
            "on_unregister": [],
            "on_update": [],
        }

        self._initialized = True
        logger.info("GlobalRegistry initialized")

    def register(self, entry: RegistryEntry) -> None:
        """
        Register a new entry in the global registry.

        Args:
            entry: The registry entry to register

        Raises:
            ValueError: If an entry with the same name already exists
        """
        if entry.name in self._entries:
            raise ValueError(f"Entry with name '{entry.name}' already registered")

        # Add to main storage
        self._entries[entry.name] = entry

        # Add to type index
        self._type_index[entry.entry_type][entry.name] = entry.name

        # Update tag index
        if hasattr(entry, "tags") and entry.tags:
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = []
                if entry.name not in self._tag_index[tag]:
                    self._tag_index[tag].append(entry.name)

        # Update dependency index
        if hasattr(entry, "dependencies") and entry.dependencies:
            for dep in entry.dependencies:
                if dep not in self._dependency_index:
                    self._dependency_index[dep] = []
                if entry.name not in self._dependency_index[dep]:
                    self._dependency_index[dep].append(entry.name)

        # Trigger event
        self._trigger_event("on_register", entry)

        logger.info("Registered %s entry: %s", entry.entry_type.value, entry.name)

    def unregister(self, name: str) -> bool:
        """
        Unregister an entry from the global registry.

        Args:
            name: The name of the entry to unregister

        Returns:
            True if successful, False if entry not found
        """
        if name not in self._entries:
            logger.warning("Entry '%s' not found for unregistration", name)
            return False

        entry = self._entries[name]

        # Remove from main storage
        del self._entries[name]

        # Remove from type index
        if entry.name in self._type_index[entry.entry_type]:
            del self._type_index[entry.entry_type][entry.name]

        # Remove from tag index
        if hasattr(entry, "tags") and entry.tags:
            for tag in entry.tags:
                if tag in self._tag_index and name in self._tag_index[tag]:
                    self._tag_index[tag].remove(name)
                    if not self._tag_index[tag]:
                        del self._tag_index[tag]

        # Remove from dependency index
        if hasattr(entry, "dependencies") and entry.dependencies:
            for dep in entry.dependencies:
                if (
                    dep in self._dependency_index
                    and name in self._dependency_index[dep]
                ):
                    self._dependency_index[dep].remove(name)
                    if not self._dependency_index[dep]:
                        del self._dependency_index[dep]

        # Trigger event
        self._trigger_event("on_unregister", entry)

        logger.info("Unregistered %s entry: %s", entry.entry_type.value, name)
        return True

    def get(self, name: str) -> Optional[RegistryEntry]:
        """
        Get an entry by name.

        Args:
            name: The name of the entry to retrieve

        Returns:
            The registry entry or None if not found
        """
        return self._entries.get(name)

    def get_by_type(self, entry_type: RegistryType) -> Dict[str, RegistryEntry]:
        """
        Get all entries of a specific type.

        Args:
            entry_type: The type of entries to retrieve

        Returns:
            Dictionary of registry entries
        """
        result = {}
        for name in self._type_index[entry_type]:
            result[name] = self._entries[name]
        return result

    def get_by_tag(self, tag: str) -> Dict[str, RegistryEntry]:
        """
        Get all entries with a specific tag.

        Args:
            tag: The tag to search for

        Returns:
            Dictionary of registry entries
        """
        result = {}
        if tag in self._tag_index:
            for name in self._tag_index[tag]:
                result[name] = self._entries[name]
        return result

    def get_dependents(self, name: str) -> List[str]:
        """
        Get all entries that depend on the specified entry.

        Args:
            name: The name of the entry to find dependents for

        Returns:
            List of entry names that depend on the specified entry
        """
        return self._dependency_index.get(name, []).copy()

    def list_names(self, entry_type: Optional[RegistryType] = None) -> List[str]:
        """
        List all entry names, optionally filtered by type.

        Args:
            entry_type: Optional filter by entry type

        Returns:
            List of entry names
        """
        if entry_type is None:
            return list(self._entries.keys())
        return list(self._type_index[entry_type].keys())

    def list_types(self) -> List[RegistryType]:
        """
        List all registry types that have entries.

        Returns:
            List of registry types
        """
        return [rt for rt in RegistryType if self._type_index[rt]]

    def list_tags(self) -> List[str]:
        """
        List all tags used in the registry.

        Returns:
            List of tags
        """
        return list(self._tag_index.keys())

    def update(self, name: str, **kwargs) -> bool:
        """
        Update an entry in the registry.

        Args:
            name: The name of the entry to update
            **kwargs: Fields to update

        Returns:
            True if successful, False if entry not found
        """
        if name not in self._entries:
            logger.warning(f"Entry '{name}' not found for update")
            return False

        entry = self._entries[name]

        # Update fields
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        # Update timestamp
        entry.updated_at = datetime.now()

        # Trigger event
        self._trigger_event("on_update", entry)

        logger.info("Updated entry: %s", name)
        return True

    def enable(self, name: str) -> bool:
        """
        Enable an entry in the registry.

        Args:
            name: The name of the entry to enable

        Returns:
            True if successful, False if entry not found
        """
        return self.update(name, enabled=True)

    def disable(self, name: str) -> bool:
        """
        Disable an entry in the registry.

        Args:
            name: The name of the entry to disable

        Returns:
            True if successful, False if entry not found
        """
        return self.update(name, enabled=False)

    def add_event_handler(self, event: str, handler: Callable) -> None:
        """
        Add an event handler.

        Args:
            event: The event type ("on_register", "on_unregister", "on_update")
            handler: The handler function
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)
        else:
            raise ValueError(f"Unknown event type: {event}")

    def remove_event_handler(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: The event type
            handler: The handler function to remove
        """
        if event in self._event_handlers:
            try:
                self._event_handlers[event].remove(handler)
            except ValueError:
                # Handler not found, ignore
                pass

    def _trigger_event(self, event: str, entry: RegistryEntry) -> None:
        """
        Trigger an event.

        Args:
            event: The event type
            entry: The registry entry
        """
        for handler in self._event_handlers.get(event, []):
            try:
                handler(entry)
            except Exception as e:
                logger.error("Error in event handler for %s: %s", event, e)

    def get_registry_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the registry.

        Returns:
            Dictionary with registry summary
        """
        summary = {
            "total_entries": len(self._entries),
            "entries_by_type": {
                rt.value: len(self._type_index[rt]) for rt in RegistryType
            },
            "total_tags": len(self._tag_index),
            "enabled_entries": sum(1 for e in self._entries.values() if e.enabled),
            "disabled_entries": sum(1 for e in self._entries.values() if not e.enabled),
        }

        return summary

    def clear(self) -> None:
        """Clear all entries from the registry."""
        self._entries.clear()
        for index in self._type_index.values():
            index.clear()
        self._tag_index.clear()
        self._dependency_index.clear()
        logger.info("GlobalRegistry cleared")

    def export_registry(self) -> Dict[str, Any]:
        """
        Export the registry to a dictionary.

        Returns:
            Dictionary representation of the registry
        """
        export_data = {
            "entries": {},
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "total_entries": len(self._entries),
            },
        }

        for name, entry in self._entries.items():
            entry_data = {
                "name": entry.name,
                "entry_type": entry.entry_type.value,
                "description": entry.description,
                "version": entry.version,
                "metadata": entry.metadata,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat(),
                "enabled": entry.enabled,
            }

            # Add type-specific fields
            if isinstance(entry, AgentRegistryEntry):
                entry_data.update(
                    {
                        "framework": entry.framework,
                        "capabilities": entry.capabilities,
                        "config_schema": entry.config_schema,
                    }
                )
            elif isinstance(entry, ScenarioRegistryEntry):
                entry_data.update(
                    {
                        "duration_ticks": entry.duration_ticks,
                        "dependencies": entry.dependencies,
                        "config_schema": entry.config_schema,
                    }
                )
            elif isinstance(entry, MetricRegistryEntry):
                entry_data.update(
                    {
                        "category": entry.category,
                        "tags": entry.tags,
                        "config_schema": entry.config_schema,
                    }
                )
            elif isinstance(entry, ServiceRegistryEntry):
                entry_data.update(
                    {
                        "singleton": entry.singleton,
                        "dependencies": entry.dependencies,
                        "config_schema": entry.config_schema,
                    }
                )
            elif isinstance(entry, ToolRegistryEntry):
                entry_data.update(
                    {
                        "input_schema": entry.input_schema,
                        "output_schema": entry.output_schema,
                        "config_schema": entry.config_schema,
                    }
                )
            elif isinstance(entry, RunnerRegistryEntry):
                entry_data.update(
                    {"framework": entry.framework, "config_schema": entry.config_schema}
                )

            export_data["entries"][name] = entry_data

        return export_data

    def import_registry(self, data: Dict[str, Any]) -> None:
        """
        Import registry data from a dictionary.

        Args:
            data: Dictionary containing registry data
        """
        # Clear existing registry
        self.clear()

        # Import entries
        for _, entry_data in data.get("entries", {}).items():
            entry_type = RegistryType(entry_data["entry_type"])

            # Create appropriate entry type
            if entry_type == RegistryType.AGENT:
                entry = AgentRegistryEntry(
                    name=entry_data["name"],
                    description=entry_data.get("description", ""),
                    version=entry_data.get("version", "1.0.0"),
                    metadata=entry_data.get("metadata", {}),
                    enabled=entry_data.get("enabled", True),
                    framework=entry_data.get("framework", "unknown"),
                    capabilities=entry_data.get("capabilities", []),
                    config_schema=entry_data.get("config_schema", {}),
                )
            elif entry_type == RegistryType.SCENARIO:
                entry = ScenarioRegistryEntry(
                    name=entry_data["name"],
                    description=entry_data.get("description", ""),
                    version=entry_data.get("version", "1.0.0"),
                    metadata=entry_data.get("metadata", {}),
                    enabled=entry_data.get("enabled", True),
                    duration_ticks=entry_data.get("duration_ticks", 100),
                    dependencies=entry_data.get("dependencies", []),
                    config_schema=entry_data.get("config_schema", {}),
                )
            elif entry_type == RegistryType.METRIC:
                entry = MetricRegistryEntry(
                    name=entry_data["name"],
                    description=entry_data.get("description", ""),
                    version=entry_data.get("version", "1.0.0"),
                    metadata=entry_data.get("metadata", {}),
                    enabled=entry_data.get("enabled", True),
                    category=entry_data.get("category", "general"),
                    tags=entry_data.get("tags", []),
                    config_schema=entry_data.get("config_schema", {}),
                )
            elif entry_type == RegistryType.SERVICE:
                entry = ServiceRegistryEntry(
                    name=entry_data["name"],
                    description=entry_data.get("description", ""),
                    version=entry_data.get("version", "1.0.0"),
                    metadata=entry_data.get("metadata", {}),
                    enabled=entry_data.get("enabled", True),
                    singleton=entry_data.get("singleton", True),
                    dependencies=entry_data.get("dependencies", []),
                    config_schema=entry_data.get("config_schema", {}),
                )
            elif entry_type == RegistryType.TOOL:
                entry = ToolRegistryEntry(
                    name=entry_data["name"],
                    description=entry_data.get("description", ""),
                    version=entry_data.get("version", "1.0.0"),
                    metadata=entry_data.get("metadata", {}),
                    enabled=entry_data.get("enabled", True),
                    input_schema=entry_data.get("input_schema", {}),
                    output_schema=entry_data.get("output_schema", {}),
                    config_schema=entry_data.get("config_schema", {}),
                )
            elif entry_type == RegistryType.RUNNER:
                entry = RunnerRegistryEntry(
                    name=entry_data["name"],
                    description=entry_data.get("description", ""),
                    version=entry_data.get("version", "1.0.0"),
                    metadata=entry_data.get("metadata", {}),
                    enabled=entry_data.get("enabled", True),
                    framework=entry_data.get("framework", "unknown"),
                    config_schema=entry_data.get("config_schema", {}),
                )
            else:
                logger.warning("Unknown entry type: %s", entry_type)
                continue

            # Set timestamps
            entry.created_at = datetime.fromisoformat(entry_data["created_at"])
            entry.updated_at = datetime.fromisoformat(entry_data["updated_at"])

            # Register the entry
            self.register(entry)

        logger.info(
            "Imported %d entries into GlobalRegistry", len(data.get('entries', {}))
        )


# Lazy global instance of the registry to avoid import-time side effects
from typing import Optional as _Optional  # local alias to avoid polluting exports

_global_registry: _Optional[GlobalRegistry] = None


def get_global_registry() -> GlobalRegistry:
    """
    Lazy initializer returning a singleton GlobalRegistry.
    Avoids import-time side effects during package installation or test discovery.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = GlobalRegistry()
    return _global_registry


class _LazyGlobalRegistry:
    """
    Backward-compatible proxy that defers instantiation until an attribute is used.
    Importers can continue to use `from benchmarking.registry.global_registry import global_registry`
    without triggering work at import time.
    """

    def __getattr__(self, name):
        return getattr(get_global_registry(), name)


# Backward-compatible proxy
global_registry = _LazyGlobalRegistry()
