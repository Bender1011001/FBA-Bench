extends Control

## SimulationViewer.gd
## Main simulation visualization controller with agent introspection

# UI References
@onready var scenario_dropdown = $HSplitContainer/LeftPanel/VBoxContainer/ScenarioDropdown
@onready var agent_dropdown = $HSplitContainer/LeftPanel/VBoxContainer/AgentDropdown
@onready var seed_input = $HSplitContainer/LeftPanel/VBoxContainer/SeedInput
@onready var max_ticks_input = $HSplitContainer/LeftPanel/VBoxContainer/MaxTicksInput
@onready var speed_slider = $HSplitContainer/LeftPanel/VBoxContainer/SpeedSlider
@onready var cinematic_toggle = $HSplitContainer/LeftPanel/VBoxContainer/CinematicToggle
@onready var start_btn = $HSplitContainer/LeftPanel/VBoxContainer/ButtonContainer/StartButton
@onready var step_btn = $HSplitContainer/LeftPanel/VBoxContainer/ButtonContainer/StepButton
@onready var stop_btn = $HSplitContainer/LeftPanel/VBoxContainer/ButtonContainer/StopButton

# Scene structure helpers (for cinematic mode)
@onready var split_container = $HSplitContainer
@onready var left_panel = $HSplitContainer/LeftPanel
@onready var overlay_ui = $HSplitContainer/CenterPanel/OverlayUI
@onready var zoom_controls = $HSplitContainer/CenterPanel/OverlayUI/ZoomControls

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

# Cinematic observer visuals
var products_container: Node2D
var effects_container: Node2D
var event_feed: RichTextLabel
var cinematic_hud: Control
var cinematic_hud_metrics: Label
var cinematic_hud_hint: Label
var cinematic_feed: RichTextLabel
var cinematic_feed_panel: Control
var end_card: PanelContainer
var end_card_body: RichTextLabel

var zone_rects: Dictionary = {}
var zone_glows: Dictionary = {}
var zone_base_colors: Dictionary = {}

var product_baselines: Dictionary = {}
var last_product_inventory: Dictionary = {}
var last_product_price: Dictionary = {}

var feed_lines: Array[String] = []
var rng := RandomNumberGenerator.new()

var last_total_revenue: float = 0.0
var last_total_units_sold: int = 0
var last_tick_seen: int = -1
var cinematic_mode: bool = false
var _split_offset_prev: int = 250
var _main_top_prev_visible: bool = true
var _main_bottom_prev_visible: bool = true
var _cinematic_last_focus_tick: int = -9999
var low_stock_warned: Dictionary = {}

# End-card highlight tracking (computed incrementally so we don't need full tick history).
var best_rev_tick: int = -1
var best_rev_delta: float = 0.0
var best_units_tick: int = -1
var best_units_delta: int = 0

# Demo automation (for screen recordings)
var demo_autostart: bool = false
var demo_autoquit: bool = false
var demo_done_file: String = ""
var demo_start_delay_s: float = 3.0
var demo_end_hold_s: float = 4.0

func _env_bool(name: String, default_value: bool = false) -> bool:
	var v = OS.get_environment(name)
	if v == "":
		return default_value
	v = v.strip_edges().to_lower()
	return v == "1" or v == "true" or v == "yes" or v == "y" or v == "on"

func _env_int(name: String, default_value: int) -> int:
	var v = OS.get_environment(name)
	if v == "":
		return default_value
	var n = int(v)
	return n

func _env_float(name: String, default_value: float) -> float:
	var v = OS.get_environment(name)
	if v == "":
		return default_value
	var n = float(v)
	return n

func _select_option_by_text(opt: OptionButton, label: String) -> void:
	if opt == null:
		return
	var target = str(label).strip_edges()
	if target == "":
		return
	for i in range(opt.item_count):
		if str(opt.get_item_text(i)) == target:
			opt.select(i)
			return

func _configure_demo_from_env() -> void:
	demo_autostart = _env_bool("FBA_BENCH_DEMO_AUTOSTART", false)
	if not demo_autostart:
		return

	demo_autoquit = _env_bool("FBA_BENCH_DEMO_AUTOQUIT", true)
	demo_done_file = OS.get_environment("FBA_BENCH_DEMO_DONE_FILE")
	demo_start_delay_s = _env_float("FBA_BENCH_DEMO_START_DELAY_SECONDS", 3.0)
	demo_end_hold_s = _env_float("FBA_BENCH_DEMO_ENDCARD_HOLD_SECONDS", 4.0)

	_select_option_by_text(scenario_dropdown, OS.get_environment("FBA_BENCH_DEMO_SCENARIO"))
	_select_option_by_text(agent_dropdown, OS.get_environment("FBA_BENCH_DEMO_AGENT"))

	seed_input.value = float(_env_int("FBA_BENCH_DEMO_SEED", int(seed_input.value)))
	max_ticks_input.value = float(_env_int("FBA_BENCH_DEMO_MAX_TICKS", int(max_ticks_input.value)))
	speed_slider.value = _env_float("FBA_BENCH_DEMO_SPEED", float(speed_slider.value))

	if _env_bool("FBA_BENCH_DEMO_CINEMATIC", true):
		cinematic_toggle.button_pressed = true
		_set_cinematic_mode(true)

	if _env_bool("FBA_BENCH_DEMO_FULLSCREEN", false):
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)

	# Delay start so recording can begin cleanly.
	var delay = max(0.1, float(demo_start_delay_s))
	get_tree().create_timer(delay).timeout.connect(func():
		if not is_running:
			_on_start_pressed()
	)

func _ready():
	_connect_signals()
	_update_button_states()
	rng.randomize()
	_fetch_initial_data()
	_setup_charts()
	_setup_event_feed()
	_setup_end_card()
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
	SimulationState.simulation_finished.connect(_on_simulation_finished)
	agent_inspector.close_requested.connect(_on_inspector_closed)
	# Initialize inspector hidden
	agent_inspector.visible = false
	# Observer-only: STEP isn't implemented end-to-end; hide it to avoid confusion.
	step_btn.visible = false
	
	# Create dynamic container for competitors if not present
	if not warehouse_container.has_node("CompetitorContainer"):
		var comp_cont = Node2D.new()
		comp_cont.name = "CompetitorContainer"
		warehouse_container.add_child(comp_cont)

	# Containers for products + FX (used for observer-mode visuals)
	if not warehouse_container.has_node("ProductsContainer"):
		var prod_cont = Node2D.new()
		prod_cont.name = "ProductsContainer"
		warehouse_container.add_child(prod_cont)
	products_container = warehouse_container.get_node("ProductsContainer") as Node2D

	if not warehouse_container.has_node("EffectsContainer"):
		var fx_cont = Node2D.new()
		fx_cont.name = "EffectsContainer"
		warehouse_container.add_child(fx_cont)
	effects_container = warehouse_container.get_node("EffectsContainer") as Node2D

	# Start in non-cinematic mode but keep toggle state consistent
	_set_cinematic_mode(bool(cinematic_toggle.button_pressed))
	_configure_demo_from_env()
		
	print("[SimViewer] Ready - Dropdowns populated")

func _draw_warehouse_grid():
	zone_rects.clear()
	zone_glows.clear()
	zone_base_colors.clear()

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
		var zone_name = str(z.get("name", ""))
		var zone_col = z.get("col", Color.WHITE)
		var zone_pos = z.get("pos", Vector2.ZERO)

		var zone_box = ReferenceRect.new() # Hollow rect with border
		zone_box.border_color = zone_col
		zone_box.border_width = 1.5
		zone_box.editor_only = false # Ensure visible in game
		zone_box.size = Vector2(180, 280)
		zone_box.position = zone_pos
		grid.add_child(zone_box)
		
		# Glow effect (color rect with low alpha)
		var glow = ColorRect.new()
		var gc = zone_col
		gc.a = 0.05
		glow.color = gc
		glow.size = zone_box.size
		glow.position = zone_pos
		grid.add_child(glow)

		if zone_name != "":
			zone_rects[zone_name] = Rect2(zone_pos, zone_box.size)
			zone_glows[zone_name] = glow
			zone_base_colors[zone_name] = zone_col
		
		var label = Label.new()
		label.text = zone_name
		label.position = Vector2(zone_pos.x, zone_pos.y - 25)
		label.size = Vector2(180, 25)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.add_theme_color_override("font_color", zone_col)
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

func _setup_event_feed():
	# Lightweight live narration for screen recordings.
	var header = Label.new()
	header.text = "LIVE FEED"
	header.add_theme_font_size_override("font_size", 12)
	header.add_theme_color_override("font_color", Color("#3b82f6"))
	left_vbox.add_child(header)

	event_feed = RichTextLabel.new()
	event_feed.bbcode_enabled = true
	event_feed.scroll_active = false
	event_feed.custom_minimum_size = Vector2(0, 170)
	event_feed.text = "[color=gray]Waiting for tick data...[/color]"
	left_vbox.add_child(event_feed)

func _setup_end_card():
	# End-of-run summary card shown when we receive simulation_end.
	if end_card != null:
		return
	if overlay_ui == null:
		return

	end_card = PanelContainer.new()
	end_card.visible = false
	end_card.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	# Center-anchored controls need explicit offsets to get a size.
	end_card.offset_left = -280
	end_card.offset_top = -160
	end_card.offset_right = 280
	end_card.offset_bottom = 160
	overlay_ui.add_child(end_card)

	var margin = MarginContainer.new()
	margin.theme_override_constants.margin_left = 16
	margin.theme_override_constants.margin_right = 16
	margin.theme_override_constants.margin_top = 16
	margin.theme_override_constants.margin_bottom = 16
	end_card.add_child(margin)

	var v = VBoxContainer.new()
	v.theme_override_constants.separation = 10
	margin.add_child(v)

	var title = Label.new()
	title.text = "RUN COMPLETE"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color("#a3e635"))
	v.add_child(title)

	end_card_body = RichTextLabel.new()
	end_card_body.bbcode_enabled = true
	end_card_body.scroll_active = false
	end_card_body.custom_minimum_size = Vector2(520, 220)
	end_card_body.text = ""
	v.add_child(end_card_body)

	var btn_row = HBoxContainer.new()
	btn_row.alignment = BoxContainer.ALIGNMENT_CENTER
	btn_row.theme_override_constants.separation = 10
	v.add_child(btn_row)

	var close_btn = Button.new()
	close_btn.text = "Close"
	close_btn.pressed.connect(func():
		end_card.visible = false
	)
	btn_row.add_child(close_btn)

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
	cinematic_toggle.toggled.connect(_on_cinematic_toggled)
	
	ApiClient.request_completed.connect(_on_api_request_completed)
	ApiClient.request_failed.connect(_on_api_request_failed)

func _unhandled_input(event):
	# Keyboard toggles for filming.
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_C:
			# Toggle cinematic mode without needing UI.
			cinematic_toggle.button_pressed = !cinematic_toggle.button_pressed
			_set_cinematic_mode(bool(cinematic_toggle.button_pressed))

func _on_cinematic_toggled(enabled: bool):
	_set_cinematic_mode(enabled)

func _set_cinematic_mode(enabled: bool) -> void:
	if enabled == cinematic_mode:
		return
	cinematic_mode = enabled
	_ensure_cinematic_hud()

	# Collapse controls to maximize viewport.
	if split_container != null:
		if enabled:
			_split_offset_prev = int(split_container.split_offset)
			split_container.split_offset = 0
		else:
			split_container.split_offset = _split_offset_prev

	if left_panel != null:
		left_panel.visible = !enabled
	if zoom_controls != null:
		zoom_controls.visible = !enabled
	if agent_inspector != null and enabled:
		agent_inspector.visible = false

	# Hide parent top/bottom bars for clean video framing (best effort).
	var bars = _get_main_bars()
	if bars.has("top"):
		var top = bars["top"]
		if enabled:
			_main_top_prev_visible = bool(top.visible)
			top.visible = false
		else:
			top.visible = _main_top_prev_visible
	if bars.has("bottom"):
		var bottom = bars["bottom"]
		if enabled:
			_main_bottom_prev_visible = bool(bottom.visible)
			bottom.visible = false
		else:
			bottom.visible = _main_bottom_prev_visible

	if cinematic_hud != null:
		cinematic_hud.visible = enabled
	if cinematic_feed_panel != null:
		cinematic_feed_panel.visible = enabled

func _get_main_bars() -> Dictionary:
	var out: Dictionary = {}
	var root = get_tree().get_root()
	if root == null:
		return out
	var main = root.get_node_or_null("Main")
	if main == null:
		return out
	var top = main.get_node_or_null("VBoxContainer/TopBar")
	var bottom = main.get_node_or_null("VBoxContainer/BottomBar")
	if top != null:
		out["top"] = top
	if bottom != null:
		out["bottom"] = bottom
	return out

func _ensure_cinematic_hud():
	if cinematic_hud != null:
		return
	if overlay_ui == null:
		return

	cinematic_hud = PanelContainer.new()
	cinematic_hud.visible = false
	cinematic_hud.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	cinematic_hud.offset_left = 12
	cinematic_hud.offset_top = 12
	cinematic_hud.offset_right = 12 + 280
	cinematic_hud.offset_bottom = 12 + 70
	overlay_ui.add_child(cinematic_hud)

	var hud_margin = MarginContainer.new()
	hud_margin.theme_override_constants.margin_left = 10
	hud_margin.theme_override_constants.margin_right = 10
	hud_margin.theme_override_constants.margin_top = 8
	hud_margin.theme_override_constants.margin_bottom = 8
	cinematic_hud.add_child(hud_margin)

	var v = VBoxContainer.new()
	v.theme_override_constants.separation = 2
	hud_margin.add_child(v)

	cinematic_hud_metrics = Label.new()
	cinematic_hud_metrics.text = "Tick: 0   Revenue: $0.00   Inv: 0"
	cinematic_hud_metrics.add_theme_font_size_override("font_size", 13)
	v.add_child(cinematic_hud_metrics)

	cinematic_hud_hint = Label.new()
	cinematic_hud_hint.text = "Cinematic Mode (press C to exit)"
	cinematic_hud_hint.add_theme_font_size_override("font_size", 11)
	cinematic_hud_hint.add_theme_color_override("font_color", Color(1, 1, 1, 0.65))
	v.add_child(cinematic_hud_hint)

	cinematic_feed_panel = PanelContainer.new()
	cinematic_feed_panel.visible = false
	cinematic_feed_panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	cinematic_feed_panel.offset_left = 12
	cinematic_feed_panel.offset_right = 12 + 430
	cinematic_feed_panel.offset_bottom = -12
	cinematic_feed_panel.offset_top = -12 - 200
	overlay_ui.add_child(cinematic_feed_panel)

	var feed_margin = MarginContainer.new()
	feed_margin.theme_override_constants.margin_left = 10
	feed_margin.theme_override_constants.margin_right = 10
	feed_margin.theme_override_constants.margin_top = 8
	feed_margin.theme_override_constants.margin_bottom = 8
	cinematic_feed_panel.add_child(feed_margin)

	cinematic_feed = RichTextLabel.new()
	cinematic_feed.bbcode_enabled = true
	cinematic_feed.scroll_active = false
	cinematic_feed.fit_content = true
	cinematic_feed.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	feed_margin.add_child(cinematic_feed)

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
	_reset_observer_state()
	if end_card:
		end_card.visible = false
	
	var config = {
		"scenario": scenario_dropdown.get_item_text(scenario_dropdown.selected),
		"agent": agent_dropdown.get_item_text(agent_dropdown.selected),
		"seed": int(seed_input.value),
		"max_ticks": int(max_ticks_input.value),
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
	_reset_observer_state()
	if end_card:
		end_card.visible = false

func _on_simulation_tick(data: Dictionary):
	var tick = int(data.get("tick", 0))
	var metrics = data.get("metrics", {})
	var products = data.get("products", [])
	if not (products is Array):
		products = []
	
	tick_label.text = "Tick: %d" % tick
	revenue_label.text = "Revenue: $%.2f" % metrics.get("total_revenue", 0.0)
	inventory_label.text = "Inventory: %d units" % metrics.get("inventory_count", 0)
	orders_label.text = "Orders: %d pending" % metrics.get("pending_orders", 0)

	if cinematic_hud_metrics:
		cinematic_hud_metrics.text = "T:%d  Rev:$%.2f  P:$%.2f  Inv:%d" % [
			tick,
			float(metrics.get("total_revenue", 0.0)),
			float(metrics.get("total_profit", 0.0)),
			int(metrics.get("inventory_count", 0))
		]
	
	# Update Charts
	if revenue_chart:
		revenue_chart.add_point(metrics.get("total_revenue", 0.0))
	if profit_chart:
		profit_chart.add_point(float(metrics.get("inventory_count", 0)))
		
	# Update visualization
	_update_products(products)
	_process_tick_activity(tick, metrics, products)
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

func _reset_observer_state():
	product_baselines.clear()
	last_product_inventory.clear()
	last_product_price.clear()
	last_total_revenue = 0.0
	last_total_units_sold = 0
	last_tick_seen = -1
	feed_lines.clear()
	low_stock_warned.clear()
	best_rev_tick = -1
	best_rev_delta = 0.0
	best_units_tick = -1
	best_units_delta = 0

	if event_feed:
		event_feed.text = "[color=gray]Waiting for tick data...[/color]"
	if cinematic_feed:
		cinematic_feed.text = "[color=gray]Waiting for tick data...[/color]"

	if products_container:
		for child in products_container.get_children():
			child.queue_free()
	if effects_container:
		for child in effects_container.get_children():
			child.queue_free()

func _update_products(products: Array):
	if products_container == null:
		return
	if products.is_empty():
		return

	# Layout products inside STORAGE zone (bars shrink/grow with inventory).
	var storage_rect = _zone_rect("STORAGE")
	var w = 26.0
	var max_h = storage_rect.size.y - 55.0
	var base_y = storage_rect.position.y + storage_rect.size.y - 15.0
	var left_x = storage_rect.position.x + 18.0
	var right_x = storage_rect.position.x + storage_rect.size.x - 18.0
	var count = max(1, products.size())
	var spacing = (right_x - left_x) / float(max(1, count - 1))

	var idx = 0
	for p in products:
		if not (p is Dictionary):
			continue
		var asin = str(p.get("asin", ""))
		if asin == "":
			continue
		var inv = int(p.get("inventory", 0))

		if not product_baselines.has(asin):
			product_baselines[asin] = max(1, inv)

		var node = products_container.get_node_or_null(asin)
		if node == null:
			node = _create_product_bar(asin, w, max_h)
			node.name = asin
			products_container.add_child(node)

		# Position bars left->right within storage zone.
		var x = left_x + (idx * spacing)
		node.position = Vector2(x, base_y)

		# Scale bar height by inventory vs baseline (cap for restock spikes).
		var baseline = float(product_baselines.get(asin, 1))
		var ratio = clamp(float(inv) / max(1.0, baseline), 0.02, 1.25)
		var bar = node.get_node("Bar") as Polygon2D
		var outline = node.get_node("Outline") as Line2D
		if bar:
			bar.scale = Vector2(1.0, ratio)
		if outline:
			outline.scale = Vector2(1.0, ratio)

		# Label content (price + inv).
		var price = float(p.get("price", 0.0))
		var lbl = node.get_node("Label") as Label
		if lbl:
			lbl.text = "%s\n$%.2f\ninv %d" % [asin, price, inv]

		idx += 1

	# Cleanup: remove bars that are no longer in the payload.
	var keep: Dictionary = {}
	for p2 in products:
		if p2 is Dictionary:
			var a = str(p2.get("asin", ""))
			if a != "":
				keep[a] = true
	for child in products_container.get_children():
		if not keep.has(child.name):
			child.queue_free()

func _create_product_bar(asin: String, width: float, max_height: float) -> Node2D:
	var visual = Node2D.new()
	var c = _color_for_id(asin)

	var bar = Polygon2D.new()
	bar.name = "Bar"
	bar.polygon = PackedVector2Array([
		Vector2(-width / 2.0, 0),
		Vector2(width / 2.0, 0),
		Vector2(width / 2.0, -max_height),
		Vector2(-width / 2.0, -max_height),
	])
	bar.color = c
	bar.color.a = 0.25
	visual.add_child(bar)

	var outline = Line2D.new()
	outline.name = "Outline"
	outline.points = PackedVector2Array([
		Vector2(-width / 2.0, 0),
		Vector2(width / 2.0, 0),
		Vector2(width / 2.0, -max_height),
		Vector2(-width / 2.0, -max_height),
		Vector2(-width / 2.0, 0),
	])
	outline.default_color = c
	outline.default_color.a = 0.85
	outline.width = 1.5
	visual.add_child(outline)

	var label = Label.new()
	label.name = "Label"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.position = Vector2(-55, -max_height - 42)
	label.custom_minimum_size = Vector2(110, 0)
	visual.add_child(label)

	return visual

func _process_tick_activity(tick: int, metrics: Dictionary, products: Array) -> void:
	# Reset if a new run starts.
	if last_tick_seen != -1 and tick < last_tick_seen:
		_reset_observer_state()

	var had_prev = (last_tick_seen != -1)
	var total_revenue = float(metrics.get("total_revenue", 0.0))
	var total_units_sold = int(metrics.get("units_sold", 0))
	var inv_units = int(metrics.get("inventory_count", 0))

	var delta_rev = 0.0
	var delta_units = 0
	if had_prev:
		delta_rev = total_revenue - last_total_revenue
		delta_units = total_units_sold - last_total_units_sold

	last_total_revenue = total_revenue
	last_total_units_sold = total_units_sold
	last_tick_seen = tick

	# Update best-of-run highlights (delta per tick).
	if had_prev:
		if delta_rev > best_rev_delta:
			best_rev_delta = delta_rev
			best_rev_tick = tick
		if delta_units > best_units_delta:
			best_units_delta = delta_units
			best_units_tick = tick

	# Headline line (good for videos).
	var rev_prefix = "+" if delta_rev >= 0.0 else "-"
	var rev_color = "#a3e635" if delta_rev >= 0.0 else "#f87171"
	var units_prefix = "+" if delta_units >= 0 else "-"
	var headline = "T%03d  [color=%s]%s$%.2f[/color]  %s%d units  inv %d" % [
		tick, rev_color, rev_prefix, abs(delta_rev), units_prefix, abs(delta_units), inv_units
	]
	_feed_push(headline)

	# "Shock"-style callouts for recording: big activity spikes.
	if tick > 0 and delta_rev >= 50.0:
		var ship_center = _zone_rect("SHIPPING").position + (_zone_rect("SHIPPING").size / 2.0)
		_spawn_callout("REVENUE SURGE", ship_center, Color("#a3e635"))
		_flash_zone("SHIPPING", 0.20)

	# Per-product deltas drive the warehouse animations.
	var activity: Array[Dictionary] = []
	for p in products:
		if not (p is Dictionary):
			continue
		var asin = str(p.get("asin", ""))
		if asin == "":
			continue
		var inv = int(p.get("inventory", 0))
		var price = float(p.get("price", 0.0))

		var prev_inv = int(last_product_inventory.get(asin, inv))
		var prev_price = float(last_product_price.get(asin, price))
		var inv_delta = inv - prev_inv
		var price_delta = price - prev_price

		last_product_inventory[asin] = inv
		last_product_price[asin] = price

		# Only keep lines for interesting changes.
		if inv_delta != 0 or abs(price_delta) > 0.0001:
			activity.append({"asin": asin, "inv": inv, "inv_delta": inv_delta, "price": price, "price_delta": price_delta})

	# Sort by absolute inventory movement so big changes show first.
	activity.sort_custom(func(a, b):
		return abs(int(b.get("inv_delta", 0))) < abs(int(a.get("inv_delta", 0)))
	)

	var shown = 0
	var focus_target = Vector2(400, 300)
	var focus_zoom = 1.0
	var focus_priority = 0
	for item in activity:
		if shown >= 4:
			break
		var asin = str(item.get("asin", ""))
		var inv = int(item.get("inv", 0))
		var inv_delta = int(item.get("inv_delta", 0))
		var price = float(item.get("price", 0.0))
		var price_delta = float(item.get("price_delta", 0.0))
		var c = _color_for_id(asin)

		if inv_delta < 0:
			var sold = -inv_delta
			_spawn_sale_packages(asin, sold)
			_flash_zone("PACKING")
			_flash_zone("SHIPPING")
			_feed_push("%s sold %d @ $%.2f (inv %d)" % [_tag_color(asin, c), sold, price, inv])
			if focus_priority < 2:
				focus_target = _zone_rect("SHIPPING").position + (_zone_rect("SHIPPING").size / 2.0)
				focus_zoom = 1.35
				focus_priority = 2
			if inv == 0:
				_spawn_callout("SOLD OUT", _product_anchor(asin), Color("#f87171"))
				_flash_zone("STORAGE", 0.22)
				if focus_priority < 3:
					focus_target = _product_anchor(asin)
					focus_zoom = 1.65
					focus_priority = 3
		elif inv_delta > 0:
			_spawn_restock_packages(asin, inv_delta)
			_flash_zone("RECEIVING")
			_flash_zone("STORAGE")
			_feed_push("%s restock +%d (inv %d)" % [_tag_color(asin, c), inv_delta, inv])
			if focus_priority < 1:
				focus_target = _zone_rect("RECEIVING").position + (_zone_rect("RECEIVING").size / 2.0)
				focus_zoom = 1.25
				focus_priority = 1

		if abs(price_delta) > 0.0001:
			var prev_price = price - price_delta
			_feed_push("%s price $%.2f -> $%.2f" % [_tag_color(asin, c), prev_price, price])
			if focus_priority < 1:
				focus_target = _product_anchor(asin)
				focus_zoom = 1.35
				focus_priority = 1

		# Low stock warning (video-friendly pacing).
		var baseline = float(product_baselines.get(asin, max(1, inv)))
		var ratio = float(inv) / max(1.0, baseline)
		if inv > 0 and ratio <= 0.12 and not low_stock_warned.has(asin):
			low_stock_warned[asin] = true
			_spawn_callout("LOW STOCK", _product_anchor(asin), Color("#fbbf24"))
			_flash_zone("STORAGE", 0.18)
			_feed_push("%s [color=#fbbf24]LOW STOCK[/color] (inv %d)" % [_tag_color(asin, c), inv])
		if ratio >= 0.25 and low_stock_warned.has(asin):
			low_stock_warned.erase(asin)

		shown += 1

	# Cinematic camera: follow the most important activity with a cooldown.
	if cinematic_mode:
		if tick - _cinematic_last_focus_tick >= 2 and focus_priority > 0:
			_cinematic_focus(focus_target, focus_zoom, 0.75)
			_cinematic_last_focus_tick = tick

func _feed_push(line: String) -> void:
	feed_lines.append(line)
	if feed_lines.size() > 14:
		feed_lines.pop_front()
	if event_feed:
		event_feed.text = "\n".join(feed_lines)
	if cinematic_feed:
		cinematic_feed.text = "\n".join(feed_lines)

func _tag_color(text: String, c: Color) -> String:
	var hex = c.to_html(false)
	return "[color=#%s]%s[/color]" % [hex, text]

func _color_for_id(id: String) -> Color:
	var acc = 0
	for i in range(id.length()):
		acc = int((acc * 33) + id.unicode_at(i)) & 0x7fffffff
	var hue = float(acc % 360) / 360.0
	return Color.from_hsv(hue, 0.85, 1.0, 1.0)

func _zone_rect(name: String) -> Rect2:
	var v = zone_rects.get(name, null)
	if v is Rect2:
		return v
	return Rect2(Vector2.ZERO, Vector2(800, 600))

func _rand_in_rect(r: Rect2) -> Vector2:
	return Vector2(
		rng.randf_range(r.position.x, r.position.x + r.size.x),
		rng.randf_range(r.position.y, r.position.y + r.size.y)
	)

func _product_anchor(asin: String) -> Vector2:
	if products_container == null:
		return Vector2(400, 300)
	var node = products_container.get_node_or_null(asin)
	if node:
		return node.position
	return Vector2(400, 300)

func _spawn_sale_packages(asin: String, sold: int) -> void:
	if effects_container == null:
		return
	var c = _color_for_id(asin)
	var start = _product_anchor(asin) + Vector2(rng.randf_range(-10, 10), rng.randf_range(-10, 10))
	var packing = _rand_in_rect(_zone_rect("PACKING"))
	var shipping = _rand_in_rect(_zone_rect("SHIPPING"))

	var count = min(sold, 12)
	for i in range(count):
		var points: Array[Vector2] = [start, packing, shipping]
		_spawn_package_path(points, c, rng.randf_range(0.8, 1.2))

func _spawn_restock_packages(asin: String, added: int) -> void:
	if effects_container == null:
		return
	var c = _color_for_id(asin)
	var receiving = _rand_in_rect(_zone_rect("RECEIVING"))
	var storage = _product_anchor(asin) + Vector2(rng.randf_range(-10, 10), rng.randf_range(-10, 10))

	var count = min(added, 10)
	for i in range(count):
		var points: Array[Vector2] = [receiving, storage]
		_spawn_package_path(points, c, rng.randf_range(0.7, 1.0))

func _spawn_package_path(points: Array[Vector2], c: Color, duration: float) -> void:
	if points.size() < 2:
		return

	var pkg = Polygon2D.new()
	pkg.polygon = PackedVector2Array([
		Vector2(-4, -4),
		Vector2(4, -4),
		Vector2(4, 4),
		Vector2(-4, 4),
	])
	pkg.color = c
	pkg.color.a = 0.8
	effects_container.add_child(pkg)
	pkg.position = points[0]

	var move = create_tween()
	for i in range(1, points.size()):
		move.tween_property(pkg, "position", points[i], duration / float(points.size() - 1)).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)

	var fade = create_tween()
	fade.tween_property(pkg, "modulate:a", 0.0, duration)
	fade.tween_callback(func(): pkg.queue_free())

func _spawn_callout(text: String, pos: Vector2, col: Color) -> void:
	if effects_container == null:
		return
	var lbl = Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", 16)
	lbl.add_theme_color_override("font_color", col)
	lbl.position = pos + Vector2(-50, -70)
	lbl.custom_minimum_size = Vector2(100, 0)
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	effects_container.add_child(lbl)

	var move = create_tween()
	move.tween_property(lbl, "position", lbl.position + Vector2(0, -22), 0.8).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)

	var fade = create_tween()
	fade.tween_property(lbl, "modulate:a", 0.0, 0.8)
	fade.tween_callback(func(): lbl.queue_free())

func _flash_zone(zone: String, intensity: float = 0.18) -> void:
	if not zone_glows.has(zone) or not zone_base_colors.has(zone):
		return
	var glow = zone_glows.get(zone)
	var base = zone_base_colors.get(zone, Color.WHITE)
	if glow == null:
		return

	var bright = base
	bright.a = intensity
	var dim = base
	dim.a = 0.05

	glow.color = bright
	create_tween().tween_property(glow, "color", dim, 0.6).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)

func _cinematic_focus(pos: Vector2, zoom: float, duration: float = 0.6) -> void:
	if camera == null:
		return
	var target_zoom = clamp(zoom, MIN_ZOOM, MAX_ZOOM)
	current_zoom = target_zoom

	# Kill any in-flight camera tween to avoid jitter.
	if camera.has_meta("cin_tween"):
		var t = camera.get_meta("cin_tween")
		if t and t.is_valid():
			t.kill()

	var tween = create_tween()
	tween.tween_property(camera, "position", pos, duration).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tween.tween_property(camera, "zoom", Vector2(target_zoom, target_zoom), duration).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	camera.set_meta("cin_tween", tween)

func _on_simulation_finished(results: Dictionary) -> void:
	# Backend run completed; show end card summary.
	is_running = false
	_update_button_states()

	if end_card == null or end_card_body == null:
		return

	var total_ticks = int(results.get("total_ticks", 0))
	var total_revenue = float(results.get("total_revenue", 0.0))
	var total_profit = float(results.get("total_profit", 0.0))
	var units = int(results.get("total_units_sold", 0))
	var inv_val = float(results.get("final_inventory_value", 0.0))
	var margin = float(results.get("profit_margin", 0.0))

	var hi = _compute_run_highlights()
	end_card_body.text = (
		"[b]Summary[/b]\n" +
		"- Ticks: %d\n" % total_ticks +
		"- Revenue: $%.2f\n" % total_revenue +
		"- Profit: $%.2f  (margin %.1f%%)\n" % [total_profit, margin] +
		"- Units sold: %d\n" % units +
		"- Final inventory value: $%.2f\n\n" % inv_val +
		"[b]Highlights[/b]\n" +
		"- Best revenue tick: T%03d  +$%.2f\n" % [int(hi.get("best_rev_tick", -1)), float(hi.get("best_rev_delta", 0.0))] +
		"- Best units tick: T%03d  +%d units\n\n" % [int(hi.get("best_units_tick", -1)), int(hi.get("best_units_delta", 0))] +
		"[color=gray]Tip: Press C to toggle Cinematic Mode.[/color]"
	)

	end_card.visible = true

	# Demo mode: auto-quit after showing end card (and optionally write a sentinel file).
	if demo_autostart and demo_autoquit:
		var hold = max(0.1, float(demo_end_hold_s))
		get_tree().create_timer(hold).timeout.connect(func():
			if demo_done_file != "":
				var f = FileAccess.open(demo_done_file, FileAccess.WRITE)
				if f != null:
					f.store_string("done\n")
					f.close()
			get_tree().quit()
		)

func _compute_run_highlights() -> Dictionary:
	# Prefer incremental tracking (covers full runs even when tick_history is capped).
	if best_rev_tick != -1 or best_units_tick != -1:
		return {
			"best_rev_tick": best_rev_tick,
			"best_rev_delta": best_rev_delta,
			"best_units_tick": best_units_tick,
			"best_units_delta": best_units_delta,
		}

	var best_rev_tick = -1
	var best_rev_delta = 0.0
	var best_units_tick = -1
	var best_units_delta = 0

	var prev_rev = 0.0
	var prev_units = 0

	for t in SimulationState.tick_history:
		if not (t is Dictionary):
			continue
		var tick = int(t.get("tick", 0))
		var m = t.get("metrics", {})
		var rev = float(m.get("total_revenue", 0.0))
		var units = int(m.get("units_sold", 0))
		var d_rev = rev - prev_rev
		var d_units = units - prev_units
		if d_rev > best_rev_delta:
			best_rev_delta = d_rev
			best_rev_tick = tick
		if d_units > best_units_delta:
			best_units_delta = d_units
			best_units_tick = tick
		prev_rev = rev
		prev_units = units

	return {
		"best_rev_tick": best_rev_tick,
		"best_rev_delta": best_rev_delta,
		"best_units_tick": best_units_tick,
		"best_units_delta": best_units_delta,
	}
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
