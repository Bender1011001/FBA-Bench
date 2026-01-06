# Agent Runners - Context

> **Last Updated**: 2026-01-05

## Purpose

The Agent Runners module provides an abstraction layer for executing AI agents across different frameworks. It decouples the simulation logic from specific LLM orchestration libraries like LangChain or CrewAI.

## Key Components

| Component | Description |
|-----------|-------------|
| `AgentManager` | Central orchestrator (52KB, 1200+ LOC). Manages agent lifecycles, decision cycles, and framework-specific registration. |
| `BaseAgentRunner` | Abstract base class defining the `decide()` and `learn()` interface for all agents. |
| `AgentRegistry` | Maps framework names (e.g., "crewai", "langchain") to their respective runner implementations. |
| `Framework Runners` | Implementations for `CrewAI`, `LangChain`, and a `DIY` (manual) agent runner. |
| `compat.py` | Compatibility layer for supporting legacy agent configurations. |

## Execution Flow

1. `AgentManager.create_agent(config)` is called.
2. The `AgentRegistry` identifies the correct runner type (e.g., `LangChainRunner`).
3. During a simulation tick, `AgentManager.run_decision_cycle()` iterates through active agents.
4. Each agent runner executes its `decide(state)` method, returning a list of `ToolCall` actions.

## ⚠️ Known Issues

| Location | Issue | Severity |
|----------|-------|----------|
| `agent_manager.py` | Extremely large (1200+ LOC). Contains significant technical debt from multiple refactors and "back-compat" layers. | High (Maintainability) |
| `agent_manager.py:186` | Contains an internal `_StubRunner` class used within `create_agent` - typically a sign of incomplete refactoring or test-leaked code. | Medium |
| `unified_runner_factory.py`| Entire file is a deprecation shim forwarding to `registry.py`. | Low (Tech Debt) |

## Related

- [src/agents](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/agents/CONTEXT.md) - Agent logic and memory.
- [src/fba_bench_core](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_bench_core/CONTEXT.md) - Simulation engine that triggers decision cycles.
