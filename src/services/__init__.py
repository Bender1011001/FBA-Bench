import os
import warnings

# Issue 91: Conditionalize warning to prevent spam in logs/tests
if not os.environ.get("FBA_BENCH_SUPPRESS_DEPRECATION"):
    warnings.warn(
        "The 'services' package is deprecated; use 'fba_bench_core.services'. "
        "Set FBA_BENCH_SUPPRESS_DEPRECATION=1 to suppress this warning.",
        DeprecationWarning,
        stacklevel=2,
    )

from fba_bench_core.services import * # noqa: F403
