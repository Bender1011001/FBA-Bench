#!/usr/bin/env python3
"""
Simple WebSocket test script for FBA-Bench API endpoints.
"""

import asyncio
import json
from datetime import datetime

import websockets

# This module is a manual connectivity script, not part of automated pytest runs.
__test__ = False


async def test_websocket_events():
    """Test the /ws/events WebSocket endpoint."""
    uri = "ws://localhost:8000/ws/events"
    print(f"[{datetime.now()}] Testing WebSocket: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to /ws/events")

            # Send a ping message
            ping_msg = {"type": "ping", "timestamp": datetime.now().isoformat()}
            await websocket.send(json.dumps(ping_msg))
            print("📤 Sent ping message")

            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"📥 Received: {data}")

            return True

    except Exception as e:
        print(f"❌ /ws/events failed: {e}")
        return False


async def test_websocket_benchmarking():
    """Test the /ws/benchmarking WebSocket endpoint."""
    uri = "ws://localhost:8000/ws/benchmarking"
    print(f"[{datetime.now()}] Testing WebSocket: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to /ws/benchmarking")

            # Send a ping message
            ping_msg = {"type": "ping", "timestamp": datetime.now().isoformat()}
            await websocket.send(json.dumps(ping_msg))
            print("📤 Sent ping message")

            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"📥 Received: {data}")

            return True

    except Exception as e:
        print(f"❌ /ws/benchmarking failed: {e}")
        return False


async def main():
    """Run WebSocket tests."""
    print("🔌 Testing FBA-Bench WebSocket Endpoints")
    print("=" * 50)

    # Test both endpoints
    events_result = await test_websocket_events()
    benchmarking_result = await test_websocket_benchmarking()

    print("\n" + "=" * 50)
    print("📊 WebSocket Test Results:")
    print(f"  /ws/events: {'✅ PASS' if events_result else '❌ FAIL'}")
    print(f"  /ws/benchmarking: {'✅ PASS' if benchmarking_result else '❌ FAIL'}")

    overall_success = events_result and benchmarking_result
    print(f"\n🎯 Overall WebSocket Status: {'✅ ALL PASS' if overall_success else '❌ SOME FAILED'}")

    return overall_success


if __name__ == "__main__":
    asyncio.run(main())
