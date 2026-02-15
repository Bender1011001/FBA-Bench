extends Node

## SimulationState.gd
## Central state management for the simulation data.

signal simulation_started(sim_id: String)
signal simulation_updated(tick_data: Dictionary)
signal simulation_finished(results: Dictionary)

var current_sim_id: String = ""
var last_tick: int = 0
var tick_data: Dictionary = {}
var tick_history: Array = []
var active_agents: Array = []
var world_state: Dictionary = {}

func _ready():
	WebSocketClient.message_received.connect(_on_socket_message)
	WebSocketClient.tick_received.connect(_process_tick)

func _on_socket_message(data: Dictionary):
	# Handle explicit type field (legacy protocol)
	if data.has("type"):
		match data["type"]:
			"simulation_start":
				current_sim_id = data.get("simulation_id", "")
				simulation_started.emit(current_sim_id)
				return
			"tick":
				_process_tick(data)
				return
			"simulation_end":
				simulation_finished.emit(data.get("results", {}))
				return
	
	# Infer message type from data shape (new protocol / realtime.py snapshot)
	if data.has("tick"):
		_process_tick(data)
	elif data.has("status"):
		var status = data.get("status", "")
		if status == "completed" or status == "stopped":
			simulation_finished.emit(data)
		elif status == "running":
			current_sim_id = data.get("id", "")
			simulation_started.emit(current_sim_id)
	elif data.has("kpis"):
		# Snapshot format from /api/v1/simulation/snapshot or event
		_process_snapshot(data)

func _process_tick(data: Dictionary):
	last_tick = data.get("tick", 0)
	tick_data = data
	world_state = data.get("world", {})
	active_agents = data.get("agents", [])
	
	# Keep history manageable (e.g., last 100 ticks)
	tick_history.append(data)
	if tick_history.size() > 100:
		tick_history.remove_at(0)
	
	# Emit with consistent structure
	simulation_updated.emit(data)

func _process_snapshot(data: Dictionary):
	# Map snapshot format to tick-like structure for UI consumption
	var kpis = data.get("kpis", {})
	if not (kpis is Dictionary):
		kpis = {}
	var snapshot_tick_data = {
		"tick": int(data.get("tick", last_tick)),
		"metrics": {
			"total_revenue": float(kpis.get("revenue", 0.0)),
			"total_profit": float(kpis.get("profit", 0.0)),
			"units_sold": int(kpis.get("units_sold", 0)),
			# Snapshot KPIs don't include inventory/pending orders yet; keep sane defaults.
			"inventory_count": int(kpis.get("inventory_count", kpis.get("inventory_units", 0))),
			"pending_orders": int(kpis.get("pending_orders", 0)),
		},
		"agents": data.get("agents", []),
		"world": {},
		"heatmap": []
	}
	_process_tick(snapshot_tick_data)

func reset():
	current_sim_id = ""
	last_tick = 0
	tick_history.clear()
	active_agents.clear()
	world_state.clear()
