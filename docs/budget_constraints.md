# Budget & Cost Constraints

## Overview

FBA-Bench includes a **budget enforcement layer** intended to make agent comparisons fair and to prevent "unlimited tool/LLM usage" from dominating results.

The core components are:
- `src/constraints/budget_enforcer.py` (`BudgetEnforcer`): meters tokens/cost/calls per agent, per tool, per tick and per run.
- `src/constraints/agent_gateway.py` (`AgentGateway`): optional wrapper that can (a) block calls before they happen and (b) record usage after responses.
- `src/constraints/tier_configs/*.yaml`: tier presets used by legacy/compat flows and tests.

## BudgetEnforcer (Metering + Events)

`BudgetEnforcer` tracks usage windows:
- `tick`: counters reset every tick via `TickEvent` subscription.
- `run`: counters accumulate for the full run.

It can enforce:
- Overall limits: tokens/cost per tick or per run.
- Tool limits: calls/tokens/cost per tick or per run, per tool name.

When approaching or exceeding limits, it emits typed events:
- `fba_events.budget.BudgetWarning`
- `fba_events.budget.BudgetExceeded`

## Configuration

There are two config shapes in the codebase:

### 1) New metering schema (dict config)

This is the schema described in `src/constraints/budget_enforcer.py`:

```yaml
limits:
  total_tokens_per_tick: 200000
  total_tokens_per_run: 5000000
  total_cost_cents_per_tick: 1000
  total_cost_cents_per_run: 25000
tool_limits:
  decide_action:
    calls_per_tick: 10
    calls_per_run: 2000
    tokens_per_tick: 60000
    tokens_per_run: 2000000
    cost_cents_per_tick: 300
    cost_cents_per_run: 8000
warning_threshold_pct: 0.8
allow_soft_overage: false
```

### 2) Legacy tier configs (YAML presets)

Tier presets live in `src/constraints/tier_configs/` (example: `t2_config.yaml`):

```yaml
budget_constraints:
  max_tokens_per_action: 32000
  max_total_tokens: 1000000
  token_cost_per_1k: 0.12
  violation_penalty_weight: 2.5
  grace_period_percentage: 5.0
enforcement:
  hard_fail_on_violation: true
  inject_budget_status: true
  track_token_efficiency: true
```

These fields are still supported via backward-compat “duck typing” in `BudgetEnforcer.__init__()`.

## AgentGateway (Optional)

`AgentGateway` (`src/constraints/agent_gateway.py`) can:
- Estimate prompt tokens before a call and check `budget_enforcer.can_afford(...)`.
- Postprocess a response and meter the actual prompt + completion tokens via `budget_enforcer.meter_api_call(...)`.
- Optionally inject a budget status block into the prompt when `inject_budget_status` is enabled (legacy config path).

## Practical Guidance

- Use budgets when benchmarking agent architectures so results don’t collapse into “who spent the most tokens.”
- Prefer tool-level budgets in addition to overall budgets (it prevents a single tool from dominating).
- If you want hard stops on constraint violations, set `allow_soft_overage: false` and rely on `BudgetViolationError` + `BudgetExceeded` events for enforcement behavior.

