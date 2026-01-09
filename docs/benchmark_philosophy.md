# FBA-Bench Benchmark Philosophy

## We Have Two Benchmarks. Know the Difference.

| | 🧠 LLM Benchmark | 🤖 Agent Benchmark |
|---|-----------------|-------------------|
| **What it tests** | Raw model capability | Your agent system |
| **Memory** | In-prompt only | Bring your own |
| **Tools** | None | Your tooling |
| **If it fails** | Model's fault | System's fault |
| **Runtime** | Hours | Varies |
| **Script** | `run_grok_live.py` | Agent runners |

---

## The LLM Benchmark Is Honest

We give the LLM **everything it needs** in the prompt:
- Current inventory
- Today's orders
- Competitor prices
- Active market events
- Yesterday's results (feedback!)

Then we ask it to decide. **365 times.** With consequences.

No external memory. No vector retrieval. No scaffolding to blame.

If GPT-4o beats Claude, it's because GPT-4o is better at this task. Not because it had a better RAG pipeline.

---

## Why No Memory System?

> "But VendingBench uses memory tools!"

Yes. And when their models "derail," you can't tell if it's because:
- The LLM forgot its strategy
- The vector DB returned bad context  
- The scratchpad filled with garbage
- The embedding model was miscalibrated

**A system is only as good as its worst component.**

We isolate the variable. We test the LLM.

---

## The Agent Benchmark Exists Too

If you want to test your CrewAI setup against LangChain against your DIY agent, use the **Agent Benchmark**.

That's a fair comparison of *systems*, including the scaffolding you built.

Register your agent runner in `src/agent_runners/` and let it compete.

---

## Summary

| Question | Use |
|----------|-----|
| "Which LLM is best for business reasoning?" | LLM Benchmark |
| "Is my agent architecture any good?" | Agent Benchmark |
| "Does memory help?" | Compare both |

---

## Running the LLM Benchmark

```bash
# Configure
nano simulation_settings.yaml

# Run (expect ~6 hours for 1 year)
export OPENROUTER_API_KEY="sk-or-..."
poetry run python run_grok_live.py
```

Results are saved to `results/` with full decision history.

---

## The Runtime Is the Point

| Benchmark | Runtime | What It Skips |
|-----------|---------|---------------|
| MMLU | 10 min | Consequences |
| HumanEval | 20 min | Multi-turn |
| MT-Bench | 30 min | Long-horizon |
| **FBA-Bench** | **6 hours** | **Nothing** |

If you want fast, use a fast benchmark.

If you want real, use FBA-Bench.
