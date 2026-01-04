# Campaign Concept: The "Loss Porn" Stress Test 📉💥

**Status:** Concept Phase  
**Target:** AI Researchers, FinTech CTOs, Twitter/X Crypto/Finance Community  
**Goal:** Viral attention for FBA-Bench by showing "Smarter" models failing spectacularly in realistic financial crises.

---

## The Hook

> "We gave GPT-5.2 $10 Million and a Ledger. It went bankrupt in 45 minutes."

Benchmarks usually show green checkmarks. We want to show **Red Candles**. 
We are building the **"Dark Souls" of Financial Agent Benchmarks**.

---

## The Scenarios

### 1. The "Powell Pivot" (Macro Shock)
*   **Setup:** Agent manages a bond portfolio.
*   **Event:** Fed unexpectedly raises rates by 75bps. 
*   **Win Condition:** Agent hedges duration immediately.
*   **Loss Porn:** Agent holds long duration, portfolio drops 15%, margin call triggers, agent panic-sells at the bottom.
*   **Visual:** A liquidation email notification screenshot.

### 2. The "Short Squeeze" (Market Structure)
*   **Setup:** Agent is short a "dying" retail stock (e.g., GAME).
*   **Event:** Social sentiment spikes 400% (simulated Twitter feed input).
*   **Win Condition:** Cover early or buy calls.
*   **Loss Porn:** Agent doubles down on shorts based on "fundamentals", gets liquidated by retail flow.

### 3. The "Fat Finger" (Operational Risk)
*   **Setup:** Simple trade execution.
*   **Event:** A glitch in the specific `OrderEntry` tool swaps "Price" and "Quantity".
*   **Win Condition:** Agent creates a sanity check before confirming.
*   **Loss Porn:** Agent buys 50,000 units at $1000 instead of 1000 units at $50. Immediate insolvency.

---

## Execution Plan

1.  **Configure `Tier 2 Advanced`**: Ensure `InterestRateHikeEvent` and `SocialSentimentSpike` are enabled in `configs/tier_2_advanced.yaml`.
2.  **Run the Benchmark**: Focus on **Liquidation Events**.
3.  **The "Kill Feed" Dashboard**: A live-updated webpage showing real-time agent PnL and bankruptcy declarations.
    *   *Headline:* "Grok just lost $2M on a bad cocoa futures trade."
4.  **Content Output**: 
    *   Short video clips of the "Terminal" showing the agent's frantic logs trying to cover positions.
    *   Post-mortem blog posts: "Why Gemini Panicked: An Anatomy of a Crash."

---

## Why This Gets Attention
*   **Schadenfreude:** People love seeing "smart" AI make human mistakes.
*   **Realism:** This tests *survival*, not just "reasoning".
*   **High Stakes:** Financial loss is universally understood.

**Next Step:** Implement the `Tier 2` shocks in `src/fba_bench_core/services/world_store/events.py` and run the simulation.
