extends Control

## Main.gd
## App shell controller for view navigation, status, and presentation utilities.

@onready var status_dot: ColorRect = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/StatusIndicator/Dot
@onready var status_label: Label = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/StatusIndicator/StatusLabel
@onready var log_label: Label = $VBoxContainer/BottomBar/MarginContainer/HBoxContainer/LogLabel
@onready var recording_toggle: Button = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/RecordingToggle

@onready var sim_btn: Button = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/NavButtons/SimulationBtn
@onready var leaderboard_btn: Button = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/NavButtons/LeaderboardBtn
@onready var sandbox_btn: Button = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/NavButtons/SandboxBtn

@onready var simulation_view: Control = $VBoxContainer/Content/SimulationView
@onready var leaderboard_view: Control = $VBoxContainer/Content/LeaderboardView
@onready var sandbox_view: Control = $VBoxContainer/Content/SandboxView

var current_view := "simulation"
var recording_layout_enabled := false
var transition_tween: Tween

func _ready() -> void:
	UiDesignSystem.apply_to_control(self)
	_connect_signals()
	_update_nav_buttons()
	_update_log("Observer shell ready. Checking services...")
	_setup_status_animation()

	WebSocketClient.connect_to_server()
	_check_api_health()
	_play_boot_sequence()
	_add_disclaimer()

func _connect_signals() -> void:
	sim_btn.pressed.connect(_show_simulation)
	leaderboard_btn.pressed.connect(_show_leaderboard)
	sandbox_btn.pressed.connect(_show_sandbox)
	recording_toggle.pressed.connect(_toggle_recording_layout)

	WebSocketClient.connected.connect(_on_ws_connected)
	WebSocketClient.disconnected.connect(_on_ws_disconnected)

func _setup_status_animation() -> void:
	var tween := create_tween().set_loops()
	tween.tween_property(status_dot, "modulate:a", 0.5, 0.9).set_trans(Tween.TRANS_SINE)
	tween.tween_property(status_dot, "modulate:a", 1.0, 0.9).set_trans(Tween.TRANS_SINE)

func _check_api_health() -> void:
	ApiClient.get_request("/api/v1/health")

func _play_boot_sequence() -> void:
	$VBoxContainer.visible = false

	var overlay := ColorRect.new()
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.color = UiDesignSystem.COLOR_BG
	add_child(overlay)

	var center_box := VBoxContainer.new()
	center_box.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	center_box.add_theme_constant_override("separation", 10)
	overlay.add_child(center_box)

	var label := Label.new()
	label.theme_type_variation = &"ObserverTitle"
	label.text = "FBA-Bench Observer"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	center_box.add_child(label)

	var subtitle := Label.new()
	subtitle.theme_type_variation = &"ObserverMuted"
	subtitle.text = "Loading simulation theater"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	center_box.add_child(subtitle)

	var progress := ProgressBar.new()
	progress.custom_minimum_size = Vector2(320, 8)
	progress.show_percentage = false
	center_box.add_child(progress)

	var tween := create_tween()
	tween.tween_property(progress, "value", 45.0, 0.5).set_trans(Tween.TRANS_CUBIC)
	tween.tween_callback(func(): subtitle.text = "Syncing API + realtime stream")
	tween.tween_property(progress, "value", 82.0, 0.8).set_trans(Tween.TRANS_CUBIC)
	tween.tween_callback(func(): subtitle.text = "Preparing observer HUD")
	tween.tween_property(progress, "value", 100.0, 0.5).set_trans(Tween.TRANS_CUBIC)
	tween.tween_callback(func():
		overlay.queue_free()
		$VBoxContainer.visible = true
		$VBoxContainer.modulate.a = 0.0
		create_tween().tween_property($VBoxContainer, "modulate:a", 1.0, 0.45)
	)

func _add_disclaimer() -> void:
	var disclaimer := Label.new()
	disclaimer.text = "Simulation output for benchmark visualization only."
	disclaimer.theme_type_variation = &"ObserverMuted"
	disclaimer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	disclaimer.position -= Vector2(12, 10)
	add_child(disclaimer)

func _switch_view(to_view: Control) -> void:
	var views: Array[Control] = [simulation_view, leaderboard_view, sandbox_view]
	for view in views:
		if view == to_view:
			view.visible = true
			view.modulate.a = 0.0
			view.position = Vector2(24, 0)
			if transition_tween != null and transition_tween.is_running():
				transition_tween.kill()
			transition_tween = create_tween().set_parallel(true)
			transition_tween.tween_property(view, "modulate:a", 1.0, 0.28).set_trans(Tween.TRANS_CUBIC)
			transition_tween.tween_property(view, "position:x", 0.0, 0.28).set_trans(Tween.TRANS_CUBIC)
		else:
			view.visible = false

func _show_simulation() -> void:
	current_view = "simulation"
	_switch_view(simulation_view)
	_update_nav_buttons()
	_update_log("View: Simulation Theater")

func _show_leaderboard() -> void:
	current_view = "leaderboard"
	_switch_view(leaderboard_view)
	_update_nav_buttons()
	_update_log("View: Leaderboard")

func _show_sandbox() -> void:
	current_view = "sandbox"
	_switch_view(sandbox_view)
	_update_nav_buttons()
	_update_log("View: Sandbox Lab")

func _update_nav_buttons() -> void:
	sim_btn.button_pressed = current_view == "simulation"
	leaderboard_btn.button_pressed = current_view == "leaderboard"
	sandbox_btn.button_pressed = current_view == "sandbox"

func _toggle_recording_layout() -> void:
	recording_layout_enabled = !recording_layout_enabled
	UiDesignSystem.set_recording_layout(recording_layout_enabled)
	recording_toggle.text = "Recording Layout: ON" if recording_layout_enabled else "Recording Layout"
	_update_log("Recording layout %s" % ("enabled" if recording_layout_enabled else "disabled"))

func _update_log(message: String) -> void:
	log_label.text = message

func _on_ws_connected() -> void:
	status_dot.color = Color("#8EE67A")
	status_label.text = "Connected"
	_update_log("Realtime connected")

func _on_ws_disconnected() -> void:
	status_dot.color = Color("#FF7E89")
	status_label.text = "Disconnected"
	_update_log("Realtime disconnected")