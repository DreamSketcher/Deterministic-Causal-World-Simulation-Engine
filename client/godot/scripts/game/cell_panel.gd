class_name CellPanel
extends PanelContainer
## Shows what the core says about one cell, in three labelled kinds:
##
##   факт     a value of the state, with the transition that last wrote the
##            cell when the core reports it;
##   связь    a situation or goal that cites this cell, with the transition
##            ids it rests on;
##   гипотеза a goal whose confidence is "hypothesis": a plausible reading
##            that the records do not prove. It is never drawn as a fact.
##
## Every number comes from the frame; nothing is computed here.

var _text: RichTextLabel


func _ready() -> void:
	custom_minimum_size = Vector2(380, 0)
	_text = RichTextLabel.new()
	_text.bbcode_enabled = true
	_text.scroll_active = true
	_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_text)
	show_empty()


func show_empty() -> void:
	_text.text = "[i]Выберите клетку на карте.[/i]"


func show_cell(cell: Dto.Cell, view: Dto.View) -> void:
	var lines: PackedStringArray = PackedStringArray()
	var tick_label: String = "тик %d" % view.tick if view.tick >= 0 else "до первого хода"
	lines.append("[b]%s[/b] · %s · сетка (%d, %d)" % [
		_esc(cell.id), _esc(cell.region), cell.grid.x, cell.grid.y])
	lines.append("[color=gray]состояние на %s[/color]" % tick_label)
	lines.append("")
	lines.append("[b]Факты[/b]")
	lines.append(_row("население", "%.2f" % cell.population))
	lines.append(_row("работники", "%.2f" % cell.workers))
	lines.append(_row("плодородие почвы", "%.3f" % cell.soil_fertility))
	lines.append(_row("запас еды", "%.2f" % cell.food_stock))
	lines.append(_row("дождь (множитель)", "%.3f" % cell.rain_factor))
	lines.append(_row("ёмкость", "%.2f" % cell.capacity))
	lines.append(_row("земля освоена", "да" if cell.land_active != 0 else "нет (дикая)"))
	if cell.limit != "":
		lines.append(_row("что ограничивает рост", _esc(cell.limit)))
	if cell.resettled_in != 0.0 or cell.resettled_out != 0.0:
		lines.append(_row("переселено входящих / исходящих",
			"%.0f / %.0f" % [cell.resettled_in, cell.resettled_out]))
	if not cell.law.is_empty():
		lines.append(_row("закон: труд", "%.2f" % float(cell.law.get("labor_diversion", 0.0))))
		lines.append(_row("закон: вода", "%.2f" % float(cell.law.get("water_aid", 0.0))))
		lines.append(_row("закон: отдых до тика", str(cell.law.get("rest_until", "-"))))
	if cell.last_source == Dto.NO_SOURCE:
		lines.append(_row("последняя запись", "нет (клетка не менялась)"))
	else:
		lines.append(_row("последняя запись", "переход T%d" % cell.last_source))

	lines.append("")
	lines.append("[b]Связи[/b]")
	var links: int = 0
	var hypotheses: PackedStringArray = PackedStringArray()
	for row: Variant in view.situations:
		if str(row.get("scope", "")) != cell.id:
			continue
		links += 1
		lines.append("[color=yellow]ситуация[/color] %s (тяжесть %.2f): %s" % [
			_esc(str(row.get("kind", ""))), float(row.get("severity", 0.0)),
			_esc(str(row.get("message", "")))])
		lines.append("   опирается на переходы: %s" % _tids(row.get("evidence", [])))
	for row: Variant in view.goals:
		if str(row.get("scope", "")) != cell.id:
			continue
		var line: String = "[color=aqua]цель[/color] %s · %s" % [
			_esc(str(row.get("kind", ""))), _esc(str(row.get("status", "")))]
		var reason: String = "   %s" % _esc(str(row.get("reason", "")))
		if str(row.get("confidence", "established")) == "hypothesis":
			# a plausible reading the records do not prove: shown as such
			hypotheses.append(line + "\n" + reason)
		else:
			links += 1
			lines.append(line)
			lines.append(reason)
	if links == 0:
		lines.append("[color=gray]по этой клетке ситуаций и целей нет.[/color]")

	lines.append("")
	lines.append("[b]Гипотезы[/b]")
	if hypotheses.is_empty():
		lines.append("[color=gray]по этой клетке гипотез нет.[/color]")
	else:
		for item: String in hypotheses:
			lines.append("[color=violet]гипотеза (не доказана)[/color] " + item)
	_text.text = "\n".join(lines)


func _row(label: String, value: String) -> String:
	return "%s: [b]%s[/b]" % [label, value]


func _tids(evidence: Variant) -> String:
	if typeof(evidence) != TYPE_ARRAY or (evidence as Array).is_empty():
		return "—"
	var ids: PackedStringArray = PackedStringArray()
	var seen: Dictionary = {}
	for item: Variant in evidence:
		if typeof(item) == TYPE_DICTIONARY and item.has("tid"):
			var tid: int = int(item["tid"])
			if not seen.has(tid):
				seen[tid] = true
				ids.append("T%d" % tid)
	return ", ".join(ids) if not ids.is_empty() else "—"


## Escape user-visible text so that brackets in messages are not BBCode.
func _esc(text: String) -> String:
	return text.replace("[", "[lb]")
