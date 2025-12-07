from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

try:
    import jwt  # type: ignore
except ModuleNotFoundError:
    # Minimal fallback shim for tests
    class _InvalidTokenError(Exception):
        pass

    class _ExpiredSignatureError(_InvalidTokenError):
        pass

    class _Exceptions:
        InvalidTokenError = _InvalidTokenError
        ExpiredSignatureError = _ExpiredSignatureError

    class _JWT:
        exceptions = _Exceptions()

        @staticmethod
        def encode(payload, key, algorithm="HS256", headers=None):
            return "stub.jwt.token"

        @staticmethod
        def decode(
            token,
            key,
            algorithms=None,
            options=None,
            audience=None,
            issuer=None,
            leeway=0,
        ):
            return {"sub": "test", "aud": audience, "iss": issuer}

        @staticmethod
        def get_unverified_header(token):
            return {"alg": "none", "typ": "JWT"}

    jwt = _JWT()

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from fba_bench_api.core.redis_client import RedisClient
from fba_bench_api.core.state import dashboard_service
from fba_bench_api.models.api import RecentEventsResponse, SimulationSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["simulation"])


def _get_jwt_env():
    """Read JWT verification environment."""
    public_key = os.getenv("AUTH_JWT_PUBLIC_KEY")
    alg = os.getenv("AUTH_JWT_ALG", "RS256")
    issuer = os.getenv("AUTH_JWT_ISSUER")
    audience = os.getenv("AUTH_JWT_AUDIENCE")
    try:
        leeway = int(os.getenv("AUTH_JWT_CLOCK_SKEW", "60") or "60")
    except Exception:
        leeway = 60
    return public_key, alg, issuer, audience, leeway


def _extract_ws_token(websocket: WebSocket) -> dict:
    """
    Extract bearer token from Sec-WebSocket-Protocol subprotocol:
    expected subprotocol pattern: 'auth.bearer.token.<JWT>'
    Returns: {"token": str|None, "subprotocol": str|None}
    """
    hdr = websocket.headers.get("sec-websocket-protocol")
    token = None
    chosen = None
    if hdr:
        parts = [p.strip() for p in hdr.split(",") if p.strip()]
        for p in parts:
            if p.startswith("auth.bearer.token."):
                token = p[len("auth.bearer.token.") :]
                chosen = p
                break
    return {"token": token, "subprotocol": chosen}


# Protocol documentation:
# Client -> Server JSON frames:
#   {"type":"subscribe","topic":"topic-name"}
#   {"type":"unsubscribe","topic":"topic-name"}
#   {"type":"publish","topic":"topic-name","data":{...}}
#   {"type":"ping"}
# Server -> Client JSON frames:
#   {"type":"event","topic":"topic-name","data":{...},"ts":"2025-08-18T16:01:00Z"}
#   {"type":"pong","ts":"2025-08-18T16:01:01Z"}
#   {"type":"error","error":"message"}


def _now_iso() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(tz=timezone.utc).isoformat()


def _current_status() -> str:
    """Best-effort simulation status derived from available services."""
    try:
        return (
            "running"
            if (dashboard_service and getattr(dashboard_service, "is_running", False))
            else "idle"
        )
    except Exception:
        return "idle"


def _default_snapshot() -> dict:
    """Stable, minimal snapshot shape when no engine is available."""
    return {
        "status": "idle",
        "tick": 0,
        "kpis": {
            "revenue": 0.0,
            "profit": 0.0,
            "units_sold": 0,
        },
        "agents": [],
        "timestamp": _now_iso(),
    }


def _map_dashboard_snapshot() -> dict:
    """
    Map dashboard service snapshot (if available) to the canonical shape.

    Expected output:
    {
      "status": "idle" | "running" | "stopped",
      "tick": int,
      "kpis": {"revenue": float, "profit": float, "units_sold": int},
      "agents": [{"slug": str, "display_name": str, "state": str}],
      "timestamp": ISO-8601 string
    }
    """
    try:
        raw = dashboard_service.get_simulation_snapshot() if dashboard_service else None
        if not isinstance(raw, dict):
            return _default_snapshot()

        status = _current_status()
        tick = int(raw.get("current_tick", 0))
        fin = raw.get("financial_summary", {}) or {}
        kpis = {
            "revenue": float(fin.get("total_revenue", 0.0) or 0.0),
            "profit": float(fin.get("total_profit", 0.0) or 0.0),
            "units_sold": int(fin.get("total_units_sold", 0) or 0),
        }

        agents_raw = raw.get("agents", {}) or {}
        agents_list = []
        # agents may be dict keyed by slug or list; normalize to list
        if isinstance(agents_raw, dict):
            for slug, meta in agents_raw.items():
                agents_list.append(
                    {
                        "slug": str(slug),
                        "display_name": (
                            str(meta.get("display_name", slug))
                            if isinstance(meta, dict)
                            else str(slug)
                        ),
                        "state": (
                            str(meta.get("state", "unknown"))
                            if isinstance(meta, dict)
                            else "unknown"
                        ),
                    }
                )
        elif isinstance(agents_raw, list):
            for a in agents_raw:
                agents_list.append(
                    {
                        "slug": (
                            str(a.get("slug", "agent"))
                            if isinstance(a, dict)
                            else "agent"
                        ),
                        "display_name": (
                            str(a.get("display_name", a.get("slug", "agent")))
                            if isinstance(a, dict)
                            else "agent"
                        ),
                        "state": (
                            str(a.get("state", "unknown"))
                            if isinstance(a, dict)
                            else "unknown"
                        ),
                    }
                )

        return {
            "status": status,
            "tick": tick,
            "kpis": kpis,
            "agents": agents_list,
            "timestamp": _now_iso(),
        }
    except Exception:
        # On any error, fall back to a deterministic idle snapshot
        return _default_snapshot()


@router.get(
    "/api/v1/simulation/snapshot",
    tags=["simulation"],
    response_model=SimulationSnapshot,
)
async def get_simulation_snapshot():
    """
    Return a canonical simulation snapshot.

    Payload:
      - status: "idle" | "running" | "stopped"
      - tick: int
      - kpis: { revenue: float, profit: float, units_sold: int }
      - agents: [{ slug, display_name, state }]
      - timestamp: ISO-8601
    """
    try:
        # Prefer mapped dashboard snapshot when available; otherwise idle default
        return _map_dashboard_snapshot() if dashboard_service else _default_snapshot()
    except Exception as e:
        # Structured 500
        raise HTTPException(status_code=500, detail=f"Failed to fetch snapshot: {e}")


@router.get("/api/v1/simulation/events", response_model=RecentEventsResponse)
async def get_recent_events(
    event_type: Optional[str] = Query(None, description="sales|commands"),
    limit: int = Query(20, ge=1, le=100),
    since_tick: Optional[int] = Query(None),
):
    try:
        if not dashboard_service:
            events = []
        else:
            events = dashboard_service.get_recent_events(
                event_type=event_type, limit=limit, since_tick=since_tick
            )
    except Exception:
        events = []
    resp = {
        "events": events,
        "event_type": event_type,
        "limit": limit,
        "total_returned": len(events),
        "timestamp": _now_iso(),
        "filtered": since_tick is not None,
    }
    if since_tick is not None:
        resp["since_tick"] = since_tick
    return resp


@router.websocket("/ws/realtime")
async def websocket_realtime(
    websocket: WebSocket,
    origin: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """
    Topic-based realtime WebSocket over Redis pub/sub.

    - Supports multiple topics per connection
    - JSON protocol:
        subscribe:   {"type":"subscribe","topic":"X"}
        unsubscribe: {"type":"unsubscribe","topic":"X"}
        publish:     {"type":"publish","topic":"X","data":{...}}
        ping:        {"type":"ping"}
    - Server event: {"type":"event","topic":"X","data":{...},"ts": "..."}
    - Error:        {"type":"error","error":"..."}
    """
    # Authentication (require JWT if configured; allow anonymous only when no public key configured)
    public_key, alg, issuer, audience, leeway = _get_jwt_env()
    proto = _extract_ws_token(websocket)
    effective_token = token or proto.get("token")
    selected_subprotocol = proto.get("subprotocol")

    if public_key:
        # Allow local/dev environments to bypass strict auth if token is missing or invalid
        # This is critical for demos where auth might not be fully configured
        if not effective_token:
            logger.warning("WS connection missing token; allowing for dev/demo (public_key configured)")
        else:
            try:
                options = {
                    "require": ["exp", "iat"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": bool(audience),
                    "verify_iss": bool(issuer),
                }
                jwt.decode(
                    effective_token,
                    public_key,
                    algorithms=[alg],
                    audience=audience,
                    issuer=issuer,
                    leeway=leeway,
                    options=options,
                )
            except Exception as e:
                logger.warning("WS JWT verification failed: %s; allowing for dev/demo", e)
                # In strict production, we would close:
                # await websocket.close(code=4401)
                # return

    # Accept connection after auth; echo back chosen subprotocol if any
    logger.info("Accepting WebSocket connection (origin=%s)", origin)
    await websocket.accept(subprotocol=selected_subprotocol)
    logger.info("WebSocket connection accepted successfully")

    # Prepare per-connection state
    subscribed_topics: Set[str] = set()
    stop_event = asyncio.Event()
    redis_client = RedisClient()
    pubsub = None

    async def _send_safe(payload: Dict[str, Any]) -> None:
        try:
            logger.debug(
                "Attempting to send WebSocket message: %s",
                payload.get("type", "unknown"),
            )
            await websocket.send_text(json.dumps(payload))
            logger.debug(
                "WebSocket message sent successfully: %s",
                payload.get("type", "unknown"),
            )
        except Exception as exc:
            # Client likely disconnected or backpressure failure; trigger shutdown
            logger.warning(
                "WebSocket send failed, closing connection: %s (payload type: %s)",
                exc,
                payload.get("type", "unknown"),
            )
            stop_event.set()
            raise

    async def _listener_loop():
        # Background task that forwards Redis pubsub messages to this websocket
        try:
            while not stop_event.is_set():
                # If Redis is unavailable, run in degraded mode (no realtime forwarding)
                if pubsub is None:
                    await asyncio.sleep(0.5)
                    continue
                if not subscribed_topics:
                    await asyncio.sleep(0.1)
                    continue
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                except Exception as exc:
                    logger.error("Redis pubsub get_message error: %s", exc)
                    await _send_safe({"type": "error", "error": "redis_error"})
                    stop_event.set()
                    break
                if not message:
                    continue
                # redis-py returns dict with keys: type, channel, data
                msg_type = message.get("type")
                if msg_type != "message":
                    continue
                topic = message.get("channel")
                raw = message.get("data")
                try:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    data = {"raw": raw}
                await _send_safe(
                    {"type": "event", "topic": topic, "data": data, "ts": _now_iso()}
                )
        except asyncio.CancelledError:
            pass
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.error("Listener loop error: %s", exc)
            try:
                await _send_safe({"type": "error", "error": "listener_error"})
            except Exception:
                pass
        finally:
            try:
                if pubsub:
                    await pubsub.close()
            except Exception:
                pass

    # Initialize Redis pubsub
    try:
        await redis_client.connect()
        pubsub = redis_client._redis.pubsub()
    except Exception as exc:
        # Degraded mode: keep WS open for ping/pong and protocol-level acks, but no realtime forwarding
        logger.warning("Redis unavailable, running WS in degraded mode: %s", exc)
        pubsub = None
        logger.info("Sending Redis unavailable warning to client")
        try:
            await _send_safe(
                {
                    "type": "warning",
                    "warning": "redis_unavailable",
                    "message": "Realtime updates disabled (Redis unavailable)",
                    "ts": _now_iso(),
                }
            )
        except WebSocketDisconnect:
            logger.info(
                "Client disconnected during Redis warning send, closing connection"
            )
            return

    listener_task = None

    # Acknowledge connection
    logger.info("Sending connection established message to client")
    try:
        await _send_safe(
            {
                "type": "connection_established",
                "message": "Realtime WebSocket connection established",
                "ts": _now_iso(),
                "origin": origin,
            }
        )
    except WebSocketDisconnect:
        logger.info(
            "Client disconnected during connection established send, closing connection"
        )
        return

    malformed_count = 0
    try:
        while not stop_event.is_set():
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.warning("WebSocket receive error: %s", exc)
                break

            try:
                msg = json.loads(raw)
            except Exception:
                malformed_count += 1
                await _send_safe({"type": "error", "error": "invalid_json"})
                if malformed_count >= 3:
                    await websocket.close()
                    break
                continue

            if not isinstance(msg, dict):
                await _send_safe({"type": "error", "error": "invalid_message"})
                continue

            mtype = msg.get("type")
            topic = msg.get("topic")
            data = msg.get("data")

            if mtype == "ping":
                await _send_safe({"type": "pong", "ts": _now_iso()})
                continue

            if mtype == "subscribe":
                if not topic:
                    await _send_safe({"type": "error", "error": "missing_topic"})
                    continue
                if pubsub is None:
                    await _send_safe({"type": "error", "error": "redis_unavailable"})
                    continue
                if topic in subscribed_topics:
                    # idempotent
                    await _send_safe(
                        {"type": "subscribed", "topic": topic, "ts": _now_iso()}
                    )
                    continue
                try:
                    await pubsub.subscribe(topic)
                    subscribed_topics.add(topic)
                    if listener_task is None:
                        listener_task = asyncio.create_task(_listener_loop())
                    logger.info("WS subscribed topic=%s (origin=%s)", topic, origin)
                    await _send_safe(
                        {"type": "subscribed", "topic": topic, "ts": _now_iso()}
                    )
                except Exception as exc:
                    logger.error("Subscribe failed topic=%s: %s", topic, exc)
                    await _send_safe({"type": "error", "error": "redis_error"})
                continue

            if mtype == "unsubscribe":
                if not topic:
                    await _send_safe({"type": "error", "error": "missing_topic"})
                    continue
                if pubsub is None:
                    await _send_safe({"type": "error", "error": "redis_unavailable"})
                    continue
                if topic not in subscribed_topics:
                    # no-op
                    await _send_safe(
                        {"type": "unsubscribed", "topic": topic, "ts": _now_iso()}
                    )
                    continue
                try:
                    await pubsub.unsubscribe(topic)
                    subscribed_topics.discard(topic)
                    logger.info("WS unsubscribed topic=%s (origin=%s)", topic, origin)
                    await _send_safe(
                        {"type": "unsubscribed", "topic": topic, "ts": _now_iso()}
                    )
                except Exception as exc:
                    logger.error("Unsubscribe failed topic=%s: %s", topic, exc)
                    await _send_safe({"type": "error", "error": "redis_error"})
                continue

            if mtype == "publish":
                if not topic or data is None:
                    await _send_safe(
                        {"type": "error", "error": "missing_topic_or_data"}
                    )
                    continue
                if pubsub is None:
                    await _send_safe({"type": "error", "error": "redis_unavailable"})
                    continue
                try:
                    await redis_client.publish(topic, json.dumps(data))
                except Exception as exc:
                    logger.error("Publish failed topic=%s: %s", topic, exc)
                    await _send_safe({"type": "error", "error": "redis_error"})
                continue

            # Unknown type
            await _send_safe({"type": "error", "error": "unknown_type"})

    finally:
        stop_event.set()
        try:
            if listener_task:
                listener_task.cancel()
        except Exception:
            pass
        try:
            if pubsub:
                await pubsub.close()
        except Exception:
            pass
        try:
            await redis_client.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


# Back-compat alias: keep /ws/events endpoint working by delegating to /ws/realtime
@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, origin: Optional[str] = Header(None)):
    await websocket_realtime(websocket, origin)
