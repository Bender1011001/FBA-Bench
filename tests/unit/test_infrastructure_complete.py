import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Use importorskip for optional infrastructure modules
try:
    from infrastructure.deployment import (
        DeploymentConfig,
        DeploymentEnvironment,
        DeploymentManager,
        DeploymentType,
    )
    from infrastructure.distributed_coordinator import DistributedCoordinator
    from infrastructure.distributed_event_bus import (
        DistributedEventBus,
        MockRedisBroker,
    )
    from infrastructure.fast_forward_engine import FastForwardEngine
    from infrastructure.llm_batcher import LLMBatcher
    from infrastructure.performance_monitor import PerformanceMonitor
    from infrastructure.resource_manager import ResourceManager
except ImportError as e:
    pytest.skip(f"Infrastructure modules not available: {e}", allow_module_level=True)


class TestDistributedEventBus(unittest.TestCase):
    """Test suite for the DistributedEventBus class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.broker = MockRedisBroker()
        self.event_bus = DistributedEventBus(self.broker)

    async def async_setUp(self):
        """Async set up for tests that need it."""
        await self.event_bus.start()

    async def async_tearDown(self):
        """Async tear down for tests that need it."""
        await self.event_bus.stop()

    def test_event_bus_initialization(self):
        """Test that the event bus initializes correctly."""
        self.assertIsNotNone(self.event_bus)
        self.assertEqual(self.event_bus._broker, self.broker)
        self.assertEqual(len(self.event_bus._subscriptions), 0)

    @pytest.mark.asyncio
    async def test_event_bus_start_stop(self):
        """Test starting and stopping the event bus."""
        await self.event_bus.start()
        self.assertTrue(self.event_bus._running)

        await self.event_bus.stop()
        self.assertFalse(self.event_bus._running)

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self):
        """Test publishing and subscribing to events."""
        await self.event_bus.start()

        # Set up a mock handler
        received_events = []

        async def mock_handler(event_data):
            received_events.append(event_data)

        # Subscribe to an event type
        await self.event_bus.subscribe_to_event("test_event", mock_handler)

        # Publish an event
        test_data = {"message": "test"}
        await self.event_bus.publish_event("test_event", test_data)

        # Give a moment for async processing
        await asyncio.sleep(0.1)

        # Verify the handler was called
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0], test_data)

        await self.event_bus.stop()

    @pytest.mark.asyncio
    async def test_create_partition(self):
        """Test creating partitions."""
        await self.event_bus.start()

        # Create a partition
        await self.event_bus.create_partition("test_partition", ["agent1", "agent2"])

        # Verify the partition was created
        self.assertIn("test_partition", self.event_bus._partitions)
        self.assertEqual(
            self.event_bus._partitions["test_partition"], ["agent1", "agent2"]
        )

        await self.event_bus.stop()

    @pytest.mark.asyncio
    async def test_register_worker(self):
        """Test registering workers."""
        await self.event_bus.start()

        # Register a worker
        capabilities = {"model": "gpt-4", "max_tokens": 1000}
        await self.event_bus.register_worker("worker1", capabilities)

        # Verify the worker was registered
        self.assertIn("worker1", self.event_bus._workers)
        self.assertEqual(self.event_bus._workers["worker1"], capabilities)

        await self.event_bus.stop()


class TestDistributedCoordinator(unittest.TestCase):
    """Test suite for the DistributedCoordinator class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.event_bus = Mock()
        self.simulation_config = Mock()
        self.coordinator = DistributedCoordinator(
            self.event_bus, self.simulation_config
        )

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self):
        """Test that the coordinator initializes correctly."""
        self.assertIsNotNone(self.coordinator)
        self.assertEqual(self.coordinator._distributed_event_bus, self.event_bus)
        self.assertEqual(self.coordinator._simulation_config, self.simulation_config)
        self.assertEqual(len(self.coordinator._workers), 0)

    @pytest.mark.asyncio
    async def test_coordinator_start_stop(self):
        """Test starting and stopping the coordinator."""
        # Mock the event bus methods
        self.event_bus.subscribe_to_event = AsyncMock()
        self.event_bus.publish_event = AsyncMock()

        await self.coordinator.start()
        self.assertTrue(self.coordinator._running)

        await self.coordinator.stop()
        self.assertFalse(self.coordinator._running)

    @pytest.mark.asyncio
    async def test_spawn_worker(self):
        """Test spawning workers."""
        # Mock the event bus methods
        self.event_bus.subscribe_to_event = AsyncMock()
        self.event_bus.publish_event = AsyncMock()

        await self.coordinator.start()

        # Spawn a worker
        partition_config = {"partition_id": "test_partition", "agents": ["agent1"]}
        worker_id = await self.coordinator.spawn_worker(partition_config)

        # Verify the worker was spawned
        self.assertIsNotNone(worker_id)
        self.assertIn(worker_id, self.coordinator._workers)

        await self.coordinator.stop()

    @pytest.mark.asyncio
    async def test_coordinate_tick_progression(self):
        """Test coordinating tick progression."""
        # Mock the event bus methods
        self.event_bus.subscribe_to_event = AsyncMock()
        self.event_bus.publish_event = AsyncMock()

        await self.coordinator.start()

        # Add a mock worker
        self.coordinator._workers["worker1"] = Mock()
        self.coordinator._workers["worker1"].send_tick = AsyncMock()
        self.coordinator._workers["worker1"].send_tick.return_value = {"status": "ack"}

        # Test tick progression
        await self.coordinator.coordinate_tick_progression()

        await self.coordinator.stop()

    @pytest.mark.asyncio
    async def test_aggregate_simulation_results(self):
        """Test aggregating simulation results."""
        # Mock the event bus methods
        self.event_bus.subscribe_to_event = AsyncMock()
        self.event_bus.publish_event = AsyncMock()

        await self.coordinator.start()

        # Add mock workers with results
        self.coordinator._workers["worker1"] = Mock()
        self.coordinator._workers["worker1"].get_results = AsyncMock()
        self.coordinator._workers["worker1"].get_results.return_value = {"profit": 1000}

        self.coordinator._workers["worker2"] = Mock()
        self.coordinator._workers["worker2"].get_results = AsyncMock()
        self.coordinator._workers["worker2"].get_results.return_value = {"profit": 1500}

        # Aggregate results
        results = await self.coordinator.aggregate_simulation_results()

        # Verify results
        self.assertEqual(len(results), 2)
        self.assertIn({"profit": 1000}, results)
        self.assertIn({"profit": 1500}, results)

        await self.coordinator.stop()


class TestFastForwardEngine(unittest.TestCase):
    """Test suite for the FastForwardEngine class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.event_bus = Mock()
        self.simulation_orchestrator = Mock()
        self.engine = FastForwardEngine(self.event_bus, self.simulation_orchestrator)

    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """Test that the engine initializes correctly."""
        self.assertIsNotNone(self.engine)
        self.assertEqual(self.engine._event_bus, self.event_bus)
        self.assertEqual(
            self.engine._simulation_orchestrator, self.simulation_orchestrator
        )
        self.assertEqual(len(self.engine._agent_activities), 0)

    @pytest.mark.asyncio
    async def test_engine_start_stop(self):
        """Test starting and stopping the engine."""
        # Mock the event bus methods
        self.event_bus.subscribe_to_event = AsyncMock()

        await self.engine.start()
        self.assertTrue(self.engine._running)

        await self.engine.stop()
        self.assertFalse(self.engine._running)

    @pytest.mark.asyncio
    async def test_fast_forward_to_tick(self):
        """Test fast forwarding to a specific tick."""
        # Mock the event bus methods
        self.event_bus.subscribe_to_event = AsyncMock()

        await self.engine.start()

        # Mock the simulation orchestrator
        self.simulation_orchestrator.get_current_tick = Mock(return_value=10)
        self.simulation_orchestrator.set_tick = AsyncMock()

        # Fast forward to tick 50
        await self.engine.fast_forward_to_tick(50)

        # Verify the orchestrator was called
        self.simulation_orchestrator.set_tick.assert_called_once_with(50)

        await self.engine.stop()


class TestLLMBatcher(unittest.TestCase):
    """Test suite for the LLMBatcher class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.batcher = LLMBatcher()

    @pytest.mark.asyncio
    async def test_batcher_initialization(self):
        """Test that the batcher initializes correctly."""
        self.assertIsNotNone(self.batcher)
        self.assertEqual(len(self.batcher._pending_requests), 0)
        self.assertEqual(self.batcher._max_batch_size, 10)
        self.assertEqual(self.batcher._timeout_ms, 100)

    @pytest.mark.asyncio
    async def test_batcher_start_stop(self):
        """Test starting and stopping the batcher."""
        await self.batcher.start()
        self.assertTrue(self.batcher._running)

        await self.batcher.stop()
        self.assertFalse(self.batcher._running)

    @pytest.mark.asyncio
    async def test_add_request(self):
        """Test adding requests to the batcher."""
        await self.batcher.start()

        # Create a mock callback
        callback = Mock()

        # Add a request
        self.batcher.add_request("req1", "Test prompt", "gpt-4", callback)

        # Verify the request was added
        self.assertEqual(len(self.batcher._pending_requests), 1)
        self.assertIn("req1", self.batcher._pending_requests)

        await self.batcher.stop()

    @pytest.mark.asyncio
    async def test_set_batch_parameters(self):
        """Test setting batch parameters."""
        self.batcher.set_batch_parameters(
            max_size=20, timeout_ms=200, similarity_threshold=0.8
        )

        self.assertEqual(self.batcher._max_batch_size, 20)
        self.assertEqual(self.batcher._timeout_ms, 200)
        self.assertEqual(self.batcher._similarity_threshold, 0.8)


class TestPerformanceMonitor(unittest.TestCase):
    """Test suite for the PerformanceMonitor class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.monitor = PerformanceMonitor()

    @pytest.mark.asyncio
    async def test_monitor_initialization(self):
        """Test that the monitor initializes correctly."""
        self.assertIsNotNone(self.monitor)
        self.assertEqual(len(self.monitor._metrics_history), 0)

    @pytest.mark.asyncio
    async def test_monitor_start_stop(self):
        """Test starting and stopping the monitor."""
        await self.monitor.start()
        self.assertTrue(self.monitor._monitoring)

        await self.monitor.stop()
        self.assertFalse(self.monitor._monitoring)

    def test_monitor_system_resources(self):
        """Test monitoring system resources."""
        # Mock psutil functions
        with (
            patch("psutil.cpu_percent") as mock_cpu,
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.disk_usage") as mock_disk,
        ):
            mock_cpu.return_value = 50.0
            mock_memory.return_value = Mock(percent=60.0)
            mock_disk.return_value = Mock(percent=30.0)

            metrics = self.monitor.monitor_system_resources()

            self.assertEqual(metrics["cpu_percent"], 50.0)
            self.assertEqual(metrics["memory_percent"], 60.0)
            self.assertEqual(metrics["disk_percent"], 30.0)

    def test_detect_bottlenecks(self):
        """Test detecting bottlenecks."""
        # Create metrics with bottlenecks
        metrics = {"cpu_percent": 90.0, "memory_percent": 85.0, "disk_percent": 40.0}

        bottlenecks = self.monitor.detect_bottlenecks(metrics)

        self.assertIn("High CPU usage", bottlenecks)
        self.assertIn("High memory usage", bottlenecks)

    def test_suggest_optimizations(self):
        """Test suggesting optimizations."""
        bottlenecks = ["High CPU usage", "High memory usage"]

        optimizations = self.monitor.suggest_optimizations(bottlenecks)

        self.assertIn("Consider scaling horizontally", optimizations)
        self.assertIn("Optimize memory usage", optimizations)


class TestResourceManager(unittest.TestCase):
    """Test suite for the ResourceManager class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.resource_manager = ResourceManager()

    def test_resource_manager_initialization(self):
        """Test that the resource manager initializes correctly."""
        self.assertIsNotNone(self.resource_manager)
        self.assertEqual(len(self.resource_manager._token_budgets), 0)
        self.assertEqual(self.resource_manager._global_token_cap, 1000000)

    def test_set_token_budget(self):
        """Test setting token budgets."""
        self.resource_manager.set_token_budget("agent1", 10000)

        self.assertEqual(self.resource_manager._token_budgets["agent1"], 10000)

    def test_set_global_token_cap(self):
        """Test setting global token cap."""
        self.resource_manager.set_global_token_cap(500000)

        self.assertEqual(self.resource_manager._global_token_cap, 500000)

    def test_allocate_tokens(self):
        """Test allocating tokens."""
        self.resource_manager.set_token_budget("agent1", 10000)

        # Allocate tokens
        result = self.resource_manager.allocate_tokens("agent1", "general", 1000)

        self.assertTrue(result)
        self.assertEqual(self.resource_manager._token_usage["agent1"], 1000)

    def test_record_llm_cost(self):
        """Test recording LLM costs."""
        self.resource_manager.record_llm_cost("gpt-4", 0.02, 1000)

        self.assertEqual(self.resource_manager._llm_costs["gpt-4"]["total_cost"], 0.02)
        self.assertEqual(
            self.resource_manager._llm_costs["gpt-4"]["total_tokens"], 1000
        )

    def test_get_current_token_usage(self):
        """Test getting current token usage."""
        self.resource_manager.set_token_budget("agent1", 10000)
        self.resource_manager.allocate_tokens("agent1", "general", 1000)

        usage = self.resource_manager.get_current_token_usage("agent1")

        self.assertEqual(usage, 1000)

    def test_enforce_cost_limits(self):
        """Test enforcing cost limits."""
        self.resource_manager.set_global_token_cap(1000)
        self.resource_manager.record_llm_cost("gpt-4", 100.0, 1000)

        # This should raise an exception due to exceeding cost limits
        with self.assertRaises(Exception):
            self.resource_manager.enforce_cost_limits(50.0)


class TestDeploymentManager(unittest.TestCase):
    """Test suite for the DeploymentManager class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = DeploymentConfig(
            environment=DeploymentEnvironment.LOCAL,
            deployment_type=DeploymentType.DOCKER_COMPOSE,
            resource_limits={"cpu": "2", "memory": "4GB"},
            scaling_config={"min_instances": 1, "max_instances": 3},
        )
        self.deployment_manager = DeploymentManager(self.config)

    def test_deployment_manager_initialization(self):
        """Test that the deployment manager initializes correctly."""
        self.assertIsNotNone(self.deployment_manager)
        self.assertEqual(self.deployment_manager.config, self.config)

    def test_set_default_resources(self):
        """Test setting default resources."""
        self.deployment_manager._set_default_resources()

        self.assertIsNotNone(self.deployment_manager.resource_limits)
        self.assertIn("cpu", self.deployment_manager.resource_limits)
        self.assertIn("memory", self.deployment_manager.resource_limits)

    @patch("subprocess.run")
    def test_deploy_docker_compose(self, mock_run):
        """Test deploying with Docker Compose."""
        mock_run.return_value = Mock(returncode=0)

        result = self.deployment_manager._deploy_docker_compose()

        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_deploy_kubernetes(self, mock_run):
        """Test deploying with Kubernetes."""
        mock_run.return_value = Mock(returncode=0)

        result = self.deployment_manager._deploy_kubernetes()

        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_deploy_local(self, mock_run):
        """Test deploying locally."""
        mock_run.return_value = Mock(returncode=0)

        result = self.deployment_manager._deploy_local()

        self.assertTrue(result)

    @patch("subprocess.run")
    def test_status_docker_compose(self, mock_run):
        """Test getting status with Docker Compose."""
        mock_run.return_value = Mock(stdout="Running", returncode=0)

        status = self.deployment_manager._status_docker_compose()

        self.assertIn("status", status)
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
