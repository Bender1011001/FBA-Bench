# Realism + Memory Execution Plan

## Objective
Deliver a benchmark that is difficult to dismiss by strong AI evaluators:
- realistic business decision surface
- reproducible methodology
- explicit memory ablations (stateless vs memory-enabled)

## Phase 1: Simulation Realism Core (2 weeks)

### Ticket R1: Expand decision surface
- Add first-class actions: `set_price`, `restock`, `ad_budget_shift`, `supplier_order`, `customer_ops_response`.
- Ensure action costs and constraints are enforced (cash, lead time, inventory, risk).
- Acceptance:
  - Each action affects measurable KPIs in sim.
  - Invalid actions are rejected with explicit reason logs.

### Ticket R2: Data realism
- Add lagged signals and noisy observability to mimic real ops.
- Add delayed consequences (e.g., replenishment lead time, review impact lag).
- Acceptance:
  - KPI changes can occur with delayed effect.
  - Same seed reproduces identical outcomes.

### Ticket R3: Counterfactual baseline
- Run baseline policy in parallel for each scenario.
- Store daily regret and attribution.
- Acceptance:
  - Daily and cumulative regret emitted in results.

## Phase 2: Reflective Memory v1 (1 week)

### Ticket M1: Daily keep/update/discard loop
- Add daily review output contract:
  - `keep[]`, `update[]`, `discard[]`
- Use weighted retention score:
  - `0.35 impact + 0.25 reusability + 0.15 confidence + 0.15 novelty + 0.10 recency - penalties`
- Acceptance:
  - Memory retention is bounded and deterministic in heuristic mode.

### Ticket M2: Weekly consolidation
- Promote strong episodic memories to long-term memory.
- Merge duplicates and update evidence counts/confidence.
- Acceptance:
  - Long-term memory count remains within hard cap.
  - Consolidation metrics stored per week.

### Ticket M3: Retrieval gating
- Inject only top relevant memories per decision.
- Relevance factors:
  - decision type, ASIN scope, tag overlap, freshness.
- Acceptance:
  - Prompt memory context stays inside configured limit.

## Phase 3: Benchmark Methodology (1 week)

### Ticket B1: Ablation matrix
- Run:
  - `stateless`
  - `reflective-memory (heuristic review)`
  - `reflective-memory (llm review)`
- Acceptance:
  - Single report comparing score, variance, and failure profile.

### Ticket B2: Holdout discipline
- Keep hidden holdout scenarios not used for tuning.
- Acceptance:
  - Public runs clearly label tuned vs holdout.

### Ticket B3: Repro package
- Persist:
  - seed, config, per-day decisions, per-day memory state changes.
- Acceptance:
  - Third party can replay same run and match key metrics.

## Demo Readout Requirements
- Show at least one case where memory helps.
- Show at least one case where memory hurts.
- Show exact tradeoff in latency/tokens/cost.
- Publish failure gallery, not just best runs.

## Current v1 Status
- Implemented:
  - `ReflectiveMemoryV1` module with daily review, weekly consolidation, and retrieval.
  - `run_grok_proper_sim.py` integration behind flags:
    - `--memory-mode {stateless,reflective}`
    - `--memory-review-mode {heuristic,llm}`
    - `--no-weekly-consolidation`
  - Expanded sim decision surface in `run_grok_proper_sim.py`:
    - `supplier_orders` with lead-time/risk inbound flow
    - `ad_budget_shift` with delayed demand impact
    - `customer_ops` with backlog/rating tradeoffs
  - Unit tests for memory scoring/consolidation/retrieval.
