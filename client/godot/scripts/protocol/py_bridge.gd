class_name PyBridge
extends Node
## Owns the Python core process and its pipes.
##
## Two background threads read the pipes line by line: one for stdout (the
## protocol) and one for stderr (the core's log, kept as a short tail). The
## threads only fill guarded arrays; the main thread drains them in poll(),
## so no game code runs on a reader thread and the main thread never blocks
## on a pipe. The core writes ASCII only (jsonl.py), so every line decodes.
##
## Lifecycle: start() -> lines via line_received -> stop() asks the core to
## shut down -> poll() ends it (bridge_ended) once it exits, or kills it after
## STOP_GRACE_MSEC. Quitting the game waits for bridge_ended, not a fixed delay.

signal line_received(line: String)
signal bridge_failed(reason: String)
signal bridge_ended(reason: String)
## One line of the core's log (stderr), on the main thread, in order.
signal log_line_received(line: String)

const STOP_GRACE_MSEC: int = 1500
const STDERR_TAIL_LINES: int = 20
const LOG_QUEUE_MAX: int = 500  ## a flood of log lines drops the oldest, never blocks

## Last lines of the core's log. For error messages only, never protocol.
var stderr_tail: PackedStringArray = PackedStringArray()
## When true, every protocol line sent and received is printed to the Godot
## Output panel (the debugger console). Set it before start().
var trace: bool = false

var _pid: int = -1
var _stdio: FileAccess = null
var _stderr: FileAccess = null
var _out_thread: Thread = null
var _err_thread: Thread = null
var _mutex: Mutex = Mutex.new()
var _inbox: Array[String] = []
var _log_inbox: Array[String] = []
var _running: bool = false
var _stop_started_msec: int = -1
var _ended: bool = false


## Start the core: `python -c` puts `src_dir` on sys.path and runs the
## JSON Lines server on `db_dir`. Returns false (and emits bridge_failed)
## if the interpreter cannot be started.
func start(python: String, src_dir: String, db_dir: String) -> bool:
	if _running:
		return true
	DirAccess.make_dir_recursive_absolute(db_dir)
	var args: PackedStringArray = PackedStringArray([
		"-c",
		"import sys; sys.path.insert(0, sys.argv[1]); "
		+ "from causal_world.server.jsonl import main; "
		+ "sys.exit(main(['--db-dir', sys.argv[2]]))",
		src_dir,
		db_dir,
	])
	var pipe: Dictionary = OS.execute_with_pipe(python, args)
	if pipe.is_empty():
		bridge_failed.emit("could not start the Python core: '%s'" % python)
		return false
	_pid = int(pipe["pid"])
	_stdio = pipe["stdio"]
	_stderr = pipe["stderr"]
	_running = true
	_ended = false
	_stop_started_msec = -1
	stderr_tail = PackedStringArray()
	_inbox.clear()
	_log_inbox.clear()
	_out_thread = Thread.new()
	_out_thread.start(_read_pipe.bind(_stdio, false))
	_err_thread = Thread.new()
	_err_thread.start(_read_pipe.bind(_stderr, true))
	return true


func is_running() -> bool:
	return _running


func send(message: Dictionary) -> bool:
	if not _running or _stdio == null:
		return false
	var line: String = JSON.stringify(message)
	if trace:
		print("[proto >>] %s" % line.left(400))
	_stdio.store_string(line + "\n")
	return _stdio.get_error() == OK


## Drain queued lines onto the main thread and watch the process. Call from
## _process(). Never blocks.
func poll() -> void:
	_emit_queued()
	if not _running:
		return
	if not OS.is_process_running(_pid):
		_finish("the Python core exited")
	elif _stop_started_msec >= 0 and Time.get_ticks_msec() - _stop_started_msec > STOP_GRACE_MSEC:
		OS.kill(_pid)
		_finish("stopped (the core did not exit in time, so it was killed)")


## Ask the core to stop. It replies "bye" and exits; poll() finishes the bridge.
## Returns at once; wait for bridge_ended if the caller must act after exit.
func stop() -> void:
	if not _running or _stop_started_msec >= 0:
		return
	send({"type": "shutdown"})
	_stop_started_msec = Time.get_ticks_msec()


func _exit_tree() -> void:
	if _running:
		# the window is closing: do not wait for the core, the journal is
		# committed every step, so a kill loses nothing that was not already
		# committed
		OS.kill(_pid)
		_finish("closed with the window")


func _emit_queued() -> void:
	_mutex.lock()
	var lines: Array[String] = _inbox.duplicate()
	var logs: Array[String] = _log_inbox.duplicate()
	_inbox.clear()
	_log_inbox.clear()
	_mutex.unlock()
	for line: String in logs:
		log_line_received.emit(line)
	for line: String in lines:
		line_received.emit(line)


func _finish(reason: String) -> void:
	if _ended:
		return
	_ended = true
	_running = false
	# both pipes reach end-of-file once the process is gone, so the reader
	# threads return; joining them here cannot block
	if _out_thread != null and _out_thread.is_started():
		_out_thread.wait_to_finish()
	if _err_thread != null and _err_thread.is_started():
		_err_thread.wait_to_finish()
	_emit_queued()  # lines that arrived just before the exit (e.g. "bye")
	_stdio = null
	_stderr = null
	bridge_ended.emit(reason)


## Runs on a reader thread. Stdout lines go to the inbox; stderr lines go to
## the tail. Only mutex-guarded data is touched.
func _read_pipe(stream: FileAccess, is_log: bool) -> void:
	while stream != null and stream.is_open():
		var line: String = stream.get_line()
		if line.is_empty():
			if stream.get_error() != OK or stream.eof_reached():
				break
			continue
		_mutex.lock()
		if is_log:
			stderr_tail.append(line)
			while stderr_tail.size() > STDERR_TAIL_LINES:
				stderr_tail.remove_at(0)
			_log_inbox.append(line)
			while _log_inbox.size() > LOG_QUEUE_MAX:
				_log_inbox.remove_at(0)
		else:
			_inbox.append(line)
		_mutex.unlock()
