# Golden Master Policy

Golden masters are deterministic baselines used to detect regressions in simulation outputs.

## When To Use

Use golden masters when changes could affect:
- event streams
- final state
- metrics (profit, ROI, inventory, etc.)

## Running Verification

```bash
make verify-golden
```

## Updating Baselines

Regeneration should happen in a dedicated PR:
1. Generate new baselines with the appropriate script(s).
2. Commit only the baselines that are intended to change.
3. Document the reason for the change and expected diffs.

