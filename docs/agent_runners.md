# Agent Runners & Modes

## Overview

Agent runners are the “adapter layer” between:
- the simulation tick loop (state + events)
- the agent framework (LangChain, CrewAI, DIY, baseline bots)
- optional constraints (budgets) and memory systems

Core directory: `src/agent_runners/`

## Supported Runners

- LangChain runner: `src/agent_runners/langchain_runner.py`
- CrewAI runner: `src/agent_runners/crewai_runner.py`
- DIY runner (custom): `src/agent_runners/diy_runner.py`
- Runner factory/registry:
  - `src/agent_runners/runner_factory.py`
  - `src/agent_runners/unified_runner_factory.py`

## Long-Term Memory (Production Path)

Per-day memory consolidation is implemented in:
- `src/agent_runners/long_term_memory.py`

Integration points:
- Runners inject memory into prompts and call consolidation at day boundaries.
- `src/agent_runners/agent_manager.py` triggers consolidation between ticks.

See: `docs/cognitive_memory.md`

## Behavior Modes: Competition Awareness

Runner configs support a `competition_awareness` switch:
- `aware`: explicitly tell agents they are competing (optimize relative performance)
- `unaware`: omit the competitive framing

See: `docs/cognitive_memory.md`

## Budgets / Constraints

Runners can be paired with budget tooling:
- `src/constraints/budget_enforcer.py`
- `src/constraints/agent_gateway.py`

See: `docs/budget_constraints.md`

## Configuration Files

Runner config schema helpers live under:
- `src/agent_runners/configs/`

Example config files:
- `src/agent_runners/configs/product_sourcing_agent.yaml`

