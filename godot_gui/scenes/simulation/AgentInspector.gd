extends PanelContainer

## AgentInspector.gd
## Displays detailed audit logs and internal state for a selected agent

signal close_requested
signal dump_requested(agent_id)

@onready var agent_name_lbl = $VBoxContainer/Header/HBoxContainer/AgentName
@onready var role_lbl = $VBoxContainer/TabContainer/Status/RoleLabel
@onready var state_lbl = $VBoxContainer/TabContainer/Status/StateLabel
@onready var thought_text = $VBoxContainer/TabContainer/Status/ThoughtPanel/ThoughtText
@onready var llm_stats = $VBoxContainer/TabContainer/Cognition/LLMStats
@onready var tool_call_list = $VBoxContainer/TabContainer/Cognition/ToolCallList
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
	
	# Load premium theme
	var theme = load("res://UITheme.tres")
	if theme:
		self.theme = theme
		
	# Setup ToolCallList
	tool_call_list.columns = 2
	tool_call_list.set_column_title(0, "Tool")
	tool_call_list.set_column_title(1, "Arguments")
	tool_call_list.column_titles_visible = true
	
	close_btn.modulate = Color(1.0, 0.4, 0.4) # Make close button subtle red

func update_agent_data(agent_data: Dictionary):
	current_agent_id = agent_data.get("id", agent_data.get("slug", "Unknown"))
	agent_name_lbl.text = "Agent: " + current_agent_id
	
	# Update Status
	var role = agent_data.get("role", "Trader")
	var state = agent_data.get("state", "Idle")
	role_lbl.text = "[b]Role:[/b] " + role
	state_lbl.text = "[b]State:[/b] " + _get_colored_state(state)
	
	# Update "Thought" / Reasoning (Primary Value Prop)
	var thought = agent_data.get("last_reasoning", "No active train of thought.")
	if thought.strip_edges() == "":
		thought = "Wait... (Agent is contemplating next move)"
	thought_text.text = thought
	
	# Update Cognition (Tool Calls & LLM Stats)
	_update_llm_stats(agent_data.get("llm_usage", {}))
	_update_tool_calls(agent_data.get("last_tool_calls", []))
	
	# Update Financials
	var financials = agent_data.get("financials", {})
	cash_val.text = "$%.2f" % financials.get("cash", 0.0)
	inv_val.text = "$%.2f" % financials.get("inventory_value", 0.0)
	
	var profit = financials.get("net_profit", 0.0)
	profit_val.text = ("+" if profit >= 0 else "") + "$%.2f" % profit
	profit_val.add_theme_color_override("font_color", Color.GREEN if profit >= 0 else Color.RED)
	
	# Update Logs
	var events = agent_data.get("recent_events", [])
	log_list.clear()
	for evt in events:
		log_list.add_item(str(evt))

func _update_llm_stats(usage: Dictionary):
	if usage.is_empty():
		llm_stats.text = "[color=gray]No LLM activity recorded for this turn.[/color]"
		return
		
	var prompt = usage.get("prompt_tokens", 0)
	var completion = usage.get("completion_tokens", 0)
	var total = usage.get("total_tokens", prompt + completion)
	var cost = usage.get("total_cost_usd", 0.0)
	
	llm_stats.text = "[b]LLM Performance:[/b]\n" + \
		"• Tokens: %d (P: %d, C: %d)\n" % [total, prompt, completion] + \
		"• Est. Cost: [color=yellow]$%.4f[/color]" % cost

func _update_tool_calls(calls: Array):
	tool_call_list.clear()
	var root = tool_call_list.create_item()
	
	if calls.is_empty():
		var item = tool_call_list.create_item(root)
		item.set_text(0, "None")
		item.set_text(1, "No tool calls in last decision cycle.")
		return
		
	for call in calls:
		var item = tool_call_list.create_item(root)
		var tool_name = call.get("function", {}).get("name", "unknown")
		var args = call.get("function", {}).get("arguments", "{}")
		
		# If args is a stringified JSON, try to make it prettier
		if args is String and args.length() > 50:
			args = args.substr(0, 47) + "..."
			
		item.set_text(0, tool_name)
		item.set_text(1, str(args))
		item.set_tooltip_text(1, str(call.get("function", {}).get("arguments", "")))

func _get_colored_state(state: String) -> String:
	match state.to_lower():
		"active", "buying", "selling", "deciding":
			return "[color=#a3e635]" + state + "[/color]" # Neon Green
		"bankrupt", "error", "failed":
			return "[color=#f87171]" + state + "[/color]" # Soft Red
		"idle", "waiting", "sleeping":
			return "[color=#fbbf24]" + state + "[/color]" # Amber
		_:
			return state
