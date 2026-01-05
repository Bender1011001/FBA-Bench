extends Node

## WebSocketClient.gd
## Manages real-time WebSocket connection for simulation updates.
## Uses the topic-based /ws/realtime protocol.

signal connected
signal disconnected
signal message_received(data: Dictionary)
signal error_occurred(error: String)
signal topic_subscribed(topic: String)

var socket: WebSocketPeer = WebSocketPeer.new()
var is_connected: bool = false
var last_state: int = WebSocketPeer.STATE_CLOSED
var pending_subscriptions: Array[String] = []

const WS_URL = "ws://localhost:8000/ws/realtime"

func _ready():
	set_process(true)

func connect_to_server():
	if is_connected or socket.get_ready_state() == WebSocketPeer.STATE_CONNECTING:
		return
	socket.connect_to_url(WS_URL)
	print("[WS] Connecting to: ", WS_URL)

func disconnect_from_server():
	socket.close()

func subscribe_topic(topic: String):
	if is_connected:
		_send_subscribe(topic)
	else:
		pending_subscriptions.append(topic)

func _send_subscribe(topic: String):
	var msg = {"type": "subscribe", "topic": topic}
	socket.send_text(JSON.stringify(msg))
	print("[WS] Subscribing to topic: ", topic)

func send_ping():
	if is_connected:
		socket.send_text(JSON.stringify({"type": "ping"}))

func _process(_delta):
	socket.poll()
	var state = socket.get_ready_state()
	
	if state != last_state:
		_handle_state_change(state)
		last_state = state
	
	if state == WebSocketPeer.STATE_OPEN:
		while socket.get_available_packet_count() > 0:
			var packet = socket.get_packet()
			var message_str = packet.get_string_from_utf8()
			var data = JSON.parse_string(message_str)
			if data is Dictionary:
				_handle_server_message(data)
			else:
				print("[WS] Received non-JSON message: ", message_str)

func _handle_state_change(new_state: int):
	match new_state:
		WebSocketPeer.STATE_OPEN:
			is_connected = true
			connected.emit()
			print("[WS] Connected")
			# Process pending subscriptions
			for topic in pending_subscriptions:
				_send_subscribe(topic)
			pending_subscriptions.clear()
		WebSocketPeer.STATE_CLOSED:
			is_connected = false
			disconnected.emit()
			print("[WS] Disconnected")
		WebSocketPeer.STATE_CONNECTING:
			print("[WS] Connecting...")
		WebSocketPeer.STATE_CLOSING:
			print("[WS] Closing...")

func _handle_server_message(msg: Dictionary):
	var msg_type = msg.get("type", "")
	
	match msg_type:
		"connection_established":
			print("[WS] Connection acknowledged by server")
		"subscribed":
			var topic = msg.get("topic", "")
			topic_subscribed.emit(topic)
			print("[WS] Subscribed to: ", topic)
		"event":
			# This is the main data payload
			var event_data = msg.get("data", {})
			if event_data is Dictionary:
				message_received.emit(event_data)
		"pong":
			print("[WS] Pong received")
		"error":
			var error_msg = msg.get("error", "Unknown error")
			error_occurred.emit(error_msg)
			print("[WS] Error: ", error_msg)
		"warning":
			print("[WS] Warning: ", msg.get("message", ""))
		_:
			print("[WS] Unknown message type: ", msg_type)

func send_data(data: Dictionary):
	if is_connected:
		socket.send_text(JSON.stringify(data))
	else:
		error_occurred.emit("Cannot send data: Not connected")
