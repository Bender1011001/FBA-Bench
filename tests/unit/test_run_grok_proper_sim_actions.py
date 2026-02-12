from __future__ import annotations

from run_grok_proper_sim import MarketSimulator


def test_supplier_orders_create_inbound_po_and_cost() -> None:
    sim = MarketSimulator(seed=7)
    start_capital = sim.state.capital

    decisions = {
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [{"sku": "P001", "quantity": 80}],
        "ad_budget_shift": {},
        "customer_ops": {},
    }
    results = sim.apply_agent_decisions(decisions, orders=[])

    assert results["supplier_orders_placed"] >= 1
    assert len(sim.state.pending_inbound_orders) >= 1
    assert sim.state.capital < start_capital
    assert results["costs"] > 0


def test_inbound_orders_arrive_and_increase_stock() -> None:
    sim = MarketSimulator(seed=11)
    decisions = {
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [{"sku": "P001", "quantity": 100}],
        "ad_budget_shift": {},
        "customer_ops": {},
    }
    sim.apply_agent_decisions(decisions, orders=[])
    assert sim.state.pending_inbound_orders

    before_stock = sim.state.products["P001"].stock
    sim.state.pending_inbound_orders[0].days_until_arrival = 0
    events = sim.process_inbound_orders()
    after_stock = sim.state.products["P001"].stock

    assert events
    assert after_stock >= before_stock


def test_ad_budget_shift_sets_next_day_boost_and_tracks_spend() -> None:
    sim = MarketSimulator(seed=3)

    decisions = {
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [],
        "ad_budget_shift": {"P001": 60.0},
        "customer_ops": {},
    }
    results = sim.apply_agent_decisions(decisions, orders=[])

    assert float(results["ad_spend"]) > 0.0
    assert sim.state.products["P001"].next_day_ad_boost > 1.0
    assert float(sim.state.total_ad_spend) > 0.0
    assert sim.state.daily_ad_spend


def test_customer_ops_reduces_backlog() -> None:
    sim = MarketSimulator(seed=19)
    sim.state.customer_backlog["P001"] = 18
    before = sim.state.customer_backlog["P001"]

    decisions = {
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [],
        "ad_budget_shift": {},
        "customer_ops": {"P001": "proactive"},
    }
    results = sim.apply_agent_decisions(decisions, orders=[])
    after = sim.state.customer_backlog["P001"]

    assert results["service_tickets_resolved"] > 0
    assert after < before
