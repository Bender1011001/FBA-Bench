# Long-Term Memory & Agent Modes

## Overview

FBA-Bench Enterprise includes a built-in, LLM-driven **Long-Term Memory (LTM)** system designed for long-horizon runs: after each simulation day, agents can *choose what to remember* and *what to forget*.

Separately, agent runners support **behavior modes** like competition awareness (agents are explicitly told they are competing vs. not told).

## Production LTM: Per-Day Consolidation

The production path is implemented in:
- `src/agent_runners/long_term_memory.py` (memory store + reflection prompt + daily digest)
- `src/agent_runners/langchain_runner.py` and `src/agent_runners/crewai_runner.py` (LLM reflection + prompt injection)
- `src/agent_runners/agent_manager.py` (triggers consolidation for tick `T-1` at the start of tick `T`)

### How It Works (High-Level)

1. Each tick/day, the simulation emits events (sales, inventory updates, price changes, supply events, etc.).
2. The AgentManager buffers tick-scoped event summaries and the agent’s tool calls.
3. At the day boundary, the runner builds a compact **daily digest** (what happened + key metrics).
4. The runner asks an LLM to produce a strict JSON decision:
   - `promote`: short, durable memory items to store long-term
   - `forget`: ids to delete from long-term memory
5. The `LongTermMemoryStore` applies the promotion/forgetting decision and enforces a hard capacity cap.
6. On subsequent days, the top-N most important LTM items are injected into the agent’s prompt.

### Key Config Knobs (LangChain/CrewAI Runners)

- `long_term_memory_enabled`: enable per-day consolidation
- `long_term_memory_max_items`: hard cap on stored memories
- `long_term_memory_prompt_items`: how many items are injected into the daily prompt
- `long_term_memory_max_additions_per_day`: limit “promotion” per day
- `long_term_memory_max_forgets_per_day`: limit “forgetting” per day
- `long_term_memory_max_chars_per_item`: prevents oversized memories

## Agent Behavior Modes: Competition Awareness

Both `LangChainRunnerConfig` and `CrewAIRunnerConfig` support:
- `competition_awareness: "aware" | "unaware"`

In `aware` mode, the runner augments the system prompt to explicitly frame the task as a competitive, multi-agent setting (optimize *relative* performance and anticipate rivals). In `unaware` mode, that framing is omitted.

## Experimental Memory Suite (Research)

There is also an experimental memory research suite under `src/memory_experiments/`, including:
- `src/memory_experiments/dual_memory_manager.py` (short-term vs long-term architecture)
- `src/memory_experiments/reflection_module.py` (periodic reflection/consolidation algorithms)

These modules are useful for research variants and ablations, but the per-day consolidation described above is the production path used by the framework runners.
