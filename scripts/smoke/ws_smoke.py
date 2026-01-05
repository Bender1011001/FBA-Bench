#!/usr/bin/env python3
"""
WebSocket smoke client.

Requirements (install locally, not added to project dependencies):
  pip install websockets

CLI:
  python scripts/smoke/ws_smoke.py --url "ws://localhost:8000/ws/realtime?topic=health" --jwt "<TOKEN>"

Behavior:
- Sets Sec-WebSocket-Protocol to "auth.bearer.token.<JWT>" as required by the backend
  WebSocket endpoint implemented at [python.function websocket_realtime()](fba_bench_api/api/routes/realtime.py:190).
- On successful connection, waits briefly, prints "WS connected", then exits 0.
- On failure, prints the error and exits non-zero.
"""

import argparse
import asyncio
import sys

try:
    import websockets  # type: ignore
except ImportError:
    sys.stderr.write("Missing dependency: websockets. Install with: pip install websockets\n")
    sys.exit(2)


async def ws_probe(url: str, jwt: str, timeout: float = 10.0) -> int:
    subprotocol = f"auth.bearer.token.{jwt}"
    try:
        async with asyncio.timeout(timeout):
            async with websockets.connect(
                url,
                subprotocols=[subprotocol],
                ping_interval=20,
                close_timeout=5,
                max_queue=None,
            ) as ws:
                # Optionally read a short message if server sends one; not required
                await asyncio.sleep(0.5)
                print("WS connected")
                try:
                    await ws.close()
                except Exception:
                    pass
                return 0
    except Exception as e:
        sys.stderr.write(f"WS connection failed: {e}\n")
        return 1


def main():
    parser = argparse.ArgumentParser(description="WebSocket smoke client")
    parser.add_argument(
        "--url",
        required=True,
        help='WebSocket URL, e.g., "ws://localhost:8000/ws/realtime?topic=health"',
    )
    parser.add_argument(
        "--jwt", required=True, help="Bearer token to attach via Sec-WebSocket-Protocol"
    )
    parser.add_argument(
        "--rate", type=float, default=0, help="Flood rate in Hz (msgs/sec). 0 = verify connection only."
    )
    parser.add_argument(
        "--topic", type=str, default=None, help="Topic to publish to (required if rate > 0)"
    )
    parser.add_argument(
        "--duration", type=float, default=10.0, help="Duration of flood in seconds"
    )
    
    args = parser.parse_args()

    if args.rate > 0 and not args.topic:
        parser.error("--topic is required when --rate is > 0")

    try:
        if args.rate > 0:
            code = asyncio.run(ws_flood(args.url, args.jwt, args.topic, args.rate, args.duration))
        else:
            code = asyncio.run(ws_probe(args.url, args.jwt))
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


async def ws_flood(url: str, jwt: str, topic: str, rate: float, duration: float) -> int:
    import json
    import random
    import time
    
    subprotocol = f"auth.bearer.token.{jwt}"
    print(f"Connecting to {url}...")
    
    try:
        async with websockets.connect(
            url,
            subprotocols=[subprotocol],
            ping_interval=20,
            close_timeout=5,
            max_queue=None,
        ) as ws:
            print("WS connected. Starting flood...")
            
            start_time = time.time()
            frame_count = 0
            period = 1.0 / rate
            
            while time.time() - start_time < duration:
                loop_start = time.time()
                
                # Generate realistic payload matching SimulationViewer.gd expectations
                # Payload: { "type": "publish", "topic": ..., "data": { ... } }
                
                # Data structure:
                # {
                #   "tick": int,
                #   "metrics": { ... },
                #   "agents": [ ... ],
                #   "heatmap": [ ... ]
                # }
                
                sim_data = {
                    "tick": frame_count,
                    "metrics": {
                        "total_revenue": random.uniform(1000, 10000) + frame_count,
                        "inventory_count": int(random.uniform(100, 500)),
                        "pending_orders": int(random.uniform(0, 50))
                    },
                    "agents": [],
                    "heatmap": []
                }
                
                # Generate 10-20 agents
                num_agents = 15
                for i in range(num_agents):
                    agent = {
                        "id": f"Agent-{i}",
                        "role": random.choice(["Strategic", "Analyst", "Logistics", "Trader"]),
                        "x": random.uniform(50, 750),
                        "y": random.uniform(50, 550),
                        "state": random.choice(["active", "idle", "deciding", "buying"]),
                        "financials": {
                            "cash": random.uniform(500, 2000),
                            "net_profit": random.uniform(-100, 200),
                            "inventory_value": random.uniform(0, 500)
                        },
                        "last_reasoning": "Processing market data stream...",
                        "llm_usage": {
                            "total_tokens": random.randint(50, 150),
                            "total_cost_usd": random.uniform(0.001, 0.05)
                        },
                        "recent_events": [f"Event {random.randint(1000, 9999)}"]
                    }
                    sim_data["agents"].append(agent)
                
                msg = {
                    "type": "publish",
                    "topic": topic,
                    "data": sim_data
                }
                
                await ws.send(json.dumps(msg))
                frame_count += 1
                
                if frame_count % int(rate) == 0:
                    print(f"Sent {frame_count} frames...")
                
                elapsed = time.time() - loop_start
                sleep_time = max(0, period - elapsed)
                await asyncio.sleep(sleep_time)
                
            print(f"Flood complete. Sent {frame_count} frames.")
            return 0
            
    except Exception as e:
        sys.stderr.write(f"Flood failed: {e}\n")
        return 1


if __name__ == "__main__":
    main()
