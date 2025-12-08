import asyncio
import inspect
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable, Deque, Dict, List, Optional

__all__ = ["DistributedEventBus", "MockRedisBroker"]


class DistributedEventBus:
    """
    Minimal in-memory pub/sub bus used by infrastructure tests.

    Provides both synchronous convenience methods (subscribe/publish) and
    async-compatible control surface used by higher-level infrastructure like
    DistributedCoordinator. This keeps the implementation non-invasive while
    being test-friendly.

    Supported methods:
    - subscribe(topic, handler) / unsubscribe(topic, handler) : sync handlers
    - publish(topic, payload) : sync publish
    - async start()/stop() : lifecycle hooks (no-op for in-memory)
    - async subscribe_to_event(topic, handler) : async-compatible subscribe wrapper
    - async publish_event(topic, payload, target_partition=None) : async-compatible publish wrapper
    - async register_worker(worker_id, capabilities) : test-friendly registration hook
    - async create_partition(partition_id, agents) : create logical partition (no-op)
    - async handle_worker_failure(worker_id) : test-friendly failure handler (no-op)
    """

    def __init__(self, broker: Optional[Any] = None) -> None:
        self._broker = broker
        self._subscriptions: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
        # Optional partitions/workers tracking for unit tests that inspect state
        self._partitions: Dict[str, List[str]] = {}
        self._registered_workers: Dict[str, Dict[str, Any]] = {}
        # Alias expected by tests
        self._workers = self._registered_workers
        # Running state expected by tests
        self._running: bool = False
        # If we register handlers with an external broker that expects synchronous callables,
        # keep wrapper mapping so we can unsubscribe correctly.
        self._broker_handler_wrappers: Dict[Callable[[Any], Any], Callable[[Any], Any]] = {}
        # Logger for debug output in async wrappers
        self.logger = logging.getLogger(__name__)

    # --- Synchronous API (backwards compatible) ----------------------------
    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        # Avoid duplicate registration which leads to double-delivery in tests
        if handler not in self._subscriptions[topic]:
            self._subscriptions[topic].append(handler)
        if self._broker and hasattr(self._broker, "subscribe"):
            # Normalize handler for brokers that expect synchronous callables:
            broker_handler = handler
            try:
                if inspect.iscoroutinefunction(handler) or inspect.isawaitable(
                    getattr(handler, "__call__", None)
                ):
                    # Wrap async handler so broker's sync publish schedules it properly
                    def _sync_wrapper(payload: Any, _h=handler):
                        try:
                            # Check for running loop in current thread
                            loop = asyncio.get_running_loop()
                            loop.create_task(_h(payload))
                        except RuntimeError:
                            # No running loop, try to schedule in a new loop or fail gracefully
                            try:
                                asyncio.run(_h(payload))
                            except Exception:
                                pass

                    broker_handler = _sync_wrapper
                    # Track wrapper so we can remove it on unsubscribe
                    self._broker_handler_wrappers[handler] = broker_handler
            except Exception:
                broker_handler = handler

            try:
                self._broker.subscribe(topic, broker_handler)
            except TypeError:
                # Some brokers accept only (topic,)
                try:
                    self._broker.subscribe(topic)
                except Exception:
                    pass
            except Exception:
                # Ignore broker errors to keep tests non-invasive
                pass

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        handlers = self._subscriptions.get(topic)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            pass

        # If we previously wrapped this handler for the broker, remove the wrapped one too
        if self._broker and hasattr(self._broker, "unsubscribe"):
            broker_handler = self._broker_handler_wrappers.pop(handler, None)
            try:
                if broker_handler:
                    self._broker.unsubscribe(topic, broker_handler)
                else:
                    # Fall back to attempting to remove original handler
                    self._broker.unsubscribe(topic, handler)
            except Exception:
                # Ignore broker unsubscribe errors
                pass

    def publish(self, topic: str, payload: Any) -> None:
        # Use canonical event shape for synchronous publish to match async publish_event
        event = {"event_type": topic, "event_data": payload}
        # Iterate over a snapshot to allow handlers to modify subscriptions safely
        for h in list(self._subscriptions.get(topic, ())):
            try:
                result = h(event)
                # If handler returned a coroutine, schedule it so it runs (non-blocking)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # Fallback for sync execution of coroutine if needed, or swallow
                        pass
            except Exception:
                # Do not let handler errors break publishing loop in tests
                pass
        if self._broker and hasattr(self._broker, "publish"):
            try:
                # Broker may expect the canonical event shape as well
                self._broker.publish(topic, event)
            except Exception:
                pass

    # --- Async-compatible, non-invasive shims ------------------------------
    async def start(self) -> None:
        """Async lifecycle hook to match DistributedCoordinator expectations."""
        self._running = True
        # If underlying broker has start/connect, try to call it
        if self._broker and hasattr(self._broker, "start"):
            try:
                maybe = self._broker.start()
                if asyncio.iscoroutine(maybe):
                    await maybe
            except Exception:
                pass

    async def stop(self) -> None:
        """Async lifecycle hook to match DistributedCoordinator expectations."""
        if self._broker and hasattr(self._broker, "stop"):
            try:
                maybe = self._broker.stop()
                if asyncio.iscoroutine(maybe):
                    await maybe
            except Exception:
                pass
        self._running = False

    async def subscribe_to_event(self, topic: str, handler: Callable[[Any], None]) -> None:
        """Async wrapper used by higher-level components (naming kept to match tests)."""
        # Keep underlying subscription synchronous for in-memory bus
        self.subscribe(topic, handler)

    async def publish_event(
        self, topic: str, payload: Any, target_partition: Optional[str] = None
    ) -> None:
        """Async wrapper to publish events; target_partition is ignored for in-memory bus.

        This implementation will wrap the payload into a canonical event shape expected by tests:
            {"event_type": topic, "event_data": payload}

        It will call synchronous handlers directly and will detect coroutine results from async
        handlers and await them. Exceptions in handlers are isolated so publishing proceeds for
        other handlers.
        """
        # Canonical event shape
        event = {"event_type": topic, "event_data": payload}

        handlers = list(self._subscriptions.get(topic, ()))
        pending = []

        # Debug: log canonical event and how many handlers will be invoked
        try:
            self.logger.debug(
                "publish_event canonical event=%s handlers=%d target_partition=%s",
                event,
                len(handlers),
                target_partition,
            )
        except Exception:
            pass

        for h in handlers:
            try:
                result = h(event)
                # Debug: indicate whether handler returned a coroutine (async handler)
                try:
                    self.logger.debug(
                        "publish_event handler=%s returned_coroutine=%s",
                        getattr(h, "__name__", repr(h)),
                        asyncio.iscoroutine(result),
                    )
                except Exception:
                    pass
                # If handler returned a coroutine, schedule it
                if asyncio.iscoroutine(result):
                    pending.append(asyncio.create_task(result))
            except Exception:
                # Do not let handler exceptions stop other handlers
                continue

        # Await any async handlers
        if pending:
            try:
                await asyncio.gather(*pending, return_exceptions=True)
            except Exception:
                # Swallow to match non-invasive behavior in tests
                pass

        # Also notify underlying broker if it supports async publish
        if self._broker and hasattr(self._broker, "publish"):
            try:
                maybe = self._broker.publish(topic, event)
                if asyncio.iscoroutine(maybe):
                    await maybe
            except Exception:
                pass

    async def register_worker(self, worker_id: str, capabilities: Dict[str, Any]) -> None:
        """Register a worker for test introspection; non-invasive bookkeeping."""
        self._registered_workers[worker_id] = {
            "capabilities": dict(capabilities),
            "registered_at": time.time(),
        }

    async def create_partition(self, partition_id: str, agents: List[str]) -> None:
        """Create a logical partition used in tests; idempotent and non-invasive."""
        self._partitions[partition_id] = list(agents)

    async def handle_worker_failure(self, worker_id: str) -> None:
        """Non-invasive failure handler called by coordinator; simply deregisters the worker."""
        try:
            self._registered_workers.pop(worker_id, None)
        except Exception:
            pass


class MockRedisBroker:
    """
    Lightweight stand-in for a Redis-based broker used in tests.
    Provides:
      - publish(channel, message)
      - subscribe(channel, handler)
      - get_queue(channel) for test introspection
    Internally uses deques per channel and synchronous dispatch to handlers.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, Deque[Any]] = defaultdict(deque)
        self._handlers: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, channel: str, handler: Callable[[Any], None]) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            self._handlers[channel].append(handler)

    def unsubscribe(self, channel: str, handler: Callable[[Any], None]) -> None:
        with self._lock:
            handlers = self._handlers.get(channel)
            if not handlers:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def publish(self, channel: str, message: Any) -> None:
        with self._lock:
            self._channels[channel].append(message)
            handlers = list(self._handlers.get(channel, ()))
        # Invoke handlers outside lock
        for h in handlers:
            try:
                h(message)
            except Exception:
                pass

    def get_queue(self, channel: str) -> Deque[Any]:
        # For tests to inspect enqueued messages
        return self._channels[channel]

    def pop(self, channel: str) -> Optional[Any]:
        with self._lock:
            if self._channels[channel]:
                return self._channels[channel].popleft()
            return None
