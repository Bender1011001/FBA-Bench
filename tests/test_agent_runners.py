"""
Tests for the agent runner framework abstraction layer.

Tests the framework-agnostic interface, factory system, configuration,
and integration with existing FBA-Bench systems.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from fba_bench.core.types import SimulationState, ToolCall
from models.product import Product
from money import Money

from agent_runners import (
    AgentManager,
    AgentRunner,
    AgentRunnerConfig,
    AgentRunnerError,
    DIYConfig,
    RunnerFactory,
    check_framework_availability,
    create_agent_builder,
    validate_config,
)
from event_bus import EventBus


class MockAgentRunner(AgentRunner):
    """Mock agent runner for testing."""

    def __init__(self, agent_id: str, config: dict):
        super().__init__(agent_id, config)
        self.initialized = False
        self.decisions = []

    async def initialize(self, config: dict) -> None:
        self.initialized = True
        self._initialized = True

    async def decide(self, state: SimulationState) -> list[ToolCall]:
        decision = ToolCall(
            tool_name="set_price",
            parameters={"asin": "B0TEST", "price": 19.99},
            confidence=0.8,
            reasoning="Mock decision",
        )
        self.decisions.append(decision)
        return [decision]

    async def cleanup(self) -> None:
        self.initialized = False


@pytest.fixture
def sample_product():
    """Create a sample product for testing."""
    return Product(
        asin="B0TEST123",
        category="electronics",
        cost=Money.from_dollars(10.0),
        price=Money.from_dollars(20.0),
        base_demand=100.0,
        inventory_units=50,
    )


@pytest.fixture
def sample_simulation_state(sample_product):
    """Create a sample simulation state."""
    return SimulationState(
        tick=1,
        simulation_time=datetime.utcnow(),
        products=[sample_product],
        recent_events=[],
        financial_position={"cash": 1000.0},
        market_conditions={"volatility": "low"},
    )


@pytest.fixture
def event_bus():
    """Create a mock event bus."""
    return Mock(spec=EventBus)


class TestAgentRunnerInterface:
    """Test the base AgentRunner interface."""

    def test_tool_call_validation(self):
        """Test ToolCall validation."""
        # Valid tool call
        tool_call = ToolCall(
            tool_name="set_price",
            parameters={"asin": "B0TEST", "price": 19.99},
            confidence=0.8,
        )
        assert tool_call.tool_name == "set_price"
        assert tool_call.confidence == 0.8

        # Invalid confidence
        with pytest.raises(ValueError):
            ToolCall(tool_name="test", parameters={}, confidence=1.5)  # Invalid

        # Empty tool name
        with pytest.raises(ValueError):
            ToolCall(tool_name="", parameters={})

    def test_simulation_state_methods(self, sample_simulation_state):
        """Test SimulationState utility methods."""
        state = sample_simulation_state

        # Test get_product
        product = state.get_product("B0TEST123")
        assert product is not None
        assert product.asin == "B0TEST123"

        # Test non-existent product
        assert state.get_product("B0NONEXISTENT") is None

        # Test get_recent_events_since_tick
        events = state.get_recent_events_since_tick(0)
        assert isinstance(events, list)


class TestRunnerFactory:
    """Test the RunnerFactory system."""

    def test_register_custom_runner(self):
        """Test registering a custom runner."""
        # Register mock runner
        RunnerFactory.register_runner("mock", MockAgentRunner, {"test": True})

        # Check registration
        assert "mock" in RunnerFactory.get_all_frameworks()
        assert RunnerFactory.is_framework_available("mock")

        # Create instance
        runner = RunnerFactory.create_runner("mock", "test_agent", {})
        assert isinstance(runner, MockAgentRunner)
        assert runner.agent_id == "test_agent"

    def test_unknown_framework_error(self):
        """Test error handling for unknown frameworks."""
        with pytest.raises(AgentRunnerError):
            RunnerFactory.create_runner("unknown_framework", "test", {})

    def test_framework_info(self):
        """Test getting framework information."""
        # Register mock runner first
        RunnerFactory.register_runner("mock", MockAgentRunner)

        info = RunnerFactory.get_framework_info("mock")
        assert info["name"] == "mock"
        assert info["class"] == "MockAgentRunner"
        assert info["available"] is True

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid DIY config
        config = {"agent_type": "advanced", "strategy": "profit_maximizer"}
        validated = RunnerFactory.validate_config("diy", config)
        assert "agent_type" in validated

        # Invalid DIY config
        with pytest.raises(AgentRunnerError):
            RunnerFactory.validate_config("diy", {"agent_type": "invalid"})


class TestAgentBuilderPattern:
    """Test the builder pattern for agent creation."""

    def test_builder_pattern(self):
        """Test creating agents with builder pattern."""
        # Register mock runner
        RunnerFactory.register_runner("mock", MockAgentRunner)

        agent = (
            create_agent_builder("mock", "builder_test")
            .with_config(test_param="test_value")
            .build()
        )

        assert agent.agent_id == "builder_test"
        assert "test_param" in agent.config

    @pytest.mark.asyncio
    async def test_builder_with_initialization(self):
        """Test builder pattern with initialization."""
        RunnerFactory.register_runner("mock", MockAgentRunner)

        agent = await (
            create_agent_builder("mock", "init_test")
            .with_config(test_param="test_value")
            .build_and_initialize()
        )

        assert isinstance(agent, MockAgentRunner)
        assert agent.initialized is True


class TestAgentManager:
    """Test the AgentManager integration layer."""

    @pytest.mark.asyncio
    async def test_agent_registration(self, event_bus):
        """Test agent registration and management."""
        # Setup
        event_bus.subscribe = AsyncMock()
        manager = AgentManager(event_bus)
        await manager.initialize()

        # Register mock runner
        RunnerFactory.register_runner("mock", MockAgentRunner)

        # Register agent
        runner = await manager.register_agent("test_agent", "mock", {})
        assert isinstance(runner, MockAgentRunner)
        assert "test_agent" in manager.get_registered_agents()

        # Check stats
        stats = manager.stats
        assert stats["total_agents"] == 1
        assert stats["active_agents"] == 1

    @pytest.mark.asyncio
    async def test_agent_decision_processing(self, event_bus, sample_simulation_state):
        """Test agent decision processing."""
        event_bus.subscribe = AsyncMock()
        event_bus.publish = AsyncMock()

        manager = AgentManager(event_bus)
        await manager.initialize()

        # Register mock runner
        RunnerFactory.register_runner("mock", MockAgentRunner)
        runner = await manager.register_agent("test_agent", "mock", {})

        # Process decision
        registration = manager.agents["test_agent"]
        await manager._process_agent_decision(registration, sample_simulation_state)

        # Check decision was made
        assert len(runner.decisions) == 1
        assert registration.total_decisions == 1
        assert registration.total_tool_calls == 1

    @pytest.mark.asyncio
    async def test_health_check(self, event_bus):
        """Test agent health checking."""
        event_bus.subscribe = AsyncMock()
        manager = AgentManager(event_bus)
        await manager.initialize()

        # Register agent
        RunnerFactory.register_runner("mock", MockAgentRunner)
        await manager.register_agent("test_agent", "mock", {})

        # Health check
        health = await manager.health_check()
        assert "manager_stats" in health
        assert "agents" in health
        assert "test_agent" in health["agents"]
        assert health["agents"]["test_agent"]["active"] is True


class TestConfigurationSystem:
    """Test the configuration system."""

    def test_diy_config_creation(self):
        """Test DIY configuration creation."""
        config = DIYConfig.advanced_agent("test_agent", "B0TEST")

        assert config.agent_id == "test_agent"
        assert config.framework == "diy"
        assert config.agent_config.target_asin == "B0TEST"

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config_dict = {
            "agent_id": "test",
            "framework": "diy",
            "agent_config": {"agent_type": "advanced", "target_asin": "B0TEST"},
        }

        validated = validate_config(config_dict)
        assert isinstance(validated, AgentRunnerConfig)
        assert validated.agent_id == "test"

        # Invalid framework
        with pytest.raises(ValueError):
            validate_config({"agent_id": "test", "framework": "invalid"})

    def test_config_serialization(self):
        """Test config serialization to YAML/JSON."""
        config = DIYConfig.baseline_greedy("test_agent")

        # Test YAML
        yaml_str = config.to_yaml()
        assert "agent_id: test_agent" in yaml_str
        assert "framework: diy" in yaml_str

        # Test JSON
        json_str = config.to_json()
        assert '"agent_id": "test_agent"' in json_str

        # Test round-trip
        config_from_yaml = AgentRunnerConfig.from_yaml(yaml_str)
        assert config_from_yaml.agent_id == config.agent_id


class TestFrameworkAvailability:
    """Test framework availability checking."""

    def test_diy_framework_always_available(self):
        """Test that DIY framework is always available."""
        assert check_framework_availability("diy") is True

    def test_unknown_framework_not_available(self):
        """Test that unknown frameworks are not available."""
        assert check_framework_availability("unknown_framework") is False


@pytest.mark.asyncio
async def test_end_to_end_workflow(event_bus, sample_simulation_state):
    """Test complete end-to-end workflow."""
    # Setup
    event_bus.subscribe = AsyncMock()
    event_bus.publish = AsyncMock()

    # 1. Create agent manager
    manager = AgentManager(event_bus)
    await manager.initialize()

    # 2. Register mock framework
    RunnerFactory.register_runner("mock", MockAgentRunner)

    # 3. Create agent using builder
    config = (
        create_agent_builder("mock", "e2e_agent").with_config(test_mode=True).build()
    )

    # 4. Register agent
    runner = await manager.register_agent("e2e_agent", "mock", config.to_dict())

    # 5. Process decision
    registration = manager.agents["e2e_agent"]
    await manager._process_agent_decision(registration, sample_simulation_state)

    # 6. Verify results
    assert len(runner.decisions) == 1
    assert registration.total_decisions == 1

    # 7. Health check
    health = await manager.health_check()
    assert health["agents"]["e2e_agent"]["active"] is True

    # 8. Cleanup
    await manager.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])
