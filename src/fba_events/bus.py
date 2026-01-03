from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Awaitable, Mapping, MutableMapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[None]]
Selector = Union[type, str]
SubscriptionHandle = Tuple[Selector, Handler]


_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = InMemoryEventBus()
    return _global_event_bus


def set_event_bus(bus: EventBus) -> None:
    global _global_event_bus
    _global_event_bus = bus


class EventBus:
    """
    Async-first event bus contract.

    This base class defines the canonical async API. Implementations should be fully async and
    safe for concurrent usage from multiple tasks.

    Methods:
    - publish(event): enqueue and dispatch to matching subscribers
    - subscribe(event_selector, handler): register handler for an event class or string name
    - unsubscribe(handle): remove a previously registered handler
    - start(): start background dispatch loop(s) if required
    - stop(): stop background dispatch loop(s) gracefully
    - start_recording(): enable in-memory event recording
    - get_recorded_events(): retrieve a stable list of summarized recorded events

    Selectors:
    - event class/type: dispatches via isinstance(event, selector)
    - string event name: dispatches when the event's canonical type string matches

    Handlers:
    - async callable(event) -> None (preferred)
    - sync callable(event) -> None (will be wrapped in an async shim)

    Examples:
    - Subscribe to a class:
        async def on_tick(evt): ...
        handle = await bus.subscribe(TickEvent, on_tick)

    - Publish an event:
        await bus.publish(TickEvent(...))

    - Recording:
        await bus.start_recording()
        recorded = await bus.get_recorded_events()
    """

    async def publish(self, event: Any) -> None:
        raise NotImplementedError

    async def subscribe(self, event_selector: Any, handler: Any) -> Any:
        raise NotImplementedError

    async def unsubscribe(self, handle: Any) -> None:
        raise NotImplementedError

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def start_recording(self) -> None:
        raise NotImplementedError

    async def get_recorded_events(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def log_event(self, event: Any, event_type: str, ts: str) -> None:
        """
        Hook for logging/auditing events when they are published.
        Implementations should ensure this is non-blocking and resilient.
        Default is a no-op for compatibility.
        """
        return None


class InMemoryEventBus(EventBus):
    """
    In-memory asyncio-based EventBus implementation.

    Features:
    - asyncio.Queue staging of events
    - Background runner task to drain the queue
    - Concurrent handler execution per event via asyncio.create_task
    - Resilient to handler errors (logged, do not stop the bus)
    - Optional in-memory recording of summarized events for observability

    Recording schema (stable):
    { "event_type": str, "timestamp": str, "data": dict }
    """

    def __init__(self) -> None:
        # Subscribers keyed by either event class or string name
        self._subscribers: MutableMapping[Selector, List[Handler]] = {}
        # compat: defer queue creation to start() to bind to the running loop at start time, not import time
        self._queue: Optional[asyncio.Queue[Tuple[Any, str, str]]] = None
        self._runner_task: Optional[asyncio.Task] = None
        # compat: track the loop used to run the bus for safe teardown/restart
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Track handler tasks to enable graceful shutdown/drain
        self._handler_tasks: Set[asyncio.Task] = set()
        # Sentinel object used to request graceful shutdown of runner
        self._STOP = object()

        # Recording controls (defaults hardened for production-safety)
        self._recording_enabled: bool = False  # Default OFF
        self._recorded: List[Dict[str, Any]] = []
        # Cap for recorded events; default 5000, configurable via env
        self._recording_max: int = self._read_recording_max()
        self._recording_truncated: bool = False

        # Logging controls (enabled by default, configurable via env EVENT_LOGGING_ENABLED)
        self._logging_enabled: bool = self._read_logging_enabled()

        # Pre-compiled redaction configuration
        self._redact_key_patterns: List[re.Pattern] = [
            re.compile(pat, re.IGNORECASE)
            for pat in [
                "password",
                "api_key",
                "token",
                "secret",
                "authorization",
                "cookie",
            ]
        ]

        self._started: bool = False
        # Stats counters
        # Count of successfully published events for stats/observability
        self._events_published: int = 0
        # Count of events dequeued and dispatched to handlers
        self._events_processed: int = 0

    async def start(self) -> None:
        if self._started:
            return
        # compat: bind queue and runner to the current running loop at start time
        loop = asyncio.get_running_loop()
        self._loop = loop
        if self._queue is None:
            self._queue = asyncio.Queue()
        # use create_task within the currently running loop
        self._runner_task = loop.create_task(
            self._runner(), name="InMemoryEventBusRunner"
        )
        self._started = True
        logger.debug("InMemoryEventBus started")

    async def stop(self) -> None:
        if not self._started:
            return
        # Request graceful runner shutdown via sentinel
        try:
            if self._queue is not None:
                # Put a sentinel tuple that the runner will detect and exit on
                self._queue.put_nowait((self._STOP, "_STOP", ""))
        except (RuntimeError, AttributeError, TypeError):
            # If queue is gone or closed, proceed to awaiting/cancelling the runner
            pass

        # Await runner completion
        if self._runner_task:
            try:
                await self._runner_task
            except asyncio.CancelledError:
                # Treat as graceful termination
                pass
            except RuntimeError as e:
                # Event loop closed during teardown: swallow for test stability
                logger.debug("Runner stop encountered runtime error (ignored): %s", e)
            except (RuntimeError, AttributeError, TypeError) as e:
                logger.exception("Error while stopping InMemoryEventBus runner: %s", e)

        # Gracefully wait for handler tasks to finish briefly, then cancel stragglers
        pending = {t for t in list(self._handler_tasks) if not t.done()}
        if pending:
            try:
                done, still = await asyncio.wait(pending, timeout=0.25)
            except (RuntimeError, asyncio.CancelledError):
                done, still = set(), pending
            for t in still:
                t.cancel()
            if still:
                try:
                    await asyncio.gather(*still, return_exceptions=True)
                except (RuntimeError, asyncio.CancelledError):
                    pass
            self._handler_tasks.difference_update(done | still)

        # best-effort drain and drop queue
        q = self._queue
        self._queue = None
        if q is not None:
            try:
                while not q.empty():
                    q.get_nowait()
            except (RuntimeError, AttributeError):
                pass

        # compat: release loop and queue references to avoid cross-loop binding/leaks on Windows/pytest
        self._runner_task = None
        self._loop = None
        self._started = False
        logger.debug("InMemoryEventBus stopped")

    async def publish(self, event: Any) -> None:
        """
        Enqueue an event for dispatch with resolved type string and ISO-8601 timestamp.
        Also logs the event via log_event to provide an audit trail.

        Robust to pytest/Windows loop switches:
        - If the bus was started on a different loop than the current running loop,
          re-bind the internal queue and runner to the current loop transparently.
        """
        # Ensure we are bound to the current running loop
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop; start will bind when first loop becomes active
            current_loop = None  # type: ignore[assignment]

        if not self._started or self._queue is None:
            # Lazy start binds to the current running loop
            await self.start()
        else:
            # If loop has changed (common under pytest-asyncio), rebind queue/runner
            try:
                if (
                    self._loop is not None
                    and current_loop is not None
                    and self._loop is not current_loop
                ):
                    # Best-effort signal old runner to stop
                    try:
                        if self._queue is not None:
                            self._queue.put_nowait((self._STOP, "_STOP", ""))
                    except (RuntimeError, AttributeError, TypeError):
                        pass
                    # Rebind to current loop with a fresh queue/runner
                    self._queue = asyncio.Queue()
                    self._runner_task = current_loop.create_task(
                        self._runner(), name="InMemoryEventBusRunner"
                    )
                    self._loop = current_loop
                    self._started = True
            except (RuntimeError, AttributeError, TypeError):
                # Do not fail publish due to rebind issues
                pass

        event_type = self._event_type_name(event)
        ts = datetime.now(timezone.utc).isoformat()
        try:
            await self.log_event(event, event_type, ts)
        except Exception as e:
            # Never let logging failures impact publish path
            logger.debug("log_event failed: %s", e)
        # Increment published counter
        try:
            self._events_published += 1
        except (AttributeError, TypeError):
            # Be defensive: keep publish path resilient even if counter missing
            pass

        # Decide dispatch path:
        # - If runner is not active (or just re-bound and not started yet), dispatch immediately
        #   on the current loop to guarantee delivery in test environments that swap loops.
        # - Otherwise, enqueue for the background runner.
        use_direct_dispatch = False
        try:
            if not self._started or self._queue is None:
                use_direct_dispatch = True
            else:
                # Runner considered inactive if task missing/done/cancelled
                if (
                    self._runner_task is None
                    or self._runner_task.done()
                    or self._runner_task.cancelled()
                    or self._loop is not None
                    and current_loop is not None
                    and self._loop is not current_loop
                ):
                    use_direct_dispatch = True
        except (AttributeError, TypeError):
            use_direct_dispatch = True

        if use_direct_dispatch:
            # Record immediately if enabled (mirror runner behavior)
            if self._recording_enabled:
                try:
                    if len(self._recorded) < self._recording_max:
                        summary = self._event_to_summary(event)
                        safe_summary = self._redact_sensitive(summary)
                        self._recorded.append(
                            {
                                "event_type": event_type,
                                "timestamp": ts,
                                "data": safe_summary,
                            }
                        )
                    else:
                        if not self._recording_truncated:
                            self._recording_truncated = True
                except (AttributeError, TypeError, ValueError):
                    # Never fail publish due to recording issues
                    pass

            # Find matching handlers and invoke them immediately (concurrently) to guarantee delivery
            handlers = self._matching_handlers(event, event_type)
            try:
                # Update processed counter to reflect immediate dispatch
                self._events_processed += 1
            except (AttributeError, TypeError):
                pass

            if handlers:
                try:
                    await asyncio.gather(
                        *(self._safe_invoke(h, event) for h in handlers),
                        return_exceptions=True,
                    )
                except (AttributeError, TypeError, RuntimeError, asyncio.CancelledError):
                    # Swallow to keep publish resilient
                    pass
        else:
            # Normal path: enqueue for background runner
            await self._queue.put((event, event_type, ts))

    async def subscribe(self, event_selector: Any, handler: Any) -> SubscriptionHandle:
        """
        Register a handler for a selector (class or string). Returns a handle for unsubscribe.
        If a sync handler is provided, it is wrapped in an async shim.

        Compatibility enhancement:
        - When subscribing with a class selector, also register a string selector using the
          class name. This allows events of the same name from different modules to match.

        Loop-robustness:
        - If the bus was started on a different event loop than the currently running loop,
          transparently rebind the internal queue and runner to the current loop to ensure
          handlers will be invoked in this context (pytest/Windows friendly).
        """
        if not callable(handler):
            raise TypeError("handler must be callable")

        # Rebind to current running loop if necessary
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None  # no running loop; defer to publish/start
        if (
            self._started
            and self._queue is not None
            and self._loop is not None
            and current_loop is not None
            and self._loop is not current_loop
        ):
            try:
                # Signal old runner to stop
                try:
                    self._queue.put_nowait((self._STOP, "_STOP", ""))
                except (RuntimeError, AttributeError, TypeError):
                    pass
                # Bind a fresh queue/runner on the current loop
                self._queue = asyncio.Queue()
                self._runner_task = current_loop.create_task(
                    self._runner(), name="InMemoryEventBusRunner"
                )
                self._loop = current_loop
                self._started = True
            except (RuntimeError, AttributeError, TypeError):
                # Never fail subscription due to rebind issues
                pass

        async_handler: Handler = self._wrap_handler(handler)
        sel: Selector = self._normalize_selector(event_selector)
        # Primary registration
        self._subscribers.setdefault(sel, []).append(async_handler)
        # Dual-register by type name when a class is provided to ensure cross-module compatibility
        try:
            if isinstance(event_selector, type):
                name_key = event_selector.__name__
                self._subscribers.setdefault(name_key, []).append(async_handler)
        except (AttributeError, TypeError):
            # Best-effort; ignore if type name cannot be derived
            pass
        return (sel, async_handler)

    def _normalize_selector(self, selector: Any) -> Selector:
        if isinstance(selector, type):
            return selector
        if isinstance(selector, str):
            return selector
        raise TypeError(
            f"Unsupported event selector type: {type(selector)}. Use type or str."
        )

    async def unsubscribe(self, handle: SubscriptionHandle) -> None:
        """
        Remove a previously registered handler. If the handle is unknown, no-op.
        """
        sel, async_handler = handle
        handlers = self._subscribers.get(sel)
        if not handlers:
            return
        try:
            handlers.remove(async_handler)
            if not handlers:
                # Drop empty lists to keep mapping tidy
                self._subscribers.pop(sel, None)
        except ValueError:
            # Already removed or never registered; ignore
            pass

    class _ImmediateDone:
        def __await__(self):
            if False:
                yield None
            return None

    class _ImmediateValue:
        """
        An object that behaves like the provided value (list-like for recorded events)
        and is also awaitable to yield that same value immediately.

        This enables hybrid APIs where callers may either:
          - use the result directly in synchronous code, or
          - `await` it in asynchronous code.
        """

        def __init__(self, value: Any):
            self._value = value

        # Behave like the underlying list for common usages
        def __iter__(self):
            return iter(self._value)

        def __len__(self):
            return len(self._value)

        def __getitem__(self, index):
            return self._value[index]

        def __await__(self):
            if False:
                yield None
            return self._value

    def start_recording(self) -> Any:
        """
        Hybrid start_recording that works whether or not callers `await` it.

        Side effects happen immediately so tests that call `bus.start_recording()`
        without awaiting will still enable recording. When awaited, the returned
        object is awaitable and completes instantly.
        """
        # Enable recording; do not clear existing buffer to avoid losing prior diagnostics
        self._recording_enabled = True
        return InMemoryEventBus._ImmediateDone()

    def stop_recording(self) -> Any:
        """
        Hybrid stop_recording that works whether or not callers `await` it.

        Disables in-memory recording. Returns an awaitable object so callers may
        optionally `await bus.stop_recording()`, but this is not required.
        """
        self._recording_enabled = False
        return InMemoryEventBus._ImmediateDone()

    def get_recorded_events(self) -> Any:
        """
        Hybrid getter that works whether or not callers `await` it.

        Returns:
            - When used synchronously: behaves like List[Dict[str, Any]] of recorded events (shallow copy)
            - When awaited: yields the same List[Dict[str, Any]]
        """
        # Return a shallow copy to ensure stability for callers
        # Non-blocking, respects cap (we stop appending once cap reached)
        return InMemoryEventBus._ImmediateValue(list(self._recorded))

    def get_stats(self) -> Dict[str, Any]:
        """
        Return basic operational statistics for observability and tests.
        Keys:
            - started: whether the bus is started
            - events_published: number of events accepted via publish()
            - events_processed: number of events dequeued and dispatched
            - subscribers: total registered handler count
        """
        try:
            subs = sum(len(v) for v in self._subscribers.values())
        except (AttributeError, TypeError):
            subs = 0
        return {
            "started": bool(getattr(self, "_started", False)),
            "events_published": int(getattr(self, "_events_published", 0)),
            "events_processed": int(getattr(self, "_events_processed", 0)),
            "subscribers": int(subs),
        }

    async def log_event(self, event: Any, event_type: str, ts: str) -> None:
        """
        Structured event logging hook.
        Creates a redacted, JSON-serializable summary and emits it to the logger.
        This is separate from in-memory recording used for observability snapshots.
        """
        if not getattr(self, "_logging_enabled", True):
            return
        try:
            summary = self._event_to_summary(event)
            safe_summary = self._redact_sensitive(summary)

            # Ensure records reach pytest's caplog by forcing propagation and INFO level temporarily.
            _log = logging.getLogger("fba_events.bus")
            prev_level = _log.level
            prev_propagate = getattr(_log, "propagate", True)
            prev_disabled = _log.disabled
            try:
                _log.disabled = False
                _log.setLevel(logging.INFO)
                _log.propagate = True
                _log.info(
                    "Event published",
                    extra={
                        "event_type": event_type,
                        "timestamp": ts,
                        "event": safe_summary,
                    },
                )
            finally:
                # Restore previous logger state
                try:
                    _log.setLevel(prev_level)
                except (AttributeError, TypeError):
                    pass
                try:
                    _log.propagate = prev_propagate
                except (AttributeError, TypeError):
                    pass
                _log.disabled = prev_disabled

            # Fallback: ensure record is handled even if upstream handlers misbehave
            try:
                rec = logging.makeLogRecord(
                    {
                        "name": "fba_events.bus",
                        "levelno": logging.INFO,
                        "levelname": "INFO",
                        "msg": "Event published",
                        "event_type": event_type,
                        "timestamp": ts,
                        "event": safe_summary,
                    }
                )
                logging.getLogger("fba_events.bus").handle(rec)
            except (AttributeError, TypeError, RuntimeError):
                pass
        except Exception as e:
            # Logging must never interfere with event flow
            try:
                logger.debug("Event logging skipped: %s", e)
            except (AttributeError, TypeError):
                pass

    # -------------------------
    # Internal implementation
    # -------------------------

    async def _runner(self) -> None:
        try:
            while True:
                event, event_type, ts = await self._queue.get()
                # Sentinel: exit loop gracefully
                if event is getattr(self, "_STOP", None):
                    break

                # Update processed counter
                try:
                    self._events_processed += 1
                except (AttributeError, TypeError):
                    # Defensive: keep runner resilient even if counter missing
                    pass

                # Collect handlers for class selectors (isinstance) and string selectors
                handlers = self._matching_handlers(event, event_type)

                # Record before dispatch to ensure full audit trail even if handlers fail
                if self._recording_enabled:
                    try:
                        if len(self._recorded) < self._recording_max:
                            # Build summary and redact sensitive fields
                            summary = self._event_to_summary(event)
                            safe_summary = self._redact_sensitive(summary)
                            self._recorded.append(
                                {
                                    "event_type": event_type,
                                    "timestamp": ts,
                                    "data": safe_summary,
                                }
                            )
                        else:
                            # Cap reached; mark truncated and stop appending
                            if not self._recording_truncated:
                                self._recording_truncated = True
                    except Exception as rec_e:
                        # Defensive: never crash the bus due to recording failure
                        logger.warning(
                            "Failed to record event %s: %s", event_type, rec_e
                        )
                        try:
                            # Append minimal error record if capacity allows
                            if len(self._recorded) < self._recording_max:
                                self._recorded.append(
                                    {
                                        "event_type": event_type,
                                        "timestamp": ts,
                                        "data": {"_error": "recording_failed"},
                                    }
                                )
                            else:
                                if not self._recording_truncated:
                                    self._recording_truncated = True
                        except (AttributeError, TypeError, KeyError):
                            # As a last resort, swallow errors silently to keep dispatching
                            pass

                # Dispatch concurrently
                for h in handlers:
                    t = asyncio.create_task(
                        self._safe_invoke(h, event), name=f"EventHandler[{event_type}]"
                    )
                    self._handler_tasks.add(t)
                    t.add_done_callback(lambda task: self._handler_tasks.discard(task))
        except asyncio.CancelledError:
            # Graceful exit via cancellation
            return
        except RuntimeError as e:
            # Typical during test teardown: "Event loop is closed" / "no running event loop"
            logger.debug("InMemoryEventBus runner exiting due to runtime error: %s", e)
            return
        except Exception as e:
            logger.exception("Unhandled exception in InMemoryEventBus runner: %s", e)
            # Avoid attempting restart if the loop may be closing
            try:
                loop = asyncio.get_running_loop()
                if self._started and loop.is_running():
                    await asyncio.sleep(0.01)
                    asyncio.create_task(
                        self._runner(), name="InMemoryEventBusRunner-Restarted"
                    )
            except (RuntimeError, AttributeError):
                # If we cannot confirm a healthy loop, exit
                return

    def _matching_handlers(self, event: Any, event_type: str) -> List[Handler]:
        matched: List[Handler] = []

        # String keys
        str_handlers = self._subscribers.get(event_type)
        if str_handlers:
            matched.extend(str_handlers)

        # Class keys: iterate and isinstance
        for key, handlers in self._subscribers.items():
            if isinstance(key, str):
                continue
            try:
                if isinstance(event, key):  # type: ignore[arg-type]
                    matched.extend(handlers)
            except (AttributeError, TypeError):
                # Non-type keys or unexpected selector; ignore
                continue

        # Deduplicate to avoid double-delivery when a handler is registered under both
        # the class selector and the string selector for the same event type.
        unique: List[Handler] = []
        seen: set[Handler] = set()
        for h in matched:
            if h not in seen:
                unique.append(h)
                seen.add(h)

        return unique

    async def _safe_invoke(self, handler: Handler, event: Any) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "Event handler error for %s: %s",
                self._event_type_name(event),
                e,
                exc_info=True,
            )

    def _wrap_handler(self, handler: Any) -> Handler:
        if asyncio.iscoroutinefunction(handler):
            return handler  # type: ignore[return-value]

        async def _shim(evt: Any) -> None:
            loop = asyncio.get_running_loop()
            # Execute sync handler in default executor to avoid blocking
            await loop.run_in_executor(None, handler, evt)

        return _shim

    def _event_type_name(self, event: Any) -> str:
        """
        Resolve canonical event type string.
        Preference: event.__class__.__name__, else getattr(event, 'event_type', str)
        """
        try:
            return event.__class__.__name__
        except (AttributeError, TypeError):
            pass
        try:
            et = getattr(event, "event_type", None)
            if isinstance(et, str):
                return et
        except (AttributeError, TypeError):
            pass
        return str(type(event))

    def _event_to_summary(self, event: Any) -> Dict[str, Any]:
        """
        Best-effort conversion to a JSON-serializable summary dict.
        Priority:
        - event.to_summary_dict() if available
        - dataclasses.asdict if dataclass
        - vars(event) filtered/converted to JSON-serializable primitives
        """
        # 1) Explicit summary if provided
        try:
            to_sum = getattr(event, "to_summary_dict", None)
            if callable(to_sum):
                data = to_sum()
                if isinstance(data, dict):
                    return self._jsonify_dict(data)
        except (AttributeError, TypeError):
            pass

        # 2) Dataclass fallback
        try:
            if is_dataclass(event):
                return self._jsonify_dict(asdict(event))
        except (AttributeError, TypeError):
            pass

        # 3) Generic object __dict__ fallback
        try:
            d = vars(event)
            if isinstance(d, dict):
                return self._jsonify_dict(d)
        except (AttributeError, TypeError):
            pass

        # 4) Last resort: string representation
        return {"repr": repr(event)}

    def _jsonify_dict(self, d: Mapping[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in d.items():
            out[k] = self._to_jsonable(v)
        return out

    def _to_jsonable(self, v: Any) -> Any:
        # Primitives
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        # Datetime -> ISO
        if isinstance(v, datetime):
            # Preserve timezone if present; assume UTC otherwise
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc).isoformat()
            return v.isoformat()
        # Dict
        if isinstance(v, dict):
            return {
                str(self._to_jsonable(k)): self._to_jsonable(val)
                for k, val in v.items()
            }
        # List/Tuple
        if isinstance(v, (list, tuple)):
            return [self._to_jsonable(i) for i in v]
        # Dataclasses
        if is_dataclass(v):
            try:
                return self._jsonify_dict(asdict(v))
            except (AttributeError, TypeError):
                return str(v)
        # Money or other custom types -> str()
        try:
            return str(v)
        except (AttributeError, TypeError):
            return repr(v)

    # -------------------------
    # Recording configuration & helpers
    # -------------------------
    def _read_recording_max(self) -> int:
        default_max = 5000
        try:
            val = os.getenv("EVENT_RECORDING_MAX", str(default_max)).strip()
            if not val:
                return default_max
            parsed = int(val)
            return parsed if parsed > 0 else default_max
        except (ValueError, TypeError):
            return default_max

    def _read_logging_enabled(self) -> bool:
        """
        Read EVENT_LOGGING_ENABLED env to toggle structured logging on publish.
        Accepts: "0", "false", "no" (case-insensitive) to disable; enabled otherwise.
        """
        try:
            val = os.getenv("EVENT_LOGGING_ENABLED", "1").strip().lower()
            return val not in ("0", "false", "no")
        except (AttributeError, TypeError):
            return True

    def get_recording_stats(self) -> Dict[str, Any]:
        """
        Read-only recording stats.
        Returns: {"enabled": bool, "count": int, "truncated": bool, "max": int}
        """
        return {
            "enabled": self._recording_enabled,
            "count": len(self._recorded),
            "truncated": self._recording_truncated,
            "max": self._recording_max,
        }

    def _redact_sensitive(
        self,
        data: Any,
        *,
        max_depth: int = 20,
        _depth: int = 0,
        _seen: Optional[Set[int]] = None,
    ) -> Any:
        """
        Return a deep-copied, redacted version of data.
        Redacts values for keys matching common sensitive names (case-insensitive).
        Handles dicts/lists/tuples safely, avoids cycles by tracking visited ids.
        """
        if _seen is None:
            _seen = set()

        # Depth guard
        if _depth > max_depth:
            return data  # Stop traversal; return as-is (already jsonified primitives expected)

        # Prevent cycles
        obj_id = id(data)
        if obj_id in _seen:
            return data
        _seen.add(obj_id)

        # Primitives remain as-is
        if data is None or isinstance(data, (bool, int, float, str)):
            return data

        # Dict: redact keys
        if isinstance(data, dict):
            redacted: Dict[Any, Any] = {}
            for k, v in data.items():
                key_str = str(k)
                value = v
                if any(pat.search(key_str) for pat in self._redact_key_patterns):
                    redacted[key_str] = "[redacted]"
                else:
                    redacted[key_str] = self._redact_sensitive(
                        v, max_depth=max_depth, _depth=_depth + 1, _seen=_seen
                    )
            return redacted

        # List/Tuple
        if isinstance(data, (list, tuple)):
            return [
                self._redact_sensitive(
                    i, max_depth=max_depth, _depth=_depth + 1, _seen=_seen
                )
                for i in data
            ]

        # Fallback: keep string representation (should be rare after _to_jsonable)
        try:
            return str(data)
        except (AttributeError, TypeError):
            return repr(data)

    def clear_recorded_events(self) -> None:
        """Clear the in-memory recorded events buffer."""
        try:
            self._recorded.clear()
            self._recording_truncated = False
        except (AttributeError, TypeError):
            self._recorded = []
            self._recording_truncated = False

    def get_stats(self) -> Dict[str, Any]:
        """Basic bus stats for introspection."""
        try:
            pending = len(
                [t for t in getattr(self, "_handler_tasks", set()) if not t.done()]
            )
        except (AttributeError, TypeError):
            pending = 0
        return {
            "subscribers": sum(len(v) for v in self._subscribers.values()),
            "recording": self.get_recording_stats(),
            "started": self._started,
            "pending_handlers": pending,
            "events_published": getattr(self, "_events_published", 0),
        }
