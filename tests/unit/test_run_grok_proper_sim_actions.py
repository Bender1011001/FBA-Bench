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


def test_generated_order_ids_are_unique_across_days() -> None:
    sim = MarketSimulator(seed=83)
    sim.state.day = 1
    day1_orders = sim.generate_daily_orders()
    ids_day1 = {order.order_id for order in day1_orders}

    sim.state.day = 2
    day2_orders = sim.generate_daily_orders()
    ids_day2 = {order.order_id for order in day2_orders}

    assert ids_day1
    assert ids_day2
    assert ids_day1.isdisjoint(ids_day2)
    assert sim.state.next_order_sequence == (len(day1_orders) + len(day2_orders))


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

    results = sim.apply_agent_decisions(
        decisions, orders=[], pre_day_adjustments=adjustments
    )

    assert results["returns_processed"] == 1
    assert results["refunds_paid"] == Decimal("25.00")
    assert results["salvage_recovered"] == Decimal("5.00")
    assert results["revenue"] == Decimal("-20.00")


def test_category_based_return_probability_is_higher_for_audio_than_accessories() -> (
    None
):
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


def test_demand_multiplier_recalculation_handles_overlapping_events() -> None:
    sim = MarketSimulator(seed=89)
    sku = "P001"
    product = sim.state.products[sku]
    sim.state.active_events = [
        AdversarialEvent(
            event_id="EVT-1-demand_spike",
            event_type="demand_spike",
            affected_sku=sku,
            severity=0.6,
            days_remaining=1,
            description="spike",
        ),
        AdversarialEvent(
            event_id="EVT-1-demand_crash",
            event_type="demand_crash",
            affected_sku=sku,
            severity=0.4,
            days_remaining=3,
            description="crash",
        ),
    ]

    sim._recalculate_demand_multipliers()
    expected_before = sim._demand_event_multiplier(
        "demand_spike", 0.6
    ) * sim._demand_event_multiplier(
        "demand_crash",
        0.4,
    )
    assert abs(product.demand_multiplier - expected_before) < 1e-9

    sim.update_events()
    expected_after = sim._demand_event_multiplier("demand_crash", 0.4)
    assert abs(product.demand_multiplier - expected_after) < 1e-9


def test_price_war_initial_shock_scales_with_severity() -> None:
    sku = "P001"
    sim_low = MarketSimulator(seed=97)
    sim_high = MarketSimulator(seed=97)

    low_event = AdversarialEvent(
        event_id="EVT-LOW-price_war",
        event_type="price_war",
        affected_sku=sku,
        severity=0.3,
        days_remaining=5,
        description="low severity price war",
    )
    high_event = AdversarialEvent(
        event_id="EVT-HIGH-price_war",
        event_type="price_war",
        affected_sku=sku,
        severity=1.0,
        days_remaining=5,
        description="high severity price war",
    )

    sim_low._apply_event_initial_effects(low_event)
    sim_high._apply_event_initial_effects(high_event)
    avg_low = sum(
        float(c.price) for c in sim_low.state.competitors if c.sku == sku
    ) / max(
        1,
        len([c for c in sim_low.state.competitors if c.sku == sku]),
    )
    avg_high = sum(
        float(c.price) for c in sim_high.state.competitors if c.sku == sku
    ) / max(
        1,
        len([c for c in sim_high.state.competitors if c.sku == sku]),
    )

    assert avg_high < avg_low


def test_price_war_active_pressure_affects_daily_competitor_evolution() -> None:
    sku = "P001"
    sim_base = MarketSimulator(seed=101)
    sim_war = MarketSimulator(seed=101)
    sim_war.state.active_events.append(
        AdversarialEvent(
            event_id="EVT-WAR-price_war",
            event_type="price_war",
            affected_sku=sku,
            severity=1.0,
            days_remaining=5,
            description="active price war",
        )
    )

    sim_base.evolve_competitor_prices()
    sim_war.evolve_competitor_prices()
    avg_base = sum(
        float(c.price) for c in sim_base.state.competitors if c.sku == sku
    ) / max(
        1,
        len([c for c in sim_base.state.competitors if c.sku == sku]),
    )
    avg_war = sum(
        float(c.price) for c in sim_war.state.competitors if c.sku == sku
    ) / max(
        1,
        len([c for c in sim_war.state.competitors if c.sku == sku]),
    )

    assert avg_war < avg_base


def test_review_bomb_severity_scales_rating_drop_and_recovery() -> None:
    sku = "P001"

    sim_low = MarketSimulator(seed=103)
    sim_low.state.products[sku].rating = 4.8
    low_event = AdversarialEvent(
        event_id="EVT-LOW-review_bomb",
        event_type="review_bomb",
        affected_sku=sku,
        severity=0.3,
        days_remaining=2,
        description="low severity review bomb",
    )
    sim_low._apply_event_initial_effects(low_event)
    low_drop = 4.8 - sim_low.state.products[sku].rating

    sim_high = MarketSimulator(seed=103)
    sim_high.state.products[sku].rating = 4.8
    high_event = AdversarialEvent(
        event_id="EVT-HIGH-review_bomb",
        event_type="review_bomb",
        affected_sku=sku,
        severity=1.0,
        days_remaining=2,
        description="high severity review bomb",
    )
    sim_high._apply_event_initial_effects(high_event)
    high_drop = 4.8 - sim_high.state.products[sku].rating

    assert high_drop > low_drop

    sim_recover_low = MarketSimulator(seed=107)
    sim_recover_low.state.products[sku].rating = 3.0
    sim_recover_low.state.active_events = [
        AdversarialEvent(
            event_id="EVT-END-LOW-review_bomb",
            event_type="review_bomb",
            affected_sku=sku,
            severity=0.3,
            days_remaining=1,
            description="ending low review bomb",
        )
    ]
    sim_recover_low.update_events()
    low_recovered = sim_recover_low.state.products[sku].rating

    sim_recover_high = MarketSimulator(seed=107)
    sim_recover_high.state.products[sku].rating = 3.0
    sim_recover_high.state.active_events = [
        AdversarialEvent(
            event_id="EVT-END-HIGH-review_bomb",
            event_type="review_bomb",
            affected_sku=sku,
            severity=1.0,
            days_remaining=1,
            description="ending high review bomb",
        )
    ]
    sim_recover_high.update_events()
    high_recovered = sim_recover_high.state.products[sku].rating

    assert high_recovered > low_recovered
