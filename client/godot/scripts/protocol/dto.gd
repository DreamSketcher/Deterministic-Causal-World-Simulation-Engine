class_name Dto
extends RefCounted
## Typed views of the Python core's replies.
##
## The field list and the types come from res://contract/v1.json — the same
## file the Python contract test reads. validate() checks a reply against it;
## the typed classes below read only the fields the client draws.
##
## Nothing here computes game state. Derived numbers (for example the change
## of a cell between two frames) are presentation of two facts, never rules.

const CONTRACT_PATH: String = "res://contract/v1.json"
const NO_SOURCE: int = -1  ## a cell's last_source of "none" (no transition)


static func load_contract() -> Dictionary:
	var text: String = FileAccess.get_file_as_string(CONTRACT_PATH)
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("contract unreadable: %s" % CONTRACT_PATH)
		return {}
	return parsed


static func parse_line(line: String) -> Variant:
	return JSON.parse_string(line)


static func type_ok(value: Variant, declared: String) -> bool:
	for alternative: String in declared.split("|"):
		if _is_type(value, alternative):
			return true
	return false


static func validate(reply: Variant, spec_name: String, contract: Dictionary) -> PackedStringArray:
	var errors := PackedStringArray()
	if typeof(reply) != TYPE_DICTIONARY:
		errors.append("%s: not an object" % spec_name)
		return errors
	var spec: Dictionary = contract.get(spec_name, {})
	var fields: Dictionary = reply
	for key: String in spec:
		if not fields.has(key):
			errors.append("%s.%s: missing" % [spec_name, key])
		elif not type_ok(fields[key], spec[key]):
			errors.append("%s.%s: expected %s" % [spec_name, key, spec[key]])
	return errors


static func _is_type(value: Variant, declared: String) -> bool:
	var kind: int = typeof(value)
	match declared:
		"int":
			if kind == TYPE_INT:
				return true
			if kind == TYPE_FLOAT:
				var number: float = value
				return is_equal_approx(number, roundf(number))
			return false
		"number":
			return kind == TYPE_INT or kind == TYPE_FLOAT
		"string":
			return kind == TYPE_STRING
		"bool":
			return kind == TYPE_BOOL
		"object":
			return kind == TYPE_DICTIONARY
		"array":
			return kind == TYPE_ARRAY
		"null":
			return kind == TYPE_NIL
	return false


static func to_float(value: Variant, fallback: float = 0.0) -> float:
	var kind: int = typeof(value)
	if kind == TYPE_INT or kind == TYPE_FLOAT:
		return float(value)
	return fallback


static func to_int(value: Variant, fallback: int = 0) -> int:
	var kind: int = typeof(value)
	if kind == TYPE_INT or kind == TYPE_FLOAT:
		return int(value)
	return fallback


## A cell is a grid square of one region (v0.8 spatial world).
class Cell:
	extends RefCounted
	var id: String = ""
	var region: String = ""
	var grid: Vector2i = Vector2i.ZERO
	var population: float = 0.0
	var workers: float = 0.0
	var soil_fertility: float = 0.0
	var food_stock: float = 0.0
	var rain_factor: float = 0.0
	var capacity: float = 0.0
	var land_active: int = 0
	var claim_state: float = 0.0
	var terraces: float = 0.0
	var resettled_in: float = 0.0
	var resettled_out: float = 0.0
	var resettle_state: float = 0.0
	## The transition id that last wrote this cell, or NO_SOURCE.
	var last_source: int = NO_SOURCE
	## Present only when the growth limit is defined (land_active).
	var limit: String = ""
	var law: Dictionary = {}

	static func from(d: Dictionary) -> Cell:
		var c := Cell.new()
		c.id = str(d.get("id", ""))
		c.region = str(d.get("region", ""))
		c.grid = Vector2i(Dto.to_int(d.get("x")), Dto.to_int(d.get("y")))
		c.population = Dto.to_float(d.get("population"))
		c.workers = Dto.to_float(d.get("workers"))
		c.soil_fertility = Dto.to_float(d.get("soil_fertility"))
		c.food_stock = Dto.to_float(d.get("food_stock"))
		c.rain_factor = Dto.to_float(d.get("rain_factor"))
		c.capacity = Dto.to_float(d.get("capacity"))
		c.land_active = Dto.to_int(d.get("land_active"))
		c.claim_state = Dto.to_float(d.get("claim_state"))
		c.terraces = Dto.to_float(d.get("terraces"))
		c.resettled_in = Dto.to_float(d.get("resettled_in"))
		c.resettled_out = Dto.to_float(d.get("resettled_out"))
		c.resettle_state = Dto.to_float(d.get("resettle_state"))
		var source: Variant = d.get("last_source")
		c.last_source = Dto.to_int(source, NO_SOURCE) if typeof(source) != TYPE_STRING else NO_SOURCE
		c.limit = str(d.get("limit", ""))
		var raw_law: Variant = d.get("law", {})
		c.law = raw_law if typeof(raw_law) == TYPE_DICTIONARY else {}
		return c


class Region:
	extends RefCounted
	var id: String = ""
	var population: float = 0.0
	var workers: float = 0.0
	var soil_fertility: float = 0.0
	var food_stock: float = 0.0
	var temperature: float = 0.0
	var rainfall: float = 0.0
	var disease_load: float = 0.0

	static func from(d: Dictionary) -> Region:
		var r := Region.new()
		r.id = str(d.get("id", ""))
		r.population = Dto.to_float(d.get("population"))
		r.workers = Dto.to_float(d.get("workers"))
		r.soil_fertility = Dto.to_float(d.get("soil_fertility"))
		r.food_stock = Dto.to_float(d.get("food_stock"))
		r.temperature = Dto.to_float(d.get("temperature"))
		r.rainfall = Dto.to_float(d.get("rainfall"))
		r.disease_load = Dto.to_float(d.get("disease_load"))
		return r


## A frame (after a decision) or a view (``look``, no step): both carry the
## same world section, so the client has one code path for drawing.
class View:
	extends RefCounted
	var kind: String = ""  ## "frame" or "view"
	var seq: int = -1  ## -1 for a view
	var tick: int = -1  ## the last completed step; -1 before the first
	var applied: bool = true
	var reject: String = ""
	var alive: bool = true
	var hunger: float = 0.0
	var health: float = 0.0
	var region: String = ""
	var last_action: int = -1
	var journal_total: int = 0
	var journal_committed: int = 0
	var journal_rejected: int = 0
	var journal_hash: String = ""
	var alive_agents: int = 0
	var total_agents: int = 0
	var cells: Array[Cell] = []
	var regions: Array[Region] = []
	var situations: Array = []
	var goals: Array = []
	var decree: Dictionary = {}
	## Present only on the frame that ended the life (the verdict).
	var finished: Dictionary = {}

	static func from(d: Dictionary) -> View:
		var v := View.new()
		v.kind = str(d.get("type", ""))
		v.seq = Dto.to_int(d.get("seq"), -1)
		v.tick = Dto.to_int(d.get("tick"), -1)
		v.applied = bool(d.get("applied", true))
		v.reject = str(d.get("reject", ""))
		v.alive = bool(d.get("alive", true))
		var you: Dictionary = d.get("you", {})
		v.hunger = Dto.to_float(you.get("hunger"))
		v.health = Dto.to_float(you.get("health"))
		v.region = str(you.get("region", ""))
		v.last_action = Dto.to_int(you.get("last_action"), -1)
		var journal: Dictionary = d.get("journal", {})
		v.journal_total = Dto.to_int(journal.get("total"))
		v.journal_committed = Dto.to_int(journal.get("committed"))
		v.journal_rejected = Dto.to_int(journal.get("rejected"))
		v.journal_hash = str(journal.get("hash", ""))
		var world: Dictionary = d.get("world", {})
		v.alive_agents = Dto.to_int(world.get("alive_agents"))
		v.total_agents = Dto.to_int(world.get("total_agents"))
		for row: Variant in world.get("cells", []):
			v.cells.append(Cell.from(row))
		for row: Variant in world.get("regions", []):
			v.regions.append(Region.from(row))
		v.situations = world.get("situations", [])
		v.goals = world.get("goals", [])
		var raw_decree: Variant = d.get("decree")
		v.decree = raw_decree if typeof(raw_decree) == TYPE_DICTIONARY else {}
		var raw_finished: Variant = d.get("finished")
		v.finished = raw_finished if typeof(raw_finished) == TYPE_DICTIONARY else {}
		return v

	func cell_by_id(cell_id: String) -> Cell:
		for c: Cell in cells:
			if c.id == cell_id:
				return c
		return null
