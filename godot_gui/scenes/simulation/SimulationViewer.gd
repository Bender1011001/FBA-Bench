extends Control

## SimulationViewer.gd
## Main simulation visualization controller with agent introspection

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

# Overlay UI
@onready var agent_inspector = $HSplitContainer/CenterPanel/OverlayUI/AgentInspector
@onready var zoom_in_btn = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls/ZoomIn
@onready var zoom_out_btn = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls/ZoomOut
@onready var reset_view_btn = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls/ResetView
@onready var left_vbox = $HSplitContainer/LeftPanel/VBoxContainer

var is_running: bool = false
var current_zoom: float = 1.0
const ZOOM_STEP = 0.1
const MIN_ZOOM = 0.25
const MAX_ZOOM = 4.0

# Simulation state
var pending_simulation_id: String = ""
var current_websocket_topic: String = ""

# Charts
var revenue_chart: Control
var profit_chart: Control

func _ready():
	_connect_signals()
	_update_button_states()
	_fetch_initial_data()
	_setup_charts()
	_draw_warehouse_grid()
	
	# Add fallback items if dropdowns are empty
	if scenario_dropdown.item_count == 0:
		scenario_dropdown.add_item("tier1_basic")
		scenario_dropdown.add_item("tier2_advanced")
	if agent_dropdown.item_count == 0:
		agent_dropdown.add_item("gpt-4o")
		agent_dropdown.add_item("claude-3-opus")
	
	SimulationState.simulation_updated.connect(_on_simulation_tick)
	agent_inspector.close_requested.connect(_on_inspector_closed)
	# Initialize inspector hidden
	agent_inspector.visible = false
	print("[SimViewer] Ready - Dropdowns populated")

func _draw_warehouse_grid():
	# Draw a simple grid background in the warehouse
	var grid = Node2D.new()
	grid.name = "WarehouseGrid"
	warehouse_container.add_child(grid)
	
	# Draw grid lines
	for x in range(0, 801, 50):
		var line = Line2D.new()
		line.points = [Vector2(x, 0), Vector2(x, 600)]
		line.default_color = Color(0.2, 0.2, 0.3, 0.5)
		line.width = 1
		grid.add_child(line)
	for y in range(0, 601, 50):
		var line = Line2D.new()
		line.points = [Vector2(0, y), Vector2(800, y)]
		line.default_color = Color(0.2, 0.2, 0.3, 0.5)
		line.width = 1
		grid.add_child(line)
	
	# Add warehouse zones placeholder
	var zone_labels = ["RECEIVING", "STORAGE", "PACKING", "SHIPPING"]
	var zone_colors = [Color.DARK_BLUE, Color.DARK_GREEN, Color.DARK_ORANGE, Color.DARK_RED]
	for i in range(4):
		var zone = ColorRect.new()
		zone.color = zone_colors[i]
		zone.color.a = 0.2
		zone.size = Vector2(180, 280)
		zone.position = Vector2(20 + i * 195, 160)
		grid.add_child(zone)
		
		var label = Label.new()
		label.text = zone_labels[i]
		label.position = Vector2(20 + i * 195 + 50, 140)
		label.add_theme_font_size_override("font_size", 14)
		grid.add_child(label)

func _setup_charts():
	var chart_script = load("res://scenes/simulation/PerformanceChart.gd")
	
	revenue_chart = Control.new()
	revenue_chart.set_script(chart_script)
	revenue_chart.custom_minimum_size = Vector2(0, 80)
	revenue_chart.label = "Revenue"
	revenue_chart.line_color = Color.CYAN
	left_vbox.add_child(revenue_chart)
	
	profit_chart = Control.new()
	profit_chart.set_script(chart_script)
	profit_chart.custom_minimum_size = Vector2(0, 80)
	profit_chart.label = "Inventory"
	profit_chart.line_color = Color.GREEN_YELLOW
	left_vbox.add_child(profit_chart)

func _fetch_initial_data():
	ApiClient.get_scenarios()
	ApiClient.get_models()

func _connect_signals():
	start_btn.pressed.connect(_on_start_pressed)
	step_btn.pressed.connect(_on_step_pressed)
	stop_btn.pressed.connect(_on_stop_pressed)
	zoom_in_btn.pressed.connect(_on_zoom_in)
	zoom_out_btn.pressed.connect(_on_zoom_out)
	reset_view_btn.pressed.connect(_on_reset_view)
	
	ApiClient.request_completed.connect(_on_api_request_completed)
	ApiClient.request_failed.connect(_on_api_request_failed)

func _on_api_request_completed(endpoint: String, response: Variant):
	if endpoint == "/api/v1/scenarios":
		_populate_scenarios(response)
	elif endpoint == "/api/v1/llm/models":
		_populate_models(response)
	elif endpoint == "/api/v1/simulation":
		# Step 1: Simulation created
		if response is Dictionary and response.has("id"):
			pending_simulation_id = response["id"]
			current_websocket_topic = response.get("websocket_topic", "")
			print("[SimViewer] Simulation created: ", pending_simulation_id)
			ApiClient.start_simulation_by_id(pending_simulation_id)
		else:
			_reset_run_state()
	elif endpoint.ends_with("/start"):
		# Step 2: Simulation started, trigger run
		print("[SimViewer] Simulation started, triggering run...")
		ApiClient.run_simulation_by_id(pending_simulation_id)
	elif endpoint.ends_with("/run"):
		# Step 3: Run started, connect WebSocket
		print("[SimViewer] Run active, subscribing to WS topic: ", current_websocket_topic)
		WebSocketClient.connect_to_server()
		WebSocketClient.subscribe_topic(current_websocket_topic)

func _on_api_request_failed(endpoint: String, error: String):
	print("[SimViewer] API Error: ", endpoint, " - ", error)
	if endpoint == "/api/v1/simulation" or endpoint.ends_with("/start"):
		_reset_run_state()

func _reset_run_state():
	is_running = false
	pending_simulation_id = ""
	_update_button_states()

func _populate_scenarios(data: Variant):
	scenario_dropdown.clear()
	if data is Dictionary and data.has("scenarios"):
		for scenario in data["scenarios"]:
			scenario_dropdown.add_item(scenario.get("id", "unknown"))
	elif data is Array:
		for scenario in data:
			if scenario is Dictionary:
				scenario_dropdown.add_item(scenario.get("id", "unknown"))

func _populate_models(data: Variant):
	agent_dropdown.clear()
	if data is Dictionary and data.has("models"):
		for model in data["models"]:
			agent_dropdown.add_item(model.get("id", "unknown"))

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
	
	# Step 1: Create simulation
	ApiClient.create_simulation(config)

func _on_step_pressed():
	WebSocketClient.send_data({"action": "step"})

func _on_stop_pressed():
	is_running = false
	_update_button_states()
	WebSocketClient.disconnect_from_server()

func _on_simulation_tick(data: Dictionary):
	var tick = data.get("tick", 0)
	var metrics = data.get("metrics", {})
	
	tick_label.text = "Tick: %d" % tick
	revenue_label.text = "Revenue: $%.2f" % metrics.get("total_revenue", 0.0)
	inventory_label.text = "Inventory: %d units" % metrics.get("inventory_count", 0)
	orders_label.text = "Orders: %d pending" % metrics.get("pending_orders", 0)
	
	# Update Charts
	if revenue_chart:
		revenue_chart.add_point(metrics.get("total_revenue", 0.0))
	if profit_chart:
		profit_chart.add_point(float(metrics.get("inventory_count", 0)))
		
	# Update visualization
	_update_agents(data.get("agents", []))
	_update_heatmap(data.get("heatmap", []))
	
	# If inspector is open, update its data if it matches the current agent
	if agent_inspector.visible:
		# Find the agent data for the currently inspected agent
		var current_id = agent_inspector.current_agent_id
		for agent in data.get("agents", []):
			if agent.get("id") == current_id:
				agent_inspector.update_agent_data(agent)
				break

func _update_agents(agents: Array):
	# Clear existing agent visuals
	for child in agent_container.get_children():
		child.queue_free()
	
	# Draw agent positions
	for agent_data in agents:
		var agent_visual = _create_agent_visual(agent_data)
		agent_container.add_child(agent_visual)

func _update_heatmap(heatmap_data: Array):
	if heatmap_data.is_empty():
		return
		
	# Simple heatmap implementation: clear and redraw
	heatmap_overlay.queue_redraw()
	heatmap_overlay.set_meta("data", heatmap_data)
	if not heatmap_overlay.is_connected("draw", _on_heatmap_draw):
		heatmap_overlay.draw.connect(_on_heatmap_draw)

func _on_heatmap_draw():
	var data = heatmap_overlay.get_meta("data", [])
	for point in data:
		var x = point.get("x", 0)
		var y = point.get("y", 0)
		var value = point.get("value", 0.0)
		var size = point.get("size", 20.0)
		
		# Map value to color (0.0=translucent, 1.0=bright orange)
		var color = Color(1.0, 0.5, 0.0, value * 0.5)
		heatmap_overlay.draw_rect(Rect2(Vector2(x - size/2, y - size/2), Vector2(size, size)), color)

func _create_agent_visual(agent_data: Dictionary) -> Node2D:
	var visual = Node2D.new()
	
	# Body
	var circle = Polygon2D.new()
	var points: PackedVector2Array = []
	var radius = 12.0
	for i in range(32):
		var angle = i * TAU / 32.0
		points.append(Vector2(cos(angle), sin(angle)) * radius)
	circle.polygon = points
	
	# Multi-colored agents based on role
	var role = agent_data.get("role", "").to_lower()
	if "strategic" in role: circle.color = Color.CYAN
	elif "analyst" in role: circle.color = Color.GREEN_YELLOW
	elif "logistics" in role: circle.color = Color.ORANGE
	else: circle.color = Color.NAVY_BLUE
	
	visual.add_child(circle)
	
	# Glow effect
	var glow = Polygon2D.new()
	var glow_points: PackedVector2Array = []
	for i in range(32):
		var angle = i * TAU / 32.0
		glow_points.append(Vector2(cos(angle), sin(angle)) * (radius + 4))
	glow.polygon = glow_points
	glow.color = circle.color
	glow.color.a = 0.2
	visual.add_child(glow)
	
	# ID Label
	var label = Label.new()
	label.text = agent_data.get("id", "?")
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.position = Vector2(-50, radius + 2)
	label.custom_minimum_size = Vector2(100, 0)
	visual.add_child(label)
	
	# Click area
	var btn = Button.new()
	btn.flat = true
	btn.custom_minimum_size = Vector2(radius * 2, radius * 2)
	btn.position = Vector2(-radius, -radius)
	btn.pressed.connect(func(): _on_agent_clicked(agent_data))
	visual.add_child(btn)
	
	visual.position = Vector2(agent_data.get("x", 0), agent_data.get("y", 0))
	return visual

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

func _on_inspector_closed():
	agent_inspector.visible = false

func _on_agent_clicked(agent_data: Dictionary):
	agent_inspector.visible = true
	agent_inspector.update_agent_data(agent_data)
