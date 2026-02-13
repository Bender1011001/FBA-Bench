# Why It Takes Hours

FBA-Bench is a time-series simulation benchmark. The system is intentionally not a single-turn prompt test.

## What Makes It Slow

- **Tick-based evaluation**: each tick represents a day (or other discrete unit) in a simulated business.
- **Stateful consequences**: decisions compound; a bad inventory decision today affects stockouts and cashflow later.
- **Determinism and logging**: runs capture enough information to be replayed and validated.

## What To Do If You Need Faster Runs

- Use fewer days/ticks in configs.
- Reduce scenario complexity.
- Run a smaller seed set.
- Disable optional observability exporters in local runs.

