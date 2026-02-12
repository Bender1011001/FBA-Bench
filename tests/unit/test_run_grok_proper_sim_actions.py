from __future__ import annotations

from decimal import Decimal

from run_grok_proper_sim import (
    AdversarialEvent,
    MarketSimulator,
    Order,
    PendingInboundOrder,
    PendingReturn,
)


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


def test_accept_all_orders_handles_orders_not_listed_by_id() -> None:
    sim = MarketSimulator(seed=23)
    product = sim.state.products["P001"]
    product.stock = 10

    orders = [
        Order(
            order_id="ORD-UNSEEN-1",
            sku="P001",
            quantity=1,
            max_price=product.price + Decimal("10.00"),
        )
    ]
    decisions = {
        "reasoning": "Fulfill all demand unless blocked.",
        "accept_all_orders": True,
        "accept_skus": [],
        "reject_skus": [],
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [],
        "ad_budget_shift": {},
        "customer_ops": {},
    }
    results = sim.apply_agent_decisions(decisions, orders=orders)

    assert results["orders_fulfilled"] == 1
    assert results["orders_rejected"] == 0


def test_state_days_remaining_uses_total_days_setting() -> None:
    sim = MarketSimulator(seed=31)
    sim.state.day = 3
    sim.state.total_days = 10
    state = sim.get_state_for_agent(orders=[])

    assert state["total_days"] == 10
    assert state["days_remaining"] == 7


def test_fulfillment_and_payment_fees_are_recorded() -> None:
    sim = MarketSimulator(seed=29)
    product = sim.state.products["P002"]
    product.stock = 10
    orders = [
        Order(
            order_id="ORD-FEE-1",
            sku="P002",
            quantity=2,
            max_price=product.price + Decimal("5.00"),
        )
    ]
    decisions = {
        "accept_all_orders": True,
        "accept_skus": [],
        "reject_skus": [],
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [],
        "ad_budget_shift": {},
        "customer_ops": {},
    }
    results = sim.apply_agent_decisions(decisions, orders=orders)

    assert results["orders_fulfilled"] == 1
    assert results["fulfillment_fees"] > 0
    assert results["payment_processing_fees"] > 0
    assert results["costs"] >= (
        results["fulfillment_fees"]
        + results["payment_processing_fees"]
        + results["fixed_operating_cost"]
    )


def test_opening_equity_includes_inventory_value() -> None:
    sim = MarketSimulator(seed=41)
    expected_equity = sim.state.capital + sim.state.starting_inventory_value

    assert sim.state.starting_equity == expected_equity
    assert sim.state.starting_inventory_value > 0


def test_pending_refund_exposure_reduces_equity() -> None:
    sim = MarketSimulator(seed=71)
    baseline_equity = sim.state.get_equity()
    sim.state.pending_returns.append(
        PendingReturn(
            return_id="RET-LIAB-1",
            order_id="ORD-LIAB-1",
            sku="P001",
            quantity=1,
            refund_amount=Decimal("30.00"),
            days_until_resolution=3,
            restockable=False,
            recovery_rate=0.0,
        )
    )

    assert sim.state.get_pending_refund_exposure() == Decimal("30.00")
    assert sim.state.get_equity() == baseline_equity - Decimal("30.00")


def test_process_pending_returns_refunds_and_restocks() -> None:
    sim = MarketSimulator(seed=43)
    before_capital = sim.state.capital
    before_stock = sim.state.products["P001"].stock
    sim.state.pending_returns.append(
        PendingReturn(
            return_id="RET-T-1",
            order_id="ORD-T-1",
            sku="P001",
            quantity=2,
            refund_amount=Decimal("39.98"),
            days_until_resolution=0,
            restockable=True,
            recovery_rate=1.0,
        )
    )

    adjustment = sim.process_pending_returns()

    assert adjustment["returns_processed"] == 1
    assert adjustment["refunds_paid"] > 0
    assert sim.state.capital < before_capital
    assert sim.state.products["P001"].stock >= before_stock
    assert not sim.state.pending_returns


def test_partial_refund_stays_pending_without_double_restock() -> None:
    sim = MarketSimulator(seed=73)
    sim.state.capital = Decimal("10.00")
    start_stock = sim.state.products["P001"].stock
    sim.state.pending_returns.append(
        PendingReturn(
            return_id="RET-PART-1",
            order_id="ORD-PART-1",
            sku="P001",
            quantity=2,
            refund_amount=Decimal("39.98"),
            days_until_resolution=0,
            restockable=True,
            recovery_rate=1.0,
        )
    )

    first = sim.process_pending_returns()
    assert first["returns_processed"] == 1
    assert first["refunds_paid"] == Decimal("10.00")
    assert len(sim.state.pending_returns) == 1
    assert sim.state.pending_returns[0].refund_amount == Decimal("29.98")
    assert sim.state.pending_returns[0].inventory_reconciled is True
    stock_after_first = sim.state.products["P001"].stock
    assert stock_after_first == start_stock + 2

    sim.state.capital = Decimal("40.00")
    second = sim.process_pending_returns()
    assert second["returns_processed"] == 0
    assert second["refunds_paid"] == Decimal("29.98")
    assert not sim.state.pending_returns
    assert sim.state.products["P001"].stock == stock_after_first


def test_apply_agent_decisions_applies_external_return_adjustments() -> None:
    sim = MarketSimulator(seed=47)
    decisions = {
        "accept_all_orders": False,
        "accept_orders": [],
        "price_changes": {},
        "restock": {},
        "supplier_orders": [],
        "ad_budget_shift": {},
        "customer_ops": {},
    }
    adjustments = {
        "returns_processed": 1,
        "refunds_paid": Decimal("25.00"),
        "salvage_recovered": Decimal("5.00"),
        "events": ["return adjustment applied"],
    }

    results = sim.apply_agent_decisions(decisions, orders=[], pre_day_adjustments=adjustments)

    assert results["returns_processed"] == 1
    assert results["refunds_paid"] == Decimal("25.00")
    assert results["salvage_recovered"] == Decimal("5.00")
    assert results["revenue"] == Decimal("-20.00")


def test_category_based_return_probability_is_higher_for_audio_than_accessories() -> None:
    sim = MarketSimulator(seed=53)
    audio = sim.state.products["P001"]
    accessory = sim.state.products["P007"]
    audio.rating = 4.5
    accessory.rating = 4.5

    audio_order = Order(
        order_id="ORD-RISK-A",
        sku="P001",
        quantity=1,
        max_price=audio.price + Decimal("5.00"),
    )
    accessory_order = Order(
        order_id="ORD-RISK-B",
        sku="P007",
        quantity=1,
        max_price=accessory.price + Decimal("5.00"),
    )

    audio_risk = sim._estimate_return_probability(audio, audio_order)
    accessory_risk = sim._estimate_return_probability(accessory, accessory_order)

    assert audio_risk > accessory_risk


def test_supply_shock_can_delay_inbound_orders(monkeypatch) -> None:
    sim = MarketSimulator(seed=59)
    sim.state.pending_inbound_orders = [
        PendingInboundOrder(
            po_id="PO-T-1",
            supplier_id="SUP-P001-1",
            sku="P001",
            quantity=50,
            unit_cost=Decimal("15.00"),
            reliability=0.9,
            days_until_arrival=5,
            lane="overseas_ocean",
        )
    ]
    sim.state.active_events.append(
        AdversarialEvent(
            event_id="EVT-1-supply_shock",
            event_type="supply_shock",
            affected_sku="P001",
            severity=1.0,
            days_remaining=5,
            description="test supply shock",
        )
    )

    monkeypatch.setattr(sim.rng, "random", lambda: 0.0)
    monkeypatch.setattr(sim.rng, "randint", lambda _a, _b: 2)

    events = sim.process_inbound_orders()

    assert any("Supplier delay" in e for e in events)
    assert sim.state.total_supplier_delay_events == 1
    assert sim.state.total_supplier_delay_days == 2
    assert sim.state.pending_inbound_orders[0].days_until_arrival == 6


def test_inbound_delay_respects_cumulative_delay_cap(monkeypatch) -> None:
    sim = MarketSimulator(seed=79)
    sim.state.pending_inbound_orders = [
        PendingInboundOrder(
            po_id="PO-CAP-1",
            supplier_id="SUP-P001-1",
            sku="P001",
            quantity=50,
            unit_cost=Decimal("15.00"),
            reliability=0.9,
            days_until_arrival=5,
            lane="overseas_ocean",
            cumulative_delay_days=13,
        )
    ]

    monkeypatch.setattr(sim.rng, "random", lambda: 0.0)
    monkeypatch.setattr(sim.rng, "randint", lambda _a, _b: 3)

    first_events = sim.process_inbound_orders()
    assert any("Supplier delay" in e for e in first_events)
    assert sim.state.pending_inbound_orders[0].cumulative_delay_days == 14
    assert sim.state.pending_inbound_orders[0].days_until_arrival == 5

    second_events = sim.process_inbound_orders()
    assert not any("Supplier delay" in e for e in second_events)
    assert sim.state.total_supplier_delay_events == 1
    assert sim.state.pending_inbound_orders[0].days_until_arrival == 4
