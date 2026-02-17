extends PanelContainer

class_name MetricCard

enum Tone {
	NEUTRAL,
	GOOD,
	WARN,
	DANGER,
}

@onready var title_label: Label = $Margin/VBox/Title
@onready var value_label: Label = $Margin/VBox/Value
@onready var delta_label: Label = $Margin/VBox/Delta

func _ready() -> void:
	theme_type_variation = &"ObserverInsetPanel"

func configure(title: String, value_text: String, delta_text: String, tone: Tone = Tone.NEUTRAL) -> void:
	set_title(title)
	set_value(value_text)
	set_delta(delta_text, tone)

func set_title(text_value: String) -> void:
	title_label.text = text_value

func set_value(text_value: String) -> void:
	value_label.text = text_value

func set_delta(text_value: String, tone: Tone = Tone.NEUTRAL) -> void:
	delta_label.text = text_value
	match tone:
		Tone.GOOD:
			delta_label.modulate = Color("#8EE67A")
		Tone.WARN:
			delta_label.modulate = Color("#FFC470")
		Tone.DANGER:
			delta_label.modulate = Color("#FF7E89")
		_:
			delta_label.modulate = Color("#95A8C9")