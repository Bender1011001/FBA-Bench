extends Control

## Sandbox.gd
## Experiment configuration and execution interface

# Config panel references
@onready var scenario_dropdown = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/ScenarioFile
@onready var initial_capital = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/InitialCapital/SpinBox
@onready var max_ticks = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/MaxTicks/SpinBox
@onready var volatility_slider = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/Volatility/Slider
@onready var volatility_label = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/Volatility/Value
@onready var competitors_spin = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/Competitors/SpinBox
@onready var agent_dropdown = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/AgentModel
@onready var temperature_slider = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/Temperature/Slider
@onready var temperature_label = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/Temperature/Value
@onready var run_btn = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/ButtonBox/RunButton
@onready var save_btn = $MarginContainer/HSplitContainer/ConfigPanel/ScrollContainer/VBoxContainer/ButtonBox/SaveButton

# Results panel references
@onready var results_log = $MarginContainer/HSplitContainer/ResultsPanel/VBoxContainer/ResultsLog
@onready var progress_bar = $MarginContainer/HSplitContainer/ResultsPanel/VBoxContainer/ProgressBar

var is_running: bool = false
var pending_simulation_id: String = ""
var current_websocket_topic: String = ""

func _ready():
	_connect_signals()
	_fetch_initial_data()

func _fetch_initial_data():
	_log("Fetching configuration from backend...")
	ApiClient.get_scenarios()
	ApiClient.get_models()

func _connect_signals():
	volatility_slider.value_changed.connect(_on_volatility_changed)
	temperature_slider.value_changed.connect(_on_temperature_changed)
	run_btn.pressed.connect(_on_run_pressed)
	save_btn.pressed.connect(_on_save_pressed)
	
	ApiClient.request_completed.connect(_on_api_request_completed)
	ApiClient.request_failed.connect(_on_api_request_failed)
	
	SimulationState.simulation_updated.connect(_on_tick_received)
	SimulationState.simulation_finished.connect(_on_experiment_finished)

func _on_api_request_completed(endpoint: String, response: Variant):
	if endpoint == "/api/v1/scenarios":
		_populate_scenarios(response)
	elif endpoint == "/api/v1/llm/models":
		_populate_models(response)
	elif endpoint == "/api/v1/simulation":
		# Step 1 complete: Simulation created, now start it
		if response is Dictionary and response.has("id"):
			pending_simulation_id = response["id"]
			current_websocket_topic = response.get("websocket_topic", "")
			_log("Simulation created: %s" % pending_simulation_id)
			_log("Starting simulation...")
			ApiClient.start_simulation_by_id(pending_simulation_id)
		else:
			_log("[color=red]Failed to create simulation: Invalid response[/color]")
			_reset_run_state()
	elif endpoint.ends_with("/start"):
		# Step 2 complete: Simulation started, now trigger run and connect WebSocket
		_log("[color=green]Simulation started![/color]")
		_log("Triggering simulation run...")
		ApiClient.run_simulation_by_id(pending_simulation_id)
	elif endpoint.ends_with("/run"):
		# Step 3 complete: Simulation running, connect WebSocket
		_log("[color=cyan]Simulation running! Subscribing to topic: %s[/color]" % current_websocket_topic)
		WebSocketClient.connect_to_server()
		WebSocketClient.subscribe_topic(current_websocket_topic)

func _on_api_request_failed(endpoint: String, error: String):
	_log("[color=red]Error fetching %s: %s[/color]" % [endpoint, error])
	if endpoint == "/api/v1/simulation" or endpoint.ends_with("/start"):
		_reset_run_state()

func _reset_run_state():
	is_running = false
	run_btn.disabled = false
	pending_simulation_id = ""

func _populate_scenarios(data: Variant):
	scenario_dropdown.clear()
	if data is Dictionary and data.has("scenarios"):
		for scenario in data["scenarios"]:
			scenario_dropdown.add_item(scenario.get("id", "unknown"))
	elif data is Array:
		for scenario in data:
			if scenario is Dictionary:
				scenario_dropdown.add_item(scenario.get("id", "unknown"))
	_log("Scenarios loaded.")

func _populate_models(data: Variant):
	agent_dropdown.clear()
	if data is Dictionary and data.has("models"):
		for model in data["models"]:
			agent_dropdown.add_item(model.get("id", "unknown"))
	_log("Models loaded.")

func _on_volatility_changed(value: float):
	volatility_label.text = "%.2f" % value

func _on_temperature_changed(value: float):
	temperature_label.text = "%.2f" % value

func _on_run_pressed():
	if is_running:
		return
	
	is_running = true
	run_btn.disabled = true
	progress_bar.value = 0
	results_log.clear()
	_log("[b]Starting experiment...[/b]")
	
	var config = _build_config()
	_log("Config: " + JSON.stringify(config))
	
	# Step 1: Create simulation with config as metadata
	ApiClient.create_simulation(config)

func _build_config() -> Dictionary:
	return {
		"scenario_file": scenario_dropdown.get_item_text(scenario_dropdown.selected),
		"initial_capital": initial_capital.value,
		"max_ticks": int(max_ticks.value),
		"market": {
			"volatility": volatility_slider.value,
			"num_competitors": int(competitors_spin.value)
		},
		"agent": {
			"model": agent_dropdown.get_item_text(agent_dropdown.selected),
			"temperature": temperature_slider.value
		}
	}

func _on_tick_received(data: Dictionary):
	var tick = data.get("tick", 0)
	var max_t = int(max_ticks.value)
	progress_bar.value = (float(tick) / max_t) * 100.0
	
	if tick % 10 == 0:
		var metrics = data.get("metrics", {})
		_log("Tick %d: Revenue=$%.2f, Inventory=%d" % [
			tick,
			metrics.get("total_revenue", 0.0),
			metrics.get("inventory_count", 0)
		])

func _on_experiment_finished(results: Dictionary):
	is_running = false
	run_btn.disabled = false
	progress_bar.value = 100
	
	_log("")
	_log("[b][color=green]EXPERIMENT COMPLETE[/color][/b]")
	_log("Final Score: %.2f" % results.get("overall_score", 0.0))
	_log("Total Revenue: $%.2f" % results.get("total_revenue", 0.0))
	_log("Success Rate: %.1f%%" % (results.get("success_rate", 0.0) * 100))
	_log("Tokens Used: %d" % results.get("total_tokens", 0))

func _on_save_pressed():
	var config = _build_config()
	var file_path = "user://sandbox_config.json"
	var file = FileAccess.open(file_path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(config, "\t"))
		file.close()
		_log("[color=green]Config saved to %s[/color]" % ProjectSettings.globalize_path(file_path))
	else:
		_log("[color=red]Failed to save config![/color]")

func _log(text: String):
	results_log.append_text(text + "\n")
