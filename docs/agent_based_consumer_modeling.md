# Agent-Based Consumer Modeling: Beyond Elasticity Curves

> [!IMPORTANT]
> The Agent-Based Consumer Modeling features described here require the **RealSimulationRunner** and a correctly instantiated **MarketSimulationService**. They are **dormant** in the standard `run_gemini_benchmark.py` CLI benchmark, which uses a simplified elasticity model.

## Overview

FBA-Bench Enterprise features an advanced Agent-Based Consumer (ABC) model. This replaces simplistic demand curves (e.g., "if price drops 10%, sales rise 5%") with **individual shopper agents** who make decisions based on heterogeneous utility functions.

Why this matters:
*   **Realistic Noise:** Demand isn't smooth; one bad review can tank a product even if the price is low.
*   **Brand Loyalty:** Shoppers can form preferences over time.
*   **Non-Linearity:** Pricing wars and review moats emerge organically from agent interactions.

## Mechanism: Utility Theory

Each `Customer` agent in the `CustomerPool` calculates a **Utility Score (U)** for a product offering based on weighted factors:

$$ U = w_{price} \times f(Price) + w_{reviews} \times f(Reviews) + w_{shipping} \times f(Shipping) + \epsilon $$

Where:
*   $w_{x}$: Weight (sensitivity) of the customer to factor $x$.
*   $f(x)$: Normalized score (e.g., lower price = higher score).
*   $\epsilon$: Random noise/whim factor.

### Decision Threshold
If $U > Threshold_{purchase}$, the customer buys the product.

## Customer Segments

The `CustomerPool` generates diverse agents with varying weights:

1.  **Price Sensitive:** High $w_{price}$. Will switch brands for a $0.50 discount.
2.  **Quality Seekers:** High $w_{reviews}$. Will pay a premium for 4.5+ stars.
3.  **Loyalists:** High brand affinity (if configured). Stick to known ASINs unless utility drops significantly.
4.  **Impulse Buyers:** High $\epsilon$, low $Threshold_{purchase}$. Unpredictable.

## Impact on Benchmarks

This model fundamentally changes optimal agent strategies:

*   **Review Moats:** An agent learns to aggressively gather early reviews (even at a loss) to build a high $f(Reviews)$ score, capturing the "Quality Seeker" segment permanently.
*   **Dynamic Pricing:** Slashing prices might not work if the product has 1 star (low $f(Reviews)$ drags down $U$ below threshold regardless of price).
*   **Shipping Speed:** Fast shipping becomes a competitive lever against lower-priced rivals.

## Configuration

To enable Agent-Based Modeling in your simulation config:

```yaml
market_simulation:
  mode: "agent_based" # vs "elasticity"
  customer_pool_size: 1000
  daily_active_users: 0.1 # 10% of pool shops daily
```

## Implementation Details

*   **Customer Logic:** `src/fba_bench_core/domain/market/customer.py`
    *   Class: `Customer`, `CustomerPool`
    *   Method: `calculate_utility`, `decide_purchase`
*   **Market Service:** `src/services/market_simulator.py`
    *   Method: `_demand_agent_based`
