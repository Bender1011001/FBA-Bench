extends Node

## SimulationState.gd
## Central state management for the simulation data.

signal simulation_started(sim_id: String)
signal simulation_updated(tick_data: Dictionary)
signal simulation_finished(results: Dictionary)

var current_sim_id: String = ""
var last_tick: int = 0
var tick_history: Array = []
var active_agents: Array = []
var world_state: Dictionary = {}

func _ready():
	WebSocketClient.message_received.connect(_on_socket_message)

func _on_socket_message(data: Dictionary):
	if data.has("type"):
		match data["type"]:
			"simulation_start":
				current_sim_id = data.get("simulation_id", "")
				simulation_started.emit(current_sim_id)
			"tick":
				_process_tick(data)
			"simulation_end":
				simulation_finished.emit(data.get("results", {}))

func _process_tick(data: Dictionary):
	last_tick = data.get("tick", 0)
	world_state = data.get("world", {})
	active_agents = data.get("agents", [])
	
	# Keep history manageable (e.g., last 100 ticks)
	tick_history.append(data)
	if tick_history.size() > 100:
		tick_history.remove_at(0)
	
	simulation_updated.emit(data)

func reset():
	current_sim_id = ""
	last_tick = 0
	tick_history.clear()
	active_agents.clear()
	world_state.clear()
