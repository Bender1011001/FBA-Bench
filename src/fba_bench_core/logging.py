"""
Unified logging bootstrap for FBA-Bench (Phase 2: Structural Unification).

Usage:
    from fba_bench_core.settings import get_settings
    from fba_bench_core.logging import configure_logging

    settings = get_settings()
    configure_logging(settings)  # idempotent

- Supports JSON and plain formats
- Supports stdout/stderr/file destinations
- Respects configured log level across root and key library loggers
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

try:
    # Optional dependency; if missing and json=True, we fall back to plain formatting
    from pythonjsonlogger import jsonlogger  # type: ignore
except ImportError:  # pragma: no cover - optional import
    jsonlogger = None  # type: ignore[assignment]


_CONFIGURED_FLAG_ENV = "FBA_LOGGING_CONFIGURED"
_configured_flag_local = False  # module-local safeguard for idempotence


def _level_from_str(level: str) -> int:
    try:
        return getattr(logging, level.upper())
    except AttributeError:
        return logging.INFO


def _make_handler(destination: str, filename: Optional[str]) -> logging.Handler:
    if destination == "stdout":
        return logging.StreamHandler(stream=sys.stdout)
    if destination == "stderr":
        return logging.StreamHandler(stream=sys.stderr)
    # file destination
    target = filename or "fba-bench.log"
    path = Path(target)
    # Ensure parent directory exists if a path is provided, ignore errors
    try:
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return logging.FileHandler(path, encoding="utf-8")


def _make_formatter(json_enabled: bool, fmt: str) -> logging.Formatter:
    if json_enabled and jsonlogger is not None:
        # Add traceparent for OTEL correlation
        class OTELJsonFormatter(jsonlogger.JsonFormatter):
            def add_fields(self, log_record, record, message_dict):
                super().add_fields(log_record, record, message_dict)
                if hasattr(record, "trace_id") and record.trace_id:
                    log_record["trace_id"] = record.trace_id
                if hasattr(record, "span_id") and record.span_id:
                    log_record["span_id"] = record.span_id
                # Extract traceparent from environment if available (set by middleware)
                traceparent = getattr(record, "traceparent", None) or os.environ.get(
                    "traceparent"
                )
                if traceparent:
                    log_record["traceparent"] = traceparent

        return OTELJsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(process)d %(threadName)s"
        )

    # Plain formatter with trace info
    formatter = logging.Formatter(fmt + " [trace:%(traceparent)s]")
    return formatter


def configure_logging(settings=None, *, force: bool = False) -> None:
    """
    Configure root logging according to settings.logging. Safe to call multiple times.

    Params:
      - settings: fba_bench_core.settings.Settings (optional; lazily loaded if None)
      - force: if True, reconfigure even if already configured
    """
    global _configured_flag_local

    if settings is None:
        try:
            from fba_bench_core.settings import (
                get_settings,
            )  # lazy import to avoid cycles

            settings = get_settings()
        except (ImportError, AttributeError, ValueError, RuntimeError):
            # As a last resort, use a minimal default if settings cannot be loaded
            class _Fallback:
                class logging:  # type: ignore
                    level = "INFO"
                    json = True  # Default to JSON for structured logging
                    destination = "stdout"
                    filename = None
                    format = "%(asctime)s %(levelname)s %(name)s - %(message)s [trace:%(traceparent)s]"

            settings = _Fallback()  # type: ignore[assignment]

    # Idempotence: guard using both env flag (cross-process convention) and module-local variable
    already_configured = (
        _configured_flag_local
        or os.environ.get(_CONFIGURED_FLAG_ENV) == "1"
        or bool(logging.getLogger().handlers)
    )
    if already_configured and not force:
        return

    lvl = _level_from_str(settings.logging.level)
    handler = _make_handler(settings.logging.destination, settings.logging.filename)
    formatter = _make_formatter(settings.logging.json, settings.logging.format)
    handler.setFormatter(formatter)

    def trace_filter(record):
        if hasattr(record, "trace_id") and record.trace_id:
            record.traceparent = f"trace_id:{record.trace_id},span_id:{getattr(record, 'span_id', 'unknown')}"
        else:
            record.traceparent = "unknown"
        return True

    handler.addFilter(trace_filter)

    root = logging.getLogger()
    # Clear existing handlers to avoid duplicate logs if force=True
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    root.setLevel(lvl)
    root.addHandler(handler)

    # Tame noisy libraries and align to chosen level, but keep them slightly less verbose
    noisy_libs = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "httpx",
        "urllib3",
        "asyncio",
    ]
    for name in noisy_libs:
        lg = logging.getLogger(name)
        lg.setLevel(max(lvl, logging.INFO))

    # Mark configured
    _configured_flag_local = True
    os.environ[_CONFIGURED_FLAG_ENV] = "1"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Convenience accessor mirroring logging.getLogger, ensuring base configuration exists.
    """
    if not (_configured_flag_local or logging.getLogger().handlers):
        try:
            configure_logging()
        except (ImportError, AttributeError, ValueError, RuntimeError):
            # Never fail logger retrieval due to configuration issues
            pass
    return logging.getLogger(name)
