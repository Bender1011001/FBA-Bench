extends PanelContainer

class_name ReplayControlsBar

signal live_requested
signal play_toggled(is_playing: bool)
signal scrub_requested(index: int)
signal speed_changed(multiplier: float)

@onready var mode_label: Label = $Margin/Row/Mode
@onready var live_button: Button = $Margin/Row/Live
@onready var play_button: Button = $Margin/Row/PlayPause
@onready var scrubber: HSlider = $Margin/Row/Scrubber
@onready var tick_label: Label = $Margin/Row/Tick
@onready var speed_option: OptionButton = $Margin/Row/Speed

var _updating: bool = false
var _is_playing: bool = false

const SPEED_STEPS: Array[float] = [0.5, 1.0, 1.5, 2.0, 3.0]

func _ready() -> void:
	theme_type_variation = &"ObserverPanel"
	for value in SPEED_STEPS:
		speed_option.add_item("x%.1f" % value)
	speed_option.select(1)

	live_button.pressed.connect(func():
		live_requested.emit()
	)
	play_button.pressed.connect(func():
		_is_playing = !_is_playing
		_apply_play_button_text()
		play_toggled.emit(_is_playing)
	)
	scrubber.value_changed.connect(_on_scrubber_changed)
	speed_option.item_selected.connect(_on_speed_selected)

func set_state(mode_text: String, total_frames: int, cursor: int, is_playing: bool, is_live: bool, can_play: bool, speed: float) -> void:
	_updating = true
	mode_label.text = mode_text
	var max_idx: int = maxi(0, total_frames - 1)
	scrubber.max_value = float(max_idx)
	scrubber.step = 1.0
	scrubber.editable = total_frames > 1
	scrubber.value = float(clamp(cursor, 0, max_idx))
	live_button.disabled = is_live
	play_button.disabled = not can_play
	_is_playing = is_playing and can_play
	_apply_play_button_text()
	tick_label.text = "T%03d / %03d" % [max(0, cursor), max_idx]

	var nearest_idx: int = 0
	var nearest_dist: float = 9999.0
	for i in range(SPEED_STEPS.size()):
		var d: float = absf(float(SPEED_STEPS[i]) - speed)
		if d < nearest_dist:
			nearest_dist = d
			nearest_idx = i
	speed_option.select(nearest_idx)
	_updating = false

func _apply_play_button_text() -> void:
	play_button.text = "Pause" if _is_playing else "Play"

func _on_scrubber_changed(value: float) -> void:
	if _updating:
		return
	scrub_requested.emit(int(round(value)))

func _on_speed_selected(index: int) -> void:
	if _updating:
		return
	if index < 0 or index >= SPEED_STEPS.size():
		return
	speed_changed.emit(float(SPEED_STEPS[index]))
