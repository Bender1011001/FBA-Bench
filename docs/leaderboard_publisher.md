# Leaderboard Publisher

## Overview

The `leaderboard_publisher.py` script ingests results from tier run directories (T0–T2) into a unified leaderboard format. It supports both per-model JSON files and a single `summary.json` per tier, normalizing data to a canonical schema. New records are appended to the existing site JSON (`repos/fba-bench-core/site/data/leaderboard.json`) without duplicates, sorted by timestamp descending. A local CSV export is also generated for file-based leaderboard use under `./leaderboard/leaderboard.csv`.

The script uses only Python standard library (no external dependencies) to avoid environment issues. It handles missing/empty results gracefully by exiting without changes. File writes are atomic (temp file → replace) for safety, with optional backups.

Key features:
- CLI-driven with defaults for ease of use.
- Robust parsing: Tries `summary.json` first, falls back to `*.json` files.
- Duplicate avoidance: By `(run_id, model_slug, tier)`.
- CSV export with canonical + optional headers.

## Usage

Run from the project root (`c:/Users/admin/Downloads/fba`).

### Example Commands (Windows)

1. Full publish with backup (assumes results exist):
   ```
   python tools\leaderboard_publisher.py --results-root .\results\openrouter_tier_runs --output-json repos\fba-bench-core\site\data\leaderboard.json --output-csv .\leaderboard\leaderboard.csv --tiers T0,T1,T2 --run-id tier-batch-20251001 --backup
   ```

2. Dry run (preview changes without writing):
   ```
   python tools\leaderboard_publisher.py --results-root .\results\openrouter_tier_runs --tiers T0 --dry-run
   ```

3. Custom run ID and partial tiers:
   ```
   python tools\leaderboard_publisher.py --results-root .\results\openrouter_tier_runs --tiers T1,T2 --run-id custom-run-001
   ```

If no results are found, the script prints a message and exits 0 without modifying files.

## Schema Details

### Canonical Schema (New Records)

New entries follow this structure, derived for compatibility with detailed tier results:

```json
{
  "model_slug": "deepseek/deepseek-chat-v3.1:free",  // Full model identifier (str)
  "provider": "deepseek",                            // Prefix before "/" in model_slug (str)
  "tier": "T0" | "T1" | "T2",                       // Tier label (str)
  "success": true | false,                           // Overall run success (bool)
  "metrics": {                                       // Dict of available metrics
    "total_profit": 123.45,                          // Primary score (float or null)
    "tokens_used": 456,                              // Token usage if present (int or null)
    "composite_score": 89.1,                         // Any aggregate score (float or null)
    // Optional: "profit_target": 150.0, "profit_target_min": 100.0
  },
  "timestamp": "2025-10-01T03:44:20Z",               // ISO8601 UTC (str)
  "run_id": "run-20251001-034420"                    // Unique run identifier (str)
}
```

The leaderboard JSON is an array of such objects (or mixed with legacy entries).

### Compatibility with Existing Site JSON

Existing `repos/fba-bench-core/site/data/leaderboard.json` uses a simpler schema (placeholder data):

```json
[
  {
    "team": "Example AI Lab",
    "model": "Example-1",
    "score": 87.2,
    "date": "2025-09-01",
    "notes": "Baseline performance on tier 1 scenarios"
  }
  // ... more entries
]
```

**Merge Strategy**:
- Load existing entries as-is (preserves legacy format).
- Append new records in canonical schema only if no duplicate `(run_id, model_slug, tier)` exists.
- Sort entire array by `timestamp` (new) or `date` (legacy) descending for stability.
- If the site parser expects legacy fields, it may need updates; otherwise, new entries provide richer data (e.g., map `score` ← `metrics.total_profit`, `model` ← `model_slug`, `date` ← `timestamp`).
- No data loss: Legacy entries remain unchanged.

### Field Mapping from Results JSON

#### From `summary.json` (per-tier aggregate):
- Array of model objects:
  - `model_slug`: From `model_slug` key.
  - `success`: From top-level `success` (bool).
  - `metrics`: From `metrics` dict; prioritize `total_profit` ← `metrics.total_profit` or `profit`.
  - Fallback: `tokens_used` ← `tokens` or `token_usage`; `composite_score` ← any score field.
  - Optional: Preserve `profit_target`, `profit_target_min`.

#### From Per-Model `*.json` (e.g., `deepseek-chat.json`):
- Filename derives `model_slug` (e.g., `deepseek-chat-v3.1_free.json` → `deepseek/deepseek-chat-v3.1:free`; replace `_` with `/` and add `:free` if missing).
- `success`: From top-level `success` (bool).
- `metrics`: From `metrics` dict or top-level `profit`/`profit_target` (normalize scalar to `{"total_profit": value}`).
- Same fallbacks as above.

Timestamps are auto-generated (UTC ISO8601) if not in source. If no files/summary, skip tier gracefully.

## Logging

- Prints run ID, tiers processed.
- Per-tier: Files ingested, records added (e.g., "Ingested 5 records from ./results/.../t0").
- Summary: Total new records, post-merge count.
- File updates: "Updated JSON: path", "Backup created: path".
- Errors: Non-fatal (e.g., skip bad JSON); fatal only on write failures.

For troubleshooting, run with `--dry-run` to inspect planned ingestion without side effects.
