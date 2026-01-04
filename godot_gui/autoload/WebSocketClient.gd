extends Node

## WebSocketClient.gd
## Manages real-time WebSocket connection for simulation updates.

signal connected
signal disconnected
signal message_received(data: Dictionary)
signal error_occurred(error: String)

var socket: WebSocketPeer = WebSocketPeer.new()
var is_connected: bool = false
var last_state: int = WebSocketPeer.STATE_CLOSED

const WS_URL = "ws://localhost:8000/ws/simulation"

func _ready():
	set_process(true)

func connect_to_server(sim_id: String = ""):
	var url = WS_URL
	if !sim_id.is_empty():
		url += "/" + sim_id
	
	socket.connect_to_url(url)
	print("Connecting to WebSocket: ", url)

func disconnect_from_server():
	socket.close()

func _process(_delta):
	socket.poll()
	var state = socket.get_ready_state()
	
	if state != last_state:
		_handle_state_change(state)
		last_state = state
	
	if state == WebSocketPeer.STATE_OPEN:
		while socket.get_available_packet_count() > 0:
			var packet = socket.get_packet()
			var message = packet.get_string_from_utf8()
			var data = JSON.parse_string(message)
			if data is Dictionary:
				message_received.emit(data)
			else:
				print("Received non-JSON or invalid message: ", message)

func _handle_state_change(new_state: int):
	match new_state:
		WebSocketPeer.STATE_OPEN:
			is_connected = true
			connected.emit()
			print("WebSocket Connected")
		WebSocketPeer.STATE_CLOSED:
			is_connected = false
			disconnected.emit()
			print("WebSocket Disconnected")
		WebSocketPeer.STATE_CONNECTING:
			print("WebSocket Connecting...")
		WebSocketPeer.STATE_CLOSING:
			print("WebSocket Closing...")

func send_data(data: Dictionary):
	if is_connected:
		socket.send_text(JSON.stringify(data))
	else:
		error_occurred.emit("Cannot send data: Not connected")
