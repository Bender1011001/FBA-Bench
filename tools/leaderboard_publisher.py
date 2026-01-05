#!/usr/bin/env python3
"""
Local Leaderboard Publisher for FBA Bench Tier 0-2 Results.
Ingests JSON/CSV from results directories and updates site leaderboard.json and local CSV.
Uses only Python standard library.
"""

import argparse
import csv
import datetime
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish tier run results to leaderboard.")
    parser.add_argument(
        "--results-root",
        default="./results/openrouter_tier_runs",
        help="Root directory containing tier directories (t0, t1, t2)."
    )
    parser.add_argument(
        "--output-json",
        default="repos/fba-bench-core/site/data/leaderboard.json",
        help="Path to output JSON file for site leaderboard."
    )
    parser.add_argument(
        "--output-csv",
        default="./leaderboard/leaderboard.csv",
        help="Path to output CSV file for local leaderboard."
    )
    parser.add_argument(
        "--tiers",
        default="T0,T1,T2",
        help="Comma-separated tiers to process (e.g., T0,T1)."
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run ID; defaults to 'run-YYYYMMDD-HHMMSS'."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing files."
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamped .bak copy of output JSON before modifying."
    )
    return parser.parse_args()


def get_run_id(run_id_arg: Optional[str]) -> str:
    if run_id_arg:
        return run_id_arg
    now = datetime.datetime.now(datetime.timezone.utc)
    return f"run-{now.strftime('%Y%m%d-%H%M%S')}"


def normalize_record(
    model_slug: str,
    tier: str,
    success: bool,
    metrics: Dict[str, Any],
    timestamp: str,
    run_id: str
) -> Dict[str, Any]:
    """Normalize to canonical schema."""
    provider = model_slug.split("/")[0] if "/" in model_slug else "unknown"
    record = {
        "model_slug": model_slug,
        "provider": provider,
        "tier": tier,
        "success": success,
        "metrics": {
            "total_profit": metrics.get("total_profit") or metrics.get("profit") or None,
            "tokens_used": metrics.get("tokens_used") or metrics.get("token_usage") or None,
            "composite_score": metrics.get("composite_score") or None,
        },
        "timestamp": timestamp,
        "run_id": run_id,
    }
    # Add any other present metrics
    for key in ["profit_target", "profit_target_min"]:
        if key in metrics and key not in record["metrics"]:
            record["metrics"][key] = metrics[key]
    return record


def load_existing_json(json_path: str) -> List[Dict[str, Any]]:
    """Load existing leaderboard JSON, create empty list if missing."""
    if not os.path.exists(json_path):
        print(f"No existing JSON at {json_path}, starting with empty list.")
        return []
    try:
        with open(json_path) as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"Warning: {json_path} is not a list, starting with empty list.")
            return []
        return data
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error loading {json_path}: {e}. Starting with empty list.")
        return []


def is_duplicate(existing: List[Dict], new_record: Dict) -> bool:
    """Check for duplicate by (run_id, model_slug, tier)."""
    key = (new_record["run_id"], new_record["model_slug"], new_record["tier"])
    for rec in existing:
        rec_key = (rec.get("run_id"), rec.get("model_slug"), rec.get("tier"))
        if rec_key == key:
            return True
    return False


def merge_and_sort(existing: List[Dict], new_records: List[Dict]) -> List[Dict]:
    """Append non-duplicate new records and sort by timestamp descending."""
    for rec in new_records:
        if not is_duplicate(existing, rec):
            existing.append(rec)
    # Sort by timestamp descending (assuming ISO8601 format)
    existing.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return existing


def write_json_atomic(json_path: str, data: List[Dict], backup: bool = False) -> None:
    """Write JSON atomically to temp file then replace."""
    tmp_path = json_path + ".tmp"
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        if backup and os.path.exists(json_path):
            timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            bak_path = f"{json_path}.bak-{timestamp}"
            shutil.copy2(json_path, bak_path)
            print(f"Backup created: {bak_path}")
        os.replace(tmp.name, json_path)
        print(f"Updated JSON: {json_path}")
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise OSError(f"Failed to write {json_path}: {e}")


def write_csv(csv_path: str, records: List[Dict]) -> None:
    """Write CSV with canonical headers."""
    if not records:
        print(f"No records to write to CSV: {csv_path}")
        return

    # Define canonical headers
    headers = [
        "timestamp", "run_id", "tier", "provider", "model_slug",
        "success", "total_profit", "tokens_used", "composite_score"
    ]
    # Add optional headers if present in records
    optional_fields = set()
    for rec in records:
        for field in rec.get("metrics", {}):
            if field not in headers:
                optional_fields.add(field)
    headers.extend(sorted(optional_fields))

    tmp_path = csv_path + ".tmp"
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="", encoding="utf-8") as tmp:
            writer = csv.DictWriter(tmp, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                row = {
                    "timestamp": rec["timestamp"],
                    "run_id": rec["run_id"],
                    "tier": rec["tier"],
                    "provider": rec["provider"],
                    "model_slug": rec["model_slug"],
                    "success": rec["success"],
                }
                metrics = rec.get("metrics", {})
                row.update({k: metrics.get(k) for k in ["total_profit", "tokens_used", "composite_score"] if k in metrics})
                row.update({k: metrics.get(k) for k in optional_fields if k in metrics})
                writer.writerow(row)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, csv_path)
        print(f"Updated CSV: {csv_path}")
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise OSError(f"Failed to write {csv_path}: {e}")


def ingest_tier(results_root: str, tier_dir: str, tier_label: str, run_id: str) -> List[Dict]:
    """Ingest results from a tier directory."""
    tier_path = Path(results_root) / tier_dir
    if not tier_path.exists():
        print(f"Tier directory not found: {tier_path}")
        return []

    records = []
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Try summary.json first
    summary_path = tier_path / "summary.json"
    if summary_path.exists():
        try:
            with open(summary_path) as f:
                summary_data = json.load(f)
            if isinstance(summary_data, list):
                for model_data in summary_data:
                    model_slug = model_data.get("model_slug", "unknown")
                    success = model_data.get("success", False)
                    metrics = model_data.get("metrics", {})
                    records.append(normalize_record(model_slug, tier_label, success, metrics, timestamp, run_id))
                print(f"Ingested {len(records)} records from {summary_path}")
                return records
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing {summary_path}: {e}")

    # Fall back to per-model *.json files
    json_files = list(tier_path.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {tier_path}")
        return []

    for json_file in json_files:
        if json_file.name == "summary.json":
            continue  # Already tried
        try:
            model_slug = json_file.stem.replace("_", "/")  # Assume filename like deepseek-chat-v3.1_free -> deepseek/chat-v3.1:free (simplified)
            if ":" not in model_slug:
                model_slug += ":free"  # Default variant if needed
            with open(json_file) as f:
                data = json.load(f)
            success = data.get("success", False)
            metrics = data.get("metrics", {}) or data.get("profit", 0) or {}
            if isinstance(metrics, (int, float)):
                metrics = {"total_profit": metrics}
            records.append(normalize_record(model_slug, tier_label, success, metrics, timestamp, run_id))
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"Error processing {json_file}: {e}")
            continue

    print(f"Ingested {len(records)} per-model records from {tier_path}")
    return records


def main():
    args = parse_args()
    tiers = [t.strip() for t in args.tiers.split(",")]
    run_id = get_run_id(args.run_id)
    print(f"Run ID: {run_id}")
    print(f"Processing tiers: {tiers}")

    all_new_records = []
    for tier_label in tiers:
        tier_dir = tier_label.lower()  # T0 -> t0
        new_records = ingest_tier(args.results_root, tier_dir, tier_label, run_id)
        all_new_records.extend(new_records)

    if not all_new_records:
        print("No results found in any tier directories. Exiting without changes.")
        sys.exit(0)

    print(f"Total new records to ingest: {len(all_new_records)}")

    if args.dry_run:
        print("DRY RUN: Would append the following records:")
        for rec in all_new_records:
            print(f"  - {rec['provider']}/{rec['model_slug']} ({rec['tier']}): success={rec['success']}, profit={rec['metrics'].get('total_profit')}")
        return

    # Load existing JSON
    existing_records = load_existing_json(args.output_json)

    # Merge
    updated_records = merge_and_sort(existing_records, all_new_records)
    print(f"After merge: {len(updated_records)} total records (added {len(all_new_records)} new)")

    # Backup if requested
    if args.backup:
        write_json_atomic(args.output_json, updated_records, backup=True)
    else:
        write_json_atomic(args.output_json, updated_records)

    # Write CSV (all records, including existing for completeness)
    write_csv(args.output_csv, updated_records)

    print("Publishing complete.")


if __name__ == "__main__":
    main()
