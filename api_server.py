"""FBA-Bench Enterprise API Server Runner.

This script serves the FastAPI application using Uvicorn when invoked directly.
Intended for local development and testing.

Usage:
    python api_server.py

This will start the server at http://localhost:8000 (configurable via env vars).
"""

import os
import sys
import uvicorn

# Ensure src is in path if running from root without install
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

try:
    from fba_bench_api.server.app_factory import create_app
except ImportError:
    # Fallback if src isn't structued as expected or dependencies missing
    print("Error: Could not import fba_bench_api. Ensure dependencies are installed.")
    sys.exit(1)

# Create the application instance for uvicorn to discover
app = create_app()

if __name__ == "__main__":
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )