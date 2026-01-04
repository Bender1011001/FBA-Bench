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
	
	# Attempt initial connection
	WebSocketClient.connect_to_server()
	_check_api_health()

func _connect_signals():
	WebSocketClient.connected.connect(_on_socket_connected)
	WebSocketClient.disconnected.connect(_on_socket_disconnected)
	ApiClient.request_failed.connect(_on_api_failed)
	
	sim_btn.pressed.connect(_show_simulation)
	leaderboard_btn.pressed.connect(_show_leaderboard)
	sandbox_btn.pressed.connect(_show_sandbox)
	theme_toggle.pressed.connect(_toggle_theme)

func _check_api_health():
	ApiClient.get_simulation_status()

func _on_socket_connected():
	status_dot.color = Color(0.2, 1.0, 0.4)
	status_label.text = "Connected"
	_update_log("Real-time stream established.")

func _on_socket_disconnected():
	status_dot.color = Color(1.0, 0.2, 0.2)
	status_label.text = "Disconnected"
	_update_log("Connection lost. Retrying...")

func _on_api_failed(endpoint: String, error: String):
	_update_log("API Error [" + endpoint + "]: " + error)

func _update_log(msg: String):
	log_label.text = msg
	print("[Main] ", msg)

# Navigation
func _show_simulation():
	current_view = "simulation"
	simulation_view.visible = true
	leaderboard_view.visible = false
	sandbox_view.visible = false
	_update_nav_buttons()
	_update_log("Viewing: Simulation")

func _show_leaderboard():
	current_view = "leaderboard"
	simulation_view.visible = false
	leaderboard_view.visible = true
	sandbox_view.visible = false
	_update_nav_buttons()
	_update_log("Viewing: Leaderboard")

func _show_sandbox():
	current_view = "sandbox"
	simulation_view.visible = false
	leaderboard_view.visible = false
	sandbox_view.visible = true
	_update_nav_buttons()
	_update_log("Viewing: Sandbox")

func _update_nav_buttons():
	sim_btn.button_pressed = (current_view == "simulation")
	leaderboard_btn.button_pressed = (current_view == "leaderboard")
	sandbox_btn.button_pressed = (current_view == "sandbox")

func _toggle_theme():
	is_dark_theme = !is_dark_theme
	# Future: Apply theme resource
	_update_log("Theme toggled (not fully implemented)")
