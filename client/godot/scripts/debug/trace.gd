class_name Trace
extends RefCounted
## Debug trace and the output log of the game.
##
## Where the output goes:
##   * the Godot **Output** panel (the bottom panel "Output" in the editor).
##     It is NOT the Debugger's Stack Trace or Errors tabs: those show errors
##     and warnings only, so a plain print() never appears there.
##   * a file: user://trace/trace-<time>.log, written and flushed line by line,
##     so it survives a crash. Its absolute path is printed at start, and the
##     report button (see game.gd) copies the report next to it.
##
## When it is on: every line has the time since start and a category:
##   input   key and mouse presses, with screen and world position
##   ui      button states, and why a button is disabled
##   map     cell clicks, zoom, pan
##   proto   protocol lines sent (>>) and received (<<), with reply time
##   frame   the result of each decision, read from the core's frame
##   bridge  start and stop of the core process
##
## Default: on in debug builds (the editor's Play button runs one), off in
## release builds. `--trace` turns it on in any build, `--no-trace` turns it off,
## and CAUSAL_WORLD_TRACE=1 turns it on.
##
## Core detail: by default the core logs ONE summary per decision (counts by
## system/operation, rejections). `--trace-detail` (or CAUSAL_WORLD_TRACE_DETAIL=1)
## adds one line per transition, which is much longer: use it for a single
## step, not a whole life, or the editor's Output panel overflows.

static var enabled: bool = false
static var _t0_msec: int = 0
static var _file: FileAccess = null
static var _file_path: String = ""


## Per-transition core detail (see the header). Off unless asked for.
static func detail_wanted() -> bool:
	if "--trace-detail" in OS.get_cmdline_user_args():
		return true
	return OS.get_environment("CAUSAL_WORLD_TRACE_DETAIL") == "1"


## Decide from the command line, the environment and the build type.
static func wanted() -> bool:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "--no-trace" in args:
		return false
	if "--trace" in args:
		return true
	if OS.get_environment("CAUSAL_WORLD_TRACE") == "1":
		return true
	return OS.is_debug_build()


static func enable(on: bool) -> void:
	enabled = on
	_t0_msec = Time.get_ticks_msec()
	if on and _file == null:
		_open_file()


## Print a line always, and write it to the trace file when that is open.
## Used by the core's log and by errors, which are shown even when tracing is off.
static func out(text: String) -> void:
	print(text)
	if _file != null:
		_file.store_line(text)
		_file.flush()


## One traced event; does nothing when tracing is off.
static func log(category: String, message: String) -> void:
	if not enabled:
		return
	out("[trace %7d ms][%s] %s" % [Time.get_ticks_msec() - _t0_msec, category, message])


## Absolute path of the trace file, or "" when there is none.
static func file_path() -> String:
	return _file_path


static func _open_file() -> void:
	DirAccess.make_dir_recursive_absolute("user://trace")
	var stamp: String = Time.get_datetime_string_from_system().replace(":", "-").replace("T", "_")
	var path: String = "user://trace/trace-%s.log" % stamp
	_file = FileAccess.open(path, FileAccess.WRITE)
	if _file == null:
		out("[trace] cannot open %s (error %d)" % [path, FileAccess.get_open_error()])
		return
	_file_path = ProjectSettings.globalize_path(path)
	out("[trace] file: %s" % _file_path)
