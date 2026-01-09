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
	
	# Apply premium theme
	var theme = load("res://UITheme.tres")
	if theme:
		self.theme = theme
		$Background.color = Color("#0f172a") # Ensure background matches theme concept

	
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
	
	# Create dynamic container for competitors if not present
	if not warehouse_container.has_node("CompetitorContainer"):
		var comp_cont = Node2D.new()
		comp_cont.name = "CompetitorContainer"
		warehouse_container.add_child(comp_cont)
		
	print("[SimViewer] Ready - Dropdowns populated")

func _draw_warehouse_grid():
	# Draw a "Cyberpunk Blueprint" grid
	var grid = Node2D.new()
	grid.name = "WarehouseGrid"
	warehouse_container.add_child(grid)
	
	# Background tint (deep technical blue)
	var bg_tint = ColorRect.new()
	bg_tint.color = Color(0.05, 0.08, 0.15, 0.3)
	bg_tint.size = Vector2(800, 600)
	grid.add_child(bg_tint)
	
	# Minor grid lines (every 25px, faint)
	for x in range(0, 801, 25):
		var line = Line2D.new()
		line.points = [Vector2(x, 0), Vector2(x, 600)]
		line.default_color = Color(0.2, 0.3, 0.4, 0.1) # Very faint blue
		line.width = 1
		grid.add_child(line)
	for y in range(0, 601, 25):
		var line = Line2D.new()
		line.points = [Vector2(0, y), Vector2(800, y)]
		line.default_color = Color(0.2, 0.3, 0.4, 0.1)
		line.width = 1
		grid.add_child(line)

	# Major grid lines (every 100px, brighter)
	for x in range(0, 801, 100):
		var line = Line2D.new()
		line.points = [Vector2(x, 0), Vector2(x, 600)]
		line.default_color = Color(0.3, 0.5, 0.7, 0.2)
		line.width = 1
		grid.add_child(line)
	for y in range(0, 601, 100):
		var line = Line2D.new()
		line.points = [Vector2(0, y), Vector2(800, y)]
		line.default_color = Color(0.3, 0.5, 0.7, 0.2)
		line.width = 1
		grid.add_child(line)
	
	# Warehouse Zones - Technical Look
	var zone_configs = [
		{"name": "RECEIVING", "col": Color(0.2, 0.6, 1.0), "pos": Vector2(20, 160)},
		{"name": "STORAGE",   "col": Color(0.2, 0.8, 0.4), "pos": Vector2(215, 160)},
		{"name": "PACKING",   "col": Color(0.9, 0.6, 0.2), "pos": Vector2(410, 160)},
		{"name": "SHIPPING",  "col": Color(1.0, 0.3, 0.3), "pos": Vector2(605, 160)}
	]
	
	for z in zone_configs:
		var zone_box = ReferenceRect.new() # Hollow rect with border
		zone_box.border_color = z.col
		zone_box.border_width = 1.5
		zone_box.editor_only = false # Ensure visible in game
		zone_box.size = Vector2(180, 280)
		zone_box.position = z.pos
		grid.add_child(zone_box)
		
		# Glow effect (color rect with low alpha)
		var glow = ColorRect.new()
		glow.color = z.col
		glow.color.a = 0.05
		glow.size = zone_box.size
		glow.position = z.pos
		grid.add_child(glow)
		
		var label = Label.new()
		label.text = z.name
		label.position = Vector2(z.pos.x, z.pos.y - 25)
		label.size = Vector2(180, 25)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.add_theme_color_override("font_color", z.col)
		label.add_theme_font_size_override("font_size", 12)
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
	_update_competitors(data.get("competitors", []))
	_update_heatmap(data.get("heatmap", []))
	
	# If inspector is open, update its data if it matches the current agent
	if agent_inspector.visible:
		# Find the agent data for the currently inspected agent
		var current_id = agent_inspector.current_agent_id
		for agent in data.get("agents", []):
			if agent.get("id") == current_id:
				agent_inspector.update_agent_data(agent)
				break

func _update_competitors(competitors: Array):
	var comp_container = warehouse_container.get_node("CompetitorContainer")
	var current_asins = {}
	
	# Layout constants
	var start_x = 50
	var start_y = 50
	var spacing_x = 120
	
	var idx = 0
	for comp_data in competitors:
		var asin = comp_data.get("asin", "")
		if asin == "": continue
		
		current_asins[asin] = true
		var comp_node = comp_container.get_node_or_null(asin)
		
		# Determine visual state
		var inventory = int(comp_data.get("inventory", 0))
		var is_oos = bool(comp_data.get("is_out_of_stock", false))
		var price = comp_data.get("price", "?.??")
		
		if not comp_node:
			comp_node = _create_competitor_visual(asin)
			comp_node.name = asin
			comp_container.add_child(comp_node)
			# Initial placement
			comp_node.position = Vector2(start_x + (idx * spacing_x), start_y)
		
		# Update Label
		var lbl = comp_node.get_node("Label")
		lbl.text = "%s\n$%s" % [asin, price]
		
		# Update Inventory Bar / OOS Status
		var inv_bar = comp_node.get_node("InventoryBar")
		var inv_fill = inv_bar.get_node("Fill")
		var status_lbl = comp_node.get_node("StatusLabel")
		
		if is_oos:
			comp_node.modulate = Color.DIM_GRAY # Fade out OOS competitors
			status_lbl.text = "SOLD OUT"
			status_lbl.modulate = Color(1.0, 0.2, 0.2) # Red text
			inv_fill.scale.x = 0
		else:
			comp_node.modulate = Color.WHITE
			status_lbl.text = "Inv: %d" % inventory
			status_lbl.modulate = Color.WHITE
			# Heuristic: Max inventory 5000 for bar scale
			var pct = clamp(float(inventory) / 5000.0, 0.0, 1.0)
			inv_fill.scale.x = pct
			
		idx += 1
	
	# Cleanup removed competitors
	for child in comp_container.get_children():
		if not current_asins.has(child.name):
			child.queue_free()

func _create_competitor_visual(asin: String) -> Node2D:
	var visual = Node2D.new()
	
	# Shape: Inverted Red Triangle (Enemy)
	var poly = Polygon2D.new()
	poly.polygon = PackedVector2Array([
		Vector2(-15, -15), 
		Vector2(15, -15), 
		Vector2(0, 15)
	])
	poly.color = Color(0.9, 0.3, 0.3) # Hostile Red
	visual.add_child(poly)
	
	# ASIN Label
	var label = Label.new()
	label.name = "Label"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.position = Vector2(-40, -45)
	label.custom_minimum_size = Vector2(80, 0)
	visual.add_child(label)
	
	# Status Label (Inventory Count or SOLD OUT)
	var status = Label.new()
	status.name = "StatusLabel"
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status.add_theme_font_size_override("font_size", 12)
	status.add_theme_color_override("font_color", Color.WHITE)
	status.position = Vector2(-40, 20)
	status.custom_minimum_size = Vector2(80, 0)
	visual.add_child(status)
	
	# Inventory Bar Background
	var bar_bg = ColorRect.new()
	bar_bg.name = "InventoryBar"
	bar_bg.color = Color(0.2, 0.2, 0.2)
	bar_bg.size = Vector2(60, 6)
	bar_bg.position = Vector2(-30, 38)
	visual.add_child(bar_bg)
	
	# Inventory Bar Fill
	var bar_fill = ColorRect.new()
	bar_fill.name = "Fill"
	bar_fill.color = Color.GREEN
	bar_fill.size = Vector2(60, 6)
	bar_bg.add_child(bar_fill)
	
	return visual

func _update_agents(agents: Array):
	var current_agent_ids = {}
	
	for agent_data in agents:
		# Get agent ID, ensuring it's a string
		var raw_id = agent_data.get("id", "")
		if str(raw_id) == "":
			continue
			
		var agent_id = str(raw_id)
		current_agent_ids[agent_id] = true
		
		var target_pos = Vector2(agent_data.get("x", 0), agent_data.get("y", 0))
		var agent_node = agent_container.get_node_or_null(agent_id)
		
		if agent_node:
			# Agent exists: Smoothly interpolate to new position
			# First, kill any active tween on this agent to prevent conflicts
			if agent_node.has_meta("movement_tween"):
				var old_tween = agent_node.get_meta("movement_tween")
				if old_tween and old_tween.is_valid():
					old_tween.kill()
			
			var tween = create_tween()
			tween.tween_property(agent_node, "position", target_pos, 0.5).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
			agent_node.set_meta("movement_tween", tween)
			
			# Update visual data (in case role/color changed, though unlikely)
			# If you want to update other properties dynamically, do it here.
			
		else:
			# New agent: Create and place immediately
			var new_agent = _create_agent_visual(agent_data)
			new_agent.name = agent_id
			agent_container.add_child(new_agent)
			# Ensure it starts at the correct position
			new_agent.position = target_pos

	# Cleanup: Remove agents that are no longer in the simulation
	for child in agent_container.get_children():
		if not current_agent_ids.has(child.name):
			# Use queue_free to safely remove
			child.queue_free()

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
	
	# High-tech Agent Visual
	var radius = 14.0
	
	# Determine color based on role
	var role = agent_data.get("role", "").to_lower()
	var base_color = Color.CYAN
	if "strategic" in role: base_color = Color("#38bdf8") # Sky blue
	elif "analyst" in role: base_color = Color("#a3e635") # Lime
	elif "logistics" in role: base_color = Color("#fb923c") # Orange
	else: base_color = Color("#818cf8") # Indigo
	
	# 1. Pulsing Outer Ring (Animation handled by tween/shader usually, simple implementation here)
	var outer_ring = Line2D.new()
	var ring_points = []
	for i in range(33):
		var angle = i * TAU / 32.0
		ring_points.append(Vector2(cos(angle), sin(angle)) * (radius + 4))
	outer_ring.points = PackedVector2Array(ring_points)
	outer_ring.default_color = base_color
	outer_ring.default_color.a = 0.4
	outer_ring.width = 1.5
	visual.add_child(outer_ring)
	
	# 2. Main Body Hexagon (Tech look) using Circle logic for simplicity but sharper
	var body = Polygon2D.new()
	var body_points = []
	for i in range(6): # Hexagon
		var angle = i * TAU / 6.0
		body_points.append(Vector2(cos(angle), sin(angle)) * radius)
	body.polygon = PackedVector2Array(body_points)
	body.color = base_color
	body.color.a = 0.2
	visual.add_child(body)
	
	# 3. Inner Core (Solid)
	var core = Polygon2D.new()
	var core_points = []
	for i in range(6):
		var angle = i * TAU / 6.0
		core_points.append(Vector2(cos(angle), sin(angle)) * (radius * 0.4))
	core.polygon = PackedVector2Array(core_points)
	core.color = base_color
	visual.add_child(core)

	# 4. Animated "Scan" Line (Rotator)
	var scanner = Line2D.new()
	scanner.points = PackedVector2Array([Vector2.ZERO, Vector2(radius + 2, 0)])
	scanner.default_color = Color.WHITE
	scanner.default_color.a = 0.6
	scanner.width = 1.0
	visual.add_child(scanner)
	
	# Rotate the scanner forever
	var tween = visual.create_tween().set_loops()
	tween.tween_property(scanner, "rotation", TAU, 2.0).from(0.0)

	# 5. ID Label (Floating)
	var label = Label.new()
	label.text = agent_data.get("id", "?")
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", Color.WHITE)
	# Add background for readability
	var lbl_style = StyleBoxFlat.new()
	lbl_style.bg_color = Color(0,0,0,0.5)
	lbl_style.corner_radius_top_left = 3
	lbl_style.corner_radius_top_right = 3
	label.add_theme_stylebox_override("normal", lbl_style)
	
	label.position = Vector2(-50, radius + 6)
	label.custom_minimum_size = Vector2(100, 0)
	visual.add_child(label)
	
	# Click area
	var btn = Button.new()
	btn.flat = true
	btn.custom_minimum_size = Vector2(radius * 3, radius * 3)
	btn.position = Vector2(-radius * 1.5, -radius * 1.5)
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
