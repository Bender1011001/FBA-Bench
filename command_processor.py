from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol

try:
    # Local import to integrate with our analyzer if available
    from trace_analyzer import TraceAnalyzer
except ImportError:
    TraceAnalyzer = None  # type: ignore


class CommandHandler(Protocol):
    async def __call__(self, args: Dict[str, Any]) -> Dict[str, Any]:
        ...


@dataclass
class CommandResult:
    ok: bool
    command: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "ok": self.ok,
            "command": self.command,
            "data": self.data,
        }
        if self.error:
            d["error"] = self.error
        return d


class SmartCommandProcessor:
    """Production-ready command processor with async handlers and deterministic behavior.

    Features:
    - Register async command handlers at runtime.
    - Built-in 'health', 'echo', 'trace_analyze' commands.
    - Deterministic outputs and strict argument validation.
    - Non-fatal error handling with structured CommandResult.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, CommandHandler] = {}
        self._register_builtin_handlers()

    # ---------------- Public API ----------------

    def register(self, name: str, handler: CommandHandler) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("Command name must be a non-empty string")
        if not callable(handler):
            raise ValueError("Handler must be callable")
        self._handlers[name] = handler

    def unregister(self, name: str) -> None:
        self._handlers.pop(name, None)

    def has(self, name: str) -> bool:
        return name in self._handlers

    def available_commands(self) -> Dict[str, str]:
        return {k: getattr(v, "__doc__", "") or "" for k, v in self._handlers.items()}

    async def process(self, command: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = args or {}
        try:
            if not command or not isinstance(command, str):
                return CommandResult(False, command or "<none>", error="Invalid command").to_dict()
            handler = self._handlers.get(command)
            if handler is None:
                return CommandResult(False, command, error=f"Unknown command: {command}").to_dict()

            # Execute handler
            data = await handler(args)
            return CommandResult(True, command, data=data).to_dict()

        except KeyError as ex:
            # Specific: missing keys or lookup errors in handlers
            return CommandResult(False, command, error=str(ex)).to_dict()
        except ValueError as ex:
            # Specific: invalid argument values/types
            return CommandResult(False, command, error=str(ex)).to_dict()
        except Exception as ex:
            # Fallback safeguard: preserve existing error payload formatting
            return CommandResult(False, command, error=str(ex)).to_dict()

    # ---------------- Built-ins ----------------

    def _register_builtin_handlers(self) -> None:
        self.register("health", self._cmd_health)
        self.register("echo", self._cmd_echo)
        self.register("trace_analyze", self._cmd_trace_analyze)

    async def _cmd_health(self, _: Dict[str, Any]) -> Dict[str, Any]:
        """Return processor health and available commands."""
        return {
            "status": "ok",
            "commands": sorted(self._handlers.keys()),
        }

    async def _cmd_echo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Echo back provided payload with metadata."""
        payload = args.get("payload", {})
        if not isinstance(payload, dict):
            raise ValueError("echo.payload must be a dict")
        return {
            "payload": payload,
            "length": len(payload),
            "keys": sorted(payload.keys()),
        }

    async def _cmd_trace_analyze(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trace/log records using TraceAnalyzer if available.

        args:
          records: list[dict] - required
          sample_limit: int - optional
          thresholds: dict - optional for anomaly detection
        """
        if TraceAnalyzer is None:
            raise RuntimeError("TraceAnalyzer not available")

        records = args.get("records")
        if not isinstance(records, list):
            raise ValueError("trace_analyze.records must be a list")
        sample_limit = int(args.get("sample_limit", 10))
        thresholds = args.get("thresholds") or {}

        analyzer = TraceAnalyzer()
        report = analyzer.analyze(records, sample_limit=sample_limit)
        # Optionally recompute anomalies with provided thresholds
        if thresholds:
            report.anomalies = analyzer.detect_anomalies(report, thresholds=thresholds)

        return {
            "summary": analyzer.summarize(report),
            "report": report.to_dict(),
        }


# Convenience function for synchronous contexts/tests
def process_command_sync(
    processor: Optional[SmartCommandProcessor],
    command: str,
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    proc = processor or SmartCommandProcessor()
    return asyncio.run(proc.process(command, args or {}))
