extends PanelContainer

class_name StoryFeedPanel

@onready var title_label: Label = $Margin/VBox/Title
@onready var feed_label: RichTextLabel = $Margin/VBox/Feed

var _lines: Array[String] = []
var max_lines := 14

func _ready() -> void:
	theme_type_variation = &"ObserverInsetPanel"
	feed_label.bbcode_enabled = true
	feed_label.scroll_active = false

func set_title(text_value: String) -> void:
	title_label.text = text_value

func clear_feed(placeholder: String = "[color=gray]Waiting for tick data...[/color]") -> void:
	_lines.clear()
	feed_label.text = placeholder

func append_line(line: String) -> void:
	_lines.append(line)
	while _lines.size() > max_lines:
		_lines.pop_front()
	feed_label.text = "\n".join(_lines)

func set_lines(lines: Array[String]) -> void:
	_lines = lines.duplicate()
	while _lines.size() > max_lines:
		_lines.pop_front()
	feed_label.text = "\n".join(_lines)

func get_lines() -> Array[String]:
	return _lines.duplicate()