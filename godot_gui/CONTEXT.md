# Godot GUI - Context

> **Last Updated**: 2026-01-05

## Purpose

Immersive Godot 4.5 visualization GUI for FBA-Bench simulations. Connects to the FastAPI backend via WebSocket for real-time updates and REST API for control operations.

## Project Configuration

| Setting | Value |
|---------|-------|
| **Engine Version** | Godot 4.5 (Forward Plus) |
| **Main Scene** | `res://scenes/main/Main.tscn` |
| **Window Size** | 1280x720, canvas_items stretch mode |
| **Language** | GDScript |

## Autoloads (Singletons)

| Autoload | Description |
|----------|-------------|
| `ApiClient` | REST API client - GET/POST to backend, helper methods for simulation control |
| `WebSocketClient` | Real-time WebSocket connection with auto-reconnect, topic subscriptions, heartbeats |
| `SimulationState` | Central state management - processes ticks, emits `simulation_updated` signal |

## Directory Structure

```
godot_gui/
├── project.godot          # Project configuration
├── autoload/              # Singletons (API, WebSocket, State)
│   ├── ApiClient.gd       # REST client (2.8KB)
│   ├── WebSocketClient.gd # WebSocket with reconnect (5.9KB)
│   └── SimulationState.gd # State management (2.5KB)
└── scenes/
    ├── main/              # Main application controller
    │   └── Main.gd        # Navigation, status, theme toggle
    ├── simulation/        # Simulation visualization
    │   ├── SimulationViewer.gd  # Main viewer (12KB)
    │   ├── AgentInspector.gd    # Agent details panel
    │   └── PerformanceChart.gd  # Real-time charts
    ├── leaderboard/       # Leaderboard view
    └── sandbox/           # Sandbox experimentation
```

## Key Signals

### WebSocketClient
```gdscript
signal connected
signal disconnected
signal tick_received(tick_data: Dictionary)
signal agent_event_received(agent_id: String, event_type: String, data: Dictionary)
signal market_event_received(data: Dictionary)
```

### SimulationState
```gdscript
signal simulation_started(sim_id: String)
signal simulation_updated(tick_data: Dictionary)  # Main signal for UI updates
signal simulation_finished(results: Dictionary)
```

## Backend Connection

- **REST API**: `http://localhost:8000` (configurable in `ApiClient.gd`)
- **WebSocket**: `ws://localhost:8000/ws/realtime` (topic-based protocol)

## Usage Flow

1. GUI connects to WebSocket on startup
2. User selects scenario/agent and clicks Start
3. `ApiClient.create_simulation()` → `start_simulation_by_id()` → `run_simulation_by_id()`
4. Subscribe to WebSocket topic for real-time updates
5. `SimulationState` processes ticks and emits `simulation_updated`
6. UI components (charts, agent visuals) react to signal

## ⚠️ Known Issues

| Location | Issue | Severity |
|----------|-------|----------|
| `Main.gd:89` | Theme toggle not fully implemented - only logs message | Low |
| `Leaderboard.gd:159-171` | Export, Compare, Replay, Verify buttons are stubs (`# Future:`) | Medium |
| `SimulationViewer.gd:89` | "Warehouse zones placeholder" comment - basic implementation | Info |

## Running the GUI

```bash
# Option 1: From Godot Editor
# Open godot_gui/ folder in Godot 4.5+, press F5

# Option 2: Via Python launcher (starts backend automatically)
python launch_godot_gui.py
```

## Related

- [fba_bench_api](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_bench_api/CONTEXT.md) - Backend API
- [realtime.py](file:///c:/Users/admin/GitHub-projects/fba/FBA-Bench-Enterprise/src/fba_bench_api/api/routes/realtime.py) - WebSocket handlers
