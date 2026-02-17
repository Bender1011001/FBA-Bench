# Cognitive Memory Consolidation: Human-Like Recall & Reflection

> [!IMPORTANT]
> The features described here rely on the **RealSimulationRunner** and the **CrewAIRunner**'s `long_term_memory` integration. They are **dormant** in the standard `run_gemini_benchmark.py` CLI benchmark, which uses ephemeral context.

## Overview

Truly agentic behavior requires an understanding of time and history beyond a sliding context window. FBA-Bench implements **Cognitive Memory Consolidation**, a system that mimics human "sleep cycles" to distill daily events into permanent, queryable long-term memory (LTM).

This allows agents to:
*   Remember strategies that failed 30 days ago.
*   Consolidate minor wins into broader heuristics.
*   Forget irrelevant noise to keep context windows clean and efficient.

## Mechanism: The "Sleep Cycle"

At the end of every simulation "day" (configurable tick interval), the agent enters a sleep cycle. During this phase, the `LongTermMemoryStore` triggers a reflection process powered by an LLM loop.

### 1. Review
The agent reviews the **Day's Events** and **Short-Term Memory** buffer.

### 2. Reflect & Distill
The system prompts the agent to answer:
*   "What key lessons did I learn today?"
*   "What strategies yielded the highest ROI?"
*   "What details can I safely forget?"

### 3. Consolidate
*   **Promote:** Critical insights are "promoted" to LTM as `MemoryItem` objects with importance scores (0.0 - 1.0).
*   **Forget:** Low-value or duplicate memories are discarded to freeing up capacity.

## Long-Term Memory (LTM) Store

The LTM is a persistent vector-compatible store that holds consolidated memories.

*   **Capacity:** Configurable `max_items` (default: 100).
*   **Retrieval:** Memories are retrieved based on semantic relevance to the current task context *before* the agent acts.
*   **Deduplication:** Prevents redundant entries (e.g., "I should lower prices" x 50).

## Benefits

| Feature | Without LTM | With LTM |
| :--- | :--- | :--- |
| **Strategy** | Reactive; repeats mistakes. | Proactive; evolves based on history. |
| **Context Window** | Flooded with noise; expensive. | Curated; high signal-to-noise ratio. |
| **Personality** | Drifts over time. | Consistent; grounded in core memories. |

## Configuration

To enable Cognitive Memory in your agent config:

```yaml
memory:
  enabled: true
  type: "long_term"
  max_items: 200
  reflection_interval: 24 # Ticks (1 day)
  forgetting_curve: 0.1   # Decay rate for unused memories
```

## Implementation Details

*   **Store Logic:** `src/agent_runners/long_term_memory.py`
    *   Class: `LongTermMemoryStore`
*   **Integration:** `src/agent_runners/crewai_runner.py`
    *   Method: `_run_reflection_cycle`
