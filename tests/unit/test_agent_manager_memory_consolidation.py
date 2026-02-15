from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from money import Money

from agent_runners.agent_manager import AgentManager
from agent_runners.base_runner import AgentRunner
from fba_events.bus import InMemoryEventBus
from fba_events.pricing import SetPriceCommand
from fba_events.time_events import TickEvent


class _RecordingRunner(AgentRunner):
    def __init__(self, agent_id: str, config: Dict[str, Any] | None = None) -> None:
        super().__init__(agent_id, config or {})
        self.consolidations: List[Dict[str, Any]] = []

    def _do_initialize(self) -> None:
        return None

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # No-op decision payload; AgentManager will still emit an AgentDecisionEvent and
        # capture tool calls for memory reflection inputs.
        return {"decisions": [], "meta": {"tick": int(context.get("tick", 0))}}

    async def consolidate_memory(self, context: Dict[str, Any]) -> None:
        self.consolidations.append(dict(context))


async def _wait_until(pred, *, timeout_s: float = 1.0) -> None:
    started = time.monotonic()
    while time.monotonic() - started < timeout_s:
        if pred():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Timed out waiting for condition")


@pytest.mark.asyncio
async def test_agent_manager_calls_consolidate_memory_once_per_day() -> None:
    bus = InMemoryEventBus()
    manager = AgentManager(event_bus=bus)
    runner = _RecordingRunner("A1", {})
    reg = manager.agent_registry.add_agent("A1", runner, "test", {})
    # Avoid running the non-LLM skills pipeline (it expects WorldStore wiring).
    reg.is_llm_only = True

    await manager.start()

    now = datetime.now(timezone.utc)
    await bus.publish(
        TickEvent(
            event_id="tick-0",
            timestamp=now,
            tick_number=0,
            simulation_time=now,
            metadata={},
        )
    )
    await asyncio.sleep(0.05)

    await bus.publish(
        SetPriceCommand(
            event_id="sp-0",
            timestamp=now,
            agent_id="A1",
            asin="B000TEST",
            new_price=Money(1234),
            reason="test",
        )
    )
    await asyncio.sleep(0.05)

    await bus.publish(
        TickEvent(
            event_id="tick-1",
            timestamp=now,
            tick_number=1,
            simulation_time=now,
            metadata={},
        )
    )
    await _wait_until(lambda: len(runner.consolidations) >= 1)

    await bus.publish(
        TickEvent(
            event_id="tick-2",
            timestamp=now,
            tick_number=2,
            simulation_time=now,
            metadata={},
        )
    )
    await _wait_until(lambda: len(runner.consolidations) >= 2)

    ticks = [int(c.get("tick", -1)) for c in runner.consolidations]
    assert ticks[:2] == [0, 1]

    day0 = runner.consolidations[0]
    recent_events = day0.get("recent_events") or []
    assert any(e.get("event_type") == "SetPriceCommand" for e in recent_events)

    await manager.stop()
    await bus.stop()
