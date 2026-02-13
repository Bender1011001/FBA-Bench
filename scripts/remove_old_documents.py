from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


DOC_EXTS = {
    ".md",
    ".rst",
    ".txt",
    ".html",
    ".css",
    # Treat JSON as documentation only when it's under docs/ (leaderboard site assets).
    ".json",
}

# Keep a minimal set of governance/legal/project-metadata docs even if "old".
EXCLUDE_BASENAMES = {
    "AGENTS.md",
    "LICENSE",
    "README.md",
    "DEV_SETUP.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "TERMS_OF_SERVICE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
}

EXCLUDE_DIR_PARTS = {
    ".git",
}


@dataclass(frozen=True)
class Candidate:
    path: Path
    mtime: datetime


def repo_root() -> Path:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        return Path(out)
    except Exception:
        return Path.cwd()


def is_doc_file(p: Path, root: Path) -> bool:
    if p.name in EXCLUDE_BASENAMES:
        return False

    # Keep core docs site assets even if they get "old"; removing them breaks the docs site.
    try:
        rel = p.relative_to(root / "docs").as_posix()
        if rel in {"index.html", "docs.html", "style.css", "sim-theater.html"}:
            return False
        if rel in {"_headers", "_redirects", ".nojekyll", "CNAME"}:
            return False
    except Exception:
        pass

    # Never treat config / code as "documents" just because they are JSON.
    # JSON is only in-scope when it lives under docs/.
    if p.suffix.lower() == ".json":
        try:
            p.relative_to(root / "docs")
        except Exception:
            return False

    return p.suffix.lower() in DOC_EXTS


def iter_doc_candidates(root: Path) -> list[Candidate]:
    out: list[Candidate] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs.
        parts = set(Path(dirpath).parts)
        if parts & EXCLUDE_DIR_PARTS:
            dirnames[:] = []
            continue

        # Skip virtualenvs and obvious runtime dirs; they are not part of "project docs".
        # (They usually aren't git-tracked anyway, but this speeds the walk.)
        dirnames[:] = [
            d
            for d in dirnames
            if d
            not in {
                ".venv",
                "venv",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            }
        ]

        for fn in filenames:
            p = Path(dirpath) / fn
            if not is_doc_file(p, root):
                continue
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            out.append(Candidate(path=p, mtime=datetime.fromtimestamp(st.st_mtime)))
    return out


def git_tracked(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    try:
        subprocess.check_output(["git", "ls-files", "--error-unmatch", rel], cwd=root, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def delete_path(path: Path, root: Path) -> None:
    if git_tracked(path, root):
        rel = path.relative_to(root).as_posix()
        subprocess.check_call(["git", "rm", "-f", rel], cwd=root)
    else:
        path.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Delete documents older than this many days (by filesystem mtime). Default: 7.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete files. Default is dry-run.")
    args = parser.parse_args(argv)

    root = repo_root()
    cutoff = datetime.now() - timedelta(days=args.days)

    candidates = iter_doc_candidates(root)
    to_delete = [c for c in candidates if c.mtime < cutoff]
    to_delete.sort(key=lambda c: (c.mtime, str(c.path)))

    print(f"repo_root: {root}")
    print(f"cutoff: {cutoff.isoformat(timespec='seconds')}")
    print(f"candidates: {len(candidates)}")
    print(f"older_than_{args.days}_days: {len(to_delete)}")

    if not to_delete:
        return 0

    for c in to_delete[:200]:
        rel = c.path.relative_to(root)
        print(f"DELETE  {c.mtime.isoformat(timespec='seconds')}  {rel.as_posix()}")
    if len(to_delete) > 200:
        print(f"... ({len(to_delete) - 200} more)")

    if not args.apply:
        print("dry-run: no files deleted (pass --apply to delete).")
        return 0

    for c in to_delete:
        delete_path(c.path, root)

    print("apply: deletion completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
