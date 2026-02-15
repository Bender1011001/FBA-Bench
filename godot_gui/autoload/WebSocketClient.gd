extends Node

## WebSocketClient.gd
## Manages real-time WebSocket connection for simulation updates.
## Uses the topic-based /ws/realtime protocol.

signal connected
signal disconnected
signal message_received(data: Dictionary)
signal topic_message_received(topic: String, data: Dictionary)
signal error_occurred(error: String)
signal topic_subscribed(topic: String)

# Specialized signals for common events
signal tick_received(tick_data: Dictionary)
signal agent_event_received(agent_id: String, event_type: String, data: Dictionary)
signal market_event_received(data: Dictionary)

var ws_url: String = "ws://localhost:8080/ws/realtime"
const RECONNECT_DELAY = 3.0
const PING_INTERVAL = 20.0

var socket: WebSocketPeer = WebSocketPeer.new()
var is_connected: bool = false
var last_state: int = WebSocketPeer.STATE_CLOSED
var subscriptions: Array[String] = []
var reconnect_timer: float = 0.0
var ping_timer: float = 0.0
var auto_reconnect: bool = true

func _ready():
	set_process(true)
	ws_url = _resolve_ws_url()
	print("[WS] URL: ", ws_url)
	# Optional: connect_to_server()

func _resolve_ws_url() -> String:
	# Prefer explicit WS URL. Otherwise derive from HTTP base URL envs.
	var u = OS.get_environment("FBA_BENCH_WS_URL")
	if u != "":
		return _normalize_url(u)

	var http_base = OS.get_environment("FBA_BENCH_HTTP_BASE_URL")
	if http_base == "":
		http_base = OS.get_environment("FBA_BENCH_BASE_URL")
	if http_base == "":
		return "ws://localhost:8080/ws/realtime" # One-click demo default

	return _derive_ws_url(_normalize_url(http_base))

func _normalize_url(u: String) -> String:
	if u.ends_with("/"):
		return u.substr(0, u.length() - 1)
	return u

func _derive_ws_url(http_base: String) -> String:
	var base = http_base
	if base.begins_with("https://"):
		base = "wss://" + base.substr(8)
	elif base.begins_with("http://"):
		base = "ws://" + base.substr(7)
	# If caller already provided a ws(s) URL, keep it.
	if base.find("/ws/") == -1:
		base += "/ws/realtime"
	return base

func connect_to_server():
	if socket.get_ready_state() != WebSocketPeer.STATE_CLOSED:
		return
	
	socket.connect_to_url(ws_url)
	print("[WS] Connecting to: ", ws_url)

func disconnect_from_server():
	auto_reconnect = false
	socket.close()

func subscribe_topic(topic: String):
	if not topic in subscriptions:
		subscriptions.append(topic)
	
	if is_connected:
		_send_subscribe(topic)

func unsubscribe_topic(topic: String):
	subscriptions.erase(topic)
	if is_connected:
		_send_unsubscribe(topic)

func _send_subscribe(topic: String):
	var msg = {"type": "subscribe", "topic": topic}
	socket.send_text(JSON.stringify(msg))
	print("[WS] Subscribing to topic: ", topic)

func _send_unsubscribe(topic: String):
	var msg = {"type": "unsubscribe", "topic": topic}
	socket.send_text(JSON.stringify(msg))
	print("[WS] Unsubscribing from topic: ", topic)

func _process(delta):
	socket.poll()
	var state = socket.get_ready_state()
	
	if state != last_state:
		_handle_state_change(state)
		last_state = state
	
	if state == WebSocketPeer.STATE_OPEN:
		is_connected = true
		_process_messages()
		_process_ping(delta)
	elif state == WebSocketPeer.STATE_CLOSED:
		is_connected = false
		if auto_reconnect:
			_process_reconnect(delta)

func _process_messages():
	while socket.get_available_packet_count() > 0:
		var packet = socket.get_packet()
		var message_str = packet.get_string_from_utf8()
		var data = JSON.parse_string(message_str)
		if data is Dictionary:
			_handle_server_message(data)
		else:
			print("[WS] Received non-JSON message: ", message_str)

func _process_ping(delta):
	ping_timer += delta
	if ping_timer >= PING_INTERVAL:
		ping_timer = 0.0
		send_ping()

func _process_reconnect(delta):
	reconnect_timer += delta
	if reconnect_timer >= RECONNECT_DELAY:
		reconnect_timer = 0.0
		print("[WS] Attempting auto-reconnect...")
		connect_to_server()

func send_command(command: String, params: Dictionary = {}):
	if is_connected:
		var msg = {
			"type": "command",
			"command": command,
			"params": params,
			"ts": Time.get_datetime_string_from_system()
		}
		socket.send_text(JSON.stringify(msg))
		print("[WS] Sent command: ", command)
	else:
		error_occurred.emit("Cannot send command: Not connected")

func _handle_state_change(new_state: int):
	match new_state:
		WebSocketPeer.STATE_OPEN:
			print("[WS] Connected")
			connected.emit()
			reconnect_timer = 0.0
			ping_timer = 0.0
			# Resubscribe to all topics
			for topic in subscriptions:
				_send_subscribe(topic)
		WebSocketPeer.STATE_CLOSED:
			print("[WS] Disconnected")
			is_connected = false
			disconnected.emit()
		WebSocketPeer.STATE_CONNECTING:
			print("[WS] Connecting...")
		WebSocketPeer.STATE_CLOSING:
			print("[WS] Closing...")

func _handle_server_message(msg: Dictionary):
	var msg_type = msg.get("type", "")
	
	match msg_type:
		"connection_established":
			print("[WS] Connection established: ", msg.get("message", ""))
		"subscribed":
			var topic = msg.get("topic", "")
			topic_subscribed.emit(topic)
			print("[WS] Confirmed subscription: ", topic)
		"unsubscribed":
			print("[WS] Confirmed unsubscription: ", msg.get("topic", ""))
		"event":
			var topic = msg.get("topic", "")
			var event_data = msg.get("data", {})
			# Emit both generic and topic-specific signals
			message_received.emit(event_data)
			topic_message_received.emit(topic, event_data)
			
			# Dispatch specialized signals based on content/topic
			if event_data.has("type"):
				match event_data["type"]:
					"tick":
						tick_received.emit(event_data)
					"agent_decision", "agent_action":
						agent_event_received.emit(event_data.get("agent_id", ""), event_data["type"], event_data)
			elif topic.contains("simulation-progress") and event_data.has("tick"):
				# Handle the fallback "simulation-progress" topic format
				tick_received.emit(event_data)
			
			if topic.contains("market"):
				market_event_received.emit(event_data)
		"pong":
			# Heartbeat received
			pass
		"error":
			var error_msg = msg.get("error", "Unknown error")
			error_occurred.emit(error_msg)
			print("[WS] Error: ", error_msg)
		"warning":
			print("[WS] Warning: ", msg.get("message", ""))
		_:
			print("[WS] Unknown message type: ", msg_type)

func send_ping():
	if is_connected:
		socket.send_text(JSON.stringify({"type": "ping"}))

func send_data(data: Dictionary):
	if is_connected:
		socket.send_text(JSON.stringify(data))
	else:
		error_occurred.emit("Cannot send data: Not connected")

func publish(topic: String, data: Dictionary):
	if is_connected:
		var msg = {
			"type": "publish",
			"topic": topic,
			"data": data
		}
		socket.send_text(JSON.stringify(msg))
	else:
		error_occurred.emit("Cannot publish: Not connected")
