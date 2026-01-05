#!/usr/bin/env python3
"""
Minimal verification script for golden masters.
Runs relevant pytest tests that perform golden master comparisons and exits non-zero on failure.
Prints concise diff summaries from test output.
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    # Run specific tests that verify against golden masters
    # These tests use GoldenMasterTester.compare_against_golden and CIIntegration.verify_reproducibility
    test_files = [
        "tests/test_reproducibility.py",
        "tests/validation/functional_validation.py",
        "integration_tests/test_scientific_reproducibility.py",
        "tests/integration/test_tier2_golden_master.py",
    ]
    
    # Ensure we're in project root
    scripts_dir = Path(__file__).parent
    project_root = scripts_dir.parent
    os.chdir(project_root)
    
    # Run pytest on relevant tests with verbose output for diffs, short traceback
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",  # Verbose for test names
        "--tb=short",  # Concise tracebacks
        "--no-header", "--no-summary",  # Minimal output, focus on failures
    ] + test_files
    
    # Use poetry if available, else direct
    try:
        result = subprocess.run(
            ["poetry", "run"] + cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=300,  # 5 min timeout
        )
    except FileNotFoundError:
        # Fallback to direct python if poetry not installed
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=300,
        )
    
    # Print output (includes diffs from test assertions)
    if result.stdout:
        print("Verification Output:")
        print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    
    # Exit non-zero if tests failed (pytest returns non-zero on failure)
    if result.returncode != 0:
        print("\n[FAILED] Golden master verification FAILED. Mismatches detected in outputs.")
        print("Review the diffs above and regenerate golden masters if intentional.")
        sys.exit(1)
    else:
        print("\n[PASSED] Golden master verification PASSED. All outputs match baselines.")
        sys.exit(0)

if __name__ == "__main__":
    main()
