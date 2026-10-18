class_name PyBridge
extends Node
## Owns the Python core process and its JSON Lines pipes.
##
## The process is started with OS.execute_with_pipe. A background thread
## blocks on stdout and queues complete lines; the main thread drains the
## queue in poll(), so no game code runs on the reader thread. Writes go
## straight to stdin from the main thread.
##
## Lifecycle: start() -> lines arrive via line_received -> stop() sends
## "shutdown" and waits briefly, then kills the process if it is still alive.

signal line_received(line: String)
signal bridge_failed(reason: String)
signal bridge_ended(reason: String)

## Last lines of the core's stderr, for error messages only (never protocol).
var stderr_tail: PackedStringArray = PackedStringArray()

var _pid: int = -1
var _stdio: FileAccess = null
var _stderr: FileAccess = null
var _reader: Thread = null
var _mutex: Mutex = Mutex.new()
var _inbox: Array[String] = []
var _running: bool = false
var _ended_emitted: bool = false


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
	_reader = Thread.new()
	_reader.start(_read_loop)
	return true


func is_running() -> bool:
	return _running


func send(message: Dictionary) -> bool:
	if not _running or _stdio == null:
		return false
	_stdio.store_string(JSON.stringify(message) + "\n")
	return _stdio.get_error() == OK


## Drain queued lines onto the main thread. Call from _process().
func poll() -> void:
	_mutex.lock()
	var lines: Array[String] = _inbox.duplicate()
	_inbox.clear()
	_mutex.unlock()
	for line: String in lines:
		line_received.emit(line)
	if _running and not OS.is_process_running(_pid):
		_end("the Python core exited")


## Ask the core to stop (it replies "bye"), then kill it if it lingers.
func stop() -> void:
	if not _running:
		return
	send({"type": "shutdown"})
	var waited: int = 0
	while OS.is_process_running(_pid) and waited < 30:
		OS.delay_msec(50)
		waited += 1
	if OS.is_process_running(_pid):
		OS.kill(_pid)
	_end("stopped")


func _exit_tree() -> void:
	stop()


func _end(reason: String) -> void:
	if _ended_emitted:
		return
	_ended_emitted = true
	_running = false
	if _stderr != null and _stderr.is_open():
		var parts: PackedStringArray = _stderr.get_as_text().split("\n", false)
		stderr_tail = parts.slice(maxi(0, parts.size() - 20))
	_stdio = null
	_stderr = null
	if _reader != null and _reader.is_started():
		_reader.wait_to_finish()
	bridge_ended.emit(reason)


## Runs on the reader thread. Only touches the mutex-guarded inbox.
func _read_loop() -> void:
	var stdio: FileAccess = _stdio
	while stdio != null and stdio.is_open():
		var line: String = stdio.get_line()
		if line.is_empty():
			if stdio.eof_reached():
				break
			continue
		_mutex.lock()
		_inbox.append(line)
		_mutex.unlock()
