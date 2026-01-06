from decimal import Decimal

import pytest

TOL = Decimal("0.00")


@pytest.mark.asyncio
@pytest.mark.parametrize("seed,days", [(0, 30), (42, 365)])
async def test_accounting_identity_every_tick(sim_factory, seed, days):
    sim = await sim_factory(seed=seed)
    audit = await sim.run_and_audit(days=days)
    for t in audit.ticks:
        assert t.debit_sum == t.credit_sum, f"Trial balance broke on day {t.day}"
        assert t.assets == t.liabilities + t.equity, f"A=L+E broke on day {t.day}"
        # Change in equity should equal net income (since owner contributions are already in equity)
        delta_equity = t.equity - audit.initial_equity
        assert (
            delta_equity == t.net_income_to_date
        ), f"Equity/NI mismatch on day {t.day}"


@pytest.mark.asyncio
async def test_no_negative_inventory_units(sim_factory):
    sim = await sim_factory(seed=1)
    audit = await sim.run_and_audit(days=120)
    for t in audit.ticks:
        for sku, units in t.inventory_units_by_sku.items():
            assert units >= 0, f"Negative units for {sku} on day {t.day}"


@pytest.mark.asyncio
async def test_fee_engine_closure(sim_factory):
    sim = await sim_factory(seed=9)
    sim.enable_fee_audits(True)
    audit = await sim.run_and_audit(days=90)
    for violation in audit.violations:
        assert "fee_mismatch" not in violation, violation


@pytest.mark.asyncio
async def test_rng_isolation(monkeypatch, sim_factory):
    # Fail hard if any code path touches the global random.*
    import random

    def _forbidden(*args, **kwargs):
        raise AssertionError("Global random.* used")

    monkeypatch.setattr(random, "random", _forbidden)
    monkeypatch.setattr(random, "randint", _forbidden)
    sim = await sim_factory(seed=123)
    await sim.run_and_audit(days=10)  # should pass with isolated rng
