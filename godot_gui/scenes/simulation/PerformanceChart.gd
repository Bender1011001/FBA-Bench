extends Control

## PerformanceChart.gd
## Simple real-time line graph for metrics

@export var line_color: Color = Color.CYAN
@export var label: String = "Metric"
@export var max_points: int = 50
@export var auto_scale: bool = true

var data_points: Array[float] = []
var max_value: float = 1.0
var min_value: float = 0.0

func _draw():
	if data_points.size() < 2:
		return
		
	var size = get_size()
	var step_x = size.x / float(max_points - 1)
	var points = PackedVector2Array()
	
	var range_v = max_value - min_value
	if range_v == 0: range_v = 1.0
	
	for i in range(data_points.size()):
		var val = data_points[i]
		var px = i * step_x
		var py = size.y - ((val - min_value) / range_v) * size.y
		points.append(Vector2(px, py))
		
	# Draw background grid
	draw_rect(Rect2(Vector2.ZERO, size), Color(1, 1, 1, 0.05))
	
	# Draw line
	draw_polyline(points, line_color, 2.0, true)
	
	# Draw label
	draw_string(ThemeDB.get_project_default_font(), Vector2(5, 15), "%s: %.1f" % [label, data_points[-1]], HORIZONTAL_ALIGNMENT_LEFT, -1, 10, line_color)

func add_point(value: float):
	data_points.append(value)
	if data_points.size() > max_points:
		data_points.remove_at(0)
		
	if auto_scale:
		_calculate_range()
	
	queue_redraw()

func _calculate_range():
	if data_points.is_empty():
		return
	max_value = data_points[0]
	min_value = data_points[0]
	for p in data_points:
		if p > max_value: max_value = p
		if p < min_value: min_value = p
	
	# Add some padding
	var padding = (max_value - min_value) * 0.1
	if padding == 0: padding = max_value * 0.1
	max_value += padding
	min_value -= padding
