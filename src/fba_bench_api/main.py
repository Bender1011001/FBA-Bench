import os

import uvicorn

from fba_bench_api.server.app_factory import create_app as _create_app


# Issue 77: Use factory pattern to avoid module-level side effects/startups.
# Expose factory for ASGI servers (uvicorn --factory ...)
def get_app():
    return _create_app()


# Back-compat exports for older tests and integrations.
# Note: this does create the app at import time. Prefer using the factory (get_app)
# in production ASGI servers.
create_app = _create_app
app = get_app()


def run():
    """Creates and runs the FastAPI application."""
    host = os.environ.get("FBA_BENCH_HOST", "0.0.0.0")
    port = int(os.environ.get("FBA_BENCH_PORT", 8000))
    reload = os.environ.get("FBA_BENCH_RELOAD", "true").lower() == "true"
    # Use factory mode string reference to ensure lazy initialization
    uvicorn.run(
        "fba_bench_api.main:get_app", host=host, port=port, reload=reload, factory=True
    )


if __name__ == "__main__":
    run()
