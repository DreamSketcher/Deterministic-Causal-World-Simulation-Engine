class_name Trace
extends RefCounted
## Debug trace to the Godot Output / Debugger console.
##
## Off unless enabled: start the game with `--trace` after `--`, or with
## CAUSAL_WORLD_TRACE=1 in the environment. Each line has the time since start
## and a category:
##   input   key and mouse presses, with screen and world position
##   ui      button states, and why a button is disabled
##   map     cell clicks, zoom, pan
##   proto   protocol lines sent (>>) and received (<<), with reply time
##   frame   the result of each decision, read from the core's frame
##   bridge  start and stop of the core process
## The core's own trace (its journal and protocol) comes as [core] lines.

static var enabled: bool = false
static var _t0_msec: int = 0


static func enable(on: bool) -> void:
	enabled = on
	_t0_msec = Time.get_ticks_msec()


static func log(category: String, message: String) -> void:
	if not enabled:
		return
	print("[trace %7d ms][%s] %s" % [Time.get_ticks_msec() - _t0_msec, category, message])


## True when the command line has --trace or CAUSAL_WORLD_TRACE=1 is set.
static func from_args() -> bool:
	if "--trace" in OS.get_cmdline_user_args():
		return true
	return OS.get_environment("CAUSAL_WORLD_TRACE") == "1"
