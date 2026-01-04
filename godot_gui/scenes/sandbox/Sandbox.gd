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

func _ready():
	_setup_dropdowns()
	_connect_signals()

func _setup_dropdowns():
	scenario_dropdown.clear()
	scenario_dropdown.add_item("tier_0_baseline.yaml")
	scenario_dropdown.add_item("tier_1_moderate.yaml")
	scenario_dropdown.add_item("tier_2_advanced.yaml")
	scenario_dropdown.add_item("tier_3_expert.yaml")
	
	agent_dropdown.clear()
	agent_dropdown.add_item("gpt-4o")
	agent_dropdown.add_item("claude-3-5-sonnet")
	agent_dropdown.add_item("gemini-2.0-flash")
	agent_dropdown.add_item("greedy-baseline")

func _connect_signals():
	volatility_slider.value_changed.connect(_on_volatility_changed)
	temperature_slider.value_changed.connect(_on_temperature_changed)
	run_btn.pressed.connect(_on_run_pressed)
	save_btn.pressed.connect(_on_save_pressed)
	
	SimulationState.simulation_updated.connect(_on_tick_received)
	SimulationState.simulation_finished.connect(_on_experiment_finished)

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
	
	ApiClient.start_simulation(config)
	WebSocketClient.connect_to_server()

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
	# Future: Save config to file
	_log("[i]Config saved (not implemented)[/i]")

func _log(text: String):
	results_log.append_text(text + "\n")
