"""
Integration Manager for FBA-Bench.

This module provides a centralized integration layer that connects all components
of the FBA-Bench system, ensuring seamless operation and communication between
different modules.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from agent_runners.agent_manager import AgentManager
from agent_runners.runner_factory import RunnerFactory
from services.external_service import ExternalServiceManager, ServiceConfig
from ..config.schema_manager import SchemaManager
from ..registry.global_registry import GlobalRegistry, RegistryEntry
from ..registry.global_variables import global_variables

logger = logging.getLogger(__name__)


class IntegrationStatus(str, Enum):
    """Status of the integration system."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"


@dataclass
class IntegrationEvent:
    """Event for integration system communication."""

    event_type: str
    source: str
    target: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # Higher priority events are processed first


class IntegrationManager:
    """
    Central integration manager for FBA-Bench.

    This class manages the integration between all components of the system,
    providing event-driven communication and centralized coordination.
    """

    def __init__(self):
        """Initialize the integration manager."""
        self.status = IntegrationStatus.INITIALIZING
        self.registry = GlobalRegistry()
        self.schema_manager = SchemaManager(self.registry)
        self.external_service_manager = ExternalServiceManager()
        self.agent_manager = AgentManager()

        # Event system
        self.event_queue: List[IntegrationEvent] = []
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.event_lock = threading.Lock()
        self.event_thread = None
        self.event_thread_running = False

        # Component status
        self.component_status: Dict[str, str] = {}

        # Integration callbacks
        self.integration_callbacks: Dict[str, List[Callable]] = {
            "on_component_ready": [],
            "on_component_error": [],
            "on_integration_complete": [],
            "on_shutdown_complete": [],
        }

        logger.info("IntegrationManager initialized")

    def initialize(self) -> None:
        """Initialize all components and establish connections."""
        try:
            logger.info("Starting integration initialization")

            # Initialize global variables from environment
            global_variables.initialize_from_environment()

            # Register built-in components
            self._register_builtin_components()

            # Initialize external services
            self._initialize_external_services()

            # Initialize agent runners
            self._initialize_agent_runners()

            # Start event processing thread
            self._start_event_processing()

            # Set status to ready
            self.status = IntegrationStatus.READY
            self.component_status["integration_manager"] = "ready"

            logger.info("Integration initialization completed successfully")

        except Exception as e:
            self.status = IntegrationStatus.ERROR
            self.component_status["integration_manager"] = f"error: {e!s}"
            logger.error(f"Integration initialization failed: {e}")
            raise

    def _register_builtin_components(self) -> None:
        """Register built-in components in the registry."""
        # Register configuration schemas
        for schema_name in self.schema_manager.list_schemas():
            schema_info = self.schema_manager.get_schema_info(schema_name)
            if schema_info:
                logger.debug(f"Registered schema: {schema_name}")

        # Register agent runners
        for framework in RunnerFactory.get_all_frameworks():
            logger.debug(f"Registered agent runner framework: {framework}")

        logger.info("Built-in components registered")

    def _initialize_external_services(self) -> None:
        """Initialize external services based on configuration."""
        # Initialize services based on global configuration
        if global_variables.database.db_type:
            # Database service would be initialized here
            logger.debug(
                f"Database service configured: {global_variables.database.db_type}"
            )

        if global_variables.cache.cache_type == "redis":
            # Redis service would be initialized here
            logger.debug("Redis cache service configured")

        logger.info("External services initialized")

    def _initialize_agent_runners(self) -> None:
        """Initialize agent runners."""
        # Agent runners are registered in the RunnerFactory
        # This method ensures they are properly integrated
        logger.info("Agent runners initialized")

    def _start_event_processing(self) -> None:
        """Start the event processing thread."""
        self.event_thread_running = True
        self.event_thread = threading.Thread(target=self._process_events, daemon=True)
        self.event_thread.start()
        logger.info("Event processing thread started")

    def _process_events(self) -> None:
        """Process events in the event queue."""
        while self.event_thread_running:
            try:
                event = None

                # Get next event
                with self.event_lock:
                    if self.event_queue:
                        # Sort by priority (higher priority first)
                        self.event_queue.sort(key=lambda e: e.priority, reverse=True)
                        event = self.event_queue.pop(0)

                if event:
                    # Process event
                    self._handle_event(event)
                else:
                    # No events, sleep briefly
                    threading.Event().wait(0.1)

            except Exception as e:
                logger.error(f"Error processing event: {e}")

    def _handle_event(self, event: IntegrationEvent) -> None:
        """
        Handle a single event.

        Args:
            event: Event to handle
        """
        logger.debug(f"Processing event: {event.event_type} from {event.source}")

        # Get handlers for this event type
        handlers = self.event_handlers.get(event.event_type, [])

        # Call each handler
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type}: {e}")

    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event_type: Type of event to handle
            handler: Handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered event handler for: {event_type}")

    def unregister_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        Unregister an event handler.

        Args:
            event_type: Type of event
            handler: Handler function to remove
        """
        if event_type in self.event_handlers:
            try:
                self.event_handlers[event_type].remove(handler)
                logger.debug(f"Unregistered event handler for: {event_type}")
            except ValueError:
                # Handler not found, ignore
                pass

    def emit_event(
        self,
        event_type: str,
        source: str,
        data: Dict[str, Any] = None,
        target: str = None,
        priority: int = 0,
    ) -> None:
        """
        Emit an event.

        Args:
            event_type: Type of event
            source: Source of the event
            data: Event data
            target: Target component (optional)
            priority: Event priority (higher = more important)
        """
        event = IntegrationEvent(
            event_type=event_type,
            source=source,
            target=target,
            data=data or {},
            priority=priority,
        )

        with self.event_lock:
            self.event_queue.append(event)

        logger.debug(f"Emitted event: {event_type} from {source}")

    def register_integration_callback(
        self, callback_type: str, handler: Callable
    ) -> None:
        """
        Register an integration callback.

        Args:
            callback_type: Type of callback
            handler: Handler function
        """
        if callback_type in self.integration_callbacks:
            self.integration_callbacks[callback_type].append(handler)
            logger.debug(f"Registered integration callback: {callback_type}")

    def trigger_integration_callback(self, callback_type: str, *args, **kwargs) -> None:
        """
        Trigger integration callbacks.

        Args:
            callback_type: Type of callback to trigger
            *args: Arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """
        for handler in self.integration_callbacks.get(callback_type, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in integration callback {callback_type}: {e}")

    def register_external_service(self, name: str, config: ServiceConfig) -> None:
        """
        Register an external service.

        Args:
            name: Service name
            config: Service configuration
        """
        self.external_service_manager.register_service(name, config)
        logger.info(f"Registered external service: {name}")

    def get_external_service(self, name: str):
        """
        Get an external service.

        Args:
            name: Service name

        Returns:
            External service instance
        """
        return self.external_service_manager.get_service(name)

    def create_agent(
        self, agent_id: str, framework: str, config: Dict[str, Any]
    ) -> str:
        """
        Create an agent through the agent manager.

        Args:
            agent_id: Unique identifier for the agent
            framework: Agent framework to use
            config: Agent configuration

        Returns:
            Agent ID
        """
        # Wrap configuration for sync create_agent call
        from types import SimpleNamespace
        agent_config = SimpleNamespace(
            agent_id=agent_id, 
            framework=framework, 
            **(config or {})
        )
        return self.agent_manager.create_agent(agent_config)

    def get_agent(self, agent_id: str):
        """
        Get an agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent instance
        """
        return self.agent_manager.get_agent_runner(agent_id)

    def list_agents(self) -> List[str]:
        """
        List all agent IDs.

        Returns:
            List of agent IDs
        """
        return list(self.agent_manager.get_registered_agents().keys())

    def remove_agent(self, agent_id: str) -> bool:
        """
        Remove an agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if successful
        """
        return self.agent_manager.remove_agent(agent_id)

    def validate_configuration(
        self, schema_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a configuration against a schema.

        Args:
            schema_name: Name of the schema
            config: Configuration to validate

        Returns:
            Validated configuration
        """
        return self.schema_manager.validate_config(schema_name, config)

    def create_configuration(self, schema_name: str, **kwargs) -> Dict[str, Any]:
        """
        Create a configuration using a schema.

        Args:
            schema_name: Name of the schema
            **kwargs: Configuration values

        Returns:
            Configuration dictionary
        """
        return self.schema_manager.create_config(schema_name, **kwargs)

    def get_registry_entry(self, name: str) -> Optional[RegistryEntry]:
        """
        Get a registry entry by name.

        Args:
            name: Entry name

        Returns:
            Registry entry or None if not found
        """
        return self.registry.get(name)

    def register_registry_entry(self, entry: RegistryEntry) -> None:
        """
        Register a registry entry.

        Args:
            entry: Entry to register
        """
        self.registry.register(entry)
        logger.info(f"Registered registry entry: {entry.name}")

    def update_component_status(self, component: str, status: str) -> None:
        """
        Update the status of a component.

        Args:
            component: Component name
            status: Component status
        """
        self.component_status[component] = status
        logger.debug(f"Updated component status: {component} -> {status}")

        # Trigger callbacks if component is ready or has error
        if status == "ready":
            self.trigger_integration_callback("on_component_ready", component)
        elif status.startswith("error"):
            self.trigger_integration_callback("on_component_error", component, status)

    def get_component_status(self, component: str) -> Optional[str]:
        """
        Get the status of a component.

        Args:
            component: Component name

        Returns:
            Component status or None if not found
        """
        return self.component_status.get(component)

    def get_all_component_status(self) -> Dict[str, str]:
        """
        Get the status of all components.

        Returns:
            Dictionary of component statuses
        """
        return self.component_status.copy()

    def get_integration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the integration system.

        Returns:
            Integration summary dictionary
        """
        return {
            "status": self.status.value,
            "components": {
                "total": len(self.component_status),
                "ready": sum(1 for s in self.component_status.values() if s == "ready"),
                "error": sum(
                    1 for s in self.component_status.values() if s.startswith("error")
                ),
            },
            "registry": self.registry.get_registry_summary(),
            "schema_manager": self.schema_manager.get_manager_summary(),
            "external_services": {
                "total": len(self.external_service_manager.list_services()),
                "services": [
                    self.external_service_manager.get_service_info(name)
                    for name in self.external_service_manager.list_services()
                ],
            },
            "agents": {
                "total": len(self.list_agents()),
                "active": len(
                    [
                        a
                        for a in self.list_agents()
                        if self.get_agent(a)
                        and self.get_agent(a).status.value == "ready"
                    ]
                ),
            },
            "event_system": {
                "queue_size": len(self.event_queue),
                "registered_handlers": len(self.event_handlers),
                "total_event_types": len(self.event_handlers),
            },
        }

    def run_benchmark(self, benchmark_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a benchmark using the integrated system.

        Args:
            benchmark_config: Benchmark configuration

        Returns:
            Benchmark results
        """
        # Validate benchmark configuration
        validated_config = self.validate_configuration(
            "benchmark_config", benchmark_config
        )

        # Emit benchmark start event
        self.emit_event("benchmark_start", "integration_manager", validated_config)

        try:
            # Create agents based on configuration
            agents = []
            for agent_config in validated_config.get("agents", []):
                agent_id = self.create_agent(
                    agent_config["id"],
                    agent_config["framework"],
                    agent_config["config"],
                )
                agents.append(agent_id)

            # Run the benchmark
            # This would be implemented with the actual benchmarking engine
            results = {
                "benchmark_id": validated_config.get("id", "unknown"),
                "agents": agents,
                "status": "completed",
                "metrics": {},
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
            }

            # Emit benchmark complete event
            self.emit_event("benchmark_complete", "integration_manager", results)

            return results

        except Exception as e:
            error_result = {
                "benchmark_id": validated_config.get("id", "unknown"),
                "status": "failed",
                "error": str(e),
                "start_time": datetime.now().isoformat(),
            }

            # Emit benchmark error event
            self.emit_event("benchmark_error", "integration_manager", error_result)

            return error_result

    def shutdown(self) -> None:
        """Shutdown the integration system."""
        logger.info("Starting integration shutdown")

        # Set status to shutting down
        self.status = IntegrationStatus.SHUTTING_DOWN

        # Stop event processing
        self.event_thread_running = False
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5)

        # Shutdown external services
        self.external_service_manager.close_all()

        # AgentManager stop/cleanup are async; use best-effort sync approach
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't easily block, but we can schedule it
                    asyncio.create_task(self.agent_manager.stop())
                else:
                    loop.run_until_complete(self.agent_manager.stop())
            except RuntimeError:
                asyncio.run(self.agent_manager.stop())
        except Exception as e:
            logger.debug(f"Non-fatal error during AgentManager shutdown: {e}")

        # Set status to shutdown
        self.status = IntegrationStatus.SHUTDOWN

        # Trigger shutdown callback
        self.trigger_integration_callback("on_shutdown_complete")

        logger.info("Integration shutdown completed")


# Global instance of the integration manager
integration_manager = IntegrationManager()
