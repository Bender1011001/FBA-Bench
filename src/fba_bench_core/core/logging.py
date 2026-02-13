"""Centralized logging configuration for FBA-Bench.

Provides:
- setup_logging(): idempotent initialization for root and common library loggers
- request_id correlation via contextvars and a logging Filter
- FastAPI/Starlette middleware to attach a request_id per request
- Optional JSON logging via python-json-logger
- Sensible defaults for dev/prod controlled by environment variables

Environment variables (optional):
- FBA_LOG_LEVEL: DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
- FBA_LOG_FORMAT: text|json (default: text)
- FBA_LOG_FILE: path to a log file (default: none)
- FBA_LOG_INCLUDE_TRACEBACKS: true|false (default: true)
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Optional

from fba_bench_core.config import get_settings

try:
    from pythonjsonlogger import jsonlogger  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    jsonlogger = None  # type: ignore


# Context var for correlation id
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("fba_request_id", default=None)


def get_request_id() -> Optional[str]:
    """Return the current request_id if set in context."""
    return _request_id_ctx.get()


def set_request_id(value: Optional[str]) -> None:
    """Set the current request_id in context."""
    _request_id_ctx.set(value)


class RequestIdFilter(logging.Filter):
    """Injects request_id into log record if available."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = get_request_id()
        record.request_id = rid if rid else "-"
        return True


class UTCFormatter(logging.Formatter):
    converter = time.gmtime


def _build_text_formatter(include_tracebacks: bool) -> logging.Formatter:
    parts = [
        "%(asctime)s",
        "%(levelname)s",
        "%(name)s",
        "[req=%(request_id)s]",
        "%(message)s",
    ]
    if include_tracebacks:
        # When exception info is present, %(message)s already includes it via logging.exception
        pass
    fmt = " | ".join(parts)
    formatter = UTCFormatter(fmt)
    formatter.default_msec_format = "%s.%03d"
    return formatter


def _build_json_formatter(include_tracebacks: bool) -> logging.Formatter:
    if jsonlogger is None:
        # Fallback to text if python-json-logger is not available
        return _build_text_formatter(include_tracebacks)
    fields = [
        "asctime",
        "levelname",
        "name",
        "request_id",
        "message",
    ]
    if include_tracebacks:
        fields.extend(["exc_info", "stack_info"])
    fmt = " ".join([f"%({f})s" for f in fields])
    formatter = jsonlogger.JsonFormatter(fmt, json_ensure_ascii=False)
    return formatter


def _sanitize_existing_handlers(root_logger: logging.Logger) -> None:
    # Avoid duplicate logs on repeated setup calls
    seen_stream = False
    new_handlers: list[logging.Handler] = []
    for h in root_logger.handlers:
        # Keep the first stream handler, drop duplicates configured elsewhere
        if isinstance(h, logging.StreamHandler):
            if not seen_stream:
                new_handlers.append(h)
                seen_stream = True
            continue
        # Keep non-stream handlers (might be file/syslog if user added)
        new_handlers.append(h)
    root_logger.handlers = new_handlers


def setup_logging(
    level: Optional[str] = None,
    json_format: Optional[bool] = None,
    log_file: Optional[str] = None,
    include_tracebacks: Optional[bool] = None,
) -> None:
    """Initialize centralized logging configuration.

    Idempotent: safe to call multiple times.

    Args:
        level: Logging level name; defaults to env FBA_LOG_LEVEL or INFO.
        json_format: Use JSON logs if True or env FBA_LOG_FORMAT=json and python-json-logger present.
        log_file: Optional path to write logs; defaults to env FBA_LOG_FILE.
        include_tracebacks: Include exception/stack info fields; defaults to env FBA_LOG_INCLUDE_TRACEBACKS or True.
    """
    # Resolve configuration from centralized settings with env/YAML precedence
    settings = get_settings()
    level_name = (level or (settings.logging_level or "INFO")).upper()
    resolved_level = getattr(logging, level_name, logging.INFO)

    fmt_setting = (settings.logging_format or "text").lower()
    resolved_json = json_format if json_format is not None else (fmt_setting == "json")
    resolved_include_tb = (
        include_tracebacks
        if include_tracebacks is not None
        else settings.logging_include_tracebacks
    )
    resolved_log_file = log_file or settings.logging_file

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    # Build formatter and base handler
    formatter = (
        _build_json_formatter(resolved_include_tb)
        if resolved_json
        else _build_text_formatter(resolved_include_tb)
    )
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(RequestIdFilter())

    # Reset handlers to avoid duplicates on re-init
    root_logger.handlers.clear()
    root_logger.addHandler(stream_handler)

    if resolved_log_file:
        try:
            fh = logging.FileHandler(resolved_log_file, encoding="utf-8")
            fh.setFormatter(formatter)
            fh.addFilter(RequestIdFilter())
            root_logger.addHandler(fh)
        except (OSError, AttributeError) as e:  # pragma: no cover
            # If file handler fails, proceed with stdout only
            root_logger.warning(f"Failed to attach file handler: {e}")

    # Quiet excessively chatty libraries but keep warnings/errors
    for noisy in (
        "uvicorn.access",
        "urllib3",
        "httpx",
        "watchfiles",
        "asyncio",
        "botocore",
    ):
        logging.getLogger(noisy).setLevel(max(resolved_level, logging.WARNING))

    # Align uvicorn loggers with our root formatter
    for uv in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(uv)
        _sanitize_existing_handlers(lg)
        for h in lg.handlers:
            h.setFormatter(formatter)
            h.addFilter(RequestIdFilter())
        lg.setLevel(resolved_level)

    # Slightly friendlier formatting for FastAPI/Starlette as well
    for fa in ("fastapi", "starlette"):
        logging.getLogger(fa).setLevel(resolved_level)


# FastAPI middleware to assign a request_id per request
try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
except (
    ImportError
):  # pragma: no cover - Starlette present with FastAPI; guard for import-time use
    BaseHTTPMiddleware = object  # type: ignore
    Request = object  # type: ignore
    Response = object  # type: ignore


class RequestIdMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """Starlette middleware that attaches a unique request_id to each request.

    - Incoming X-Request-ID is honored if present (trust boundary decisions left to deployment)
    - Otherwise generates a UUID4
    - Request ID is exposed to logging via ContextVar and response header
    """

    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        incoming = request.headers.get(self.header_name)
        rid = incoming if incoming else str(uuid.uuid4())
        token = _request_id_ctx.set(rid)
        try:
            response: Response = await call_next(request)
        finally:
            # Ensure we clear context to avoid leakage across tasks
            _request_id_ctx.reset(token)
        response.headers[self.header_name] = rid
        return response
