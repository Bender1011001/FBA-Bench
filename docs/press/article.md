# FBA-Bench: The Bankruptcy Test (and Why Most Benchmarks Miss the Point)

Most AI benchmarks are built like exams: a pile of static questions, a single turn, a score, and a leaderboard.
That is useful for measuring isolated capability, but it is not how agentic systems fail in the real world.

Real failures look like this:

1. A pricing decision that seemed "reasonable" yesterday triggers a competitor response today.
2. A restock that looked safe drains cash right before a supply shock.
3. A model that is brilliant in one-shot tasks slowly bleeds capital across weeks because it cannot manage state, risk, and compounding consequences.

If you want to know whether an LLM can survive a real operating environment, you need a benchmark that looks like an operating environment.

That is the thesis behind FBA-Bench Enterprise: a tick-based e-commerce simulation where the model makes at least one decision per simulated day, receives feedback, and carries the consequences forward. It is not about writing clean JSON once. It is about staying solvent.

## What FBA-Bench Actually Measures

FBA-Bench is an e-commerce business simulation benchmark: inventory, pricing, competitors, and adversarial market events (supply shocks, price wars, demand spikes/crashes). The objective is financial and measurable: maximize profit and avoid cash-flow death.

In the "LLM Benchmark" mode, the model is the agent. There is no hidden scaffolding to save it:

1. Each simulated day is a separate LLM call.
2. The model sees state (capital, inventory, competitor prices, events, incoming orders).
3. The model decides actions (accept/reject orders, price changes, restock).
4. The simulation applies the decisions and produces next-day feedback.

Repeat that 180 to 365+ times. Bad decisions compound. Good strategies emerge.

The output is a run record with objective metrics like:

1. Net profit and final capital.
2. ROI over the run window.
3. Number of LLM calls (one per day).
4. Token usage and response latency (because "fast and good" matters).

## Why This Is a "Real" Benchmark (in the Narrow Sense That Matters)

If your definition of "real benchmark" is "predicts whether an agent will survive a deployed, stateful, long-horizon task under uncertainty," most benchmarks are not even trying.

They miss three essential properties:

1. State: decisions must read and write a persistent world state.
2. Feedback: you must experience the consequences of your previous actions.
3. Compounding: failure is often slow (cash bleed, stockouts, margin collapse), not an instant wrong answer.

FBA-Bench forces those properties by design. It is an interactive loop, not a static test set.

This is also why it takes hours. A "thinking model" that takes 30 to 180 seconds per decision is not a bug in the benchmark. It is the cost of the thing you are measuring: deliberation, tool choice, and reliability across time.

## Two Benchmarks, One Clarity

FBA-Bench explicitly separates two questions:

1. "How good is the model as an agent with no crutches?" (LLM Benchmark)
2. "How good is my agent system design with memory/tools/RAG?" (Agent Benchmark)

Mix those up and your leaderboard becomes marketing. Split them and you get clarity.

## The Point of the Leaderboard

The leaderboard is not about claiming a universal IQ score. It is about tracking which models can:

1. Maintain stable behavior across long horizons.
2. Adapt to shocks without self-destructing.
3. Stay profitable under budget and latency constraints.

It is also why the site pulls from a JSON API snapshot (`docs/api/*.json`) rather than hardcoding results: runs are long, and you want progress visibility, not just final scores.

## What You Learn (That You Will Not See on Static Benchmarks)

A long-horizon simulation surfaces failure modes that one-shot tasks hide:

1. "Locally correct, globally fatal" decisions (e.g., restocking into a cash crunch).
2. Overreacting to noise (price thrashing, inventory oscillation).
3. Event handling under stress (price wars + supply shocks).
4. Reliability of structured outputs under time pressure.

And because the metric is profit, you cannot "prompt engineer" your way into a higher score without actually running a better business.

## Reproducibility (What Keeps It Honest)

FBA-Bench runs are configured from `simulation_settings.yaml` with a seed and scenario definition. The result artifacts are written as JSON. That means:

1. You can re-run the same scenario and compare deltas.
2. You can publish the raw run record and let others inspect it.
3. You can add stricter scenarios without changing the scoring philosophy.

## Where This Goes Next

The core question is simple: can a model survive a recession-like environment as a business operator?

From there, the roadmap is obvious:

1. More realistic operational constraints (shipping delays, refunds, ad spend, procurement lead times).
2. Multi-agent dynamics (competitors that learn, not just reprice).
3. Stronger "adversarial" tiers that combine shocks and compliance traps.
4. Better live publishing (true live APIs rather than static snapshots).

If you are building agents for real workflows, you do not need a benchmark that flatters the model.
You need one that tries to bankrupt it.

