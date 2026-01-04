extends Node

## ApiClient.gd
## Handles REST API communication with the FBA-Bench backend.

signal request_completed(endpoint: String, response: Variant)
signal request_failed(endpoint: String, error: String)

const BASE_URL = "http://localhost:8000"

func _ready():
	process_mode = PROCESS_MODE_ALWAYS

## Generic GET request
func get_request(endpoint: String) -> void:
	var http_request = HTTPRequest.new()
	add_child(http_request)
	http_request.request_completed.connect(_on_request_completed.bind(http_request, endpoint))
	
	var error = http_request.request(BASE_URL + endpoint)
	if error != OK:
		request_failed.emit(endpoint, "Failed to initiate request: " + str(error))
		http_request.queue_free()

## Generic POST request
func post_request(endpoint: String, data: Dictionary) -> void:
	var http_request = HTTPRequest.new()
	add_child(http_request)
	http_request.request_completed.connect(_on_request_completed.bind(http_request, endpoint))
	
	var json_data = JSON.stringify(data)
	var headers = ["Content-Type: application/json"]
	
	var error = http_request.request(BASE_URL + endpoint, headers, HTTPClient.METHOD_POST, json_data)
	if error != OK:
		request_failed.emit(endpoint, "Failed to initiate POST request: " + str(error))
		http_request.queue_free()

func _on_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray, http_request: HTTPRequest, endpoint: String):
	if result != HTTPRequest.RESULT_SUCCESS:
		request_failed.emit(endpoint, "HTTP Request failed with result: " + str(result))
	elif response_code >= 400:
		request_failed.emit(endpoint, "HTTP Error " + str(response_code) + ": " + body.get_string_from_utf8())
	else:
		var json = JSON.parse_string(body.get_string_from_utf8())
		request_completed.emit(endpoint, json)
	
	http_request.queue_free()

# Specific helper methods for FBA-Bench endpoints
func get_simulation_status() -> void:
	get_request("/api/simulation/status")

func get_leaderboard() -> void:
	get_request("/api/leaderboard")

func start_simulation(config: Dictionary) -> void:
	post_request("/api/simulation/start", config)
