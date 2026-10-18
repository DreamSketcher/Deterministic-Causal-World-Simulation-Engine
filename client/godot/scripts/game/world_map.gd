class_name WorldMap
extends Node2D
## Draws the grid of cells and reports a click on one of them.
##
## Cells are placed by the core's own grid coordinates (x, y). The camera
## pans with the right or middle mouse button and zooms with the wheel;
## a left click selects a cell. Clicks on the HUD never reach this node
## (the HUD consumes them), so the map only sees clicks on empty space.

signal cell_selected(cell_id: String)

const CELL_SIZE: float = 84.0
const CELL_GAP: float = 8.0
const ZOOM_STEP: float = 1.15
const ZOOM_MIN: float = 0.4
const ZOOM_MAX: float = 3.0
const HUD_OFFSET: Vector2 = Vector2(-200.0, 0.0)  ## centre the map left of the side panel

var _cells: Array[Dto.Cell] = []
var _agent_region: String = ""
var _selected: String = ""
var _camera: Camera2D
var _dragging: bool = false
var _framed: bool = false


func _ready() -> void:
	_camera = Camera2D.new()
	_camera.offset = HUD_OFFSET
	add_child(_camera)
	_camera.make_current()


func set_view(view: Dto.View) -> void:
	_cells = view.cells
	_agent_region = view.region
	if not _framed and not _cells.is_empty():
		_frame_grid()
		_framed = true
	queue_redraw()


## Forget the cells (a new life starts on an empty map).
func clear() -> void:
	_cells = []
	_selected = ""
	_framed = false
	queue_redraw()


func select(cell_id: String) -> void:
	_selected = cell_id
	queue_redraw()


func _frame_grid() -> void:
	var lo: Vector2i = _cells[0].grid
	var hi: Vector2i = _cells[0].grid
	for c: Dto.Cell in _cells:
		lo = Vector2i(mini(lo.x, c.grid.x), mini(lo.y, c.grid.y))
		hi = Vector2i(maxi(hi.x, c.grid.x), maxi(hi.y, c.grid.y))
	var centre: Vector2 = (_origin(lo) + _origin(hi) + Vector2(CELL_SIZE, CELL_SIZE)) * 0.5
	_camera.position = centre


func _origin(grid: Vector2i) -> Vector2:
	return Vector2(grid) * (CELL_SIZE + CELL_GAP)


func _cell_rect(c: Dto.Cell) -> Rect2:
	return Rect2(_origin(c.grid), Vector2(CELL_SIZE, CELL_SIZE))


func _cell_color(c: Dto.Cell) -> Color:
	if c.land_active == 0:
		return Color(0.22, 0.20, 0.18)  # wild land: not yet worked
	var fertility: float = clampf(c.soil_fertility, 0.0, 1.0)
	return Color(0.16 + 0.30 * (1.0 - fertility), 0.30 + 0.45 * fertility, 0.18)


func _draw() -> void:
	var font: Font = ThemeDB.fallback_font
	for c: Dto.Cell in _cells:
		var rect: Rect2 = _cell_rect(c)
		draw_rect(rect, _cell_color(c))
		if c.region == _agent_region:
			draw_rect(rect.grow(-3.0), Color(0.95, 0.85, 0.35, 0.35), false, 2.0)
		if c.id == _selected:
			draw_rect(rect.grow(3.0), Color(1.0, 1.0, 1.0), false, 3.0)
		draw_string(font, rect.position + Vector2(6.0, 18.0), c.id,
			HORIZONTAL_ALIGNMENT_LEFT, -1.0, 14, Color.WHITE)
		draw_string(font, rect.position + Vector2(6.0, 38.0),
			"нас. %d" % roundi(c.population), HORIZONTAL_ALIGNMENT_LEFT, -1.0, 13,
			Color(1, 1, 1, 0.9))
		draw_string(font, rect.position + Vector2(6.0, 58.0),
			"еда %d" % roundi(c.food_stock), HORIZONTAL_ALIGNMENT_LEFT, -1.0, 13,
			Color(1, 1, 1, 0.75))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		match button.button_index:
			MOUSE_BUTTON_WHEEL_UP:
				if button.pressed:
					_zoom(ZOOM_STEP)
			MOUSE_BUTTON_WHEEL_DOWN:
				if button.pressed:
					_zoom(1.0 / ZOOM_STEP)
			MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE:
				_dragging = button.pressed
				Trace.log("map", "pan %s" % ("start" if _dragging else "end"))
			MOUSE_BUTTON_LEFT:
				if button.pressed:
					_click(get_global_mouse_position())
	elif event is InputEventMouseMotion and _dragging:
		var motion := event as InputEventMouseMotion
		_camera.position -= motion.relative / _camera.zoom.x


func _zoom(factor: float) -> void:
	var z: float = clampf(_camera.zoom.x * factor, ZOOM_MIN, ZOOM_MAX)
	_camera.zoom = Vector2(z, z)
	Trace.log("map", "zoom %.2f" % z)


func _click(world_point: Vector2) -> void:
	for c: Dto.Cell in _cells:
		if _cell_rect(c).has_point(world_point):
			Trace.log("map", "click at world %s → cell %s (grid %s)" % [
				world_point, c.id, c.grid,
			])
			_selected = c.id
			queue_redraw()
			cell_selected.emit(c.id)
			return
	Trace.log("map", "click at world %s → no cell" % world_point)
