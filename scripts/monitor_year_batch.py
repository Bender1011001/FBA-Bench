#!/usr/bin/env python3
"""
Live monitor for year-like batch runs in artifacts/year_runs/<latest_timestamp>.
Prints progress updates to terminal every 10 seconds.
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path


def find_latest_run_dir():
    """Find the newest artifacts/year_runs/<timestamp> directory."""
    year_runs_dir = Path("artifacts/year_runs")
    if not year_runs_dir.exists():
        return None
    timestamps = [d for d in year_runs_dir.iterdir() if d.is_dir()]
    if not timestamps:
        return None
    latest = max(timestamps, key=lambda d: datetime.strptime(d.name, "%Y%m%d_%H%M%S"))
    return latest

def tail_file(file_path, lines=10):
    """Read the last N lines of a file."""
    if not file_path.exists():
        return []
    with open(file_path, encoding='utf-8') as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        lines_list = []
        while len(lines_list) < lines and pos > 0:
            pos -= 1
            f.seek(pos)
            if f.read(1) == '\n':
                lines_list.append(f.readline())
        return lines_list[::-1]  # Reverse to chronological order

def count_openrouter_successes(log_path):
    """Count 'OpenRouter call ok' lines in log."""
    if not log_path.exists():
        return 0
    with open(log_path, encoding='utf-8') as f:
        content = f.read()
    return len(re.findall(r'OpenRouter call ok', content))

def extract_token_usage(log_path):
    """Extract total tokens from log (sum of total_tokens)."""
    if not log_path.exists():
        return 0
    total = 0
    with open(log_path, encoding='utf-8') as f:
        for line in f:
            match = re.search(r'total_tokens=(\d+)', line)
            if match:
                total += int(match.group(1))
    return total

def main():
    print("Monitoring year-like batch runs... Press Ctrl+C to stop.")
    last_summary = ""
    while True:
        run_dir = find_latest_run_dir()
        if not run_dir:
            print(f"{datetime.now().strftime('%H:%M:%S')}: No run directory found. Waiting...")
            time.sleep(10)
            continue

        summary_path = run_dir / "summary.md"
        logs = list(run_dir.glob("*.log"))

        # Print current summary content
        if summary_path.exists():
            with open(summary_path, encoding='utf-8') as f:
                current_summary = f.read()
            if current_summary != last_summary:
                print(f"\n{datetime.now().strftime('%H:%M:%S')}: Summary updated:")
                print(current_summary)
                last_summary = current_summary

        # Print progress for each log
        print(f"\n{datetime.now().strftime('%H:%M:%S')}: Active runs in {run_dir.name} ({len(logs)} logs):")
        for log in sorted(logs):
            status = "IN_PROGRESS" if log.stat().st_size == 0 else "COMPLETE"
            openrouter_calls = count_openrouter_successes(log)
            tokens = extract_token_usage(log)
            tail = tail_file(log, 3)
            print(f"  - {log.name}: {status} | OpenRouter calls: {openrouter_calls} | Tokens: {tokens} | Tail: {' '.join(tail)}")

        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
