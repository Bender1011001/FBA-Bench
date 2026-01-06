import asyncio
from datetime import datetime

import pytest
from money import Money
from services.market_simulator import MarketSimulationService
from services.world_store import WorldStore

from fba_events.time_events import TickEvent
from fba_events.bus import InMemoryEventBus as EventBus, set_event_bus
from fba_events.pricing import SetPriceCommand


@pytest.mark.asyncio
async def test_market_simulator_demand_and_sale_and_inventory_update():
    # Arrange: event bus and world store
    bus = EventBus()
    await bus.start()
    await bus.start_recording()
    set_event_bus(bus)

    world_store = WorldStore(event_bus=bus)
    await world_store.start()

    # Create market simulator with deterministic params
    base_demand = 50
    elasticity = 1.2
    market = MarketSimulationService(
        world_store=world_store,
        event_bus=bus,
        base_demand=base_demand,
        demand_elasticity=elasticity,
    )
    await market.start()

    # Initialize product
    asin = "UNIT-TEST-ASIN-001"
    initial_price = Money.from_dollars("20.00")
    initial_inventory = 1000
    world_store.initialize_product(
        asin, initial_price, initial_inventory=initial_inventory
    )

    # Act 1: agent sets the same price (so ref price == current price) -> demand == base_demand
    set_price_cmd = SetPriceCommand(
        event_id="spc-1",
        timestamp=datetime.now(),
        agent_id="agent-ut",
        asin=asin,
        new_price=initial_price,
    )
    await bus.publish(set_price_cmd)
    # Allow arbitration to apply price
    await asyncio.sleep(0.02)

    # Publish an initial TickEvent that aligns simulation_time
    await bus.publish(
        TickEvent(
            event_id="t0",
            timestamp=datetime.now(),
            tick_number=0,
            simulation_time=datetime.now(),
        )
    )
    await asyncio.sleep(0.02)

    # Process market for ASIN
    await market.process_for_asin(asin)
    await asyncio.sleep(0.02)

    recorded = await bus.get_recorded_events()
    # Assert sale occurred for asin
    sale_events = [
        e
        for e in recorded
        if e.get("event_type") == "SaleOccurred"
        and e.get("data", {}).get("asin") == asin
    ]
    assert sale_events, "Expected a SaleOccurred event"

    # Assert units_demanded == base_demand (price/ref == 1.0)
    last_sale = sale_events[-1]
    assert (
        last_sale["data"]["units_demanded"] == base_demand
    ), f"Expected units_demanded to equal base_demand={base_demand}"

    # Assert inventory decreased
    inv_after_first = world_store.get_product_inventory_quantity(asin)
    assert inv_after_first < initial_inventory, "Inventory should decrease after sale"

    # Act 2: apply marketing visibility and ensure demand scales by multiplier
    # Set marketing visibility to 2.0 and process again
    if hasattr(world_store, "set_marketing_visibility"):
        world_store.set_marketing_visibility(asin, 2.0)
    await market.process_for_asin(asin)
    await asyncio.sleep(0.02)

    recorded2 = await bus.get_recorded_events()
    sale_events2 = [
        e
        for e in recorded2
        if e.get("event_type") == "SaleOccurred"
        and e.get("data", {}).get("asin") == asin
    ]
    assert sale_events2, "Expected another SaleOccurred event after marketing boost"
    last_sale2 = sale_events2[-1]
    # Demand should be approximately doubled (integer rounding)
    assert (
        last_sale2["data"]["units_demanded"] == base_demand * 2
    ), "Marketing visibility multiplier should scale demand"

    # Assert inventory decreased further
    inv_after_second = world_store.get_product_inventory_quantity(asin)
    assert (
        inv_after_second < inv_after_first
    ), "Inventory should continue to decrease after subsequent sale"
