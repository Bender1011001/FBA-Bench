# Godot GUI Architecture

The GUI is a Godot 4 application providing an immersive interface for the FBA-Bench simulation platform. It offers real-time visualization of agent decisions, leaderboard rankings, and sandbox experimentation. The application communicates with the FastAPI backend via REST API and WebSocket connections for live data streaming.

## Project Structure

```
godot_gui/
├── project.godot           # Godot project configuration
├── icon.svg                # Application icon
├── autoload/               # Singleton scripts (globally accessible)
│   ├── ApiClient.gd        # REST API communication
│   ├── WebSocketClient.gd  # Real-time data streaming
│   └── SimulationState.gd  # Central state management
├── scenes/
│   ├── main/
│   │   ├── Main.tscn       # Entry scene with navigation
│   │   └── Main.gd         # Navigation and status logic
│   ├── simulation/
│   │   ├── SimulationViewer.tscn  # 2D warehouse visualization
│   │   └── SimulationViewer.gd    # Simulation controls and rendering
│   ├── leaderboard/
│   │   ├── Leaderboard.tscn       # Model rankings table
│   │   └── Leaderboard.gd         # Filtering and selection
│   └── sandbox/
│       ├── Sandbox.tscn           # Experiment configuration
│       └── Sandbox.gd             # Config building and execution
└── resources/
    └── themes/             # Dark/light theme resources
```

## Core Components

### Autoload Singletons

**ApiClient.gd** — HTTP REST client for backend communication:
- `get_request(endpoint)`: Async GET requests
- `post_request(endpoint, data)`: Async POST with JSON body
- `get_simulation_status()`, `get_leaderboard()`, `start_simulation(config)`: Convenience methods
- Signals: `request_completed`, `request_failed`

**WebSocketClient.gd** — Real-time data streaming:
- `connect_to_server(sim_id)`: Establish WebSocket connection
- `disconnect_from_server()`: Clean disconnection
- `send_data(data)`: Send JSON messages
- Signals: `connected`, `disconnected`, `message_received`, `error_occurred`

**SimulationState.gd** — Central state store:
- Tracks current simulation ID, tick history, active agents, world state
- Processes incoming WebSocket messages
- Signals: `simulation_started`, `simulation_updated`, `simulation_finished`

### Views

**SimulationViewer** — Real-time 2D visualization:
- Left panel: Scenario/agent selection, start/stop controls, statistics
- Center: SubViewport with zoomable 2D warehouse view
- Agent positions rendered as colored circles
- Heatmap overlay for decision metrics (planned)

**Leaderboard** — Model rankings:
- Tree control with sortable columns: Rank, Model, Provider, Score, Success %, Profit, Tokens, Verified
- Filter bar: Search, tier filter, metric sort, verified-only toggle
- Details panel: Selected model stats with Compare/Replay/Verify actions

**Sandbox** — Experiment configuration:
- Scenario selection and parameters (capital, ticks, volatility, competitors)
- Agent model selection with temperature control
- Real-time results log with progress bar
- Save config functionality (planned)

## Data Flow

```
Backend (FastAPI)
    ↓ REST API (HTTP)
ApiClient.gd
    ↓ request_completed signal
Views (Leaderboard, etc.)

Backend (FastAPI)
    ↓ WebSocket
WebSocketClient.gd
    ↓ message_received signal
SimulationState.gd
    ↓ simulation_updated signal
SimulationViewer / Sandbox
```

## Backend Communication

### REST Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/simulation/status` | GET | Current simulation state |
| `/api/leaderboard` | GET | Model rankings with metrics |
| `/api/simulation/start` | POST | Start new simulation with config |

### WebSocket Protocol

Connect to: `ws://localhost:8000/ws/simulation/{sim_id}`

Message types (incoming):
- `simulation_start`: `{type, simulation_id}`
- `tick`: `{type, tick, metrics, agents, world, heatmap}`
- `simulation_end`: `{type, results}`

Message types (outgoing):
- `step`: `{action: "step"}` — Advance by one tick

## Theme System

The GUI supports dark/light themes via Godot's Theme resources. Toggle via the theme button in the top bar. Theme resources are stored in `resources/themes/`.

## Accessibility

- WCAG-compliant color contrast ratios
- Keyboard navigation support via Godot's focus system
- No mandatory animations or time-sensitive interactions

## Building and Exporting

### Development

Open `godot_gui/project.godot` in Godot 4.3+ and press F5 to run.

### Export Templates

Install export templates via Godot Editor → Project → Export. Supported platforms:
- Windows (x86_64)
- Linux (x86_64)
- macOS (Universal)
- Web (HTML5) — Note: WebSocket may require CORS configuration

### Automated Export

```bash
godot --headless --export-release "Windows Desktop" build/fba-bench-gui.exe
```

## Future Enhancements

- 3D warehouse visualization option
- Heatmap shader for decision metrics
- Timeline view for multi-turn interactions
- Model comparison overlays
- Reproducibility verification workflow
- Plugin system for custom visualizations