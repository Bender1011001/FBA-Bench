import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reproducibility.event_snapshots import EventSnapshot


class CIIntegration:
    """
    Handles CI-related tasks for reproducibility, such as:
    - Capturing event streams after builds for golden snapshot comparisons.
    - Providing utilities for verifying reproducibility in CI environments.
    """

    @staticmethod
    def get_current_git_sha() -> str:
        """
        Retrieves the current Git commit SHA.
        Returns 'unknown_sha' if not in a Git repository or command fails.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=Path.cwd(),
                timeout=10,
            )
            return result.stdout.strip()
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            return "unknown_sha"

    @staticmethod
    def capture_golden_snapshot(
        events: List[Dict[str, Any]], run_id: str
    ) -> Optional[Path]:
        """
        Captures a golden event snapshot, typically after a successful build/test run in CI.
        The snapshot is named using the current Git SHA and a unique run_id.
        """
        git_sha = CIIntegration.get_current_git_sha()
        if git_sha == "unknown_sha":
            print(
                "Warning: Not in a Git repository. Cannot capture golden snapshot with SHA."
            )
            return None

        print(f"Capturing golden snapshot for Git SHA: {git_sha} and Run ID: {run_id}")
        return EventSnapshot.dump_events(events, git_sha, run_id)

    @staticmethod
    def verify_reproducibility(
        current_events: List[Dict[str, Any]],
        baseline_git_sha: str,
        baseline_run_id: str,
    ) -> bool:
        """
        Compares the current event stream against a previously captured golden snapshot.
        This function is designed to be used in CI to detect reproducibility regressions.

        Args:
            current_events (List[Dict[str, Any]]): The event stream from the current run.
            baseline_git_sha (str): The Git SHA of the baseline snapshot.
            baseline_run_id (str): The Run ID of the baseline snapshot.

        Returns:
            bool: True if event streams are identical, False otherwise.
        """
        # Prefer parquet but support JSON fallback to match snapshot writer behavior
        base_stem = f"{baseline_git_sha}_{baseline_run_id}"
        parquet_path = EventSnapshot.ARTIFACTS_DIR / f"{base_stem}.parquet"
        json_path = EventSnapshot.ARTIFACTS_DIR / f"{base_stem}.json"

        if parquet_path.exists():
            target_path = parquet_path
        elif json_path.exists():
            target_path = json_path
        else:
            print(
                f"Error: Baseline snapshot '{base_stem}.parquet' (or JSON fallback) not found. Cannot verify reproducibility."
            )
            return False

        print(f"Comparing current events against baseline snapshot: {target_path}")
        baseline_events = EventSnapshot.load_events(target_path)

        is_reproducible = EventSnapshot.compare_event_streams(
            current_events, baseline_events
        )

        if is_reproducible:
            print("Reproducibility check: PASSED. Event streams are identical.")
        else:
            print("Reproducibility check: FAILED. Event streams differ.")
            # In a real CI, you might want to raise an error here.

        return is_reproducible


# Example CI workflow integration (not executed directly, but shows usage)
if __name__ == "__main__":
    # This block demonstrates how these functions might be used in a CI pipeline.
    # It assumes you have a way to get 'events' from a simulation run.
    print("CI Integration Utility - Example Usage:")

    # Simulate some events
    sample_events = [
        {
            "timestamp": datetime.datetime.now().isoformat(),  # type: ignore[attr-defined]
            "event_type": "ORDER_PLACED",
            "data": {"order_id": "1", "value": 100},
        },
        {
            "timestamp": datetime.datetime.now().isoformat(),  # type: ignore[attr-defined]
            "event_type": "SHIPMENT_CREATED",
            "data": {"shipment_id": "A", "order_id": "1"},
        },
    ]

    # Example 1: Capture a snapshot
    # In CI, 'run_id' could be a build number or dynamically generated
    current_git_sha = CIIntegration.get_current_git_sha()
    if current_git_sha != "unknown_sha":
        snapshot_path = CIIntegration.capture_golden_snapshot(
            sample_events, run_id="build_123"
        )
        if snapshot_path:
            print(f"Captured example snapshot to {snapshot_path}")

            # Example 2: Verify reproducibility against the captured snapshot
            # Simulate another run (ideally identical if deterministic)
            re_run_events = [
                {
                    "timestamp": datetime.datetime.now().isoformat(),  # type: ignore[attr-defined]
                    "event_type": "ORDER_PLACED",
                    "data": {"order_id": "1", "value": 100},
                },
                {
                    "timestamp": datetime.datetime.now().isoformat(),  # type: ignore[attr-defined]
                    "event_type": "SHIPMENT_CREATED",
                    "data": {"shipment_id": "A", "order_id": "1"},
                },
            ]

            # Note: For a real test, you'd load the baseline from a known SHA and Run ID in your artifact store
            # For this example, we're comparing against the one just created.
            is_reproducible = CIIntegration.verify_reproducibility(
                re_run_events, current_git_sha, "build_123"
            )
            print(f"Events are reproducible: {is_reproducible}")
    else:
        print("Skipping CI integration examples as not in a Git repository.")
