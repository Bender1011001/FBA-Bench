extends Control

## SimulationViewer.gd
## Main simulation visualization controller

# UI References
@onready var scenario_dropdown = $HSplitContainer/LeftPanel/VBoxContainer/ScenarioDropdown
@onready var agent_dropdown = $HSplitContainer/LeftPanel/VBoxContainer/AgentDropdown
@onready var seed_input = $HSplitContainer/LeftPanel/VBoxContainer/SeedInput
@onready var speed_slider = $HSplitContainer/LeftPanel/VBoxContainer/SpeedSlider
@onready var start_btn = $HSplitContainer/LeftPanel/VBoxContainer/ButtonContainer/StartButton
@onready var step_btn = $HSplitContainer/LeftPanel/VBoxContainer/ButtonContainer/StepButton
@onready var stop_btn = $HSplitContainer/LeftPanel/VBoxContainer/ButtonContainer/StopButton

# Stats labels
@onready var tick_label = $HSplitContainer/LeftPanel/VBoxContainer/TickLabel
@onready var revenue_label = $HSplitContainer/LeftPanel/VBoxContainer/RevenueLabel
@onready var inventory_label = $HSplitContainer/LeftPanel/VBoxContainer/InventoryLabel
@onready var orders_label = $HSplitContainer/LeftPanel/VBoxContainer/OrdersLabel

# Viewport elements
@onready var camera = $HSplitContainer/CenterPanel/WarehouseView/SubViewport/Camera2D
@onready var warehouse_container = $HSplitContainer/CenterPanel/WarehouseView/SubViewport/WarehouseContainer
@onready var agent_container = $HSplitContainer/CenterPanel/WarehouseView/SubViewport/AgentContainer
@onready var heatmap_overlay = $HSplitContainer/CenterPanel/WarehouseView/SubViewport/HeatmapOverlay

# Zoom controls
@onready var zoom_in_btn = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls/ZoomIn
@onready var zoom_out_btn = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls/ZoomOut
@onready var reset_view_btn = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls/ResetView

var is_running: bool = false
var current_zoom: float = 1.0
const ZOOM_STEP = 0.1
const MIN_ZOOM = 0.25
const MAX_ZOOM = 4.0

func _ready():
	_connect_signals()
	_populate_dropdowns()
	_update_button_states()
	
	SimulationState.simulation_updated.connect(_on_simulation_tick)

func _connect_signals():
	start_btn.pressed.connect(_on_start_pressed)
	step_btn.pressed.connect(_on_step_pressed)
	stop_btn.pressed.connect(_on_stop_pressed)
	zoom_in_btn.pressed.connect(_on_zoom_in)
	zoom_out_btn.pressed.connect(_on_zoom_out)
	reset_view_btn.pressed.connect(_on_reset_view)

func _populate_dropdowns():
	# Populate scenarios
	scenario_dropdown.clear()
	scenario_dropdown.add_item("Tier 0: Baseline")
	scenario_dropdown.add_item("Tier 1: Moderate")
	scenario_dropdown.add_item("Tier 2: Advanced")
	scenario_dropdown.add_item("Tier 3: Expert")
	
	# Populate agent models
	agent_dropdown.clear()
	agent_dropdown.add_item("GPT-4o")
	agent_dropdown.add_item("Claude Sonnet")
	agent_dropdown.add_item("Gemini Flash")
	agent_dropdown.add_item("Greedy Bot (Baseline)")

func _update_button_states():
	start_btn.disabled = is_running
	step_btn.disabled = is_running
	stop_btn.disabled = !is_running

func _on_start_pressed():
	is_running = true
	_update_button_states()
	
	var config = {
		"scenario": scenario_dropdown.get_item_text(scenario_dropdown.selected),
		"agent": agent_dropdown.get_item_text(agent_dropdown.selected),
		"seed": int(seed_input.value),
		"speed": speed_slider.value
	}
	
	ApiClient.start_simulation(config)
	WebSocketClient.connect_to_server()

func _on_step_pressed():
	# Request single tick advance
	WebSocketClient.send_data({"action": "step"})

func _on_stop_pressed():
	is_running = false
	_update_button_states()
	WebSocketClient.disconnect_from_server()

func _on_simulation_tick(data: Dictionary):
	# Update statistics
	tick_label.text = "Tick: " + str(data.get("tick", 0))
	
	var metrics = data.get("metrics", {})
	revenue_label.text = "Revenue: $%.2f" % metrics.get("total_revenue", 0.0)
	inventory_label.text = "Inventory: %d units" % metrics.get("inventory_count", 0)
	orders_label.text = "Orders: %d pending" % metrics.get("pending_orders", 0)
	
	# Update visualization
	_update_agents(data.get("agents", []))
	_update_heatmap(data.get("heatmap", []))

func _update_agents(agents: Array):
	# Clear existing agent visuals
	for child in agent_container.get_children():
		child.queue_free()
	
	# Draw agent positions
	for agent_data in agents:
		var agent_visual = _create_agent_visual(agent_data)
		agent_container.add_child(agent_visual)

func _create_agent_visual(agent_data: Dictionary) -> Node2D:
	var visual = Node2D.new()
	
	var circle = Polygon2D.new()
	var points: PackedVector2Array = []
	var radius = 15.0
	for i in range(32):
		var angle = i * TAU / 32.0
		points.append(Vector2(cos(angle), sin(angle)) * radius)
	circle.polygon = points
	circle.color = Color.CYAN
	
	visual.add_child(circle)
	visual.position = Vector2(agent_data.get("x", 0), agent_data.get("y", 0))
	
	return visual

func _update_heatmap(_heatmap_data: Array):
	# Future: Render decision heatmap overlay
	pass

# Zoom controls
func _on_zoom_in():
	current_zoom = clamp(current_zoom + ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)
	camera.zoom = Vector2(current_zoom, current_zoom)

func _on_zoom_out():
	current_zoom = clamp(current_zoom - ZOOM_STEP, MIN_ZOOM, MAX_ZOOM)
	camera.zoom = Vector2(current_zoom, current_zoom)

func _on_reset_view():
	current_zoom = 1.0
	camera.zoom = Vector2.ONE
	camera.position = Vector2(400, 300)
