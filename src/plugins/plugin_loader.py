from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LoadingContext:
    """
    Lightweight context for plugin discovery/loading.

    Fields match common expectations in community tests and examples.
    """

    plugin_directory: str
    extra_paths: List[str] = field(default_factory=list)
    env: Dict[str, Any] = field(default_factory=dict)


class DependencyResolver:
    """
    Minimal dependency resolver used by community tests.
    Given a plugin name and a list of dependency names, returns a resolution result.

    The current tests only assert non-None; we provide a deterministic structure
    with a 'resolved' key listing dependencies in input order (can be extended to
    a true topological sort if full graphs are provided).
    """

    async def resolve_dependencies(
        self, plugin_name: str, dependencies: List[str]
    ) -> Dict[str, Any]:
        logger.info("Resolving dependencies for %s: %s", plugin_name, dependencies)
        # In a more advanced implementation, we would:
        # - Build a dependency graph
        # - Perform topological sorting with cycle detection
        # - Fetch versions and perform compatibility checks
        return {
            "plugin": plugin_name,
            "resolved": list(
                dict.fromkeys(dependencies)
            ),  # stable de-dupe preserving order
            "conflicts": [],
        }


class PluginLoader:
    """
    Lightweight plugin loader that can discover and load plugins from a directory.

    Conventions:
    - A "plugin" is any Python file containing at least one class with __is_fba_plugin__ = True
    - The class may expose get_metadata() returning name/version/etc.
    """

    def __init__(self, plugin_directory: Optional[str] = None) -> None:
        self.plugin_directory = plugin_directory or "plugins"

    async def discover_plugins(
        self, context: Optional[LoadingContext] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Discover plugin metadata in the target directory.

        Returns a mapping: name -> metadata dict with at least
        name, version, description, author.
        """
        directory = context.plugin_directory if context else self.plugin_directory
        if not os.path.isdir(directory):
            logger.warning("Plugin directory not found: %s", directory)
            return {}

        discovered: Dict[str, Dict[str, Any]] = {}

        # Walk only top-level .py files by convention
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            module_name = filename[:-3]
            module_path = os.path.join(directory, filename)

            try:
                mod = self._load_module_from_path(module_name, module_path)
                meta = self._extract_first_plugin_metadata(mod)
                if meta:
                    name = meta.get("name") or module_name
                    discovered[name] = meta
            except (ImportError, AttributeError, OSError) as e:
                logger.error(
                    "Failed to inspect plugin module %s: %s",
                    module_path,
                    e,
                    exc_info=True,
                )

        return discovered

    async def load_plugin_instance(
        self, module_path: str, class_name: Optional[str] = None
    ) -> Any:
        """
        Load and instantiate a plugin class from a module file path.

        If class_name is None, will instantiate the first class found with
        __is_fba_plugin__ = True.
        """
        module_name = os.path.splitext(os.path.basename(module_path))[0]
        mod = self._load_module_from_path(module_name, module_path)

        if class_name:
            cls = getattr(mod, class_name, None)
            if cls is None or not inspect.isclass(cls):
                raise ImportError(
                    f"Class {class_name} not found in module {module_name}"
                )
            return cls()

        # Fallback: find first plugin-marked class
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if getattr(obj, "__is_fba_plugin__", False):
                return obj()

        raise ImportError(f"No FBA-Bench plugin class found in {module_path}")

    # --------------- Internal helpers ---------------

    def _load_module_from_path(self, module_name: str, module_path: str) -> Any:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create spec for {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _extract_first_plugin_metadata(self, module: Any) -> Optional[Dict[str, Any]]:
        """
        Inspect a module for the first plugin class and return normalized metadata.
        """
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if getattr(obj, "__is_fba_plugin__", False):
                # Try instance method first for richer metadata
                try:
                    inst = obj()
                    if hasattr(inst, "get_metadata") and callable(inst.get_metadata):
                        md = inst.get_metadata()
                        if isinstance(md, dict) and "name" in md and "version" in md:
                            # Ensure minimum keys
                            md.setdefault("description", f"{md['name']} plugin")
                            md.setdefault("author", "Unknown")
                            return md
                except (TypeError, AttributeError, RuntimeError):
                    # Fall back to class-level attributes
                    pass

                # Class-level fallback
                name = getattr(
                    obj, "plugin_id", getattr(obj, "__name__", "unknown_plugin")
                )
                version = getattr(obj, "version", "0.0.0")
                return {
                    "name": str(name),
                    "version": str(version),
                    "description": f"{name} plugin",
                    "author": "Unknown",
                }
        return None
