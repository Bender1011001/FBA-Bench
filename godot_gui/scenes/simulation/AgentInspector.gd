extends PanelContainer

## AgentInspector.gd
## Displays detailed audit logs and internal state for a selected agent

signal close_requested
signal dump_requested(agent_id)

@onready var agent_name_lbl = $VBoxContainer/Header/HBoxContainer/AgentName
@onready var role_lbl = $VBoxContainer/TabContainer/Status/RoleLabel
@onready var state_lbl = $VBoxContainer/TabContainer/Status/StateLabel
@onready var thought_text = $VBoxContainer/TabContainer/Status/ThoughtPanel/ThoughtText
@onready var cash_val = $VBoxContainer/TabContainer/Financials/CashRow/Value
@onready var inv_val = $VBoxContainer/TabContainer/Financials/InventoryRow/Value
@onready var profit_val = $VBoxContainer/TabContainer/Financials/ProfitRow/Value
@onready var log_list = $VBoxContainer/TabContainer/AuditLog/LogList
@onready var close_btn = $VBoxContainer/Header/HBoxContainer/CloseButton
@onready var debug_btn = $VBoxContainer/Actions/DebugButton

var current_agent_id: String = ""

func _ready():
	close_btn.pressed.connect(func(): close_requested.emit())
	debug_btn.pressed.connect(func(): dump_requested.emit(current_agent_id))

func update_agent_data(agent_data: Dictionary):
	current_agent_id = agent_data.get("id", "Unknown")
	agent_name_lbl.text = "Agent: " + current_agent_id
	
	# Update Status
	var role = agent_data.get("role", "Trader")
	var state = agent_data.get("state", "Idle")
	role_lbl.text = "[b]Role:[/b] " + role
	state_lbl.text = "[b]State:[/b] " + _get_colored_state(state)
	
	# Update "Thought" / Reasoning
	# Assuming the backend sends a "last_reasoning" field
	var thought = agent_data.get("last_reasoning", "No active train of thought.")
	thought_text.text = thought
	
	# Update Financials
	var financials = agent_data.get("financials", {})
	cash_val.text = "$%.2f" % financials.get("cash", 0.0)
	inv_val.text = "$%.2f" % financials.get("inventory_value", 0.0)
	
	var profit = financials.get("net_profit", 0.0)
	profit_val.text = ("+" if profit >= 0 else "") + "$%.2f" % profit
	profit_val.add_theme_color_override("font_color", Color.GREEN if profit >= 0 else Color.RED)
	
	# Update Logs
	# Assuming backend sends recent events
	var events = agent_data.get("recent_events", [])
	log_list.clear()
	for evt in events:
		log_list.add_item(evt)

func _get_colored_state(state: String) -> String:
	match state.to_lower():
		"active", "buying", "selling":
			return "[color=green]" + state + "[/color]"
		"bankrupt", "error":
			return "[color=red]" + state + "[/color]"
		"idle", "waiting":
			return "[color=yellow]" + state + "[/color]"
		_:
			return state
