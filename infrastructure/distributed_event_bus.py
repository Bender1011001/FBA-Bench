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
    """

    def __init__(self, broker: Optional[Any] = None) -> None:
        self._broker = broker
        self._subscriptions: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
        self._partitions: Dict[str, List[str]] = {}
        self._registered_workers: Dict[str, Dict[str, Any]] = {}
        self._workers = self._registered_workers
        self._running: bool = False
        self._broker_handler_wrappers: Dict[Callable[[Any], Any], Callable[[Any], Any]] = {}
        self.logger = logging.getLogger(__name__)

    # --- Synchronous API ----------------------------
    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")
        
        if handler not in self._subscriptions[topic]:
            self._subscriptions[topic].append(handler)
            
        if self._broker and hasattr(self._broker, "subscribe"):
            broker_handler = handler
            # Fix #102: Use standard iscoroutinefunction check for robust async detection
            if inspect.iscoroutinefunction(handler):
                # Wrap async handler so broker's sync publish schedules it properly
                def _sync_wrapper(payload: Any, _h=handler):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(_h(payload))
                    except RuntimeError:
                        # Fallback if no loop is running in this thread
                        pass

                broker_handler = _sync_wrapper
                self._broker_handler_wrappers[handler] = broker_handler

            try:
                # Attempt subscribe with varying signatures
                try:
                    self._broker.subscribe(topic, broker_handler)
                except TypeError:
                    self._broker.subscribe(topic)
            except Exception:
                pass

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        handlers = self._subscriptions.get(topic)
        if not handlers:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            pass

        if self._broker and hasattr(self._broker, "unsubscribe"):
            broker_handler = self._broker_handler_wrappers.pop(handler, None)
            try:
                if broker_handler:
                    self._broker.unsubscribe(topic, broker_handler)
                else:
                    self._broker.unsubscribe(topic, handler)
            except Exception:
                pass

    def publish(self, topic: str, payload: Any) -> None:
        """
        Synchronous publish. 
        Fix #103: Do not wrap if the payload is already in the canonical event format.
        """
        # Check if already canonical (simple heuristic)
        if isinstance(payload, dict) and "event_type" in payload and "event_data" in payload:
            event = payload
        else:
            event = {"event_type": topic, "event_data": payload}

        for h in list(self._subscriptions.get(topic, ())):
            try:
                result = h(event)
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception:
                pass
        
        if self._broker and hasattr(self._broker, "publish"):
            try:
                self._broker.publish(topic, event)
            except Exception:
                pass

    # --- Async-compatible shims ------------------------------
    async def start(self) -> None:
        self._running = True
        if self._broker and hasattr(self._broker, "start"):
            try:
                maybe = self._broker.start()
                if inspect.isawaitable(maybe):
                    await maybe
            except Exception:
                pass

    async def stop(self) -> None:
        if self._broker and hasattr(self._broker, "stop"):
            try:
                maybe = self._broker.stop()
                if inspect.isawaitable(maybe):
                    await maybe
            except Exception:
                pass
        self._running = False

    async def subscribe_to_event(self, topic: str, handler: Callable[[Any], None]) -> None:
        self.subscribe(topic, handler)

    async def publish_event(
        self, topic: str, payload: Any, target_partition: Optional[str] = None
    ) -> None:
        # Same logic as sync publish: avoid double wrapping
        if isinstance(payload, dict) and "event_type" in payload and "event_data" in payload:
            event = payload
        else:
            event = {"event_type": topic, "event_data": payload}

        handlers = list(self._subscriptions.get(topic, ()))
        pending = []

        for h in handlers:
            try:
                result = h(event)
                if inspect.isawaitable(result):
                    pending.append(asyncio.create_task(result))
            except Exception:
                continue

        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        if self._broker and hasattr(self._broker, "publish"):
            try:
                maybe = self._broker.publish(topic, event)
                if inspect.isawaitable(maybe):
                    await maybe
            except Exception:
                pass

    async def register_worker(self, worker_id: str, capabilities: Dict[str, Any]) -> None:
        self._registered_workers[worker_id] = {
            "capabilities": dict(capabilities),
            "registered_at": time.time(),
        }

    async def create_partition(self, partition_id: str, agents: List[str]) -> None:
        self._partitions[partition_id] = list(agents)

    async def handle_worker_failure(self, worker_id: str) -> None:
        try:
            self._registered_workers.pop(worker_id, None)
        except Exception:
            pass


class MockRedisBroker:
    """
    Lightweight stand-in for a Redis-based broker used in tests.
    Fixes #104: Ensures async handlers are awaited via tasks.
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
                result = h(message)
                # Fix #104: Support async handlers in MockBroker
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # We are likely in a sync test context without a loop
                        pass
            except Exception:
                pass

    def get_queue(self, channel: str) -> Deque[Any]:
        return self._channels[channel]

    def pop(self, channel: str) -> Optional[Any]:
        with self._lock:
            if self._channels[channel]:
                return self._channels[channel].popleft()
            return None
