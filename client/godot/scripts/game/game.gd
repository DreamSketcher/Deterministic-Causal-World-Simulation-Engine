class_name Game
extends Node2D
## The slice controller: starts the Python core, drives the protocol, shows
## the world and the real result of each action.
##
## Flow:  ready -> hello -> welcome -> look -> view   (the map exists, no step)
##        decide -> frame                              (one action = one tick)
##
## Rules of this file:
## * one request in flight at a time; the action button is disabled meanwhile;
## * every reply is checked against contract/v1.json; a violating reply is
##   logged and NOT drawn — nothing is silently accepted;
## * the client computes no game state. "What changed" is two facts side by
##   side (the view before and the frame after), printed as they are.

const PROTOCOL: String = "causal-world-jsonl/1"
const START: Dictionary = {
	"seed": 7,
	"ruleset": "player_resettle",
	"regions": 2,
	"agents": 54,
	"max_ticks": 200,
}
## The one player action of the slice: "work" in the core's action card.
const PLAYER_ACTION: int = 0
const ACTION_LABEL: String = "Работать (work) · ход"
const MAX_CHANGE_LINES: int = 12

var _contract: Dictionary = {}
var _bridge: PyBridge
var _map: WorldMap
var _panel: CellPanel
var _status: Label
var _act_button: Button
var _log: RichTextLabel

var _view: Dto.View = null  ## the world now (a view, or the last frame)
var _before: Dto.View = null  ## the world before the last decision
var _last_seq: int = 0
var _waiting: String = ""  ## the request kind in flight, "" when idle
var _finished: bool = false
var _selected_cell: String = ""
var _db_dir: String = ""


func _ready() -> void:
	_contract = Dto.load_contract()
	_build_ui()
	_bridge = PyBridge.new()
	add_child(_bridge)
	_bridge.line_received.connect(_on_line)
	_bridge.bridge_failed.connect(_on_bridge_failed)
	_bridge.bridge_ended.connect(_on_bridge_ended)

	var python: String = _resolve_python()
	var src: String = _resolve_src()
	_db_dir = ProjectSettings.globalize_path("user://worlds")
	_set_status("Запуск ядра: %s" % python)
	_log_line("[b]Ядро:[/b] %s" % python)
	_log_line("[b]Исходники:[/b] %s" % src)
	_log_line("[b]Архивы миров:[/b] %s" % _db_dir)
	_bridge.start(python, src, _db_dir)


func _process(_delta: float) -> void:
	_bridge.poll()


# ----------------------------------------------------------- protocol ----

func _on_line(line: String) -> void:
	var parsed: Variant = Dto.parse_line(line)
	if typeof(parsed) != TYPE_DICTIONARY:
		_log_line("[color=red]Ядро прислало не JSON-объект:[/color] %s" % line.left(120))
		return
	var msg: Dictionary = parsed
	match str(msg.get("type", "")):
		"ready":
			_on_ready(msg)
		"welcome":
			_on_welcome(msg)
		"view":
			_on_view(msg)
		"frame":
			_on_frame(msg)
		"error":
			_on_error(msg)
		"bye":
			_log_line("Ядро завершилось штатно.")
		_:
			_log_line("[color=orange]Неизвестный тип ответа:[/color] %s" % str(msg.get("type", "?")))


func _on_ready(msg: Dictionary) -> void:
	if not _accept(msg, "ready"):
		return
	_log_line("Ядро готово: протокол %s, pid %d." % [msg["protocol"], int(msg["pid"])])
	if msg["protocol"] != PROTOCOL:
		_fail("Версия протокола ядра (%s) не совпадает с клиентом (%s)." % [msg["protocol"], PROTOCOL])
		return
	var hello: Dictionary = {"type": "hello", "protocol": PROTOCOL}
	hello.merge(START)
	_request("hello", hello, "Создание мира…")


func _on_welcome(msg: Dictionary) -> void:
	if _waiting != "hello" or not _accept(msg, "welcome"):
		return
	_last_seq = int(msg["last_seq"])
	_log_line("Мир создан: %s, жизнь %s, действие «%s»." % [
		str(msg["session_id"]), str(msg["life"].get("agent", "?")),
		str(msg["action_card"].get(str(PLAYER_ACTION), "?")),
	])
	_request("look", {"type": "look"}, "Чтение мира…")


func _on_view(msg: Dictionary) -> void:
	if _waiting != "look" or not _accept(msg, "view"):
		return
	_waiting = ""
	_view = Dto.View.from(msg)
	_set_status("Мир до первого хода (тик %d). Нажмите «%s»." % [_view.tick, ACTION_LABEL])
	_refresh()


func _on_frame(msg: Dictionary) -> void:
	if _waiting != "decide" or not _accept(msg, "frame"):
		return
	_waiting = ""
	_before = _view
	_view = Dto.View.from(msg)
	_last_seq = _view.seq
	_show_result()
	if not _view.alive:
		_finished = true
	_refresh()


func _on_error(msg: Dictionary) -> void:
	if not _accept(msg, "error"):
		return
	var code: String = str(msg["code"])
	_waiting = ""
	match code:
		"seq_gap":
			# the core tells us the last applied seq: adopt it, then resend
			var resync: Variant = msg.get("resync", {})
			if typeof(resync) == TYPE_DICTIONARY and resync.has("last_seq"):
				_last_seq = int(resync["last_seq"])
			_log_line("[color=orange]Разрыв последовательности:[/color] %s" % str(msg["msg"]))
		"finalized":
			_finished = true
			_log_line("[color=orange]Жизнь уже завершена ядром.[/color]")
		_:
			_log_line("[color=red]Ядро отклонило запрос (%s):[/color] %s" % [code, str(msg["msg"])])
	_refresh()


## Validate a reply against the contract. A violating reply is not drawn.
func _accept(msg: Dictionary, spec_name: String) -> bool:
	var errors: PackedStringArray = Dto.validate(msg, spec_name, _contract)
	if errors.is_empty():
		return true
	_fail("Нарушение контракта (%s): %s" % [spec_name, "; ".join(errors)])
	return false


func _request(kind: String, message: Dictionary, status: String) -> void:
	_waiting = kind
	_set_status(status)
	_refresh()
	if not _bridge.send(message):
		_fail("Не удалось отправить запрос ядру.")


func _on_act_pressed() -> void:
	if _finished or _waiting != "" or _view == null or not _bridge.is_running():
		return
	var seq: int = _last_seq + 1
	_request("decide", {"type": "decide", "seq": seq, "action": PLAYER_ACTION},
		"Ход %d: ядро считает…" % seq)


func _on_cell_selected(cell_id: String) -> void:
	_selected_cell = cell_id
	_refresh()


# ----------------------------------------------------------- failures ----

func _on_bridge_failed(reason: String) -> void:
	_fail(reason)


func _on_bridge_ended(reason: String) -> void:
	_finished = true
	_waiting = ""
	_set_status("Ядро остановлено: %s" % reason)
	_log_line("[color=orange]Ядро остановлено:[/color] %s" % reason)
	for line: String in _bridge.stderr_tail:
		_log_line("[color=gray]%s[/color]" % line.left(160))
	_refresh()


func _fail(reason: String) -> void:
	_waiting = ""
	_set_status("Ошибка: %s" % reason)
	_log_line("[color=red]%s[/color]" % reason)
	_refresh()


# -------------------------------------------------------------- render ---

func _refresh() -> void:
	_act_button.disabled = _finished or _waiting != "" or _view == null or not _bridge.is_running()
	_quit_button.disabled = false
	if _view == null:
		return
	_map.set_view(_view)
	if _selected_cell != "":
		var cell: Dto.Cell = _view.cell_by_id(_selected_cell)
		if cell != null:
			_panel.show_cell(cell, _view)
		else:
			_selected_cell = ""
			_panel.show_empty()
	_set_status(_status_line())


func _status_line() -> String:
	var text: String = "Тик %d · население %d/%d · здоровье %.0f · голод %.2f" % [
		_view.tick, _view.alive_agents, _view.total_agents, _view.health, _view.hunger,
	]
	if _finished or not _view.alive:
		text += " · жизнь окончена"
	return text


## The result of the last decision, as facts: the view before and the frame
## after, side by side. Nothing here is recomputed by the client.
func _show_result() -> void:
	var head: String = "[b]Ход %d → тик %d[/b]" % [_view.seq, _view.tick]
	if _view.applied:
		head += " · действие применено"
	else:
		head += " · [color=orange]отклонено ядром: %s[/color]" % _view.reject
	_log_line(head)
	if _before != null:
		_log_line("  вы: здоровье %.1f → %.1f, голод %.2f → %.2f, регион %s" % [
			_before.health, _view.health, _before.hunger, _view.hunger, _view.region,
		])
		_log_line("  журнал: +%d переходов, отклонено +%d, хеш %s…" % [
			_view.journal_committed - _before.journal_committed,
			_view.journal_rejected - _before.journal_rejected,
			_view.journal_hash.left(16),
		])
		var changes: Array[String] = _cell_changes(_before, _view)
		for line: String in changes.slice(0, MAX_CHANGE_LINES):
			_log_line("  " + line)
		if changes.size() > MAX_CHANGE_LINES:
			_log_line("  … и ещё %d" % (changes.size() - MAX_CHANGE_LINES))
		for line: String in _situation_changes(_before, _view):
			_log_line("  " + line)
	if not _view.finished.is_empty():
		_log_line("[color=orange]Жизнь окончена:[/color] %s, тик смерти %s." % [
			str(_view.finished.get("reason", "?")), str(_view.finished.get("death_tick", "?")),
		])


func _cell_changes(before: Dto.View, after: Dto.View) -> Array[String]:
	var out: Array[String] = []
	for now: Dto.Cell in after.cells:
		var was: Dto.Cell = before.cell_by_id(now.id)
		if was == null:
			continue
		var fields: Array = [
			["население", was.population, now.population],
			["запасы еды", was.food_stock, now.food_stock],
			["плодородие", was.soil_fertility, now.soil_fertility],
		]
		for field: Array in fields:
			if not is_equal_approx(field[1], field[2]):
				out.append("%s · %s: %.2f → %.2f" % [now.id, field[0], field[1], field[2]])
	return out


func _situation_changes(before: Dto.View, after: Dto.View) -> Array[String]:
	var out: Array[String] = []
	var was: Dictionary = {}
	for row: Variant in before.situations:
		was["%s@%s" % [row["kind"], row["scope"]]] = true
	var now: Dictionary = {}
	for row: Variant in after.situations:
		var key: String = "%s@%s" % [row["kind"], row["scope"]]
		now[key] = true
		if not was.has(key):
			out.append("[color=yellow]новая ситуация[/color] %s @ %s: %s" % [
				row["kind"], row["scope"], str(row["message"]).left(140),
			])
	for key: String in was:
		if not now.has(key):
			out.append("снята ситуация %s" % key)
	return out


func _set_status(text: String) -> void:
	if _status != null:
		_status.text = text


func _log_line(text: String) -> void:
	if _log != null:
		_log.append_text(text + "\n")


# ------------------------------------------------------------------ UI ---

func _build_ui() -> void:
	_map = WorldMap.new()
	add_child(_map)
	_map.cell_selected.connect(_on_cell_selected)

	var layer := CanvasLayer.new()
	add_child(layer)
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE  # empty space lets clicks reach the map
	layer.add_child(root)

	var bar := HBoxContainer.new()
	bar.mouse_filter = Control.MOUSE_FILTER_PASS
	root.add_child(bar)
	_status = Label.new()
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.text = "Запуск…"
	bar.add_child(_status)
	_act_button = Button.new()
	_act_button.text = ACTION_LABEL
	_act_button.disabled = true
	_act_button.pressed.connect(_on_act_pressed)
	bar.add_child(_act_button)
	_quit_button = Button.new()
	_quit_button.text = "Выход"
	_quit_button.pressed.connect(_on_quit_pressed)
	bar.add_child(_quit_button)

	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(body)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(spacer)
	var side := VBoxContainer.new()
	side.custom_minimum_size = Vector2(400, 0)
	body.add_child(side)
	_panel = CellPanel.new()
	_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	side.add_child(_panel)
	_log = RichTextLabel.new()
	_log.bbcode_enabled = true
	_log.scroll_following = true
	_log.custom_minimum_size = Vector2(0, 220)
	side.add_child(_log)


func _on_quit_pressed() -> void:
	_bridge.stop()
	get_tree().quit()


# ------------------------------------------------------------ locating ---

## The repository root is two levels above client/godot (the project dir).
func _repo_root() -> String:
	return ProjectSettings.globalize_path("res://").path_join("../..").simplify_path()


func _resolve_src() -> String:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--src="):
			return arg.substr(6)
	return _repo_root().path_join("src")


## Order: --python= argument, CAUSAL_WORLD_PYTHON, the repo's .venv, then the
## system interpreter. The core is standard-library Python: a venv is optional.
func _resolve_python() -> String:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--python="):
			return arg.substr(9)
	var from_env: String = OS.get_environment("CAUSAL_WORLD_PYTHON")
	if not from_env.is_empty():
		return from_env
	var repo: String = _repo_root()
	for candidate: String in [
		repo.path_join(".venv/bin/python"),
		repo.path_join(".venv/Scripts/python.exe"),
	]:
		if FileAccess.file_exists(candidate):
			return candidate
	return "python" if OS.get_name() == "Windows" else "python3"
