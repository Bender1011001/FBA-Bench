extends Control

## SimulationViewer.gd
## Main simulation visualization controller with agent introspection

const REPLAY_CONTROLS_SCENE := preload("res://scenes/components/ReplayControlsBar.tscn")
const STORY_FEED_SCENE := preload("res://scenes/components/StoryFeedPanel.tscn")
const METRIC_CARD_SCENE := preload("res://scenes/components/MetricCard.tscn")
const TEXTURE_GRID := preload("res://assets/textures/floor_v2.png")
const SPRITE_AGENT := preload("res://assets/sprites/agent_v2.png")
const SPRITE_COMPETITOR := preload("res://assets/sprites/competitor_v2.png")
const SPRITE_SHADOW := preload("res://assets/sprites/fx_shadow.png")
const SPRITE_SCANNER := preload("res://assets/sprites/fx_scanner.png")
const ICON_LEDGER := preload("res://assets/icons/ledger_icon.png")
const ICON_RED_TEAM := preload("res://assets/icons/red_team_icon.png")
const ICON_MEMORY := preload("res://assets/icons/memory_icon.png")
const ICON_CONSUMER := preload("res://assets/icons/consumer_icon.png")
const MAX_TICK_BUFFER := 2400
const MAX_STORY_LINES := 14
const REPLAY_FRAME_STEP := 0.14
const CARD_TONE_NEUTRAL := 0
const CARD_TONE_GOOD := 1
const CARD_TONE_WARN := 2
const CARD_TONE_DANGER := 3

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
var story_feed_panel: Control
var replay_controls: Control
var revenue_card: Control
var units_card: Control
var risk_card: Control
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
var story_timeline: Array[Dictionary] = []
var replay_buffer: Array[Dictionary] = []
var rng := RandomNumberGenerator.new()

var last_total_revenue: float = 0.0
var last_total_profit: float = 0.0
var last_total_units_sold: int = 0
var last_tick_seen: int = -1
var cinematic_mode: bool = false
var replay_mode: bool = false
var replay_playing: bool = false
var replay_cursor: int = -1
var replay_speed: float = 1.0
var replay_accumulator: float = 0.0
var _split_offset_prev: int = 340
var _main_top_prev_visible: bool = true
var _main_bottom_prev_visible: bool = true
var _cinematic_last_focus_tick: int = -9999
var low_stock_warned: Dictionary = {}
var agent_last_strategy: Dictionary = {}

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
	UiDesignSystem.apply_to_control(self)
	
	# --- 1. ENTERPRISE LAYOUT RESTRUCTURE ---
	# Goal: Simulation is Background, UI is Overlay.
	
	# A. Move CenterPanel (Sim) to Root Background
	var center_panel = split_container.get_node("CenterPanel")
	center_panel.reparent(self)
	move_child(center_panel, 0) # Send to back
	center_panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	
	# B. Move LeftPanel to Root Overlay
	# Note: We need to ensure we grab refs before reparenting if they rely on paths, 
	# but onready vars are already resolved.
	left_panel.reparent(self)
	left_panel.set_anchors_and_offsets_preset(Control.PRESET_LEFT_WIDE)
	left_panel.set_anchor(SIDE_RIGHT, 0.0) # Un-anchor from right
	left_panel.custom_minimum_size.x = 360
	left_panel.size.x = 360
	
	# Floating "Glass" Style for Sidebar
	var side_style = StyleBoxFlat.new()
	side_style.bg_color = Color(0.05, 0.05, 0.08, 0.85) # Semi-transparent dark
	side_style.border_width_right = 1
	side_style.border_color = Color(1, 1, 1, 0.1)
	left_panel.add_theme_stylebox_override("panel", side_style)

	# C. Kill the old container
	split_container.queue_free()

	# Verify Viewport Container expansion
	var vp_container = warehouse_container.get_parent().get_parent()
	if vp_container is SubViewportContainer:
		vp_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
		vp_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		vp_container.stretch = true 
	
	_connect_signals()
	_update_button_states()
	rng.randomize()
	_fetch_initial_data()
	
	# 2. SIDEBAR RESTRUCTURE
	_reorganize_sidebar()
	_setup_modules_panel()
	_setup_metric_cards()
	_setup_charts()
	_setup_event_feed()
	_setup_replay_controls()
	_setup_end_card()
	_draw_warehouse_grid()
	
	# Background (ColorRect behind everything, just in case)
	if has_node("Background"):
		$Background.queue_free() # We use the grid texture now

	
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
		
	print("[SimViewer] Ready - Enterprise UI Layout Applied")
	_configure_demo_from_env()
		
	print("[SimViewer] Ready - Dropdowns populated")

func _process(delta: float) -> void:
	if not replay_mode or not replay_playing:
		return
	if replay_buffer.size() < 2:
		replay_playing = false
		_update_replay_controls_state()
		return

	replay_accumulator += delta * replay_speed
	while replay_accumulator >= REPLAY_FRAME_STEP:
		replay_accumulator -= REPLAY_FRAME_STEP
		replay_cursor += 1
		if replay_cursor >= replay_buffer.size():
			replay_cursor = replay_buffer.size() - 1
			replay_playing = false
			break
		_render_replay_frame(replay_cursor)
	_update_replay_controls_state()

# --- VISUALS & ANIMATION ---
var zone_arrows: Array[Line2D] = []
var zone_panels: Dictionary = {} # Map name -> Panel
var flow_phase: float = 0.0

func _process(delta: float):
	# 1. Animate Flow Arrows
	flow_phase += delta * 2.0 # Speed
	for arrow in zone_arrows:
		arrow.width = 4.0 + sin(flow_phase) * 1.5
		arrow.default_color = Color(0.2, 0.8, 1.0, 0.4 + sin(flow_phase * 3.0) * 0.2)

	# 2. Smooth Zone Focus Decay (Active Focus State)
	for z_name in zone_panels:
		var panel = zone_panels[z_name]
		var style = panel.get_theme_stylebox("panel") as StyleBoxFlat
		if style:
			# Target opacity is low (0.1), flash sets it high (0.6)
			var current_a = style.bg_color.a
			var target_a = 0.1
			if current_a > target_a:
				style.bg_color.a = lerp(current_a, target_a, delta * 3.0)
				style.border_color.a = lerp(style.border_color.a, 0.4, delta * 3.0)

func _draw_warehouse_grid():
	set_process(true) # Enable animation loop
	zone_rects.clear()
	zone_glows.clear()
	zone_base_colors.clear()
	zone_arrows.clear()
	zone_panels.clear()

	# Draw a "Cyberpunk Blueprint" grid
	var grid = Node2D.new()
	grid.name = "WarehouseGrid"
	warehouse_container.add_child(grid)
	
	# Background Texture (Market Grid) - Tiled across infinite space effectively
	var bg_tex = TextureRect.new()
	bg_tex.texture = TEXTURE_GRID
	bg_tex.stretch_mode = TextureRect.STRETCH_TILE
	bg_tex.modulate = Color(0.6, 0.6, 0.6, 1.0) 
	# Make it huge to cover any resolution
	bg_tex.size = Vector2(4000, 4000)
	bg_tex.position = Vector2(-2000, -2000) # Centered better
	grid.add_child(bg_tex)

	# Warehouse Zones - ENTERPRISE Scale
	# Moved UP (y=50) and TALLER (650px) to fill screen
	var zone_configs = [
		{"name": "RECEIVING", "col": Color(0.2, 0.6, 1.0), "pos": Vector2(50, 50)},
		{"name": "STORAGE",   "col": Color(0.2, 0.8, 0.4), "pos": Vector2(350, 50)},
		{"name": "PACKING",   "col": Color(0.9, 0.6, 0.2), "pos": Vector2(650, 50)},
		{"name": "SHIPPING",  "col": Color(1.0, 0.3, 0.3), "pos": Vector2(950, 50)}
	]
	
	# Draw Connection Arrows (Flow) BEFORE zones so they are under
	var arrow_points = [
		[Vector2(300, 375), Vector2(350, 375)], # Rec -> Sto
		[Vector2(600, 375), Vector2(650, 375)], # Sto -> Pac
		[Vector2(900, 375), Vector2(950, 375)]  # Pac -> Ship
	]
	
	for pair in arrow_points:
		var line = Line2D.new()
		line.points = PackedVector2Array(pair)
		line.width = 6.0 # Thicker base
		line.default_color = Color(0.2, 0.8, 1.0, 0.5)
		line.begin_cap_mode = Line2D.LINE_CAP_ROUND
		line.end_cap_mode = Line2D.LINE_CAP_ROUND
		grid.add_child(line)
		zone_arrows.append(line) # Track for animation
		
		# Chevron Tip
		var chev = Polygon2D.new()
		var end = pair[1]
		chev.polygon = PackedVector2Array([
			end + Vector2(-15, -10),
			end + Vector2(0, 0),
			end + Vector2(-15, 10)
		])
		chev.color = Color(0.2, 0.8, 1.0, 0.8) # Bright tip
		grid.add_child(chev)
	
	for z in zone_configs:
		var zone_name = str(z.get("name", ""))
		var zone_col = z.get("col", Color.WHITE)
		var zone_pos = z.get("pos", Vector2.ZERO)
		var zone_size = Vector2(250, 650) # TALLER

		# Solid Zone floor
		var zone_panel = Panel.new()
		var style = StyleBoxFlat.new()
		style.bg_color = zone_col
		style.bg_color.a = 0.1 # Low opacity fill (Base)
		style.border_width_left = 2
		style.border_width_top = 2
		style.border_width_right = 2
		style.border_width_bottom = 2
		style.border_color = zone_col
		style.border_color.a = 0.4
		style.corner_radius_top_left = 8
		style.corner_radius_top_right = 8
		style.corner_radius_bottom_left = 8
		style.corner_radius_bottom_right = 8
		zone_panel.add_theme_stylebox_override("panel", style)
		zone_panel.size = zone_size
		zone_panel.position = zone_pos
		grid.add_child(zone_panel)
		
		# Save rect for random placement
		if zone_name != "":
			zone_rects[zone_name] = Rect2(zone_pos, zone_size)
			zone_base_colors[zone_name] = zone_col
			zone_panels[zone_name] = zone_panel # Save for animation
		
		# Zone Label (Inside top)
		var label = Label.new()
		label.text = zone_name
		label.position = zone_pos + Vector2(0, 10)
		label.size = Vector2(zone_size.x, 30)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.add_theme_color_override("font_color", zone_col)
		label.add_theme_font_size_override("font_size", 14)
		grid.add_child(label)

func _reorganize_sidebar():
	# 1. Clear existing VBox to rebuild hierarchy
	for child in left_vbox.get_children():
		left_vbox.remove_child(child)
	
	# Theme Constants
	left_vbox.add_theme_constant_override("separation", 24) # More breathing room
	
	# --- SECTION 1: MAIN CONTROLS ---
	var control_panel = PanelContainer.new()
	var control_style = StyleBoxFlat.new()
	control_style.bg_color = Color(0.1, 0.12, 0.15, 0.0) # Transparent now
	control_panel.add_theme_stylebox_override("panel", control_style)
	
	var btn_vbox = VBoxContainer.new()
	btn_vbox.add_theme_constant_override("separation", 12)
	control_panel.add_child(btn_vbox)
	
	# Title / Brand (More prominent)
	var brand_box = VBoxContainer.new()
	brand_box.add_theme_constant_override("separation", 0)
	var brand = Label.new()
	brand.text = "FBA BENCH"
	brand.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	brand.add_theme_font_size_override("font_size", 18)
	brand.add_theme_color_override("font_color", Color("#94a3b8"))
	brand_box.add_child(brand)
	
	var sub_brand = Label.new()
	sub_brand.text = "ENTERPRISE EDITION"
	sub_brand.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub_brand.add_theme_font_size_override("font_size", 10)
	sub_brand.add_theme_color_override("font_color", Color("#30b7ff")) # Cyan highlight
	brand_box.add_child(sub_brand)
	btn_vbox.add_child(brand_box)
	
	# Spacer
	var spacer = Control.new()
	spacer.custom_minimum_size.y = 10
	btn_vbox.add_child(spacer)

	# Big START Button
	start_btn.custom_minimum_size = Vector2(0, 56)
	start_btn.text = "INITIALIZE SYSTEM"
	start_btn.icon = null 
	start_btn.add_theme_font_size_override("font_size", 15)
	var start_style = StyleBoxFlat.new()
	start_style.bg_color = Color("#0ea5e9") # Sky blue
	start_style.corner_radius_top_left = 6
	start_style.corner_radius_top_right = 6
	start_style.corner_radius_bottom_left = 6
	start_style.corner_radius_bottom_right = 6
	start_btn.add_theme_stylebox_override("normal", start_style)
	start_btn.add_theme_stylebox_override("hover", start_style.duplicate()) 
	btn_vbox.add_child(start_btn)
	
	# Stop Button (Smaller)
	stop_btn.text = "ABORT SIMULATION"
	stop_btn.flat = true
	stop_btn.add_theme_color_override("font_color", Color("#ef4444"))
	stop_btn.add_theme_color_override("font_hover_color", Color("#f87171"))
	btn_vbox.add_child(stop_btn)

	# Speed Slider MOVED to Command Deck
	# We just ensure it's not here.

	left_vbox.add_child(control_panel)

	# --- SECTION 2: KEY METRICS (Data Plates) ---
	var kpi_header = Label.new()
	kpi_header.text = "LIVE TELEMETRY"
	kpi_header.add_theme_font_size_override("font_size", 10)
	kpi_header.add_theme_color_override("font_color", Color("#475569"))
	left_vbox.add_child(kpi_header)
	
	var kpi_grid = GridContainer.new()
	kpi_grid.columns = 1 # Stacked for importance? Or 2x2. Let's do 1 column for IMPACT.
	kpi_grid.add_theme_constant_override("v_separation", 16)
	
	# Helper to make KPI cards (Data Plates)
	var make_kpi = func(ref_label: Label, title: String, color: Color):
		var p = PanelContainer.new()
		var s = StyleBoxFlat.new()
		s.bg_color = Color(0.05, 0.08, 0.1, 0.4) # Reduced opacity (was 0.8)
		s.border_width_left = 4 # Thick left bar
		s.border_color = color
		s.content_margin_left = 16
		s.content_margin_right = 16
		s.content_margin_top = 8
		s.content_margin_bottom = 8
		p.add_theme_stylebox_override("panel", s)
		
		var v = VBoxContainer.new()
		var t = Label.new()
		t.text = title.to_upper()
		t.add_theme_font_size_override("font_size", 10)
		t.add_theme_color_override("font_color", Color("#64748b"))
		v.add_child(t)
		
		ref_label.text = "---"
		ref_label.add_theme_font_size_override("font_size", 48) # MAXIMIZED (was 24)
		ref_label.add_theme_color_override("font_color", Color.WHITE)
		v.add_child(ref_label)
		p.add_child(v)
		return p
	
	kpi_grid.add_child(make_kpi.call(revenue_label, "Revenue", Color("#22c55e")))
	kpi_grid.add_child(make_kpi.call(inventory_label, "Inventory Value", Color("#eab308")))
	# Reuse Orders label for Profit
	orders_label.name = "ProfitLabel" 
	kpi_grid.add_child(make_kpi.call(orders_label, "Net Profit", Color("#3b82f6")))
	
	left_vbox.add_child(kpi_grid)
	
	# --- SECTION 3: CONFIGURATION ---
	var config_header = Label.new()
	config_header.text = "SYSTEM CONFIGURATION"
	config_header.add_theme_font_size_override("font_size", 10)
	config_header.add_theme_color_override("font_color", Color("#475569"))
	left_vbox.add_child(config_header)
	
	var config_vbox = VBoxContainer.new()
	
	# Agent Model
	var l1 = Label.new(); l1.text = "Intelligent Agent Model"; l1.add_theme_color_override("font_color", Color("#64748b")); l1.add_theme_font_size_override("font_size", 11)
	config_vbox.add_child(l1)
	ensure_parent(agent_dropdown, config_vbox)
	
	# Scenario
	var l2 = Label.new(); l2.text = "Operational Scenario"; l2.add_theme_color_override("font_color", Color("#64748b")); l2.add_theme_font_size_override("font_size", 11)
	config_vbox.add_child(l2)
	ensure_parent(scenario_dropdown, config_vbox)
	
	left_vbox.add_child(config_vbox)

	# Hide debug inputs
	seed_input.visible = false
	max_ticks_input.visible = false
	cinematic_toggle.visible = false # Always on implicitly or controlled via key
	
	# --- SECTION 4: MODULES ---
	var mod_header = Label.new()
	mod_header.text = "ACTIVE MODULES"
	mod_header.add_theme_font_size_override("font_size", 11)
	mod_header.add_theme_color_override("font_color", Color("#475569"))
	left_vbox.add_child(mod_header)

	var mod_grid = GridContainer.new()
	mod_grid.columns = 4
	mod_grid.add_theme_constant_override("h_separation", 8)
	left_vbox.add_child(mod_grid)

	var modules = [
		{"icon": ICON_LEDGER, "name": "Ledger", "color": Color("#ffd700")},
		{"icon": ICON_RED_TEAM, "name": "Red Team", "color": Color("#ff0055")},
		{"icon": ICON_MEMORY, "name": "Memory", "color": Color("#aa00ff")},
		{"icon": ICON_CONSUMER, "name": "Consumer", "color": Color("#00ffaa")}
	]

	for m in modules:
		var btn = Button.new()
		btn.custom_minimum_size = Vector2(48, 48)
		btn.icon = m.icon
		btn.expand_icon = true
		btn.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		btn.tooltip_text = m.name
		btn.flat = true
		
		# Active Tab Contrast: Clearer border
		var bg = Panel.new()
		bg.show_behind_parent = true
		bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		var bs = StyleBoxFlat.new()
		bs.bg_color = m.color
		bs.bg_color.a = 0.1
		bs.border_width_bottom = 2
		bs.border_color = m.color
		bs.border_color.a = 0.5
		bg.add_theme_stylebox_override("panel", bs)
		btn.add_child(bg)
		
		mod_grid.add_child(btn)

func ensure_parent(node: Control, new_parent: Control):
	if node.get_parent():
		node.get_parent().remove_child(node)
	new_parent.add_child(node)

func _setup_modules_panel():
	pass # Deprecated, merged into reorganize

func _setup_metric_cards():
	pass # Metrics moved to _reorganize_sidebar

func _setup_charts():
	var chart_script = load("res://scenes/simulation/PerformanceChart.gd")
	
	revenue_chart = Control.new()
	revenue_chart.set_script(chart_script)
	revenue_chart.custom_minimum_size = Vector2(0, 80)
	revenue_chart.label = "Revenue"
	revenue_chart.line_color = Color("#30b7ff")
	left_vbox.add_child(revenue_chart)
	
	profit_chart = Control.new()
	profit_chart.set_script(chart_script)
	profit_chart.custom_minimum_size = Vector2(0, 80)
	profit_chart.label = "Profit"
	profit_chart.line_color = Color("#8ee67a")
	left_vbox.add_child(profit_chart)

func _setup_event_feed():
	story_feed_panel = STORY_FEED_SCENE.instantiate()
	story_feed_panel.custom_minimum_size = Vector2(0, 190)
	left_vbox.add_child(story_feed_panel)
	story_feed_panel.call("set_title", "Story Feed")
	story_feed_panel.set("max_lines", MAX_STORY_LINES)
	event_feed = story_feed_panel.get_node("Margin/VBox/Feed") as RichTextLabel

func _setup_replay_controls():
	# COMMAND DECK (Bottom Bar)
	var deck_height = 80
	var command_deck = PanelContainer.new()
	command_deck.name = "CommandDeck"
	command_deck.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	command_deck.offset_top = -deck_height
	command_deck.grow_vertical = Control.GROW_DIRECTION_BEGIN
	
	var deck_style = StyleBoxFlat.new()
	deck_style.bg_color = Color(0.05, 0.05, 0.08, 0.85) # Reduced opacity (was 1.0)
	deck_style.border_width_top = 2
	deck_style.border_color = Color("#0ea5e9") # Cyan highlight
	command_deck.add_theme_stylebox_override("panel", deck_style)
	
	overlay_ui.add_child(command_deck)
	
	var deck_hbox = HBoxContainer.new()
	deck_hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	deck_hbox.add_theme_constant_override("separation", 32)
	command_deck.add_child(deck_hbox)

	# 1. Access Replay Controls
	replay_controls = REPLAY_CONTROLS_SCENE.instantiate()
	# Reset anchors so it fits in HBox
	replay_controls.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	replay_controls.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	deck_hbox.add_child(replay_controls)
	
	# 2. Integrate Speed Slider
	# It needs a label and proper container
	var speed_box = VBoxContainer.new()
	speed_box.alignment = BoxContainer.ALIGNMENT_CENTER
	speed_box.custom_minimum_size.x = 200
	var sp_lbl = Label.new()
	sp_lbl.text = "TIME DILATION"
	sp_lbl.add_theme_font_size_override("font_size", 10)
	sp_lbl.add_theme_color_override("font_color", Color("#64748b"))
	sp_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	speed_box.add_child(sp_lbl)
	
	ensure_parent(speed_slider, speed_box)
	speed_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	deck_hbox.add_child(speed_box)

	replay_controls.live_requested.connect(_on_replay_live_requested)
	replay_controls.play_toggled.connect(_on_replay_play_toggled)
	replay_controls.scrub_requested.connect(_on_replay_scrub_requested)
	replay_controls.speed_changed.connect(_on_replay_speed_changed)
	_update_replay_controls_state()

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
	margin.add_theme_constant_override("margin_left", 16)
	margin.add_theme_constant_override("margin_right", 16)
	margin.add_theme_constant_override("margin_top", 16)
	margin.add_theme_constant_override("margin_bottom", 16)
	end_card.add_child(margin)

	var v = VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
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
	btn_row.add_theme_constant_override("separation", 10)
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

func _on_replay_live_requested() -> void:
	replay_mode = false
	replay_playing = false
	replay_accumulator = 0.0
	if replay_buffer.size() > 0:
		replay_cursor = replay_buffer.size() - 1
		_render_replay_frame(replay_cursor)
	_update_replay_controls_state()

func _on_replay_play_toggled(playing: bool) -> void:
	if replay_buffer.size() < 2:
		replay_playing = false
		_update_replay_controls_state()
		return
	replay_mode = true
	replay_playing = playing
	replay_accumulator = 0.0
	if replay_cursor >= replay_buffer.size() - 1:
		replay_cursor = 0
	_render_replay_frame(replay_cursor)
	_update_replay_controls_state()

func _on_replay_scrub_requested(index: int) -> void:
	if replay_buffer.size() == 0:
		return
	replay_mode = true
	replay_playing = false
	replay_accumulator = 0.0
	replay_cursor = clamp(index, 0, replay_buffer.size() - 1)
	_render_replay_frame(replay_cursor)
	_update_replay_controls_state()

func _on_replay_speed_changed(multiplier: float) -> void:
	replay_speed = multiplier
	_update_replay_controls_state()

func _update_replay_controls_state() -> void:
	if replay_controls == null:
		return
	replay_controls.set_state(
		"REPLAY" if replay_mode else "LIVE",
		replay_buffer.size(),
		max(0, replay_cursor),
		replay_playing,
		not replay_mode,
		replay_buffer.size() > 1,
		replay_speed
	)

func _append_replay_frame(data: Dictionary) -> void:
	replay_buffer.append(data.duplicate(true))
	if replay_buffer.size() > MAX_TICK_BUFFER:
		replay_buffer.pop_front()
	if replay_cursor == -1:
		replay_cursor = replay_buffer.size() - 1
	if not replay_mode:
		replay_cursor = replay_buffer.size() - 1
	_update_replay_controls_state()

func _render_replay_frame(index: int) -> void:
	if index < 0 or index >= replay_buffer.size():
		return
	_render_tick_data(replay_buffer[index], false, index)

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
	hud_margin.add_theme_constant_override("margin_left", 10)
	hud_margin.add_theme_constant_override("margin_right", 10)
	hud_margin.add_theme_constant_override("margin_top", 8)
	hud_margin.add_theme_constant_override("margin_bottom", 8)
	cinematic_hud.add_child(hud_margin)

	var v = VBoxContainer.new()
	v.add_theme_constant_override("separation", 2)
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

	cinematic_feed_panel = STORY_FEED_SCENE.instantiate()
	cinematic_feed_panel.visible = false
	cinematic_feed_panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	cinematic_feed_panel.offset_left = 12
	cinematic_feed_panel.offset_right = 12 + 430
	cinematic_feed_panel.offset_bottom = -12
	cinematic_feed_panel.offset_top = -12 - 200
	overlay_ui.add_child(cinematic_feed_panel)
	cinematic_feed_panel.call("set_title", "Key Events")
	cinematic_feed_panel.set("max_lines", MAX_STORY_LINES)
	cinematic_feed = cinematic_feed_panel.get_node("Margin/VBox/Feed") as RichTextLabel

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
	# Sanitization logic
	var map_name = func(n):
		if n == "tier1_basic": return "Standard Operations (Tier 1)"
		if n == "tier2_advanced": return "Advanced Logistics (Tier 2)"
		return n.capitalize()

	if data is Dictionary and data.has("scenarios"):
		for scenario in data["scenarios"]:
			var sid = scenario.get("id", "unknown")
			scenario_dropdown.add_item(map_name.call(sid))
			scenario_dropdown.set_item_metadata(scenario_dropdown.item_count - 1, sid)
	elif data is Array:
		for scenario in data:
			if scenario is Dictionary:
				var sid = scenario.get("id", "unknown")
				scenario_dropdown.add_item(map_name.call(sid))
				scenario_dropdown.set_item_metadata(scenario_dropdown.item_count - 1, sid)

func _populate_models(data: Variant):
	agent_dropdown.clear()
	# Sanitization Logic
	var map_name = func(n):
		if n == "gpt-4o": return "Strategic AI (Omni)"
		if n.begins_with("claude"): return "Analytical AI (Opus)"
		return n

	if data is Dictionary and data.has("models"):
		for model in data["models"]:
			var mid = model.get("id", "unknown")
			agent_dropdown.add_item(map_name.call(mid))
			agent_dropdown.set_item_metadata(agent_dropdown.item_count - 1, mid)

func _update_button_states():
	start_btn.disabled = is_running
	step_btn.disabled = is_running
	stop_btn.disabled = !is_running

func _on_start_pressed():
	is_running = true
	replay_mode = false
	replay_playing = false
	replay_cursor = -1
	replay_accumulator = 0.0
	_update_button_states()
	_reset_observer_state()
	if end_card:
		end_card.visible = false
	
	# Get real IDs from metadata if available, else text
	var s_item = scenario_dropdown.selected
	var sc_id = scenario_dropdown.get_item_metadata(s_item) if s_item >= 0 else scenario_dropdown.get_item_text(s_item)
	
	var a_item = agent_dropdown.selected
	var ag_id = agent_dropdown.get_item_metadata(a_item) if a_item >= 0 else agent_dropdown.get_item_text(a_item)
	
	var config = {
		"scenario": sc_id,
		"agent": ag_id,
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
	replay_playing = false
	replay_mode = true
	if replay_buffer.size() > 0:
		replay_cursor = replay_buffer.size() - 1
	_render_replay_frame(replay_cursor)
	_update_replay_controls_state()
	if end_card:
		end_card.visible = false

func _on_simulation_tick(data: Dictionary):
	_append_replay_frame(data)
	_process_structured_events(data)
	if replay_mode:
		_update_replay_controls_state()
		return
	_render_tick_data(data, true, replay_buffer.size() - 1)

func _render_tick_data(data: Dictionary, include_activity: bool, replay_index: int = -1) -> void:
	var tick = int(data.get("tick", 0))
	var metrics = data.get("metrics", {})
	if not (metrics is Dictionary):
		metrics = {}
	var products = data.get("products", [])
	if not (products is Array):
		products = []

	var revenue_total = float(metrics.get("total_revenue", 0.0))
	var profit_total = float(metrics.get("total_profit", 0.0))
	var units_total = int(metrics.get("units_sold", 0))
	var inventory_total = int(metrics.get("inventory_count", 0))

	var delta_revenue = 0.0
	var delta_profit = 0.0
	var delta_units = 0
	if include_activity:
		if last_tick_seen != -1:
			delta_revenue = revenue_total - last_total_revenue
			delta_profit = profit_total - last_total_profit
			delta_units = units_total - last_total_units_sold
	else:
		var replay_delta = _metric_delta_for_replay(replay_index)
		delta_revenue = float(replay_delta.get("revenue", 0.0))
		delta_profit = float(replay_delta.get("profit", 0.0))
		delta_units = int(replay_delta.get("units", 0))
	
	# Timecode Format for Ticks
	var ticks_per_hour = 60 # assumption
	var total_seconds = tick * 60 # 1 tick = 1 minute sim time maybe? Or just use raw ticks
	# Making it look cool: T-HH:MM:SS (assuming 1 tick = 1 minute)
	var hrs = floor(tick / 60.0)
	var mins = tick % 60
	tick_label.text = "T-%02d:%02d:00" % [hrs, mins]
	
	revenue_label.text = "$%.2f" % revenue_total
	inventory_label.text = "$%.2f" % float(metrics.get("inventory_value", 0.0)) # Use value if available, else count?
	# Fallback if inventory_value missing
	if inventory_label.text == "$0.00" and inventory_total > 0:
		inventory_label.text = "%d units" % inventory_total
		
	# Repurposed Orders -> Profit
	orders_label.text = "$%.2f" % profit_total
	orders_label.add_theme_color_override("font_color", Color("#ef4444") if profit_total < 0 else Color("#3b82f6"))

	if cinematic_hud_metrics:
		cinematic_hud_metrics.text = "T:%d  Rev:$%.2f  P:$%.2f  Inv:%d" % [
			tick,
			revenue_total,
			profit_total,
			inventory_total
		]
	_update_metric_cards(revenue_total, units_total, inventory_total, delta_revenue, delta_profit, delta_units)
	
	# Update Charts
	if include_activity and revenue_chart:
		revenue_chart.add_point(revenue_total)
	if include_activity and profit_chart:
		profit_chart.add_point(profit_total)
		
	# Update visualization
	_update_products(products)
	if include_activity:
		_process_tick_activity(tick, metrics, products)
	else:
		_sync_feed_to_tick(tick)
	_update_agents(data.get("agents", []))
	_update_competitors(data.get("competitors", []))
	_update_heatmap(data.get("heatmap", []))

	if include_activity:
		last_total_profit = profit_total
	
	# If inspector is open, update its data if it matches the current agent
	if agent_inspector.visible:
		# Find the agent data for the currently inspected agent
		var current_id = agent_inspector.current_agent_id
		for agent in data.get("agents", []):
			if agent.get("id") == current_id:
				agent_inspector.update_agent_data(agent)
				break

func _process_structured_events(data: Dictionary) -> void:
	var tick = int(data.get("tick", max(0, last_tick_seen)))
	var events = data.get("events", [])
	if events is Array:
		for evt in events:
			if not (evt is Dictionary):
				continue
			var evt_type = str(evt.get("type", evt.get("event_type", ""))).to_lower()
			var message = str(evt.get("message", evt.get("description", evt.get("summary", ""))))
			if evt_type.find("attack") != -1 or evt_type.find("red_team") != -1:
				_feed_push("[color=#ff7e89][b]ATTACK[/b][/color] %s" % message, tick)
			elif evt_type.find("memory") != -1:
				_feed_push("[color=#8fa8ff][b]MEMORY[/b][/color] %s" % message, tick)
			elif evt_type.find("strategy") != -1:
				_feed_push("[color=#30b7ff][b]STRATEGY[/b][/color] %s" % message, tick)
			elif evt_type.find("win") != -1:
				_feed_push("[color=#8ee67a][b]WIN[/b][/color] %s" % message, tick)
			elif evt_type.find("loss") != -1 or evt_type.find("fail") != -1:
				_feed_push("[color=#ff7e89][b]LOSS[/b][/color] %s" % message, tick)

	var agents = data.get("agents", [])
	if not (agents is Array):
		return
	for agent in agents:
		if not (agent is Dictionary):
			continue
		var agent_id = str(agent.get("id", ""))
		if agent_id == "":
			continue
		var strategy = str(agent.get("strategy", agent.get("plan", "")))
		if strategy != "":
			var prev_strategy = str(agent_last_strategy.get(agent_id, strategy))
			if prev_strategy != strategy:
				_feed_push("[color=#30b7ff]%s[/color] strategy shift: %s" % [agent_id, strategy], tick)
			agent_last_strategy[agent_id] = strategy
		var calls = agent.get("last_tool_calls", [])
		if calls is Array:
			for call in calls:
				if not (call is Dictionary):
					continue
				var fn = str(call.get("function", {}).get("name", ""))
				if fn.findn("memory") != -1:
					_feed_push("[color=#8fa8ff]%s[/color] memory decision via [i]%s[/i]" % [agent_id, fn], tick)

func _metric_delta_for_replay(index: int) -> Dictionary:
	if index <= 0 or index >= replay_buffer.size():
		return {"revenue": 0.0, "profit": 0.0, "units": 0}
	var current_metrics = replay_buffer[index].get("metrics", {})
	var prev_metrics = replay_buffer[index - 1].get("metrics", {})
	if not (current_metrics is Dictionary):
		current_metrics = {}
	if not (prev_metrics is Dictionary):
		prev_metrics = {}
	return {
		"revenue": float(current_metrics.get("total_revenue", 0.0)) - float(prev_metrics.get("total_revenue", 0.0)),
		"profit": float(current_metrics.get("total_profit", 0.0)) - float(prev_metrics.get("total_profit", 0.0)),
		"units": int(current_metrics.get("units_sold", 0)) - int(prev_metrics.get("units_sold", 0))
	}

func _update_metric_cards(revenue_total: float, units_total: int, inventory_total: int, delta_revenue: float, _delta_profit: float, delta_units: int) -> void:
	if revenue_card == null or units_card == null or risk_card == null:
		return
	var revenue_tone = CARD_TONE_GOOD if delta_revenue >= 0.0 else CARD_TONE_DANGER
	var revenue_prefix = "+" if delta_revenue >= 0.0 else "-"
	revenue_card.call("configure",
		"Revenue",
		"$%.2f" % revenue_total,
		"%s$%.2f / tick" % [revenue_prefix, abs(delta_revenue)],
		revenue_tone
	)
	var units_tone = CARD_TONE_GOOD if delta_units > 0 else CARD_TONE_NEUTRAL
	units_card.call("configure",
		"Units",
		"%d" % units_total,
		("+%d this tick" % delta_units) if delta_units >= 0 else ("%d this tick" % delta_units),
		units_tone
	)
	var risk_text = "Stable"
	var risk_delta = "No alerts"
	var risk_tone = CARD_TONE_GOOD
	if inventory_total <= 0:
		risk_text = "Stockout"
		risk_delta = "Immediate restock required"
		risk_tone = CARD_TONE_DANGER
	elif inventory_total < 50:
		risk_text = "Low"
		risk_delta = "Reorder soon"
		risk_tone = CARD_TONE_WARN
	risk_card.call("configure", "Inventory", risk_text, risk_delta, risk_tone)

func _sync_feed_to_tick(tick: int) -> void:
	var lines: Array[String] = []
	for i in range(story_timeline.size() - 1, -1, -1):
		var entry = story_timeline[i]
		if int(entry.get("tick", -1)) <= tick:
			lines.push_front(str(entry.get("line", "")))
		if lines.size() >= MAX_STORY_LINES:
			break
	feed_lines = lines
	if story_feed_panel:
		story_feed_panel.set_lines(feed_lines)
	elif event_feed:
		event_feed.text = "\n".join(feed_lines)
	if cinematic_feed_panel and cinematic_feed_panel.has_method("set_lines"):
		cinematic_feed_panel.call("set_lines", feed_lines)
	elif cinematic_feed:
		cinematic_feed.text = "\n".join(feed_lines)

func _reset_observer_state():
	product_baselines.clear()
	last_product_inventory.clear()
	last_product_price.clear()
	last_total_revenue = 0.0
	last_total_profit = 0.0
	last_total_units_sold = 0
	last_tick_seen = -1
	feed_lines.clear()
	story_timeline.clear()
	replay_buffer.clear()
	replay_mode = false
	replay_playing = false
	replay_cursor = -1
	replay_accumulator = 0.0
	low_stock_warned.clear()
	agent_last_strategy.clear()
	best_rev_tick = -1
	best_rev_delta = 0.0
	best_units_tick = -1
	best_units_delta = 0

	if story_feed_panel:
		story_feed_panel.clear_feed()
	elif event_feed:
		event_feed.text = "[color=gray]Waiting for tick data...[/color]"
	if cinematic_feed_panel and cinematic_feed_panel.has_method("clear_feed"):
		cinematic_feed_panel.call("clear_feed")
	elif cinematic_feed:
		cinematic_feed.text = "[color=gray]Waiting for tick data...[/color]"

	if products_container:
		for child in products_container.get_children():
			child.queue_free()
	if effects_container:
		for child in effects_container.get_children():
			child.queue_free()
	if revenue_chart and revenue_chart.has_method("clear_points"):
		revenue_chart.clear_points()
	if profit_chart and profit_chart.has_method("clear_points"):
		profit_chart.clear_points()
	_update_replay_controls_state()

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

func _feed_push(line: String, tick_hint: int = -1) -> void:
	feed_lines.append(line)
	if feed_lines.size() > 14:
		feed_lines.pop_front()
	var event_tick = tick_hint if tick_hint >= 0 else max(0, last_tick_seen)
	story_timeline.append({"tick": event_tick, "line": line})
	if story_timeline.size() > 600:
		story_timeline.pop_front()
	if story_feed_panel:
		story_feed_panel.set_lines(feed_lines)
	elif event_feed:
		event_feed.text = "\n".join(feed_lines)
	if cinematic_feed_panel and cinematic_feed_panel.has_method("set_lines"):
		cinematic_feed_panel.call("set_lines", feed_lines)
	elif cinematic_feed:
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

func _flash_zone(zone: String, intensity: float = 0.6) -> void:
	# 1. New Active Focus (Physical Panel)
	if zone_panels.has(zone):
		var panel = zone_panels[zone]
		var style = panel.get_theme_stylebox("panel") as StyleBoxFlat
		if style:
			# Boost opacity substantially (Active Focus)
			style.bg_color.a = 0.6 * intensity # Focus Brightness
			style.border_color.a = 1.0 * intensity

	# 2. Old Glow (Optional/Legacy support)
	if zone_glows.has(zone):
		var glow = zone_glows[zone]
		if glow is Control:
			var tw = create_tween()
			tw.tween_property(glow, "modulate:a", 0.5 * intensity, 0.1)
			tw.tween_property(glow, "modulate:a", 0.0, 0.3)

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

func _compute_run_highlights() -> Dictionary:
	var out = {
		"best_rev_tick": best_rev_tick,
		"best_rev_delta": best_rev_delta,
		"best_units_tick": best_units_tick,
		"best_units_delta": best_units_delta
	}
	return out

func _on_simulation_finished(results: Dictionary) -> void:
	# Backend run completed; show end card summary.
	is_running = false
	replay_mode = true
	replay_playing = false
	if replay_buffer.size() > 0:
		replay_cursor = replay_buffer.size() - 1
	_update_replay_controls_state()
	_update_button_states()

	if end_card == null or end_card_body == null:
		return

	var total_ticks = int(results.get("total_ticks", 0))
	var total_revenue = float(results.get("total_revenue", 0.0))
	var total_profit = float(results.get("total_profit", 0.0))
	var units = int(results.get("total_units_sold", 0))
	var inv_val = float(results.get("final_inventory_value", 0.0))
	var margin = float(results.get("profit_margin", 0.0))
	var outcome_line = "[color=#8ee67a]Win condition met[/color]"
	if total_profit < 0.0:
		outcome_line = "[color=#ff7e89]Loss: negative run profit[/color]"

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
		"- Best units tick: T%03d  +%d units\n" % [int(hi.get("best_units_tick", -1)), int(hi.get("best_units_delta", 0))] +
	)
	
	# Demo Automation: Auto-quit after delay
	if demo_autoquit:
		if demo_done_file != "":
			var f = FileAccess.open(demo_done_file, FileAccess.WRITE)
			if f:
				f.store_string("done")
				f.close()
		
		get_tree().create_timer(max(0.1, demo_end_hold_s)).timeout.connect(func():
			get_tree().quit()
		)

func _update_competitors(competitors: Array):
	var comp_container = warehouse_container.get_node("CompetitorContainer")
	var current_asins = {}
	var start_x = 50
	var start_y = 50
	var spacing_x = 120
	var idx = 0
	for comp_data in competitors:
		var asin = comp_data.get("asin", "")
		if asin == "": continue
		current_asins[asin] = true
		var comp_node = comp_container.get_node_or_null(asin)
		var inventory = int(comp_data.get("inventory", 0))
		var is_oos = bool(comp_data.get("is_out_of_stock", false))
		var price = comp_data.get("price", "?.??")
		if not comp_node:
			comp_node = _create_competitor_visual(asin)
			comp_node.name = asin
			comp_container.add_child(comp_node)
			comp_node.position = Vector2(start_x + (idx * spacing_x), start_y)
		var lbl = comp_node.get_node("Label")
		lbl.text = "%s\n$%s" % [asin, price]
		var inv_bar = comp_node.get_node("InventoryBar")
		var inv_fill = inv_bar.get_node("Fill")
		var status_lbl = comp_node.get_node("StatusLabel")
		if is_oos:
			comp_node.modulate = Color.DIM_GRAY
			status_lbl.text = "SOLD OUT"
			status_lbl.modulate = Color(1.0, 0.2, 0.2)
			inv_fill.scale.x = 0
		else:
			comp_node.modulate = Color.WHITE
			status_lbl.text = "Inv: %d" % inventory
			status_lbl.modulate = Color.WHITE
			var pct = clamp(float(inventory) / 5000.0, 0.0, 1.0)
			inv_fill.scale.x = pct
		idx += 1
	for child in comp_container.get_children():
		if not current_asins.has(child.name):
			child.queue_free()

func _create_competitor_visual(asin: String) -> Node2D:
	var visual = Node2D.new()
	
	# FX: Shadow Blob
	var shadow = Sprite2D.new()
	shadow.texture = SPRITE_SHADOW
	shadow.scale = Vector2(0.3, 0.3)
	shadow.modulate = Color(0, 0, 0, 0.6)
	shadow.position = Vector2(0, 5) # Slight offset
	visual.add_child(shadow)

	# Main Sprite
	var sprite = Sprite2D.new()
	sprite.texture = SPRITE_COMPETITOR
	sprite.scale = Vector2(0.22, 0.22) # Adjust for ~256px source
	sprite.rotation_degrees = -90 # Face down/left aggressive
	visual.add_child(sprite)
	var label = Label.new()
	label.name = "Label"
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.position = Vector2(-40, -55)
	label.custom_minimum_size = Vector2(80, 0)
	visual.add_child(label)
	var status = Label.new()
	status.name = "StatusLabel"
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status.add_theme_font_size_override("font_size", 12)
	status.add_theme_color_override("font_color", Color.WHITE)
	status.position = Vector2(-40, 25)
	status.custom_minimum_size = Vector2(80, 0)
	visual.add_child(status)
	var bar_bg = ColorRect.new()
	bar_bg.name = "InventoryBar"
	bar_bg.color = Color(0.2, 0.2, 0.2)
	bar_bg.size = Vector2(60, 6)
	bar_bg.position = Vector2(-30, 42)
	visual.add_child(bar_bg)
	var bar_fill = ColorRect.new()
	bar_fill.name = "Fill"
	bar_fill.color = Color.GREEN
	bar_fill.size = Vector2(60, 6)
	bar_bg.add_child(bar_fill)
	return visual

func _update_agents(agents: Array):
	var current_agent_ids = {}
	for agent_data in agents:
		var raw_id = agent_data.get("id", "")
		if str(raw_id) == "": continue
		var agent_id = str(raw_id)
		current_agent_ids[agent_id] = true
		var target_pos = Vector2(agent_data.get("x", 0), agent_data.get("y", 0))
		var agent_node = agent_container.get_node_or_null(agent_id)
		if agent_node:
			if agent_node.has_meta("movement_tween"):
				var old_tween = agent_node.get_meta("movement_tween")
				if old_tween and old_tween.is_valid(): old_tween.kill()
			var tween = create_tween()
			tween.tween_property(agent_node, "position", target_pos, 0.5).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
			agent_node.set_meta("movement_tween", tween)
		else:
			var new_agent = _create_agent_visual(agent_data)
			new_agent.name = agent_id
			agent_container.add_child(new_agent)
			new_agent.position = target_pos
		
		# Active Zone Highlighting (Narrative)
		for z_name in zone_rects:
			if zone_rects[z_name].has_point(target_pos):
				_flash_zone(z_name, 0.08) # Subtle pulse when occupied
	for child in agent_container.get_children():
		if not current_agent_ids.has(child.name): child.queue_free()

func _update_heatmap(heatmap_data: Array):
	if heatmap_data.is_empty(): return
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
		var color = Color(1.0, 0.5, 0.0, value * 0.5)
		heatmap_overlay.draw_rect(Rect2(Vector2(x - size/2, y - size/2), Vector2(size, size)), color)

func _create_agent_visual(agent_data: Dictionary) -> Node2D:
	var visual = Node2D.new()
	
	# FX: Shadow
	var shadow = Sprite2D.new()
	shadow.texture = SPRITE_SHADOW
	shadow.scale = Vector2(0.35, 0.35)
	shadow.modulate = Color(0, 0, 0, 0.5)
	shadow.position = Vector2(0, 8)
	visual.add_child(shadow)

	# FX: Scanner Beam (Vision Cone)
	var scanner = Sprite2D.new()
	scanner.texture = SPRITE_SCANNER
	scanner.offset = Vector2(100, 0) # Pivot at center, extend out
	scanner.scale = Vector2(0.8, 0.8)
	scanner.modulate = Color(0.4, 0.8, 1.0, 0.3)
	visual.add_child(scanner)
	
	# Animate Scanner Rotation
	var scan_tween = visual.create_tween().set_loops()
	scan_tween.tween_property(scanner, "rotation", TAU, 4.0).from(0.0)

	# Main Sprite
	var sprite = Sprite2D.new()
	sprite.texture = SPRITE_AGENT
	sprite.scale = Vector2(0.20, 0.20) # Adjust for ~256px source
	visual.add_child(sprite)
	var radius = 22.0
	# Make sprite color match role slightly
	var role = agent_data.get("role", "").to_lower()
	var base_color = Color.WHITE
	if "strategic" in role: base_color = Color("#e0f2fe")
	elif "analyst" in role: base_color = Color("#ecfccb")
	elif "logistics" in role: base_color = Color("#ffedd5")
	sprite.self_modulate = base_color
	var label = Label.new()
	label.text = agent_data.get("id", "?")
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 10)
	label.add_theme_color_override("font_color", Color.WHITE)
	var lbl_style = StyleBoxFlat.new()
	lbl_style.bg_color = Color(0,0,0,0.5)
	lbl_style.corner_radius_top_left = 3
	lbl_style.corner_radius_top_right = 3
	label.add_theme_stylebox_override("normal", lbl_style)
	label.position = Vector2(-50, radius + 6)
	label.custom_minimum_size = Vector2(100, 0)
	visual.add_child(label)
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
