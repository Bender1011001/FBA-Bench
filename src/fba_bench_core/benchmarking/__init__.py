"""
Compatibility shim for legacy 'fba_bench_core.benchmarking' imports.
Redirects to 'src.benchmarking' components.
"""

import sys
from src.benchmarking.core import engine
from src.benchmarking.core import config

# Expose modules that were previously under 'fba_bench_core.benchmarking'
sys.modules["fba_bench_core.benchmarking.engine"] = engine
sys.modules["fba_bench_core.benchmarking.config"] = config

__all__ = ["engine", "config"]
