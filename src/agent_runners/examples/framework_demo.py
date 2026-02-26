"""
Framework Abstraction Demo - Shows how to use different agent frameworks.

This demo demonstrates the framework-agnostic agent runner system,
showing how to create and use agents with different frameworks
(DIY, CrewAI, LangChain) through the same unified interface.
"""

import asyncio
import logging
from datetime import datetime

from agent_runners import (
    AgentManager,
    CrewAIConfig,
    DIYConfig,
    LangChainConfig,
    check_framework_availability,
    create_agent_builder,
    get_available_frameworks,
)
from fba_bench_core.event_bus import get_event_bus
from fba_events.time_events import TickEvent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_framework_abstraction():
    """Demonstrate framework-agnostic agent creation and usage."""
    print("🚀 FBA-Bench Framework Abstraction Demo")
    print("=" * 50)

    # Initialize event bus and agent manager
    event_bus = get_event_bus()
    agent_manager = AgentManager(event_bus)
    await agent_manager.initialize()

    print("\n📋 Available Frameworks:")
    available_frameworks = get_available_frameworks()
    all_frameworks = ["diy", "crewai", "langchain"]

    for framework in all_frameworks:
        status = (
            "✅ Available" if framework in available_frameworks else "❌ Not installed"
        )
        print(f"  {framework.upper()}: {status}")

    # Create agents with different frameworks
    agents_created = []

    # 1. DIY Agent (always available)
    print("\n🔧 Creating DIY Agent...")
    try:
        diy_config = DIYConfig.advanced_agent("diy_agent_1", "B0EXAMPLE01")
        diy_runner = await agent_manager.register_agent(  # noqa: F841
            "diy_agent_1", "diy", diy_config.to_dict()
        )
        agents_created.append("diy_agent_1")
        print("  ✅ DIY agent created successfully")
    except Exception as e:
        print(f"  ❌ DIY agent creation failed: {e}")

    # 2. CrewAI Agent (if available)
    if check_framework_availability("crewai"):
        print("\n👥 Creating CrewAI Agent...")
        try:
            crewai_config = CrewAIConfig.standard_crew("crewai_agent_1", "fake_api_key")
            crewai_runner = await agent_manager.register_agent(  # noqa: F841
                "crewai_agent_1", "crewai", crewai_config.to_dict()
            )
            agents_created.append("crewai_agent_1")
            print("  ✅ CrewAI agent created successfully")
        except Exception as e:
            print(f"  ❌ CrewAI agent creation failed: {e}")
    else:
        print("\n👥 CrewAI not available - skipping")

    # 3. LangChain Agent (if available)
    if check_framework_availability("langchain"):
        print("\n🔗 Creating LangChain Agent...")
        try:
            langchain_config = LangChainConfig.reasoning_agent(
                "langchain_agent_1", "fake_api_key"
            )
            langchain_runner = await agent_manager.register_agent(  # noqa: F841
                "langchain_agent_1", "langchain", langchain_config.to_dict()
            )
            agents_created.append("langchain_agent_1")
            print("  ✅ LangChain agent created successfully")
        except Exception as e:
            print(f"  ❌ LangChain agent creation failed: {e}")
    else:
        print("\n🔗 LangChain not available - skipping")

    # Demonstrate unified interface usage
    print(f"\n🎯 Testing Unified Interface with {len(agents_created)} agents")

    if agents_created:
        # Create a sample tick event
        tick_event = TickEvent(
            event_id="demo_tick_1", timestamp=datetime.utcnow(), tick_number=1
        )

        print("  📤 Publishing tick event to all agents...")

        # Publish tick event (this will trigger all agent decisions)
        await event_bus.publish("TickEvent", tick_event)

        # Wait a moment for processing
        await asyncio.sleep(1)

        # Check agent health
        print("\n📊 Agent Health Status:")
        health_data = await agent_manager.health_check()

        for agent_id in agents_created:
            if agent_id in health_data["agents"]:
                agent_health = health_data["agents"][agent_id]
                status = "✅ Healthy" if agent_health["active"] else "❌ Inactive"
                framework = agent_health["framework"]
                print(f"  {agent_id} ({framework}): {status}")
            else:
                print(f"  {agent_id}: ❌ No health data")

    # Demonstrate builder pattern
    print("\n🏗️ Builder Pattern Demo:")
    try:
        builder_agent = (
            create_agent_builder("diy", "builder_demo")
            .with_agent_settings("profit_maximizer", 0.15, "B0BUILDER")
            .with_config(verbose=True)
            .build()
        )
        print("  ✅ Agent created using builder pattern")
        print(
            f"  📋 Config: {builder_agent.agent_id}, framework: {builder_agent.framework}"
        )
    except Exception as e:
        print(f"  ❌ Builder pattern failed: {e}")

    # Framework usage statistics
    print("\n📈 Framework Usage Statistics:")
    framework_usage = agent_manager.get_framework_usage()
    for framework, count in framework_usage.items():
        print(f"  {framework}: {count} agents")

    # Cleanup
    print("\n🧹 Cleaning up...")
    await agent_manager.cleanup()
    print("  ✅ Cleanup completed")

    print("\n🎉 Demo completed successfully!")


async def demo_configuration_system():
    """Demonstrate the configuration system capabilities."""
    print("\n⚙️ Configuration System Demo")
    print("=" * 30)

    # Show different configuration methods
    print("1. Creating configs programmatically:")

    # DIY config
    diy_config = DIYConfig.baseline_greedy("test_agent")
    print(f"   DIY Config: {diy_config.agent_id} - {diy_config.framework}")

    # Show YAML export
    print("\n2. Config as YAML:")
    yaml_output = diy_config.to_yaml()
    print("   " + yaml_output.replace("\n", "\n   "))

    # Show framework examples
    print("\n3. Available config examples:")
    from agent_runners.configs.framework_configs import get_framework_examples

    examples = get_framework_examples()
    for framework, configs in examples.items():
        print(f"   {framework.upper()}:")
        for config_name, description in configs.items():
            print(f"     - {config_name}: {description}")


async def demo_dependency_management():
    """Demonstrate dependency management capabilities."""
    print("\n📦 Dependency Management Demo")
    print("=" * 32)

    from agent_runners.dependency_manager import dependency_manager

    # Show framework information
    print("Framework Information:")
    framework_info = dependency_manager.get_all_framework_info()

    for framework, info in framework_info.items():
        status = "✅" if info["available"] else "❌"
        version = info["version"] or "Not installed"
        print(f"  {status} {info['name']}: {version}")

        if not info["available"]:
            print(f"    Install: {info['install_command']}")

    # Show installation guide
    print("\n📖 Installation Guide:")
    guide = dependency_manager.get_installation_guide()
    for line in guide.split("\n"):
        print(f"   {line}")


async def main():
    """Run all demonstrations."""
    try:
        await demo_framework_abstraction()
        await demo_configuration_system()
        await demo_dependency_management()

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
