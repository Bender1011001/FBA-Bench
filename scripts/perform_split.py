#!/usr/bin/env python3
"""
Idempotent utility to perform file/directory split based on mapping.
Copies 'planned' entries to staged repos, logs 'needs_review', handles missing sources.
Generates report with counts and samples.
Windows-compatible, uses shutil for copies.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

MAPPING_FILE = "repos/file_split_map.json"
REPORT_FILE = "repos/split_report.json"
PENDING_FILE = "repos/PENDING_REVIEW.txt"
ERRORS_FILE = "repos/split_errors.log"

def validate_mapping(data: Dict[str, Any]) -> bool:
    """Validate mapping schema."""
    if "version" not in data or "entries" not in data:
        return False
    required_keys = {"source", "dest_repo", "dest_path", "status"}
    for entry in data["entries"]:
        if not isinstance(entry, dict) or not required_keys.issubset(entry.keys()):
            return False
    return True

def copy_file_idempotent(source: str, dest: str) -> bool:
    """Copy file if it doesn't exist or content differs."""
    source_path = Path(source)
    dest_path = Path(dest)
    if not source_path.exists():
        return False
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists():
        with open(source_path, "rb") as f_src, open(dest_path, "rb") as f_dest:
            if f_src.read() == f_dest.read():
                return True  # Identical, no change
    shutil.copy2(source, dest)
    return True

def copy_dir_idempotent(source: str, dest: str) -> bool:
    """Recursively copy directory, updating if needed."""
    source_path = Path(source)
    dest_path = Path(dest)
    if not source_path.exists():
        return False
    dest_path.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, dest, dirs_exist_ok=True, copy_function=shutil.copy2)
        return True
    except Exception as e:
        # Log error if copy fails
        with open(ERRORS_FILE, "a") as f:
            f.write(f"Failed to copy dir {source} to {dest}: {e}\n")
        return False

def process_entry(entry: Dict[str, Any], counters: Dict[str, int], copied_samples: List[Dict[str, str]]) -> None:
    """Process a single mapping entry."""
    source = entry["source"]
    dest_path = entry["dest_path"]
    status = entry["status"]
    dest_repo = entry["dest_repo"]

    if status == "planned":
        is_dir = os.path.isdir(source)
        success = copy_dir_idempotent(source, dest_path) if is_dir else copy_file_idempotent(source, dest_path)
        if success:
            counters["copied"] += 1
            if len(copied_samples) < 5:
                copied_samples.append({"source": source, "dest_path": dest_path})
            # Verify sample
            if os.path.exists(dest_path):
                print(f"Copied: {source} -> {dest_path}")
            else:
                with open(ERRORS_FILE, "a") as f:
                    f.write(f"Verification failed for {source} -> {dest_path}\n")
        else:
            counters["missing_sources"] += 1
            with open(ERRORS_FILE, "a") as f:
                f.write(f"Missing source: {source} (intended for {dest_repo}: {dest_path})\n")
    elif status == "needs_review":
        counters["skipped_needs_review"] += 1
        line = f"{source} -> {dest_repo}/{Path(dest_path).relative_to('repos/')} (reason: {entry.get('reason', 'N/A')})\n"
        with open(PENDING_FILE, "a") as f:
            f.write(line)
    else:
        # Unexpected status, log
        with open(ERRORS_FILE, "a") as f:
            f.write(f"Unexpected status '{status}' for {source}\n")

def main():
    """Main execution."""
    # Initialize counters and samples
    counters = {"total_entries": 0, "copied": 0, "skipped_needs_review": 0, "missing_sources": 0}
    copied_samples = []

    # Clear log files if exist (for fresh run, but append for idempotency)
    for log in [PENDING_FILE, ERRORS_FILE]:
        Path(log).touch(exist_ok=True)

    # Read and validate mapping
    with open(MAPPING_FILE) as f:
        data = json.load(f)

    if not validate_mapping(data):
        raise ValueError("Invalid mapping schema")

    entries = data["entries"]
    counters["total_entries"] = len(entries)

    # Process entries
    for entry in entries:
        process_entry(entry, counters, copied_samples)

    # Generate report
    report = {
        "version": 1,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "source_mapping": MAPPING_FILE,
        "counts": counters,
        "copied_samples": copied_samples[:5]  # Ensure max 5
    }

    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Split complete. Report: {REPORT_FILE}")
    print(f"Counters: {counters}")

if __name__ == "__main__":
    main()
