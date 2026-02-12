from __future__ import annotations

import textwrap
from decimal import Decimal

from run_grok_proper_sim import MarketSimulator, Order, _load_realism_config


def test_load_realism_config_deep_merges_override(tmp_path) -> None:
    cfg_file = tmp_path / "realism.yaml"
    cfg_file.write_text(
        textwrap.dedent(
            """
            cost_model:
              daily_platform_overhead: 15.0
            seasonality:
              weekend_multiplier: 1.2
            supplier_lanes:
              delay_days_min: 2
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = _load_realism_config(str(cfg_file))

    assert cfg["cost_model"]["daily_platform_overhead"] == 15.0
    assert cfg["seasonality"]["weekend_multiplier"] == 1.2
    # Should keep defaults not supplied in override.
    assert "profiles_by_category" in cfg["returns"]
    assert cfg["supplier_lanes"]["delay_days_min"] == 2


def test_seasonal_demand_factor_differs_between_windows() -> None:
    sim = MarketSimulator(seed=61)
    audio = sim.state.products["P001"]  # category: audio

    q4_factor = sim._seasonal_demand_factor(day=340, product=audio)
    spring_factor = sim._seasonal_demand_factor(day=120, product=audio)
    january_factor = sim._seasonal_demand_factor(day=10, product=audio)

    assert q4_factor > spring_factor
    assert january_factor < spring_factor


def test_seasonal_return_factor_increases_post_holiday() -> None:
    sim = MarketSimulator(seed=67)
    audio = sim.state.products["P001"]
    order = Order(
        order_id="ORD-R-SEASON",
        sku="P001",
        quantity=1,
        max_price=audio.price + Decimal("5.00"),
    )
    audio.rating = 4.5

    post_holiday = sim._estimate_return_probability(product=audio, order=order, day=12)
    mid_year = sim._estimate_return_probability(product=audio, order=order, day=180)

    assert post_holiday > mid_year
