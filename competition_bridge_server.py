"""competition_bridge_server.py
Bridge server: translates competition_run recording.json into Godot GUI format.
Serves REST at localhost:8080 + WebSocket at /ws/realtime.
Run: python competition_bridge_server.py
"""
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(r"E:\code.projects\fba\FBA-Bench-Enterprise")
RESULTS_DIR = BASE_DIR / "results" / "competition"
LOG_FILE = BASE_DIR / "competition_run.log"
INITIAL_INVENTORY = 500
COST_PER_UNIT = 10.0
BRIDGE_PORT = 8080

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="FBA Competition Bridge Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── WebSocket Manager ────────────────────────────────────────────────────────
connected_websockets: Set[WebSocket] = set()


async def broadcast(message: dict) -> None:
    """Send JSON message to all connected WebSocket clients."""
    disconnected: Set[WebSocket] = set()
    payload = json.dumps(message, ensure_ascii=False)
    for ws in list(connected_websockets):
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    connected_websockets -= disconnected


# ─── Recording discovery & loading ────────────────────────────────────────────
def find_latest_recording() -> Optional[Path]:
    runs = sorted(RESULTS_DIR.glob("run_*"), key=lambda p: p.name, reverse=True)
    for run_dir in runs:
        rec = run_dir / "recording.json"
        if rec.exists():
            return rec
    return None


def load_recording() -> Optional[dict]:
    rec_path = find_latest_recording()
    if not rec_path:
        return None
    try:
        return json.loads(rec_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[bridge] load_recording error: {e}")
        return None


# ─── Data helpers ─────────────────────────────────────────────────────────────
def strip_md_fences(text: str) -> str:
    """Remove ```json ... ``` markdown fences."""
    s = text.strip()
    s = re.sub(r"^```[^\n]*\n", "", s)
    s = re.sub(r"\n```$", "", s)
    return s.strip()


def extract_reasoning(raw_response: str, parse_error: Optional[str] = None) -> str:
    """Pull the 'reasoning' field from an agent's LLM response."""
    if not raw_response:
        return f"[PARSE ERROR] {str(parse_error)[:300]}" if parse_error else ""
    cleaned = strip_md_fences(raw_response)
    try:
        data = json.loads(cleaned)
        reasoning = str(data.get("reasoning", ""))
        conf = data.get("confidence", None)
        if reasoning:
            suffix = f"  [confidence={conf:.2f}]" if conf is not None else ""
            return (reasoning[:600] + suffix)
    except Exception:
        pass
    # Regex fallback for malformed JSON
    m = re.search(r'"reasoning"\s*:\s*"(.*?)(?:",\s*"confidence|"\s*\})', raw_response, re.DOTALL)
    if m:
        return m.group(1)[:500].replace("\\n", " ").replace('\\"', '"')
    if parse_error:
        return f"[PARSE ERROR] {str(parse_error)[:300]}"
    return raw_response[:300]


def build_tick_message(recording: dict, tick_num: int,
                       cumulative: Dict[str, dict]) -> Optional[dict]:
    """Translate one recording tick into a Godot GUI tick message."""
    tick_data = next((t for t in recording.get("ticks", [])
                      if t.get("tick") == tick_num), None)
    if not tick_data:
        return None

    agents_meta = {a["id"]: a for a in recording.get("agents", [])}
    decisions = tick_data.get("agent_decisions", {})
    standings = tick_data.get("standings_before", [])

    # Build rank / cumulative profit lookup from standings
    rank_lookup: Dict[str, int] = {}
    profit_lookup: Dict[str, float] = {}
    for s in standings:
        name = s.get("agent_name", "")
        rank_lookup[name] = s.get("rank", 99)
        profit_lookup[name] = float(s.get("cumulative_profit_usd", 0.0))

    # Snapshot previous prices for change-event generation
    prev_prices = {aid: cumulative.get(aid, {}).get("price", 20.0)
                   for aid in decisions}

    day_revenue = 0.0
    day_profit = 0.0
    day_units = 0
    agents_list = []
    products_list = []
    events_list = []

    for agent_id, dec in decisions.items():
        meta = agents_meta.get(agent_id, {})
        agent_name = meta.get("name", agent_id)
        avatar = meta.get("avatar", "")

        new_price = float(dec.get("new_price", 20.0))
        units_sold = int(dec.get("units_sold", 0))
        day_profit_usd = int(dec.get("day_profit_cents", 0)) / 100.0
        prompt_tok = int(dec.get("prompt_tokens", 0))
        comp_tok = int(dec.get("completion_tokens", 0))
        parse_error = dec.get("parse_error")
        raw_resp = dec.get("raw_response", "")
        from_cache = bool(dec.get("from_cache", False))

        # Update cumulative per-agent state
        if agent_id not in cumulative:
            cumulative[agent_id] = {
                "inventory": INITIAL_INVENTORY, "total_profit": 0.0,
                "total_units": 0, "total_tokens": 0, "price": 20.0,
                "success_days": 0, "total_days": 0,
            }
        c = cumulative[agent_id]
        c["inventory"] = max(0, c["inventory"] - units_sold)
        c["total_profit"] += day_profit_usd
        c["total_units"] += units_sold
        c["total_tokens"] += prompt_tok + comp_tok
        c["price"] = new_price
        c["total_days"] += 1
        if not parse_error:
            c["success_days"] += 1

        day_revenue += new_price * units_sold
        day_profit += day_profit_usd
        day_units += units_sold

        reasoning = extract_reasoning(raw_resp, parse_error)
        rank = rank_lookup.get(agent_name, 99)
        cum_profit = profit_lookup.get(agent_name, c["total_profit"])

        agents_list.append({
            "id": agent_id, "name": agent_name, "avatar": avatar,
            "rank": rank, "strategy": reasoning,
            "profit": cum_profit, "day_profit": day_profit_usd,
            "price": new_price, "units_sold_today": units_sold,
            "total_units": c["total_units"], "inventory": c["inventory"],
            "tokens": c["total_tokens"], "from_cache": from_cache,
            "has_error": bool(parse_error),
            "error": str(parse_error)[:300] if parse_error else "",
            "model": meta.get("model", ""), "last_tool_calls": [],
        })

        asin = agent_id.replace("agent-", "").upper()[:12]
        products_list.append({
            "asin": asin, "name": agent_name,
            "inventory": c["inventory"], "price": new_price,
        })

        # Emit pricing-change events
        prev = prev_prices.get(agent_id, 20.0)
        if abs(new_price - prev) > 0.001:
            arrow = "UP" if new_price > prev else "DOWN"
            events_list.append({"type": "pricing",
                "message": (f"{agent_name} {arrow} ${prev:.2f}->"
                            f"${new_price:.2f} | sold {units_sold} +${day_profit_usd:.2f}")})
        elif units_sold > 0:
            events_list.append({"type": "strategy",
                "message": f"{agent_name} sold {units_sold}u @ ${new_price:.2f} +${day_profit_usd:.2f}"})

        if parse_error and "429" not in str(parse_error):
            events_list.append({"type": "loss",
                "message": f"{agent_name} parse error – holding ${new_price:.2f}"})

    agents_list.sort(key=lambda a: a["rank"])
    total_inv = sum(c.get("inventory", 0) for c in cumulative.values())

    return {
        "type": "tick",
        "tick": tick_num,
        "day": tick_num,
        "days_total": recording.get("days_total", 365),
        "simulation_time": tick_data.get("simulation_time", ""),
        "metrics": {
            "total_revenue": day_revenue,
            "total_profit": day_profit,
            "units_sold": day_units,
            "inventory_count": total_inv,
            "inventory_value": total_inv * COST_PER_UNIT,
        },
        "products": products_list,
        "agents": agents_list,
        "competitors": [
            {"asin": p["asin"], "name": p["name"], "price": f"{p['price']:.2f}",
             "inventory": p["inventory"], "is_out_of_stock": p["inventory"] <= 0}
            for p in products_list
        ],
        "events": events_list,
        "heatmap": [],
        "world": {},
    }


def build_leaderboard(recording: dict, cumulative: Dict[str, dict]) -> list:
    """Build leaderboard array for /api/v1/leaderboard."""
    if not recording:
        return []
    agents_meta = {a["id"]: a for a in recording.get("agents", [])}
    ticks = recording.get("ticks", [])
    if not ticks:
        return []
    standings = ticks[-1].get("standings_before", [])
    board = []
    for s in standings:
        agent_name = s.get("agent_name", "")
        cum_profit = float(s.get("cumulative_profit_usd", 0.0))
        agent_id = next(
            (aid for aid, m in agents_meta.items() if m.get("name") == agent_name),
            None
        )
        c = cumulative.get(agent_id, {}) if agent_id else {}
        total_days = max(1, c.get("total_days", 1))
        success_days = c.get("success_days", total_days)
        model = agents_meta.get(agent_id, {}).get("model", "") if agent_id else ""
        provider = model.split("/")[0] if model and "/" in model else "builtin"
        board.append({
            "model_name": agent_name,
            "provider": provider,
            "overall_score": round(cum_profit / max(1.0, cum_profit + 50.0), 4),
            "success_rate": round(success_days / total_days, 4),
            "avg_profit": round(cum_profit / total_days, 4),
            "total_tokens": c.get("total_tokens", 0),
            "verified": success_days == total_days,
            "rank": s.get("rank", 99),
            "cumulative_profit": cum_profit,
        })
    board.sort(key=lambda x: x["rank"])
    return board


# ─── Global mutable state ─────────────────────────────────────────────────────
_last_broadcast_tick: int = 0
_cumulative_state: Dict[str, dict] = {}
_sim_running: bool = False
SIM_ID = "competition-live-365"


# ─── REST Endpoints ───────────────────────────────────────────────────────────
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "FBA Competition Bridge",
            "sim_running": _sim_running, "last_tick": _last_broadcast_tick}


@app.get("/api/v1/leaderboard")
async def leaderboard():
    rec = load_recording()
    return JSONResponse(build_leaderboard(rec or {}, _cumulative_state))


@app.get("/api/v1/scenarios")
async def scenarios():
    return {"scenarios": [
        {"id": "competition_365", "name": "365-Day Live Competition",
         "description": "11 AI agents compete in Amazon FBA pricing over 365 days"},
        {"id": "tier1_basic", "name": "Tier 1 Basic", "description": "Standard ops"},
    ]}


@app.get("/api/v1/llm/models")
async def models():
    rec = load_recording()
    if not rec:
        return {"models": [{"id": "live", "name": "Live Competition"}]}
    return {"models": [
        {"id": a["id"], "name": a["name"],
         "model": a.get("model", ""), "avatar": a.get("avatar", "")}
        for a in rec.get("agents", [])
    ]}


@app.post("/api/v1/simulation")
async def create_simulation(body: dict = None):
    global _sim_running
    _sim_running = True
    return {"id": SIM_ID, "status": "created", "websocket_topic": "competition"}


@app.post("/api/v1/simulation/{sim_id}/start")
async def start_simulation(sim_id: str):
    return {"id": sim_id, "status": "started"}


@app.post("/api/v1/simulation/{sim_id}/run")
async def run_simulation(sim_id: str):
    global _sim_running
    _sim_running = True
    return {"id": sim_id, "status": "running"}


@app.get("/api/v1/simulation/snapshot")
async def snapshot():
    rec = load_recording()
    if not rec:
        return {"status": "no_data"}
    ticks = rec.get("ticks", [])
    if not ticks:
        return {"status": "no_ticks"}
    last = ticks[-1]
    return {
        "status": "running" if rec.get("partial") else "completed",
        "tick": last.get("tick", 0),
        "days_total": rec.get("days_total", 365),
        "leaderboard": last.get("standings_before", []),
        "run_id": rec.get("run_id", ""),
    }


# ─── WebSocket endpoint ───────────────────────────────────────────────────────
@app.websocket("/ws/realtime")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    print(f"[WS] Client connected — total {len(connected_websockets)}")

    # Greet client
    await websocket.send_text(json.dumps({
        "type": "connection_established",
        "message": "FBA Competition Bridge — live 365-day run",
    }))

    # Replay all completed ticks so far (fast replay, 50ms between)
    rec = load_recording()
    if rec and _last_broadcast_tick > 0:
        print(f"[WS] Replaying ticks 1–{_last_broadcast_tick} for new client")
        cum = {}  # Private copy for replay
        for tick_num in range(1, _last_broadcast_tick + 1):
            msg = build_tick_message(rec, tick_num, cum)
            if msg:
                try:
                    await websocket.send_text(json.dumps({
                        "type": "event",
                        "topic": "competition",
                        "data": msg,
                    }, ensure_ascii=False))
                    await asyncio.sleep(0.04)  # 40 ms per replay frame
                except Exception:
                    break

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=25.0)
                msg = json.loads(raw)
                t = msg.get("type", "")
                if t == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif t == "subscribe":
                    topic = msg.get("topic", "")
                    await websocket.send_text(json.dumps({"type": "subscribed", "topic": topic}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    finally:
        connected_websockets.discard(websocket)


# ─── Background poller ────────────────────────────────────────────────────────
async def poll_recording():
    """Continuously poll recording.json; broadcast new ticks over WebSocket."""
    global _last_broadcast_tick, _cumulative_state, _sim_running
    print("[bridge] Poller started")

    # First pass: build cumulative state without broadcasting
    rec = load_recording()
    if rec:
        ticks = rec.get("ticks", [])
        for tick_num in range(1, len(ticks) + 1):
            build_tick_message(rec, tick_num, _cumulative_state)
            _last_broadcast_tick = tick_num
        print(f"[bridge] Initial catch-up: ticks 1–{_last_broadcast_tick}")

    while True:
        await asyncio.sleep(5)
        try:
            rec = load_recording()
            if not rec:
                continue
            ticks = rec.get("ticks", [])
            for tick_num in range(_last_broadcast_tick + 1, len(ticks) + 1):
                msg = build_tick_message(rec, tick_num, _cumulative_state)
                if msg:
                    _last_broadcast_tick = tick_num
                    if connected_websockets:
                        ws_envelope = {
                            "type": "event",
                            "topic": "competition",
                            "data": msg,
                        }
                        await broadcast(ws_envelope)
                        print(f"[bridge] Broadcast Day {tick_num} "
                              f"→ {len(connected_websockets)} client(s)")
        except Exception as e:
            print(f"[bridge] Poller error: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poll_recording())
    print(f"[bridge] Server online at http://localhost:{BRIDGE_PORT}")
    print(f"[bridge] WebSocket: ws://localhost:{BRIDGE_PORT}/ws/realtime")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_PORT, log_level="info")
