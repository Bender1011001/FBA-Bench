# Golden Master Policy

## Purpose and Scope

Golden masters provide a mechanism for ensuring reproducibility and detecting regressions in the FBA-Bench simulation outputs. They capture stable, deterministic baselines of simulation runs, including event streams, final states, and key metrics. This policy applies to all simulation components under `src/fba_bench_core/` and related benchmarking tools, focusing on regression detection for core logic changes that could affect simulation behavior, such as agent decision-making, event generation, or metric calculations.

The scope includes:
- Verifying bit-perfect reproducibility across runs with the same inputs and seeds.
- Detecting unintended changes in outputs due to code modifications.
- Enforcing determinism in LLM interactions and random processes via fixed seeds and caching.

This does not cover non-deterministic external integrations (e.g., live APIs) unless explicitly mocked for testing.

## What Constitutes a Golden Master

A golden master is a serialized snapshot of a complete simulation run, including:
- **Event Stream**: Full sequence of events (e.g., `TickEvent`, `SaleOccurred`) with normalized schemas (e.g., `event_type` preferred over `type`).
- **Final State**: End-of-simulation data (e.g., agent cash, total sales, inventory levels).
- **Metadata**: Run details like timestamp, seed, simulation mode, and LLM interaction logs (if applicable).
- **Hashes**: SHA-256 for data integrity and event stream verification.

Golden masters must be generated under deterministic conditions:
- Fixed master seed (via `src/reproducibility/sim_seed.py`).
- Deterministic LLM mode (temperature=0, caching enabled via `src/reproducibility/llm_cache.py`).
- No external randomness or timestamps that vary (normalized during capture).

They represent "stable outputs" that should reproduce identically across environments (local, CI, production-like simulations).

## Storage Location

Golden masters are stored in the `golden_masters/` directory at the project root:
- **Layout**: Flat structure for simplicity; subdirectories by category (e.g., `golden_masters/integration/`, `golden_masters/unit/`) for organization if volume grows.
- **Naming Conventions**:
  - Format: `<label>.golden` (uncompressed JSON) or `<label>.golden.gz` (compressed).
  - `<label>`: Descriptive and unique, e.g., `integration_test_baseline_v1`, `tier_2_simulation_seed42_v1`.
  - Versioning: Append `_vN` (e.g., `_v2`) for controlled updates to allow drift approval.
  - Avoid spaces; use underscores or hyphens.

Example:
```
golden_masters/
├── integration_test_baseline_v1.golden.gz
├── tier_2_product_sourcing_seed42_v1.golden
└── multi_agent_cooperative_v1.golden.gz
```

Files are generated via `src/reproducibility/golden_master.py` and stored with compression enabled by default.

## Regeneration Workflow

Regenerate golden masters when:
- Core simulation logic changes (e.g., agent behavior, event handling, metrics computation).
- Dependencies update that could affect outputs (e.g., LLM model changes).
- New features introduce backward-incompatible output changes.

**Process**:
1. Run the simulation locally in deterministic mode: `poetry run python scripts/run_simulation.py --seed 42 --deterministic`.
2. Capture the output using `GoldenMasterTester.record_golden_master(simulation_data, label="new_baseline_v2")` or via test fixtures.
3. Commit the updated `.golden` file(s) in a dedicated PR branch (e.g., `update-golden-masters-v2`).
4. Include a clear PR description: "Regenerating golden masters for [change reason]; diffs show [expected changes]."
5. **Mandatory Review**: At least two approvals from core maintainers; one must be from the reproducibility owner.
6. Merge only after CI passes (including verification against old masters if transitional).

Do not regenerate for minor fixes (e.g., logging); only for output-affecting changes.

## CI Enforcement and Failure Semantics

CI enforces golden master verification on every push/PR via `.github/workflows/ci.yml`:
- After running tests, `scripts/verify_golden_masters.py` compares current outputs against baselines.
- Any mismatch (critical differences in events, states, or hashes) fails the build with exit code 1.
- Failure uploads diff summaries and artifacts for review.
- Coverage thresholds are also enforced post-verification.

Semantics:
- **Pass**: Outputs match exactly (or within configured tolerances for numerics/timestamps).
- **Fail**: Mismatch detected; PR cannot merge until resolved (regenerate or fix regression).
- Fast-fail: Workflow stops on verification failure to avoid unnecessary steps.
- Artifacts: Diff reports, coverage XML/HTML, and JUnit for debugging.

## Local Developer Workflow

**Verification**:
- Run full check: `make verify-golden` (wraps `poetry run python scripts/verify_golden_masters.py`).
- This executes relevant tests (e.g., `tests/test_reproducibility.py`, `tests/validation/functional_validation.py`) and prints diffs on failure.
- Exit non-zero if mismatches found.

**Update Process**:
1. Identify affected masters from test failures or change impact.
2. Regenerate: `poetry run python scripts/update_golden_masters.py --label integration_test_baseline --seed 42`.
3. Verify locally: `make verify-golden`.
4. Commit and PR as per regeneration workflow.

**Troubleshooting**:
- View diffs: Rerun verification with `--verbose`.
- Tolerances: Adjust via `GoldenMasterTester.set_tolerance_levels()` in scripts if needed (e.g., for minor float drift), but document and review.

## Change Control

For intentional output changes (e.g., feature adding new events):
- **Controlled Drift**: Bump version in label (e.g., `baseline_v1` → `baseline_v2`); keep old for transition.
- **Approval**: PR must include rationale, before/after diffs, and impact assessment (e.g., "New event type added; no regression in existing metrics").
- **Deprecation**: After 2 releases, archive old masters (rename to `deprecated_v1.golden`); remove after 6 months.
- No drift without PR; all changes gated by CI.

If drift is uncontrolled (e.g., non-deterministic bug), fix the root cause first.

## Ownership

- **Reproducibility Owner**: [TBD - assign to lead engineer]; responsible for policy enforcement, tool maintenance, and reviewing regenerations.
- **Sign-off for Regressions**: Core team (at least 2 members); one must be the reproducibility owner for output-affecting changes.
- **Escalation**: If disputes, escalate to tech lead; ultimate authority is project maintainer.

This policy is versioned; updates require similar review process.
