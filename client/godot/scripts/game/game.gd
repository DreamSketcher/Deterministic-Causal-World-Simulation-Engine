class_name Game
extends Node2D
## The slice controller: starts the Python core, drives the protocol, shows
## the world and the real result of each action.
##
## Flow:  ready -> hello -> welcome -> look -> view   (the map exists, no step)
##        decide -> frame                              (one action = one tick)
##        finished in a frame                          (the life has ended)
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
const ACTION_LABEL: String = "Работать (ход)"
const MAX_CHANGE_LINES: int = 12
## Labels of the core's death classifier (observer/deaths.py), in Russian.
const CAUSE_LABELS: Dictionary = {
	"starvation": "голод",
	"disease": "болезнь",
	"disease+starvation": "голод и болезнь",
	"acute_infection": "острая инфекция",
	"other": "другая причина (ядро не отнесло к голоду или болезни)",
}
const INTRO: String = (
	"[b]Что это.[/b] Срез проверяет связку: карта и панель показывают реальный мир "
	+ "Python-ядра, а ход проходит через его API.\n"
	+ "[b]Что делать.[/b] Кликните клетку на карте — панель покажет её факты, связи "
	+ "и гипотезы. Нажимайте «Работать (ход)»: каждое нажатие — один тик мира. "
	+ "Журнал ниже покажет, что изменилось.\n"
	+ "[b]Конец.[/b] В срезе одно действие, поэтому жизнь агента может закончиться. "
	+ "В эталонном сценарии смерть наступает на тике 45. Тогда ходы закрываются, "
	+ "а «Начать заново» создаёт новый мир.\n"
)

var _contract: Dictionary = {}
var _bridge: PyBridge
var _map: WorldMap
var _panel: CellPanel
var _status: Label
var _act_button: Button
var _restart_button: Button
var _export_button: Button
var _quit_button: Button
var _log: RichTextLabel

var _view: Dto.View = null  ## the world now (a view, or the last frame)
var _before: Dto.View = null  ## the world before the last decision
var _last_seq: int = 0
var _waiting: String = ""  ## the request kind in flight, "" when idle
var _finished: bool = false
var _selected_cell: String = ""
var _restarting: bool = false
var _quitting: bool = false
var _db_dir: String = ""
var _request_kind: String = ""  ## the request in flight, for the trace
var _request_msec: int = -1  ## when it was sent, for the reply time
var _last_block_reason: String = "?"  ## last logged reason the action button is off
var _last_view: Dictionary = {}  ## the last view reply, raw, for the report
var _last_frame: Dictionary = {}  ## the last frame reply, raw, for the report
var _log_plain: PackedStringArray = PackedStringArray()  ## the game log, without tags
var _tags: RegEx = RegEx.create_from_string("\\[[^\\]]*\\]")


func _ready() -> void:
	Trace.enable(Trace.wanted())
	Trace.log("bridge", "godot %s, os %s, debug build %s, trace %s" % [
		Engine.get_version_info()["string"], OS.get_name(),
		str(OS.is_debug_build()), str(Trace.enabled),
	])
	_contract = Dto.load_contract()
	_build_ui()
	_bridge = PyBridge.new()
	add_child(_bridge)
	_bridge.line_received.connect(_on_line)
	_bridge.log_line_received.connect(_on_core_log)
	_bridge.bridge_failed.connect(_on_bridge_failed)
	_bridge.bridge_ended.connect(_on_bridge_ended)
	_db_dir = ProjectSettings.globalize_path("user://worlds")
	_log_line(INTRO)
	if Trace.enabled:
		_log_line("[color=gray]Трасса: вкладка Output (нижняя панель редактора). "
			+ "Файл трассы: %s[/color]" % Trace.file_path())
	_start_core()


## Keys and mouse presses, with their positions. _input sees every event,
## including those the UI consumes, and never consumes one itself.
func _input(event: InputEvent) -> void:
	if not Trace.enabled:
		return
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.pressed:
			Trace.log("input", "mouse %s down at screen %s, world %s" % [
				button.button_index, button.position, get_global_mouse_position(),
			])
	elif event is InputEventKey:
		var key := event as InputEventKey
		if key.pressed and not key.echo:
			Trace.log("input", "key %s" % OS.get_keycode_string(key.keycode))


func _process(_delta: float) -> void:
	_bridge.poll()


func _start_core() -> void:
	var python: String = _resolve_python()
	var src: String = _resolve_src()
	_set_status("Запуск ядра…")
	_log_line("[color=gray]ядро: %s · исходники: %s · архивы миров: %s[/color]" % [
		python, src, _db_dir,
	])
	Trace.log("bridge", "start: python=%s src=%s db=%s trace_core=%s detail=%s" % [
		python, src, _db_dir, str(Trace.enabled), str(Trace.detail_wanted()),
	])
	_bridge.start(python, src, _db_dir, Trace.enabled, Trace.detail_wanted())
	_refresh()


# ----------------------------------------------------------- protocol ----

func _on_line(line: String) -> void:
	var waited: String = ""
	if _request_msec >= 0:
		waited = " (%d ms after %s)" % [Time.get_ticks_msec() - _request_msec, _request_kind]
	Trace.log("proto", "<< %s%s" % [line.left(400), waited])
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
			pass  # the shutdown is handled by _on_bridge_ended
		_:
			_log_line("[color=orange]Неизвестный тип ответа:[/color] %s" % str(msg.get("type", "?")))


func _on_ready(msg: Dictionary) -> void:
	if not _accept(msg, "ready"):
		return
	if msg["protocol"] != PROTOCOL:
		_fail("Версия протокола ядра (%s) не совпадает с клиентом (%s)." % [msg["protocol"], PROTOCOL])
		return
	_log_line("Ядро готово: протокол %s, pid %d." % [msg["protocol"], int(msg["pid"])])
	var hello: Dictionary = {"type": "hello", "protocol": PROTOCOL}
	hello.merge(START)
	_request("hello", hello, "Создание мира…")


func _on_welcome(msg: Dictionary) -> void:
	if _waiting != "hello" or not _accept(msg, "welcome"):
		return
	_last_seq = int(msg["last_seq"])
	var agent: String = str(msg["life"].get("agent", "?"))
	_log_line("Мир создан: %s. Агент: %s." % [str(msg["session_id"]), agent])
	_request("look", {"type": "look"}, "Чтение мира…")


func _on_view(msg: Dictionary) -> void:
	if _waiting != "look" or not _accept(msg, "view"):
		return
	_waiting = ""
	_view = Dto.View.from(msg)
	_last_view = msg
	Trace.log("frame", "view tick=%d alive=%s cells=%d regions=%d" % [
		_view.tick, str(_view.alive), _view.cells.size(), _view.regions.size(),
	])
	_set_status("Мир до первого хода. Кликните клетку или нажмите «%s»." % ACTION_LABEL)
	_refresh()


func _on_frame(msg: Dictionary) -> void:
	if _waiting != "decide" or not _accept(msg, "frame"):
		return
	_waiting = ""
	_before = _view
	_view = Dto.View.from(msg)
	_last_frame = msg
	_last_seq = _view.seq
	var gained: int = _view.journal_committed - (_before.journal_committed if _before != null else 0)
	Trace.log("frame", "seq=%d tick=%d applied=%s reject=%s alive=%s hunger=%.3f health=%.1f" % [
		_view.seq, _view.tick, str(_view.applied), _view.reject, str(_view.alive),
		_view.hunger, _view.health,
	])
	Trace.log("frame", "region=%s" % _view.region)
	Trace.log("frame", "journal committed=%d (+%d) rejected=%d hash=%s" % [
		_view.journal_committed, gained, _view.journal_rejected, _view.journal_hash.left(16),
	])
	_show_result()
	if not _view.alive or not _view.finished.is_empty():
		_finished = true
		_show_death()
	_refresh()


func _on_error(msg: Dictionary) -> void:
	if not _accept(msg, "error"):
		return
	var code: String = str(msg["code"])
	Trace.log("proto", "error code=%s seq=%s msg=%s" % [
		code, str(msg.get("seq", "-")), str(msg["msg"]),
	])
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
			_log_line("[color=orange]Жизнь уже завершена ядром — ходы не принимаются.[/color]")
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
	_request_kind = kind
	_request_msec = Time.get_ticks_msec()
	_set_status(status)
	_refresh()
	if not _bridge.send(message):
		_fail("Не удалось отправить запрос ядру.")


func _on_act_pressed() -> void:
	if not _can_act():
		Trace.log("input", "«%s» pressed while disabled: %s" % [ACTION_LABEL, _act_block_reason()])
		return
	var seq: int = _last_seq + 1
	Trace.log("input", "«%s» pressed → decide seq=%d" % [ACTION_LABEL, seq])
	_request("decide", {"type": "decide", "seq": seq, "action": PLAYER_ACTION},
		"Ход %d: ядро считает…" % seq)


func _can_act() -> bool:
	return _act_block_reason() == ""


## Why the action is not available, or "" when it is. One source for the
## button state and the trace, so the trace always explains the button.
func _act_block_reason() -> String:
	var reason: String = ""
	if _finished:
		reason = "жизнь окончена"
	elif _waiting != "":
		reason = "ждём ответ ядра (%s)" % _waiting
	elif _view == null:
		reason = "мир ещё не прочитан"
	elif _restarting:
		reason = "перезапуск мира"
	elif _quitting:
		reason = "выход"
	elif not _bridge.is_running():
		reason = "ядро не запущено"
	return reason


func _on_restart_pressed() -> void:
	if _restarting or _quitting:
		return
	Trace.log("input", "«Начать заново» pressed (core running: %s)" % str(_bridge.is_running()))
	_log_line("[b]— Новый мир —[/b]")
	if _bridge.is_running():
		_restarting = true  # the new core starts when the old one has exited
		_set_status("Завершаю прошлый мир…")
		_bridge.stop()
		_refresh()
	else:
		_reset_world()
		_start_core()


func _reset_world() -> void:
	_view = null
	_before = null
	_last_seq = 0
	_waiting = ""
	_finished = false
	_selected_cell = ""
	_map.clear()
	_panel.show_empty()


func _on_cell_selected(cell_id: String) -> void:
	Trace.log("map", "selected %s" % cell_id)
	_selected_cell = cell_id
	_refresh()


# ----------------------------------------------------------- failures ----

func _on_bridge_failed(reason: String) -> void:
	push_warning("[bridge] %s" % reason)
	_fail(reason)


## The core's log (stderr) goes to the Godot Output/Debugger console. Lines
## that look like failures are warnings, so they stand out in the debugger.
func _on_core_log(line: String) -> void:
	var text: String = "[core] %s" % line.left(600)
	Trace.out(text)
	if line.contains("Traceback") or line.contains("Error") or line.contains("Exception"):
		push_warning(text)


func _on_bridge_ended(reason: String) -> void:
	Trace.out("[bridge] ended: %s" % reason)
	_waiting = ""
	if _quitting:
		get_tree().quit()
		return
	if _restarting:
		_restarting = false
		_reset_world()
		_start_core()
		return
	_finished = true
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
	var reason: String = _act_block_reason()
	if reason != _last_block_reason:
		_last_block_reason = reason
		Trace.log("ui", "«%s» %s" % [
			ACTION_LABEL, "enabled" if reason == "" else "disabled: " + reason,
		])
	_act_button.disabled = reason != ""
	_restart_button.disabled = _restarting or _quitting
	_quit_button.disabled = _quitting
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
	if _finished:
		_set_status(_death_summary())
	else:
		_set_status(_status_line())


func _status_line() -> String:
	return "Тик %d · население %d/%d · здоровье %.0f · голод %.2f" % [
		_view.tick, _view.alive_agents, _view.total_agents, _view.health, _view.hunger,
	]


func _death_summary() -> String:
	var tick: int = int(_view.finished.get("death_tick", _view.tick))
	return "ЖИЗНЬ ОКОНЧИЛАСЬ на тике %d: %s. Ходы закрыты — «Начать заново»." % [
		tick, _cause_text(_view.finished),
	]


## The cause from the core's autopsy label; never invented by the client.
func _cause_text(finished: Dictionary) -> String:
	var autopsy: Variant = finished.get("autopsy")
	if typeof(autopsy) != TYPE_DICTIONARY:
		return "причина не определена (%s)" % str(finished.get("autopsy_error", "нет данных"))
	var label: String = str((autopsy as Dictionary).get("label", ""))
	return str(CAUSE_LABELS.get(label, label))


## The death: why it ended and what the player can do now. The facts come
## from the frame (tick, label); the text only explains them.
func _show_death() -> void:
	var reason: String = str(_view.finished.get("reason", "?"))
	if reason == "death":
		_log_line("[color=orange][b]Жизнь окончилась на тике %d.[/b][/color] Причина по ядру: %s." % [
			int(_view.finished.get("death_tick", _view.tick)), _cause_text(_view.finished),
		])
	else:
		_log_line("[color=orange][b]Жизнь окончилась:[/b][/color] %s (тик %d)." % [reason, _view.tick])
	_log_line("Дальше: ходы закрыты. Клетки и журнал остаются для просмотра. "
		+ "«Начать заново» создаёт новый мир с новым архивом.")


## The result of the last decision, as facts: the view before and the frame
## after, side by side. Nothing here is recomputed by the client.
func _show_result() -> void:
	var head: String = "[b]Ход %d → тик %d[/b]" % [_view.seq, _view.tick]
	if _view.applied:
		head += " · действие применено"
	else:
		head += " · [color=orange]отклонено ядром: %s[/color]" % _view.reject
	_log_line(head)
	if _before == null:
		return
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
	_log_plain.append(_tags.sub(text, "", true))
	if _log_plain.size() > 5000:
		_log_plain.remove_at(0)


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
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.text = "Запуск…"
	bar.add_child(_status)
	_act_button = Button.new()
	_act_button.text = ACTION_LABEL
	_act_button.disabled = true
	_act_button.pressed.connect(_on_act_pressed)
	bar.add_child(_act_button)
	_restart_button = Button.new()
	_restart_button.text = "Начать заново"
	_restart_button.pressed.connect(_on_restart_pressed)
	bar.add_child(_restart_button)
	_export_button = Button.new()
	_export_button.text = "Сохранить отчёт"
	_export_button.pressed.connect(_on_export_pressed)
	bar.add_child(_export_button)
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
	_log.custom_minimum_size = Vector2(0, 240)
	side.add_child(_log)


## Save a report for passing a result on: the last reply of the core (raw),
## the game log, the core's stderr tail and the trace file path. The absolute
## path is copied to the clipboard.
func _on_export_pressed() -> void:
	var stamp: String = Time.get_datetime_string_from_system().replace(":", "-").replace("T", "_")
	DirAccess.make_dir_recursive_absolute("user://reports")
	var path: String = "user://reports/report-%s.json" % stamp
	var report: Dictionary = {
		"time": Time.get_datetime_string_from_system(),
		"godot": Engine.get_version_info()["string"],
		"os": OS.get_name(),
		"debug_build": OS.is_debug_build(),
		"trace_file": Trace.file_path(),
		"selected_cell": _selected_cell,
		"action_state": _act_block_reason(),
		"last_view": _last_view,
		"last_frame": _last_frame,
		"stderr_tail": Array(_bridge.stderr_tail),
		"log": Array(_log_plain),
	}
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		_log_line("[color=red]Не удалось записать отчёт: %s[/color]" % path)
		return
	file.store_string(JSON.stringify(report, "  "))
	file.close()
	var absolute: String = ProjectSettings.globalize_path(path)
	DisplayServer.clipboard_set(absolute)
	Trace.out("[export] report: %s" % absolute)
	_log_line("Отчёт сохранён: %s (путь скопирован в буфер обмена)" % absolute)


func _on_quit_pressed() -> void:
	Trace.log("input", "«Выход» pressed (already quitting: %s)" % str(_quitting))
	if _quitting:
		return
	_quitting = true
	_refresh()
	if _bridge.is_running():
		_set_status("Закрываю ядро…")
		_bridge.stop()  # the quit happens in _on_bridge_ended, once the core is gone
	else:
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
