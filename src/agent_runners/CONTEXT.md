# Agent Runners - Context

> **Last Updated**: 2026-01-06

## Purpose

The Agent Runners module provides a framework-agnostic abstraction layer for executing AI agents. It uses **Lazy Loading** in `__init__.py` to resolve components like `AgentManager`, `AgentRunner`, and `AgentBuilder` from optimized submodules, minimizing import cycles and overhead.

## Key Components

| Component | Description |
|-----------|-------------|
| `AgentManager` | Central orchestrator (52KB). Handles agent registration, lifecycle, and optimized decision cycles. |
| `AgentRegistry` | Typed registry in `registry.py` mapping framework keys to runner classes and config models. |
| `AgentBuilder` | Fluent builder pattern for creating and configuring agent runners programmatically. |
| `RunnerFactory` | Compatibility facade delegating to the modern registry system. |
| `UnifiedAgentRunnerConfig` | Pydantic-based configuration model in `benchmarking.config` used for cross-framework standardization. |
| `DependencyManager` | Manages optional framework dependencies (CrewAI, LangChain) with graceful fallbacks. |

## Execution Flow

1. `AgentManager.register_agent(id, framework, config)` is called.
2. The `AgentRegistry` (via `registry.py`) creates the correct runner instance.
3. During a simulation tick, `AgentManager.run_decision_cycle()` iterates through active agents.
4. Each agent runner executes `decide(state)`, returning `ToolCall` actions.

## ⚠️ Known Issues

| Location | Issue | Severity | Status |
|----------|-------|----------|--------|
| `agent_manager.py` | Extremely large (1200+ LOC). Technical debt from multiple refactors. | High | In Progress |
| `agent_manager.py:186`| `_StubRunner` class used within `create_agent`. | Medium | Pending |
| `agent_runners` imports | Circular dependency risks and lazy resolution. | Low | ✅ Hardened |
| Configuration System | Pydantic validation vs legacy test expectations. | Low | ✅ Resolved |

## Related

- [src/agents](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/agents/CONTEXT.md) - Agent logic and memory.
- [src/fba_bench_core](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_bench_core/CONTEXT.md) - Simulation engine that triggers decision cycles.
