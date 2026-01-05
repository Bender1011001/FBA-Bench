"""
Minimal, production-safe tracer shim to satisfy imports.
Provides a no-op tracer interface that logs spans using stdlib logging.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger("instrumentation.tracer")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class Tracer:
    def __init__(self, service_name: str = "fba-bench-enterprise") -> None:
        self.service_name = service_name

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Iterator[None]:
        logger.info("start span: %s attrs=%s", name, attributes or {})
        try:
            yield
            logger.info("end span: %s", name)
        except Exception as exc:
            logger.exception("span error: %s err=%r", name, exc)
            raise

def setup_tracing(service_name: str = "fba-bench-enterprise") -> Tracer:
    """
    Initialize and return a simple tracer instance.
    """
    return Tracer(service_name=service_name)
