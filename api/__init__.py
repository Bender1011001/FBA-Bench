"""
Compatibility shim for legacy 'api' imports.
Redirects to 'fba_bench_api' components.
"""

import sys
from fba_bench_api.core import database as db
from fba_bench_api import models
from fba_bench_api.api import dependencies

# Expose modules that were previously under 'api'
sys.modules["api.db"] = db
sys.modules["api.models"] = models
sys.modules["api.dependencies"] = dependencies

__all__ = ["db", "models", "dependencies"]