import importlib
import importlib.util
import inspect
import logging
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

# Guard the optional dependency used in older examples
try:
    from benchmarking.agents.registry import agent_registry
except ImportError:  # pragma: no cover - optional
    agent_registry = None  # Fallback; only used if plugins expose register_agents()

logger = logging.getLogger(__name__)


class PluginError(Exception):
    """Custom exception for plugin-related errors."""


class PluginInterface(Protocol):
    """Protocol for general plugins."""

    def initialize(self, config: Dict[str, Any]) -> Any: ...

    def get_plugin_info(self) -> Dict[str, Any]: ...


class PluginType(Enum):
    """Canonical plugin types used by tests/community tooling."""

    SKILL = "skill"
    ANALYSIS = "analysis"
    INTEGRATION = "integration"
    SCENARIO = "scenario"
    AGENT = "agent"
    TOOL = "tool"
    METRIC = "metric"


class PluginStatus(Enum):
    """High-level plugin status values for reporting."""

    REGISTERED = "registered"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class PluginFramework:
    """
    Unified plugin framework that supports:
    - Unit test API (register_plugin_type, register_plugin, resolve dependencies, execute_plugin, etc.)
    - Community/extensibility async API (initialize, register/activate/deactivate plugins by name, discovery, etc.)
    """

    # ---------- Core lifecycle ----------
    def __init__(
        self,
        plugin_directory: Optional[str] = None,
        enable_security_validation: bool = False,
        enable_dependency_resolution: bool = True,
    ) -> None:
        # Unit-test API backing stores
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._plugin_types: Dict[str, Dict[str, Any]] = {}
        self._plugin_dependencies: Dict[str, List[str]] = {}
        self._loaded_plugins: Dict[str, Any] = {}

        # Community API state
        self._registered_named_plugins: Dict[str, Any] = (
            {}
        )  # name -> plugin object (with async lifecycle)
        self._active_plugins: Set[str] = set()

        # Options
        self.plugin_directory = plugin_directory or "plugins"
        self.enable_security_validation = enable_security_validation
        self.enable_dependency_resolution = enable_dependency_resolution

        # Extension points (optional hook system)
        self._extension_points: Dict[str, Callable] = {}
        self._plugin_versions: Dict[str, str] = {}
        logger.info("PluginFramework initialized.")

    async def initialize(self) -> bool:
        """Async initialization for community tests."""
        # Could scan directories or perform warm-up here
        return True

    async def cleanup(self) -> None:
        """Async cleanup for community tests."""
        # Deactivate all
        for name in list(self._active_plugins):
            try:
                await self.deactivate_plugin(name)
            except (PluginError, RuntimeError, AttributeError):
                pass

    # ---------- Unit test API ----------
    def register_plugin_type(self, plugin_type: Dict[str, Any]) -> str:
        """
        Register a plugin type. Expects dict with keys: name, description, base_class, interface
        Returns a generated type_id.
        """
        type_id = (
            f"type_{plugin_type.get('name', str(uuid.uuid4()))}_{uuid.uuid4().hex[:8]}"
        )
        self._plugin_types[type_id] = dict(plugin_type)
        return type_id

    def register_plugin(self, plugin: Dict[str, Any]) -> str:
        """
        Register a plugin (metadata only). Expects dict with keys:
        name, description, version, type (type_id), module_path, class_name, config, dependencies
        Returns a generated plugin_id.
        """
        plugin_id = f"plugin_{plugin.get('name', 'unnamed')}_{uuid.uuid4().hex[:8]}"
        normalized = dict(plugin)
        normalized.setdefault("dependencies", [])
        self._plugins[plugin_id] = normalized
        self._plugin_dependencies[plugin_id] = list(normalized["dependencies"])
        return plugin_id

    def unregister_plugin(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)
        self._plugin_dependencies.pop(plugin_id, None)
        # If loaded, unload too
        if plugin_id in self._loaded_plugins:
            try:
                self.unload_plugin(plugin_id)
            except (PluginError, RuntimeError, AttributeError):
                pass

    def _load_plugin_module(self, plugin_id: str) -> Any:
        """Load and instantiate the plugin class given its registration."""
        meta = self._plugins.get(plugin_id)
        if not meta:
            raise PluginError(f"Plugin {plugin_id} not registered")

        module_path = meta.get("module_path")
        class_name = meta.get("class_name")
        if not module_path or not class_name:
            raise PluginError(f"Plugin {plugin_id} missing module_path/class_name")

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is None:
            raise PluginError(f"Class {class_name} not found in {module_path}")

        # Prefer passing 'config' if constructor supports it; otherwise fall back to no-arg.
        instance: Any = None
        cfg = meta.get("config", None)
        if isinstance(cfg, dict):
            try:
                instance = cls(config=cfg)
            except TypeError:
                # Constructor doesn't accept 'config', try no-arg
                instance = None

        if instance is None:
            try:
                instance = cls()
            except TypeError as e:
                raise PluginError(
                    f"Failed to instantiate {class_name} from {module_path}: {e}"
                )

        return instance

    def load_plugin(self, plugin_id: str) -> Any:
        """Instantiate and memoize plugin instance."""
        instance = self._load_plugin_module(plugin_id)
        self._loaded_plugins[plugin_id] = instance
        return instance

    def unload_plugin(self, plugin_id: str) -> None:
        instance = self._loaded_plugins.pop(plugin_id, None)
        if instance and hasattr(instance, "cleanup") and callable(instance.cleanup):
            try:
                instance.cleanup()
            except (AttributeError, RuntimeError):
                logger.warning("Cleanup raised but was ignored", exc_info=True)

    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        return self._plugins.get(plugin_id)

    def get_plugins_by_type(self, type_id_or_name: str) -> List[Dict[str, Any]]:
        """
        Supports both unit-test usage (type_id) and community usage (type name).
        If a type_id matches, filter by that. Otherwise treat as name (e.g., 'scenario', 'agent').
        """
        # Try type_id
        if type_id_or_name in self._plugin_types:
            tid = type_id_or_name
            return [p for p in self._plugins.values() if p.get("type") == tid]

        # Fallback by name
        type_name = type_id_or_name.lower()
        # Attempt to find the first matching type_id by name
        selected_type_ids = [
            tid
            for tid, td in self._plugin_types.items()
            if td.get("name", "").lower() == type_name
        ]
        if selected_type_ids:
            return [
                p for p in self._plugins.values() if p.get("type") in selected_type_ids
            ]

        return []

    def resolve_plugin_dependencies(self, plugin_ids: List[str]) -> List[str]:
        """Topological sort based on declared dependencies within the provided set."""
        deps = {pid: set(self._plugin_dependencies.get(pid, [])) for pid in plugin_ids}
        resolved: List[str] = []
        while deps:
            ready = [pid for pid, ds in deps.items() if not ds]
            if not ready:
                # Cycle or missing dependency; break deterministically
                raise PluginError("Cyclic or unresolved dependencies detected")
            for pid in ready:
                resolved.append(pid)
                deps.pop(pid, None)
            for ds in deps.values():
                ds.difference_update(ready)
        return resolved

    def execute_plugin(self, plugin_id: str, input_data: Dict[str, Any]) -> Any:
        instance = self._loaded_plugins.get(plugin_id)
        if not instance:
            raise PluginError(f"Plugin {plugin_id} not loaded")
        if not hasattr(instance, "execute") or not callable(instance.execute):
            raise PluginError(f"Plugin {plugin_id} has no executable interface")
        return instance.execute(input_data)

    def get_plugin_status(self, plugin_id: str) -> str:
        if plugin_id in self._loaded_plugins:
            return PluginStatus.LOADED.value
        if plugin_id in self._plugins:
            return PluginStatus.REGISTERED.value
        return PluginStatus.ERROR.value

    # ---------- Community/extensibility async API (by name) ----------
    async def register_named_plugin(self, plugin_obj: Any) -> bool:
        """
        Register a runtime plugin object (community/extensibility API).
        Expected attributes on plugin_obj:
          - name: str
          - plugin_type: PluginType (or compatible)
          - version: str
        """
        name = getattr(plugin_obj, "name", None)
        version = getattr(plugin_obj, "version", None)
        if not isinstance(name, str) or not name:
            raise PluginError("Plugin object must have a valid 'name'")
        if not isinstance(version, str) or not version:
            raise PluginError("Plugin object must have a valid 'version'")

        # Perform a very light security validation when enabled
        if self.enable_security_validation:
            try:
                module = inspect.getmodule(plugin_obj.__class__)
                if module and not await self._validate_plugin_module_security(module):
                    return False
            except (OSError, SyntaxError, AttributeError):
                # Conservative default: allow if validation can't run
                pass

        self._registered_named_plugins[name] = plugin_obj
        return True

    # Backwards-compatible async alias for external callers that prefer explicit naming
    async def register_plugin_async(self, plugin_obj: Any) -> bool:
        return await self.register_named_plugin(plugin_obj)

    async def activate_plugin(self, name: str) -> bool:
        plugin = self._registered_named_plugins.get(name)
        if not plugin:
            return False
        if hasattr(plugin, "activate") and inspect.iscoroutinefunction(plugin.activate):
            ok = await plugin.activate()
            if ok:
                self._active_plugins.add(name)
            return ok
        # If no explicit activate, consider it active after initialize
        self._active_plugins.add(name)
        return True

    async def deactivate_plugin(self, name: str) -> bool:
        plugin = self._registered_named_plugins.get(name)
        if not plugin:
            return False
        if hasattr(plugin, "deactivate") and inspect.iscoroutinefunction(
            plugin.deactivate
        ):
            ok = await plugin.deactivate()
            if ok and name in self._active_plugins:
                self._active_plugins.remove(name)
            return ok
        self._active_plugins.discard(name)
        return True

    async def is_plugin_active(self, name: str) -> bool:
        return name in self._active_plugins

    async def discover_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        Return metadata for registered plugins. Community tests expect the following fields:
        name, type, version, description, author
        """
        discovered: Dict[str, Dict[str, Any]] = {}
        for name, obj in self._registered_named_plugins.items():
            metadata = {
                "name": name,
                "type": getattr(
                    getattr(obj, "plugin_type", None),
                    "value",
                    str(getattr(obj, "plugin_type", "")),
                ),
                "version": getattr(obj, "version", ""),
                "description": getattr(obj, "description", f"{name} plugin"),
                "author": getattr(obj, "author", "Unknown"),
            }
            discovered[name] = metadata
        return discovered

    async def reload_plugin(self, name: str) -> bool:
        """
        For mock plugins, emulate a reload by deactivate/activate.
        """
        if name not in self._registered_named_plugins:
            return False
        await self.deactivate_plugin(name)
        return await self.activate_plugin(name)

    # ---------- Optional hook system ----------
    def register_extension_point(self, name: str, handler: Callable) -> None:
        self._extension_points[name] = handler

    async def execute_plugin_hook(
        self, hook_name: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a hook across all loaded plugin instances registered via the unit-test API.
        """
        results: Dict[str, Any] = {}
        for plugin_id, instance in self._loaded_plugins.items():
            try:
                if hasattr(instance, hook_name) and callable(
                    getattr(instance, hook_name)
                ):
                    method = getattr(instance, hook_name)
                    if inspect.iscoroutinefunction(method):
                        results[plugin_id] = await method(context)
                    else:
                        results[plugin_id] = method(context)
            except Exception as e:  # pragma: no cover - defensive
                logger.error(
                    "Error executing hook %s for %s: %s", hook_name, plugin_id, e
                )
        return results

    # ---------- Security helpers ----------
    async def _validate_plugin_module_security(self, plugin_module: Any) -> bool:
        """
        Lightweight source inspection. Returns True on allow.
        """
        import ast
        import re

        try:
            source = inspect.getsource(plugin_module)
        except OSError:
            logger.warning("Could not inspect plugin module; allowing by default.")
            return True

        if re.search(r"\beval\s*\(", source) or re.search(r"\bexec\s*\(", source):
            logger.error("Disallowed dynamic execution found in plugin module.")
            return False

        try:
            tree = ast.parse(source)
        except SyntaxError:
            logger.error("Syntax error in plugin module during security validation.")
            return False

        forbidden = {"ctypes", "mmap"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        logger.error("Disallowed import detected: %s", alias.name)
                        return False
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden:
                    logger.error("Disallowed import-from detected: %s", node.module)
                    return False

        return True


# Backwards-compat alias expected by tests and examples
PluginManager = PluginFramework
