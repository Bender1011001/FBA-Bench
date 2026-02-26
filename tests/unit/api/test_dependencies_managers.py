import asyncio
import uuid

import pytest
from api.dependencies import ConnectionManager, ExperimentManager, SimulationManager


@pytest.mark.asyncio
async def test_simulation_manager_add_get_remove():
    mgr = SimulationManager()

    # Create a fake orchestrator with minimal get_status
    class _FakeOrchestrator:
        def __init__(self, name: str):
            self._name = name

        def get_status(self):
            return {"name": self._name, "status": "ok"}

    sim_id = "sim-" + uuid.uuid4().hex[:8]
    orch = _FakeOrchestrator("orch1")

    # add
    await mgr.add_orchestrator(sim_id, orch)
    # get
    got = await mgr.get_orchestrator(sim_id)
    assert got is orch
    # status
    status = mgr.get_simulation_status(sim_id)
    assert status == {"name": "orch1", "status": "ok"}
    # list ids
    assert sim_id in mgr.get_all_simulation_ids()
    # remove
    await mgr.remove_orchestrator(sim_id)
    assert sim_id not in mgr.get_all_simulation_ids()


@pytest.mark.asyncio
async def test_simulation_manager_concurrent_add_get():
    mgr = SimulationManager()

    class _FakeOrchestrator:
        def __init__(self, idx: int):
            self.idx = idx

        def get_status(self):
            return {"idx": self.idx}

    sim_ids = [f"sim-{i}" for i in range(25)]
    orchs = [_FakeOrchestrator(i) for i in range(25)]

    async def add_task(i: int):
        await mgr.add_orchestrator(sim_ids[i], orchs[i])

    async def get_task(i: int):
        o = await mgr.get_orchestrator(sim_ids[i])
        assert o is orchs[i]

    # Concurrently add
    await asyncio.gather(*[add_task(i) for i in range(len(sim_ids))])
    # Concurrently get
    await asyncio.gather(*[get_task(i) for i in range(len(sim_ids))])

    # Validate list
    ids = set(mgr.get_all_simulation_ids())
    assert set(sim_ids) == ids


@pytest.mark.asyncio
async def test_experiment_manager_set_get_remove():
    mgr = ExperimentManager()

    class _FakeExperimentManager:
        def __init__(self, eid: str):
            self.eid = eid

    exp_id = "exp-" + uuid.uuid4().hex[:8]
    exp_mgr = _FakeExperimentManager(exp_id)

    await mgr.set(exp_id, exp_mgr)
    got = await mgr.get(exp_id)
    assert got is exp_mgr
    assert exp_id in mgr.list_ids()

    await mgr.remove(exp_id)
    assert exp_id not in mgr.list_ids()
    # Ensure remove of non-existing is safe
    await mgr.remove(exp_id)


def test_connection_manager_stats_dynamic_categories():
    cm = ConnectionManager(max_connections=10)

    # Fabricate two "websocket" keys (we won't call methods on them)
    ws1 = object()
    ws2 = object()

    # Simulate active connections list and metadata
    cm.active_connections.extend([ws1, ws2])
    cm.connection_metadata[ws1] = {
        "client_id": "c1",
        "connected_at": "t1",
        "last_activity": "t1",
    }
    cm.connection_metadata[ws2] = {
        "client_id": "c2",
        "connected_at": "t2",
        "last_activity": "t2",
    }

    # Add dynamic subscriptions (no hardcoded categories)
    cm.connection_subscriptions[ws1] = {"alpha", "beta"}
    cm.connection_subscriptions[ws2] = {"beta", "gamma"}

    stats = cm.get_connection_stats()
    assert stats["total_connections"] == 2
    # Subscriptions should be computed dynamically and contain all keys
    assert set(stats["subscriptions"].keys()) == {"alpha", "beta", "gamma"}
    # Counts should reflect membership
    assert stats["subscriptions"]["alpha"] == 1
    assert stats["subscriptions"]["beta"] == 2
    assert stats["subscriptions"]["gamma"] == 1

    # Ensure connections array carries subscriptions for each connection
    per_conn = {c["client_id"]: set(c["subscriptions"]) for c in stats["connections"]}
    assert per_conn["c1"] == {"alpha", "beta"}
    assert per_conn["c2"] == {"beta", "gamma"}


# Additional concurrency and capacity tests for ConnectionManager

import json  # noqa: E402

import pytest  # noqa: E402


class _FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_texts = []

    async def accept(self):
        self.accepted = True

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True

    async def send_text(self, message: str):
        # Simulate successful send
        self.sent_texts.append(message)


@pytest.mark.asyncio
async def test_connection_manager_capacity_and_broadcast_concurrency():
    cm = ConnectionManager(max_connections=5)

    # Create a batch of fake websockets exceeding capacity
    sockets = [_FakeWebSocket() for _ in range(20)]

    # Attempt to connect all concurrently
    results = await asyncio.gather(*[cm.connect(ws, origin="test") for ws in sockets])

    # Count accepted vs rejected
    accepted = [ws for ws in sockets if ws.accepted and not ws.closed]
    rejected = [ws for ws in sockets if not ws.accepted or ws.closed]

    # Capacity must not be exceeded
    assert len(accepted) <= 5
    assert len(cm.active_connections) == len(accepted)

    # Broadcast an event; only accepted connections should receive it
    payload = {"type": "unit-test", "ok": True}
    await cm.broadcast_event(payload)

    for ws in accepted:
        assert len(ws.sent_texts) == 1
        # verify serialization is JSON
        json.loads(ws.sent_texts[0])

    for ws in rejected:
        assert len(ws.sent_texts) == 0

    # Disconnect all accepted sockets and ensure cleanup
    for ws in list(accepted):
        cm.disconnect(ws)

    assert len(cm.active_connections) == 0
    assert not cm.connection_metadata
    assert not cm.connection_subscriptions
