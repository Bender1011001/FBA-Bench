#!/usr/bin/env python3
"""
Simple Python Demo for FBA-Bench: Basic Multi-Agent Simulation

This standalone script demonstrates the core event-driven architecture
without Docker, external services, or API keys. It shows agents sending
commands, world store arbitration, and event propagation.

Requirements:
- Python 3.10+
- Clone the repo and run from root: python scripts/simple_python_demo.py

Expected Output:
- Setup messages
- Agent commands and responses
- Final statistics
- All tests pass message

This uses simplified classes adapted from the project's test suite.
"""

import asyncio
import sys
import uuid
from datetime import datetime

from money import Money

from events import ProductPriceUpdated, SetPriceCommand


# Simplified classes for demo (adapted from test_worldstore_standalone.py for standalone run)
class EventBusDemo:
    """Simplified EventBus for demo."""

    def __init__(self):
        self.subscribers = {}
        self.running = False

    async def start(self):
        self.running = True
        print("   📡 EventBus started")

    async def stop(self):
        self.running = False
        print("   📡 EventBus stopped")

    async def subscribe(self, event_type: str, callback):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        print(f"   📡 Subscribed to {event_type}")

    async def publish(self, event):
        if not self.running:
            return
        event_type = type(event).__name__
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    await callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")


class WorldStoreDemo:
    """Simplified WorldStore for demo."""

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._product_state = {}
        self.commands_processed = 0
        self.commands_rejected = 0
        self.min_price_threshold = Money(100)  # $1.00
        self.max_price_threshold = Money(100000)  # $1000.00
        self.max_price_change_per_tick = 0.50  # 50%

    async def start(self):
        """Subscribe to SetPriceCommand events."""
        await self.event_bus.subscribe("SetPriceCommand", self.handle_set_price_command)
        print("   🌍 WorldStore started")

    async def handle_set_price_command(self, event: SetPriceCommand):
        """Process SetPriceCommand and possibly publish ProductPriceUpdated."""
        try:
            # Validate price bounds
            if event.new_price < self.min_price_threshold:
                self.commands_rejected += 1
                print(
                    f"   🚫 Command rejected: price {event.new_price} below minimum {self.min_price_threshold}"
                )
                return

            if event.new_price > self.max_price_threshold:
                self.commands_rejected += 1
                print(
                    f"   🚫 Command rejected: price {event.new_price} above maximum {self.max_price_threshold}"
                )
                return

            # Get current price
            current_price = self._product_state.get(event.asin, Money(2000))  # Default $20.00

            # Validate price change magnitude
            price_change_ratio = abs((event.new_price.cents / current_price.cents) - 1.0)
            if price_change_ratio > self.max_price_change_per_tick:
                self.commands_rejected += 1
                print(
                    f"   🚫 Command rejected: price change {price_change_ratio:.2%} exceeds maximum"
                )
                return

            # Accept command and update state
            previous_price = current_price
            self._product_state[event.asin] = event.new_price
            self.commands_processed += 1

            # Publish ProductPriceUpdated event
            update_event = ProductPriceUpdated(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                asin=event.asin,
                new_price=event.new_price,
                previous_price=previous_price,
                agent_id=event.agent_id,
                command_id=event.event_id,
                arbitration_notes="Command accepted by WorldStoreDemo",
            )

            await self.event_bus.publish(update_event)
            print(f"   ✅ Command accepted: {event.asin} {previous_price} -> {event.new_price}")

        except Exception as e:
            print(f"   ❌ Error processing command: {e}")
            self.commands_rejected += 1

    def get_product_price(self, asin: str) -> Money:
        """Get current price for a product."""
        return self._product_state.get(asin, Money(2000))

    def get_statistics(self):
        """Get WorldStore statistics."""
        return {
            "commands_processed": self.commands_processed,
            "commands_rejected": self.commands_rejected,
            "products_managed": len(self._product_state),
        }


class AgentDemo:
    """Simplified agent for demo."""

    def __init__(self, agent_id: str, event_bus):
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.price_updates_received = []

    async def start(self):
        """Subscribe to ProductPriceUpdated events."""
        await self.event_bus.subscribe("ProductPriceUpdated", self.handle_price_update)
        print(f"   🤖 Agent {self.agent_id} started")

    async def handle_price_update(self, event: ProductPriceUpdated):
        """Handle price update events."""
        self.price_updates_received.append(event)
        print(f"   🤖 Agent {self.agent_id} received update: {event.asin} = {event.new_price}")

    async def send_price_command(self, asin: str, new_price: Money, reason: str = "Demo command"):
        """Send a SetPriceCommand."""
        command = SetPriceCommand(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            agent_id=self.agent_id,
            asin=asin,
            new_price=new_price,
            reason=reason,
        )

        print(f"   🤖 Agent {self.agent_id} sending: {asin} -> {new_price} ({reason})")
        await self.event_bus.publish(command)
        return command


async def run_demo_simulation():
    """Run the basic multi-agent simulation demo."""
    print("🚀 Starting FBA-Bench Simple Python Demo")
    print("=" * 50)
    print()

    # Setup
    print("🔧 Setting up demo environment...")
    event_bus = EventBusDemo()
    await event_bus.start()

    world_store = WorldStoreDemo(event_bus)
    await world_store.start()

    agent1 = AgentDemo("agent-001", event_bus)
    agent2 = AgentDemo("agent-002", event_bus)

    await agent1.start()
    await agent2.start()

    test_asin = "B001DEMO"
    initial_price = world_store.get_product_price(test_asin)  # Default $20.00

    print(f"✅ Demo ready: Product {test_asin} @ {initial_price}")
    print()

    try:
        # Demo 1: Basic Command Loop
        print("🧪 Demo 1: Basic Command - Agent 1 increases price")
        new_price = Money(2200)  # $22.00
        await agent1.send_price_command(test_asin, new_price, "Price increase")

        # Wait for processing
        await asyncio.sleep(0.1)

        final_price = world_store.get_product_price(test_asin)
        stats = world_store.get_statistics()

        print(f"   📊 Result: {initial_price} -> {final_price}")
        print(f"   📈 Commands processed: {stats['commands_processed']}")
        print(f"   📡 Agent 1 updates received: {len(agent1.price_updates_received)}")
        print(f"   📡 Agent 2 updates received: {len(agent2.price_updates_received)}")
        print()

        # Demo 2: Command Rejection
        print("🧪 Demo 2: Invalid Command - Agent 2 tries low price")
        invalid_price = Money(50)  # $0.50 - below min
        await agent2.send_price_command(test_asin, invalid_price, "Invalid low price")

        await asyncio.sleep(0.1)

        rejected_price = world_store.get_product_price(test_asin)
        rejected_stats = world_store.get_statistics()

        print(f"   📊 Price unchanged: {rejected_price}")
        print(f"   🚫 Commands rejected: {rejected_stats['commands_rejected']}")
        print()

        # Demo 3: Agent Competition
        print("🧪 Demo 3: Competition - Agents propose different prices")
        price_a = Money(2300)  # $23.00
        price_b = Money(2100)  # $21.00

        await agent1.send_price_command(test_asin, price_a, "Agent 1 competing")
        await agent2.send_price_command(test_asin, price_b, "Agent 2 competing")

        await asyncio.sleep(0.1)

        competition_price = world_store.get_product_price(test_asin)
        competition_stats = world_store.get_statistics()

        print(f"   📊 Final price after competition: {competition_price}")
        print(f"   📈 Total processed: {competition_stats['commands_processed']}")
        print()

        # Summary
        print("📋 DEMO SUMMARY")
        print("=" * 30)
        print(
            f"Product {test_asin}: Started @ {initial_price}, Ended @ {world_store.get_product_price(test_asin)}"
        )
        print(f"WorldStore Stats: {world_store.get_statistics()}")
        print(f"Agent 1 Events: {len(agent1.price_updates_received)}")
        print(f"Agent 2 Events: {len(agent2.price_updates_received)}")

        print("\n🎉 Demo completed successfully!")
        print("✅ Event bus propagates events to all subscribers")
        print("✅ WorldStore arbitrates and validates commands")
        print("✅ Agents receive updates and can compete")
        print(
            "\nThis demonstrates the core architecture. For full simulations, use the API or CLI."
        )

    finally:
        await event_bus.stop()
        print("\n🧹 Demo environment cleaned up")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python scripts/simple_python_demo.py")
        print("No arguments needed. Runs the basic multi-agent demo.")
        sys.exit(0)
    asyncio.run(run_demo_simulation())
