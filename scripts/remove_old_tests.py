#!/usr/bin/env python3
"""
Remove old tests by filesystem mtime.

Project policy (per user request):
- Treat tests older than 1 week as stale/false and remove them.

Safety rails:
- Keep the curated tests currently used by CI (Makefile targets).
- Keep all contract tests under tests/contracts/.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RemovalCandidate:
    path: Path
    mtime_epoch: float
    tracked: bool


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _is_git_repo(root: Path) -> bool:
    return (root / ".git").exists()


def _tracked_paths(root: Path) -> set[Path]:
    if not _is_git_repo(root):
        return set()
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=str(root),
        check=False,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return set()
    out = set()
    for line in res.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        out.add((root / rel).resolve())
    return out


def _safe_rmtree(dir_path: Path) -> None:
    try:
        shutil.rmtree(dir_path)
    except FileNotFoundError:
        return
    except PermissionError:
        # Best-effort cleanup; Windows can hold directory handles briefly.
        return


def _delete_file(root: Path, candidate: RemovalCandidate, *, apply: bool) -> None:
    rel = os.path.relpath(candidate.path, root)
    if not apply:
        return
    if candidate.tracked and _is_git_repo(root):
        subprocess.run(["git", "rm", "-f", "--", rel], cwd=str(root), check=False)
        return
    try:
        candidate.path.unlink()
    except FileNotFoundError:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="Delete tests older than N days.")
    parser.add_argument("--apply", action="store_true", help="Actually delete files.")
    args = parser.parse_args()

    root = _repo_root()
    cutoff_epoch = time.time() - (args.days * 24 * 60 * 60)

    keep_rel = {
        "tests/conftest.py",
        "tests/unit/api/test_dependencies_managers.py",
        "tests/unit/test_eventbus_logging.py",
        "tests/unit/test_learning.py",
    }
    keep_abs = {(root / p).resolve() for p in keep_rel}

    tracked = _tracked_paths(root)

    candidates: list[RemovalCandidate] = []
    searched = 0
    for base in (root / "tests", root / "integration_tests"):
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            searched += 1
            rp = p.resolve()
            if rp in keep_abs:
                continue
            # Keep all contract tests.
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.as_posix()
            if rel.startswith("tests/contracts/"):
                continue
            try:
                mtime = p.stat().st_mtime
            except FileNotFoundError:
                continue
            if mtime < cutoff_epoch:
                candidates.append(RemovalCandidate(path=p, mtime_epoch=mtime, tracked=(rp in tracked)))

    candidates.sort(key=lambda c: c.path.as_posix())

    print(f"repo_root: {root}")
    print(f"searched_py_files: {searched}")
    print(f"cutoff_days: {args.days}")
    print(f"delete_candidates: {len(candidates)}")
    print(f"mode: {'APPLY' if args.apply else 'DRY_RUN'}")

    for c in candidates[:80]:
        rel = os.path.relpath(c.path, root)
        tracked_s = "tracked" if c.tracked else "untracked"
        print(f"- {rel} ({tracked_s})")
    if len(candidates) > 80:
        print(f"... ({len(candidates) - 80} more)")

    for c in candidates:
        _delete_file(root, c, apply=args.apply)

    if args.apply:
        # Remove empty directories under tests/ and integration_tests/
        for base in (root / "tests", root / "integration_tests"):
            if not base.exists():
                continue
            # bottom-up deletion
            dirs = sorted([d for d in base.rglob("*") if d.is_dir()], reverse=True)
            for d in dirs:
                try:
                    if any(d.iterdir()):
                        continue
                except FileNotFoundError:
                    continue
                _safe_rmtree(d)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
