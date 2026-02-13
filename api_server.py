"""
Compatibility entrypoint for running the FastAPI app.

Preferred production entrypoint:
  uvicorn fba_bench_api.main:get_app --factory --host 0.0.0.0 --port 8000

This module exists because multiple Docker/compose files expect `api_server:app`.
"""

from __future__ import annotations

import os

import uvicorn

from fba_bench_api.main import get_app


# NOTE: This creates the app at import time. The codebase also supports uvicorn's
# `--factory` mode (see fba_bench_api.main:get_app) to avoid import-time side effects.
app = get_app()


def main() -> None:
    host = os.environ.get("FBA_BENCH_HOST", os.environ.get("HOST", "0.0.0.0"))
    port = int(os.environ.get("FBA_BENCH_PORT", os.environ.get("PORT", 8000)))
    reload = os.environ.get("FBA_BENCH_RELOAD", os.environ.get("UVICORN_RELOAD", "false"))
    reload_enabled = str(reload).lower() in {"1", "true", "yes", "on"}

    uvicorn.run("api_server:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    main()

