extends Control

## Main.gd
## Main application controller with navigation and status management

# UI References
@onready var status_dot = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/StatusIndicator/Dot
@onready var status_label = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/StatusIndicator/StatusLabel
@onready var log_label = $VBoxContainer/BottomBar/MarginContainer/HBoxContainer/LogLabel
@onready var theme_toggle = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/ThemeToggle

# Navigation buttons
@onready var sim_btn = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/NavButtons/SimulationBtn
@onready var leaderboard_btn = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/NavButtons/LeaderboardBtn
@onready var sandbox_btn = $VBoxContainer/TopBar/MarginContainer/HBoxContainer/NavButtons/SandboxBtn

# Views
@onready var simulation_view = $VBoxContainer/Content/SimulationView
@onready var leaderboard_view = $VBoxContainer/Content/LeaderboardView
@onready var sandbox_view = $VBoxContainer/Content/SandboxView

var current_view: String = "simulation"
var is_dark_theme: bool = true

func _ready():
	_connect_signals()
	_update_nav_buttons()
	_update_log("GUI Initialized. Connecting to backend...")
	_setup_animations()
	
	# Attempt initial connection
	WebSocketClient.connect_to_server()
	_check_api_health()

	_play_boot_sequence()

	# Add disclaimer footer
	var disclaimer = Label.new()
	disclaimer.text = "FBA-Bench is a simulation tool. Not financial advice. © 2026 Proprietary."
	disclaimer.add_theme_font_size_override("font_size", 10)
	disclaimer.add_theme_color_override("font_color", Color(1, 1, 1, 0.5))
	
	# Position at bottom right
	disclaimer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	disclaimer.position -= Vector2(10, 10) # Padding
	
	add_child(disclaimer)

func _play_boot_sequence():
	# Hide main UI initially
	$VBoxContainer.visible = false
	
	# Create boot overlay
	var overlay = ColorRect.new()
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.color = Color(0.05, 0.05, 0.08, 1.0)
	add_child(overlay)
	
	var center_box = VBoxContainer.new()
	center_box.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	overlay.add_child(center_box)
	
	var label = Label.new()
	label.text = "Initializing Kernel..."
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", Color(0.0, 0.8, 1.0))
	center_box.add_child(label)
	
	var progress = ProgressBar.new()
	progress.custom_minimum_size = Vector2(300, 4)
	progress.show_percentage = false
	center_box.add_child(progress)
	
	# Animation Sequence
	var tween = create_tween()
	
	# 0% -> 40% : Initializing Kernel
	tween.tween_property(progress, "value", 40.0, 0.6).set_trans(Tween.TRANS_CUBIC)
	tween.tween_callback(func(): label.text = "Loading Market Data...")
	
	# 40% -> 80% : Loading Market Data
	tween.tween_property(progress, "value", 80.0, 0.8).set_trans(Tween.TRANS_CUBIC)
	tween.tween_callback(func(): label.text = "Connecting to Neural Engine...")
	
	# 80% -> 100% : Connecting...
	tween.tween_property(progress, "value", 100.0, 0.6).set_trans(Tween.TRANS_CUBIC)
	
	# Finish
	tween.tween_callback(func():
		overlay.queue_free()
		$VBoxContainer.visible = true
		$VBoxContainer.modulate.a = 0.0
		create_tween().tween_property($VBoxContainer, "modulate:a", 1.0, 0.5)
	)

func _setup_animations():
	# Simple glow animation for status dot
	var tween = create_tween().set_loops()
	tween.tween_property(status_dot, "modulate:a", 0.4, 1.0).set_trans(Tween.TRANS_SINE)
	tween.tween_property(status_dot, "modulate:a", 1.0, 1.0).set_trans(Tween.TRANS_SINE)

func _switch_view(to_view: Control):
	var views = [simulation_view, leaderboard_view, sandbox_view]
	for v in views:
		if v == to_view:
			v.visible = true
			v.modulate.a = 0
			create_tween().tween_property(v, "modulate:a", 1.0, 0.3)
		else:
			v.visible = false

# Navigation
func _show_simulation():
	current_view = "simulation"
	_switch_view(simulation_view)
	_update_nav_buttons()
	_update_log("Viewing: Simulation")

func _show_leaderboard():
	current_view = "leaderboard"
	_switch_view(leaderboard_view)
	_update_nav_buttons()
	_update_log("Viewing: Leaderboard")

func _show_sandbox():
	current_view = "sandbox"
	_switch_view(sandbox_view)
	_update_nav_buttons()
	_update_log("Viewing: Sandbox")

func _update_nav_buttons():
	sim_btn.button_pressed = (current_view == "simulation")
	leaderboard_btn.button_pressed = (current_view == "leaderboard")
	sandbox_btn.button_pressed = (current_view == "sandbox")

func _toggle_theme():
	is_dark_theme = !is_dark_theme
	var theme_name = "Dark" if is_dark_theme else "Light"
	
	# Apply theme-based styling to main container
	var bg_color = Color(0.11, 0.11, 0.14, 1.0) if is_dark_theme else Color(0.95, 0.95, 0.97, 1.0)
	var text_color = Color(1, 1, 1, 1) if is_dark_theme else Color(0.1, 0.1, 0.1, 1)
	
	# Try to load theme resource if available
	var theme_path = "res://themes/%s_theme.tres" % theme_name.to_lower()
	if ResourceLoader.exists(theme_path):
		self.theme = load(theme_path)
		_update_log("Theme: %s (loaded)" % theme_name)
	else:
		# Fallback: Apply visual changes directly
		self.modulate = Color(1, 1, 1, 1) if is_dark_theme else Color(0.9, 0.9, 0.95, 1)
		_update_log("Theme: %s" % theme_name)

func _connect_signals():
	sim_btn.pressed.connect(_show_simulation)
	leaderboard_btn.pressed.connect(_show_leaderboard)
	sandbox_btn.pressed.connect(_show_sandbox)
	theme_toggle.pressed.connect(_toggle_theme)
	WebSocketClient.connected.connect(_on_ws_connected)
	WebSocketClient.disconnected.connect(_on_ws_disconnected)

func _update_log(message: String):
	log_label.text = message

func _check_api_health():
	ApiClient.get_request("/api/v1/health")

func _on_ws_connected():
	status_dot.color = Color(0.2, 1.0, 0.2, 1.0)  # Green
	status_label.text = "Connected"
	_update_log("WebSocket connected to backend")

func _on_ws_disconnected():
	status_dot.color = Color(1.0, 0.2, 0.2, 1.0)  # Red
	status_label.text = "Disconnected"
	_update_log("WebSocket disconnected")
