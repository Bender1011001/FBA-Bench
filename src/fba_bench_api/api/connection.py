"""
Connection manager module.

Manages websocket-style connections for broadcasting events. Implemented to be
test-friendly and dependency-light (works with simple fakes).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set


class ConnectionManager:
    def __init__(self, *, max_connections: int = 1000) -> None:
        self.max_connections = int(max_connections)
        self.active_connections: list[Any] = []
        self.connection_metadata: Dict[Any, Dict[str, Any]] = {}
        self.connection_subscriptions: Dict[Any, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: Any, *, origin: str = "unknown") -> bool:
        """
        Register a websocket-like connection.

        Expects the object to implement:
        - await accept()
        - await close(code=..., reason=...)
        """
        async with self._lock:
            if len(self.active_connections) >= self.max_connections:
                try:
                    await websocket.close(code=1008, reason="Capacity exceeded")
                except Exception:
                    pass
                return False

            try:
                await websocket.accept()
            except Exception:
                return False

            self.active_connections.append(websocket)
            self.connection_metadata[websocket] = {
                "client_id": getattr(websocket, "client_id", None)
                or f"client-{len(self.active_connections)}",
                "origin": origin,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }
            self.connection_subscriptions.setdefault(websocket, set())
            return True

    def disconnect(self, websocket: Any) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_metadata.pop(websocket, None)
        self.connection_subscriptions.pop(websocket, None)

    async def broadcast_event(self, payload: Dict[str, Any]) -> None:
        msg = json.dumps(payload)
        # Snapshot list so we don't break if connections mutate during broadcast.
        targets = list(self.active_connections)
        for ws in targets:
            try:
                await ws.send_text(msg)
                if ws in self.connection_metadata:
                    self.connection_metadata[ws]["last_activity"] = datetime.now(
                        timezone.utc
                    ).isoformat()
            except Exception:
                # Drop broken connections
                self.disconnect(ws)

    def broadcast(self, message: str) -> None:
        # Best-effort sync broadcast for legacy callers.
        for conn in list(self.active_connections):
            try:
                send = getattr(conn, "send_text", None)
                if callable(send):
                    res = send(message)
                    if hasattr(res, "__await__"):
                        # Avoid awaiting in sync API; fire-and-forget is acceptable here.
                        pass
            except Exception:
                self.disconnect(conn)

    def get_connection_stats(self) -> Dict[str, Any]:
        subscriptions: Dict[str, int] = {}
        for subs in self.connection_subscriptions.values():
            for s in subs:
                subscriptions[s] = subscriptions.get(s, 0) + 1

        connections = []
        for ws in self.active_connections:
            meta = self.connection_metadata.get(ws, {})
            connections.append(
                {
                    "client_id": meta.get("client_id"),
                    "connected_at": meta.get("connected_at"),
                    "last_activity": meta.get("last_activity"),
                    "subscriptions": sorted(
                        self.connection_subscriptions.get(ws, set())
                    ),
                }
            )

        return {
            "total_connections": len(self.active_connections),
            "subscriptions": subscriptions,
            "connections": connections,
        }
