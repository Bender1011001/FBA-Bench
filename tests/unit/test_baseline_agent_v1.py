import asyncio
from datetime import datetime, timezone

import pytest

# Use importorskip to gracefully handle missing optional dependencies
money = pytest.importorskip("money")
Money = money.Money

# Try imports with fallback handling
try:
    from agents.baseline.baseline_agent_v1 import BaselineAgentV1
except ImportError:
    pytest.skip("BaselineAgentV1 not available", allow_module_level=True)

try:
    from fba_events.bus import EventBus
    from fba_events.backends import AsyncioQueueBackend
except ImportError:
    try:
        from event_bus import AsyncioQueueBackend, EventBus
    except ImportError:
        pytest.skip("EventBus not available", allow_module_level=True)

try:
    from fba_events.world_events import WorldStateSnapshotEvent
except ImportError:
    try:
        from events import WorldStateSnapshotEvent
    except ImportError:
        pytest.skip("WorldStateSnapshotEvent not available", allow_module_level=True)

try:
    from services.toolbox_api_service import ToolboxAPIService
    from services.toolbox_schemas import ObserveRequest
except ImportError:
    pytest.skip("ToolboxAPIService not available", allow_module_level=True)


@pytest.fixture
def event_bus():
    import asyncio

    bus = EventBus(AsyncioQueueBackend())

    # Start the bus in a sync-compatible way
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the async operations synchronously
    loop.run_until_complete(bus.start())
    bus.start_recording()

    yield bus

    # Cleanup
    try:
        loop.run_until_complete(bus.stop())
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def toolbox(event_bus: EventBus):
    import asyncio

    svc = ToolboxAPIService()

    # Start the service in a sync-compatible way
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the async operation synchronously
    loop.run_until_complete(svc.start(event_bus))

    return svc


async def seed_snapshot(
    event_bus: EventBus, asin: str, price_cents: int, conversion_rate: float
):
    snapshot = WorldStateSnapshotEvent(
        event_id="snap-baseline",
        timestamp=datetime.now(timezone.utc),
        snapshot_id="snapshot-baseline",
        tick_number=0,
        product_count=1,
        summary_metrics={
            "products": {
                asin: {
                    "price_cents": price_cents,
                    "inventory": 100,
                    "bsr": 1000,
                    "conversion_rate": conversion_rate,
                }
            }
        },
    )
    await event_bus.publish(snapshot)
    # allow async bus to process
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_low_conversion_decreases_price(
    event_bus: EventBus, toolbox: ToolboxAPIService
):
    asin = "B00BASL01"
    await seed_snapshot(event_bus, asin, 2000, 0.03)  # $20.00, low CR

    agent = BaselineAgentV1(agent_id="agent-1", toolbox=toolbox)
    resp = agent.decide(asin)
    assert resp is not None
    await asyncio.sleep(0.05)

    # Verify a SetPriceCommand was published with a lower price
    recorded = event_bus.get_recorded_events()
    cmd = next(
        e
        for e in recorded
        if e.get("event_type") == "SetPriceCommand" and e["data"]["asin"] == asin
    )
    # 5% decrease from 2000 -> 1900 cents
    assert cmd["data"]["new_price"] == str(Money(1900))
    # Also ensure toolbox observe reflects the starting state (price unchanged until WorldStore updates)
    obs = toolbox.observe(ObserveRequest(asin=asin))
    assert obs.found is True
    assert (
        obs.price.cents == 2000
    )  # cache remains at snapshot until ProductPriceUpdated


@pytest.mark.asyncio
async def test_high_conversion_increases_price(
    event_bus: EventBus, toolbox: ToolboxAPIService
):
    asin = "B00BASL02"
    await seed_snapshot(event_bus, asin, 2000, 0.25)  # $20.00, high CR

    agent = BaselineAgentV1(agent_id="agent-1", toolbox=toolbox)
    resp = agent.decide(asin)
    assert resp is not None
    await asyncio.sleep(0.05)

    recorded = event_bus.get_recorded_events()
    cmd = next(
        e
        for e in recorded
        if e.get("event_type") == "SetPriceCommand" and e["data"]["asin"] == asin
    )
    # 5% increase from 2000 -> 2100 cents
    assert cmd["data"]["new_price"] == str(Money(2100))


@pytest.mark.asyncio
async def test_no_data_returns_none(toolbox: ToolboxAPIService):
    agent = BaselineAgentV1(agent_id="agent-1", toolbox=toolbox)
    assert agent.decide("B00UNKNOWN") is None
