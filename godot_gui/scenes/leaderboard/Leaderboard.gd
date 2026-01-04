extends Control

## Leaderboard.gd
## Handles leaderboard display, filtering, and model comparison

# UI References
@onready var search_input = $MarginContainer/VBoxContainer/FilterBar/SearchInput
@onready var tier_filter = $MarginContainer/VBoxContainer/FilterBar/TierFilter
@onready var metric_filter = $MarginContainer/VBoxContainer/FilterBar/MetricFilter
@onready var verified_checkbox = $MarginContainer/VBoxContainer/FilterBar/VerifiedOnly
@onready var refresh_btn = $MarginContainer/VBoxContainer/HeaderBox/RefreshButton
@onready var export_btn = $MarginContainer/VBoxContainer/HeaderBox/ExportButton
@onready var tree = $MarginContainer/VBoxContainer/TreeContainer/LeaderboardTree

# Details panel
@onready var model_name_label = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/StatsColumn/ModelName
@onready var success_rate_label = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/StatsColumn/SuccessRate
@onready var avg_profit_label = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/StatsColumn/AvgProfit
@onready var tokens_label = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/StatsColumn/TokensUsed
@onready var compare_btn = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/ActionsColumn/CompareButton
@onready var replay_btn = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/ActionsColumn/ReplayButton
@onready var verify_btn = $MarginContainer/VBoxContainer/DetailsPanel/VBoxContainer/DetailsContent/ActionsColumn/VerifyButton

var leaderboard_data: Array = []
var selected_model: Dictionary = {}

func _ready():
	_setup_tree()
	_setup_filters()
	_connect_signals()
	_load_leaderboard()

func _setup_tree():
	tree.set_column_title(0, "Rank")
	tree.set_column_title(1, "Model")
	tree.set_column_title(2, "Provider")
	tree.set_column_title(3, "Score")
	tree.set_column_title(4, "Success %")
	tree.set_column_title(5, "Avg Profit")
	tree.set_column_title(6, "Tokens")
	tree.set_column_title(7, "Verified")
	
	tree.set_column_expand(0, false)
	tree.set_column_custom_minimum_width(0, 60)
	tree.set_column_expand(1, true)
	tree.set_column_custom_minimum_width(1, 200)

func _setup_filters():
	tier_filter.clear()
	tier_filter.add_item("All Tiers")
	tier_filter.add_item("Tier 0: Baseline")
	tier_filter.add_item("Tier 1: Moderate")
	tier_filter.add_item("Tier 2: Advanced")
	tier_filter.add_item("Tier 3: Expert")
	
	metric_filter.clear()
	metric_filter.add_item("Overall Score")
	metric_filter.add_item("Success Rate")
	metric_filter.add_item("Profit")
	metric_filter.add_item("Token Efficiency")

func _connect_signals():
	refresh_btn.pressed.connect(_load_leaderboard)
	export_btn.pressed.connect(_export_data)
	search_input.text_changed.connect(_on_filter_changed)
	tier_filter.item_selected.connect(_on_filter_changed)
	metric_filter.item_selected.connect(_on_filter_changed)
	verified_checkbox.toggled.connect(_on_filter_changed)
	tree.item_selected.connect(_on_model_selected)
	compare_btn.pressed.connect(_on_compare_pressed)
	replay_btn.pressed.connect(_on_replay_pressed)
	verify_btn.pressed.connect(_on_verify_pressed)

func _load_leaderboard():
	ApiClient.request_completed.connect(_on_leaderboard_received, CONNECT_ONE_SHOT)
	ApiClient.get_leaderboard()

func _on_leaderboard_received(endpoint: String, data: Variant):
	if endpoint != "/api/leaderboard":
		return
	
	if data is Array:
		leaderboard_data = data
	elif data is Dictionary and data.has("results"):
		leaderboard_data = data["results"]
	else:
		leaderboard_data = []
	
	_populate_tree()

func _populate_tree():
	tree.clear()
	var root = tree.create_item()
	
	var filtered = _apply_filters(leaderboard_data)
	var rank = 1
	
	for model in filtered:
		var item = tree.create_item(root)
		item.set_text(0, str(rank))
		item.set_text(1, model.get("model_name", "Unknown"))
		item.set_text(2, model.get("provider", ""))
		item.set_text(3, "%.2f" % model.get("overall_score", 0.0))
		item.set_text(4, "%.1f%%" % (model.get("success_rate", 0.0) * 100))
		item.set_text(5, "$%.2f" % model.get("avg_profit", 0.0))
		item.set_text(6, str(model.get("total_tokens", 0)))
		item.set_text(7, "✓" if model.get("verified", false) else "")
		item.set_metadata(0, model)
		rank += 1

func _apply_filters(data: Array) -> Array:
	var result = data.duplicate()
	
	# Search filter
	var search_text = search_input.text.to_lower()
	if !search_text.is_empty():
		result = result.filter(func(m): return m.get("model_name", "").to_lower().contains(search_text))
	
	# Tier filter
	var tier_idx = tier_filter.selected
	if tier_idx > 0:
		var tier_name = "tier_" + str(tier_idx - 1)
		result = result.filter(func(m): return m.get("tier", "") == tier_name)
	
	# Verified filter
	if verified_checkbox.button_pressed:
		result = result.filter(func(m): return m.get("verified", false))
	
	# Sort by metric
	var metric_idx = metric_filter.selected
	match metric_idx:
		0: result.sort_custom(func(a, b): return a.get("overall_score", 0) > b.get("overall_score", 0))
		1: result.sort_custom(func(a, b): return a.get("success_rate", 0) > b.get("success_rate", 0))
		2: result.sort_custom(func(a, b): return a.get("avg_profit", 0) > b.get("avg_profit", 0))
		3: result.sort_custom(func(a, b): return a.get("token_efficiency", 0) > b.get("token_efficiency", 0))
	
	return result

func _on_filter_changed(_value = null):
	_populate_tree()

func _on_model_selected():
	var selected = tree.get_selected()
	if selected:
		selected_model = selected.get_metadata(0)
		_update_details_panel()

func _update_details_panel():
	model_name_label.text = "Model: " + selected_model.get("model_name", "Unknown")
	success_rate_label.text = "Success Rate: %.1f%%" % (selected_model.get("success_rate", 0.0) * 100)
	avg_profit_label.text = "Avg Profit: $%.2f" % selected_model.get("avg_profit", 0.0)
	tokens_label.text = "Tokens Used: %d" % selected_model.get("total_tokens", 0)
	
	compare_btn.disabled = false
	replay_btn.disabled = false
	verify_btn.disabled = selected_model.get("verified", false)

func _export_data():
	# Future: Export filtered leaderboard to CSV
	print("Export triggered")

func _on_compare_pressed():
	# Future: Open comparison view
	print("Compare: ", selected_model.get("model_name", ""))

func _on_replay_pressed():
	# Future: Navigate to simulation replay
	print("Replay: ", selected_model.get("simulation_id", ""))

func _on_verify_pressed():
	# Future: Trigger reproducibility verification
	print("Verify: ", selected_model.get("model_name", ""))
