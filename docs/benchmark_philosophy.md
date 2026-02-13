# Benchmark Philosophy

FBA-Bench aims to measure performance in a stateful business environment where:
- outcomes are driven by decisions over time
- feedback loops exist (inventory, competitors, fees, cash constraints)
- the system can be validated and replayed

Two modes exist:

## LLM Benchmark

The model is the agent.
- No external memory or retrieval is assumed.
- No hidden scaffolding should be required to succeed.

## Agent Benchmark

Your system is the agent.
- You may provide tools, memory, and orchestration.
- The benchmark measures the whole system, including scaffolding.

