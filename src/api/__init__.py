"""
Legacy `api.*` namespace compatibility package.

Some tests and legacy modules import from `api.*` even though the canonical
backend package is `fba_bench_api.*`. Keep a narrow shim here so those imports
resolve without forcing a large refactor.
"""

__all__ = []
