extends Node

## UiDesignSystem.gd
## Centralized design tokens, scaling, and theme application for the Godot GUI.

const THEME_PATH := "res://themes/ObserverTheme.tres"
const BASE_REFERENCE_HEIGHT := 1080.0
const MIN_UI_SCALE := 1.0
const MAX_UI_SCALE := 1.45
const RECORDING_WINDOW_SIZE := Vector2i(1920, 1080)

# Spacing tokens (8pt-ish scale).
const SPACE_1 := 6
const SPACE_2 := 10
const SPACE_3 := 14
const SPACE_4 := 20
const SPACE_5 := 28

# Type tokens.
const TYPE_LABEL := 15
const TYPE_BODY := 17
const TYPE_SECTION := 20
const TYPE_TITLE := 30

# Palette tokens.
const COLOR_BG := Color("#070D1A")
const COLOR_BG_ELEVATED := Color("#111C31")
const COLOR_BG_CARD := Color("#142645")
const COLOR_TEXT := Color("#E8F0FF")
const COLOR_TEXT_MUTED := Color("#95A8C9")
const COLOR_ACCENT := Color("#30B7FF")
const COLOR_GOOD := Color("#8EE67A")
const COLOR_WARN := Color("#FFC470")
const COLOR_DANGER := Color("#FF7E89")

var _theme: Theme

func _ready() -> void:
	_load_theme()
	_apply_scale_to_window()
	var window := get_window()
	if window != null and not window.size_changed.is_connected(_on_window_size_changed):
		window.size_changed.connect(_on_window_size_changed)

func _on_window_size_changed() -> void:
	_apply_scale_to_window()

func _load_theme() -> void:
	if _theme != null:
		return
	if ResourceLoader.exists(THEME_PATH):
		_theme = load(THEME_PATH)

func get_theme() -> Theme:
	_load_theme()
	return _theme

func apply_to_control(control: Control) -> void:
	if control == null:
		return
	var theme := get_theme()
	if theme != null:
		control.theme = theme

func apply_tokens_to_margin(container: MarginContainer, size_token: int = SPACE_4) -> void:
	if container == null:
		return
	container.add_theme_constant_override("margin_left", size_token)
	container.add_theme_constant_override("margin_right", size_token)
	container.add_theme_constant_override("margin_top", size_token)
	container.add_theme_constant_override("margin_bottom", size_token)

func set_recording_layout(enabled: bool) -> void:
	var window := get_window()
	if window == null:
		return
	if enabled:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		window.size = RECORDING_WINDOW_SIZE
		window.position = Vector2i(40, 40)
	_apply_scale_to_window()

func ui_scale_for_viewport(viewport_size: Vector2i) -> float:
	var ratio := float(viewport_size.y) / BASE_REFERENCE_HEIGHT
	return clamp(ratio, MIN_UI_SCALE, MAX_UI_SCALE)

func _apply_scale_to_window() -> void:
	var window := get_window()
	if window == null:
		return
	window.content_scale_factor = ui_scale_for_viewport(window.size)