extends Node

## ApiClient.gd
## Handles REST API communication with the FBA-Bench backend.

signal request_completed(endpoint: String, response: Variant)
signal request_failed(endpoint: String, error: String)

var base_url: String = "http://localhost:8080"

func _ready():
	process_mode = PROCESS_MODE_ALWAYS
	base_url = _normalize_base_url(_resolve_base_url())
	print("[API] Base URL: ", base_url)

func _resolve_base_url() -> String:
	# Prefer explicit HTTP base URL; fall back to generic base URL.
	var u = OS.get_environment("FBA_BENCH_HTTP_BASE_URL")
	if u == "":
		u = OS.get_environment("FBA_BENCH_BASE_URL")
	if u == "":
		u = "http://localhost:8080" # One-click demo default
	return u

func _normalize_base_url(u: String) -> String:
	if u.ends_with("/"):
		return u.substr(0, u.length() - 1)
	return u

## Generic GET request
func get_request(endpoint: String) -> void:
	var http_request = HTTPRequest.new()
	add_child(http_request)
	http_request.request_completed.connect(_on_request_completed.bind(http_request, endpoint))
	
	var error = http_request.request(base_url + endpoint)
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
	
	var error = http_request.request(base_url + endpoint, headers, HTTPClient.METHOD_POST, json_data)
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
	get_request("/api/v1/simulation/snapshot")

func get_leaderboard() -> void:
	get_request("/api/v1/leaderboard")

# Step 1: Create a simulation record (returns ID and websocket_topic)
func create_simulation(metadata: Dictionary = {}) -> void:
	post_request("/api/v1/simulation", {"metadata": metadata})

# Step 2: Start a previously created simulation by its ID
func start_simulation_by_id(simulation_id: String) -> void:
	post_request("/api/v1/simulation/%s/start" % simulation_id, {})

# Step 3: Run simulation (triggers background tick generation)
func run_simulation_by_id(simulation_id: String) -> void:
	post_request("/api/v1/simulation/%s/run" % simulation_id, {})

func get_scenarios() -> void:
	get_request("/api/v1/scenarios")

func get_models() -> void:
	get_request("/api/v1/llm/models")
