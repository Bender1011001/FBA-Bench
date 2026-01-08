extends Control

## PerformanceChart.gd
## Bloomberg-style real-time line graph for metrics

@export var line_color: Color = Color(0.0, 1.0, 0.6) # Cyan-Green suitable for dark backgrounds
@export var label: String = "Metric"
@export var max_points: int = 50
@export var auto_scale: bool = true

var data_points: Array[float] = []
var max_value: float = 1.0
var min_value: float = 0.0

const MARGIN_LEFT: float = 40.0
const MARGIN_BOTTOM: float = 20.0

func _draw():
	var size = get_size()
	var graph_rect = Rect2(MARGIN_LEFT, 0, size.x - MARGIN_LEFT, size.y - MARGIN_BOTTOM)
	
	# Draw background grid
	var range_v = max_value - min_value
	if range_v == 0: range_v = 1.0

	var grid_color = Color(0.5, 0.5, 0.5, 0.2)
	var font = ThemeDB.get_project_default_font()
	var font_size = 10
	
	# Vertical grid lines
	var num_v_lines = 10
	for i in range(num_v_lines + 1):
		var x = graph_rect.position.x + (i * graph_rect.size.x / num_v_lines)
		draw_line(Vector2(x, graph_rect.position.y), Vector2(x, graph_rect.end.y), grid_color)

	# Horizontal grid lines and Y-axis labels
	var num_h_lines = 5
	for i in range(num_h_lines + 1):
		var ratio = float(i) / float(num_h_lines)
		var y = graph_rect.end.y - (ratio * graph_rect.size.y)
		
		draw_line(Vector2(graph_rect.position.x, y), Vector2(graph_rect.end.x, y), grid_color)
		
		# Draw label
		var value = min_value + (ratio * range_v)
		var text = _format_currency(value)
		var text_size = font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
		draw_string(font, Vector2(5, y + text_size.y/3), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color.LIGHT_GRAY)

	if data_points.size() < 2:
		return
		
	var step_x = graph_rect.size.x / float(max_points - 1)
	var points = PackedVector2Array()
	
	for i in range(data_points.size()):
		var val = data_points[i]
		# Keep index relative to the end if we have less points than max? 
		# No, existing logic shifts data. i=0 is oldest.
		# If data_points is full (size == max_points), i=0 is start.
		# If data_points is growing, i=0 is start.
		# Ideally we anchor to the right? Current logic anchors to left.
		# Let's keep existing logic: spread points across width.
		
		# Recalculate step_x based on actual count if we want it to fill the screen progressively?
		# Or fixed step? Existing code: size.x / (max_points - 1). This implies it slowly fills.
		# That's fine.
		var px = graph_rect.position.x + (i * step_x)
		var py = graph_rect.end.y - ((val - min_value) / range_v) * graph_rect.size.y
		points.append(Vector2(px, py))
		
	# Draw Gradient Filled Polygon
	var polygon_points = points.duplicate()
	polygon_points.append(Vector2(points[-1].x, graph_rect.end.y))
	polygon_points.append(Vector2(points[0].x, graph_rect.end.y))
	
	var colors = PackedColorArray()
	var top_color = line_color
	top_color.a = 0.3
	var bottom_color = line_color
	bottom_color.a = 0.0
	
	for i in range(points.size()):
		colors.append(top_color)
	colors.append(bottom_color) # Bottom right
	colors.append(bottom_color) # Bottom left
	
	draw_polygon(polygon_points, colors)
	
	# Draw line
	draw_polyline(points, line_color, 2.0, true)
	
	# Draw label title
	draw_string(font, Vector2(graph_rect.position.x + 10, 20), "%s: %s" % [label, _format_currency(data_points[-1])], HORIZONTAL_ALIGNMENT_LEFT, -1, 14, line_color)

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
	if padding == 0: padding = abs(max_value) * 0.1 if max_value != 0 else 1.0
	max_value += padding
	min_value -= padding

func _format_currency(val: float) -> String:
	var abs_val = abs(val)
	var sign_str = ""
	if val < 0:
		sign_str = "-"
	
	if abs_val >= 1000000:
		return "%s$%.1fm" % [sign_str, abs_val / 1000000.0]
	elif abs_val >= 1000:
		return "%s$%.1fk" % [sign_str, abs_val / 1000.0]
	else:
		return "%s$%.0f" % [sign_str, abs_val]
