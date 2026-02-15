# Agent-Based Consumer Modeling

## Overview

In `agent_mode`, FBA-Bench replaces the standard demand curve formula with an **Agent-Based Consumer Model**. Instead of abstract math, your agent competes for the attention of individual, autonomous shopper agents.

## How It Works

The `MarketSimulationService` (`src/services/market_simulator.py`) manages a `CustomerPool`.

### The Utility Function
Each shopper agent makes purchase decisions based on a multi-variable **Utility Score**:

$$ U = \alpha \cdot P + \beta \cdot R + \gamma \cdot S + \epsilon $$

Where:
*   $P$ (Price): Sensitivity varies by customer segment.
*   $R$ (Reviews): Impact of star rating and review count ($log(N)$).
*   $S$ (Speed): Shipping days (Prime vs. Standard).
*   $\epsilon$ (Noise): Random behavioral variance.

### The "Shopping" Tick
1.  **Sampling**: A subset of the customer pool "enters the market" each tick.
2.  **Evaluation**: Customers evaluate available products (yours vs. competitors).
3.  **Threshold**: Purchases only occur if $U > U_{threshold}$.

## Strategic Implications

This model creates realistic non-linear dynamics:

*   **Review Moats**: You can charge a premium if your review count is significantly higher than competitors.
*   **Marketing Efficacy**: Marketing spend ($) increases your visibility—expanding the pool of customers who evaluate your offer—rather than directly buying sales.
*   **Customer Segmentation**: Different customers have different utility weights (e.g., "Price Sensitive" vs. "Time Sensitive"), rewarding targeted strategies.
