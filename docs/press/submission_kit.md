# Submission Kit (Copy/Paste)

This folder is meant to make public submissions fast. Replace links as needed.

## One-liners

1. "A long-horizon e-commerce simulation benchmark where LLMs run a business for 180-365 days and are scored by profit."
2. "The Bankruptcy Test: tick-based agent benchmarking with compounding consequences, not static QA."

## Short description (2-3 sentences)

FBA-Bench is a tick-based e-commerce simulation benchmark: inventory, pricing, competitors, and adversarial market events. Each simulated day is a separate LLM call with feedback loops and persistent state, and runs are scored by objective business outcomes (profit/ROI). It is built to reveal long-horizon failure modes that one-shot benchmarks miss.

## What makes it different

1. One decision per simulated day, sequentially, for months of simulated time.
2. Persistent state and feedback loops (actions change tomorrow).
3. Objective scoring (profit/ROI) instead of "vibes" grading.
4. Stress testing via shocks: supply chain disruptions, price wars, demand spikes/crashes.
5. Separates "LLM Benchmark" (model-only) from "Agent Benchmark" (your system).

## Links (fill these in)

1. Repo: https://github.com/Bender1011001/FBA-Bench-Enterprise
2. Leaderboard: https://bender1011001.github.io/FBA-Bench-Enterprise/
3. Custom domain (optional): https://fbabench.com

## Show HN post (template)

Title options:

1. Show HN: FBA-Bench - the Bankruptcy Test for LLM business agents
2. Show HN: A benchmark where LLMs run an e-commerce store for 180-365 days

Body:

Hi HN,

We built FBA-Bench Enterprise to answer a simple question: can a model survive a long-horizon operating environment, or does it slowly bleed capital under shocks?

FBA-Bench is a tick-based e-commerce sim (inventory, pricing, competitors, adversarial events). Each simulated day is a separate model decision with feedback loops and persistent state. Scoring is objective: profit/ROI and survival, plus token and latency metrics.

Links:
- Leaderboard: https://bender1011001.github.io/FBA-Bench-Enterprise/
- Repo: https://github.com/Bender1011001/FBA-Bench-Enterprise

If you want a quick mental model: most benchmarks are exams; this is a six-month job.

Questions we would love feedback on:
1) What metrics would you trust for long-horizon agent eval?
2) What scenarios would you add to try to bankrupt the agent faster?

## Reddit (r/MachineLearning) post (template)

Title:

[P] FBA-Bench: long-horizon agent benchmark scored by profit (the Bankruptcy Test)

Body:

We built FBA-Bench to test long-horizon agent behavior under compounding consequences. It is an e-commerce simulation where each simulated day is a separate model decision (pricing, restock, order acceptance) under adversarial events (price wars, supply shocks, demand spikes/crashes). Runs are scored by objective outcomes: profit/ROI and survival.

Leaderboard: https://bender1011001.github.io/FBA-Bench-Enterprise/
Repo: https://github.com/Bender1011001/FBA-Bench-Enterprise

## Product Hunt listing (template)

Tagline:

The Bankruptcy Test for LLM agents

Short description:

An e-commerce simulation benchmark where models operate for 180-365 simulated days and are ranked by profit, not one-shot QA.

First comment:

Most benchmarks are static tests. FBA-Bench is an interactive loop with persistent state and compounding consequences. We built it to measure whether models can actually operate: manage inventory, pricing, competitors, and shocks without going bankrupt.

## Cold email to newsletters (template)

Subject:

New benchmark: LLMs run a business for 180-365 days, scored by profit

Body:

Hi <Name>,

We are launching FBA-Bench Enterprise: a long-horizon agent benchmark where models run an e-commerce store for months of simulated time (one decision per day with feedback loops). We rank runs by profit/ROI and stability under shocks like price wars and supply chain disruptions.

Leaderboard: https://bender1011001.github.io/FBA-Bench-Enterprise/
Repo: https://github.com/Bender1011001/FBA-Bench-Enterprise

If you cover evaluation/agent reliability, we think this is a useful contrast to static QA benchmarks because failures compound over time instead of showing up as a single wrong answer.

Thanks,
<You>

