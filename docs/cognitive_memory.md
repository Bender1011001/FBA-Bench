# Cognitive Memory: Long-Term Recall & Consolidation

> [!IMPORTANT]
> The memory consolidation features require the **RealSimulationRunner** and the **CrewAIRunner**'s `long_term_memory` integration. They are **dormant** in the standard CLI benchmark, which uses ephemeral context.

## Overview

FBA-Bench includes a built-in, LLM-driven **Long-Term Memory (LTM)** system designed for long-horizon runs: after each simulation day, agents can *choose what to remember* and *what to forget*.

This allows agents to:
- Remember strategies that failed 30 days ago.
- Consolidate minor wins into broader heuristics.
- Forget irrelevant noise to keep context windows clean and efficient.

Separately, agent runners support **behavior modes** like competition awareness (agents are explicitly told they are competing vs. not told).

## Mechanism: The "Sleep Cycle"

At the end of every simulation "day" (configurable tick interval), the agent enters a sleep cycle:

### 1. Review
The agent reviews the **Day's Events** and **Short-Term Memory** buffer.

### 2. Reflect & Distill
The system prompts the agent to answer:
- "What key lessons did I learn today?"
- "What strategies yielded the highest ROI?"
- "What details can I safely forget?"

### 3. Consolidate
- **Promote:** Critical insights are "promoted" to LTM as `MemoryItem` objects with importance scores (0.0 - 1.0).
- **Forget:** Low-value or duplicate memories are discarded to free up capacity.

## Implementation

The production path is implemented in:
- `src/agent_runners/long_term_memory.py` — memory store, reflection prompt, daily digest
- `src/agent_runners/langchain_runner.py` and `src/agent_runners/crewai_runner.py` — LLM reflection + prompt injection
- `src/agent_runners/agent_manager.py` — triggers consolidation for tick `T-1` at the start of tick `T`

### How It Works (High-Level)

1. Each tick/day, the simulation emits events (sales, inventory updates, price changes, supply events, etc.).
2. The AgentManager buffers tick-scoped event summaries and the agent's tool calls.
3. At the day boundary, the runner builds a compact **daily digest** (what happened + key metrics).
4. The runner asks an LLM to produce a strict JSON decision:
   - `promote`: short, durable memory items to store long-term
   - `forget`: ids to delete from long-term memory
5. The `LongTermMemoryStore` applies the promotion/forgetting decision and enforces a hard capacity cap.
6. On subsequent days, the top-N most important LTM items are injected into the agent's prompt.

## LTM Store Properties

- **Capacity:** Configurable `max_items` (default: 100).
- **Retrieval:** Memories are retrieved based on semantic relevance to the current task context *before* the agent acts.
- **Deduplication:** Prevents redundant entries (e.g., "I should lower prices" x 50).

| Feature | Without LTM | With LTM |
| :--- | :--- | :--- |
| **Strategy** | Reactive; repeats mistakes. | Proactive; evolves based on history. |
| **Context Window** | Flooded with noise; expensive. | Curated; high signal-to-noise ratio. |
| **Personality** | Drifts over time. | Consistent; grounded in core memories. |

## Configuration

### Runner Config Knobs (LangChain/CrewAI)

| Key | Description |
|---|---|
| `long_term_memory_enabled` | Enable per-day consolidation |
| `long_term_memory_max_items` | Hard cap on stored memories |
| `long_term_memory_prompt_items` | How many items injected into daily prompt |
| `long_term_memory_max_additions_per_day` | Limit "promotion" per day |
| `long_term_memory_max_forgets_per_day` | Limit "forgetting" per day |
| `long_term_memory_max_chars_per_item` | Prevents oversized memories |

### YAML Config

```yaml
memory:
  enabled: true
  type: "long_term"
  max_items: 200
  reflection_interval: 24 # Ticks (1 day)
  forgetting_curve: 0.1   # Decay rate for unused memories
```

## Agent Behavior Modes: Competition Awareness

Both `LangChainRunnerConfig` and `CrewAIRunnerConfig` support:
- `competition_awareness: "aware" | "unaware"`

In `aware` mode, the runner augments the system prompt to explicitly frame the task as a competitive, multi-agent setting (optimize *relative* performance and anticipate rivals). In `unaware` mode, that framing is omitted.

## Experimental Memory Suite (Research)

There is also an experimental memory research suite under `src/memory_experiments/`, including:
- `src/memory_experiments/dual_memory_manager.py` (short-term vs long-term architecture)
- `src/memory_experiments/reflection_module.py` (periodic reflection/consolidation algorithms)

These modules are useful for research variants and ablations, but the per-day consolidation described above is the production path used by the framework runners.
