# Causal World — Godot slice (client)

A minimal 2D client (Godot 4.4, GDScript with types) over the Python core.
The core is the only source of truth: this project draws its replies and sends
actions. It computes no game state.

## What it does

1. Starts the Python core as a separate process (`causal_world.server.jsonl`).
2. Talks JSON Lines, protocol `causal-world-jsonl/1` (see `contract/v1.json`).
3. Creates a small reproducible world: seed 7, ruleset `player_resettle`,
   2 regions, 54 agents, `max_ticks` 200.
4. Reads the world **before** any step (`look` → `view`) and draws the map.
5. Click a cell: the panel shows facts, links (situations and goals with their
   transition ids), and hypotheses (never drawn as facts).
6. "Работать (work) · ход" sends one `decide`; the core takes one tick; the log
   shows the real result: the player's values before and after, journal
   growth, changed cell values, new and closed situations, and the death
   verdict if there is one.

## Layout

| Path | Role |
|---|---|
| `project.godot` | project, main scene, 1280×720, GL Compatibility renderer |
| `scenes/main.tscn` | root `Node2D` with `scripts/game/game.gd` |
| `scripts/protocol/py_bridge.gd` | starts the core (`OS.execute_with_pipe`), reader thread, inbox, `stop()` |
| `scripts/protocol/dto.gd` | contract check (`Dto.validate`) and typed views (`Dto.View`, `Dto.Cell`, `Dto.Region`) |
| `scripts/game/game.gd` | controller: protocol flow, one request in flight, result log |
| `scripts/game/world_map.gd` | grid map, camera (right/middle drag, wheel zoom), cell click |
| `scripts/game/cell_panel.gd` | the cell panel: факты / связи / гипотезы |
| `contract/v1.json` | field names and types of every reply; the Python test reads the same file |

## Running

The core is standard-library Python; the repository's `.venv` is optional.
The core is found in this order:

1. `--python=/path/to/python` (after `--` on the Godot command line);
2. the `CAUSAL_WORLD_PYTHON` environment variable;
3. `<repo>/.venv/bin/python` (or `.venv\Scripts\python.exe` on Windows);
4. `python3` (Linux) or `python` (Windows).

The sources are taken from `<repo>/src`, or from `--src=<dir>`.

```
# from the repository root, after  pip install -e ".[dev,server]"
godot --path client/godot
```

Archives of each run go to Godot's `user://worlds` (`--db-dir`). Each run gets
its own world: a named world that was left open would answer `world_busy`.

## Debugging

**Where the trace is.** All output goes to the **Output** panel (the bottom panel
of the editor, tab "Output"). It is *not* in the Debugger tabs: "Stack Trace"
and "Errors" show only errors and warnings, so a plain `print` never appears
there. A run from the editor's Play button is a debug build, so the trace is
on by default. Off in release builds.

**Trace file.** Every line is also written to `user://trace/trace-<time>.log`,
flushed per line. The absolute path is the first line of the trace
(`[trace] file: …`) and is shown in the game log.

**Report.** The "Сохранить отчёт" button writes `user://reports/report-<time>.json`
with the last raw reply of the core (view and frame), the game log, the core's
stderr tail, the selected cell, the state of the action button and the trace file
path. The absolute path of the report is copied to the clipboard.

**Switches** (after `--` on the command line, or in the environment):
`--trace` turns the trace on in any build, `--no-trace` turns it off,
`CAUSAL_WORLD_TRACE=1` turns it on. Example: `godot --path client/godot -- --trace`.

`user://` is Godot's user data folder: on Windows
`%APPDATA%\Godot\app_userdata\<project name>`, on Linux `~/.local/share/godot/app_userdata/<project name>`.

With the trace on, the Output panel shows, in order:

* `[trace  12345 ms][input]` — every key press and mouse press, with the screen
  and world position. Presses on buttons are also logged by the button handler,
  so a click that does nothing is visible.
* `[trace …][ui]` — when the action button turns on or off, and why
  (for example: `ждём ответ ядра (decide)`, `жизнь окончена`).
* `[trace …][map]` — cell clicks (with the cell and its grid position), zoom,
  pan start and end, selected cell.
* `[trace …][proto]` — every protocol line sent (`>>`) and received (`<<`), with
  the time the reply took.
* `[trace …][frame]` — the result of each decision: seq, tick, applied, alive,
  player values, journal counts, and the journal hash prefix.
* `[core] …` — the core's own trace, printed by the core itself: every request it
  receives and reply it sends, and for each step the transitions it produced
  (`T<id> t<tick> <system>/<operation> <status>`, changed fields as `old->new`,
  and the random draws). Failures are shown as warnings.
* `[bridge] …` — start and stop of the core process, and why it stopped.

The core's trace reads the journal and never writes to it. The first step's
journal hash is the one in `tests/golden/godot_slice_reference.json`, so the
trace can be checked against the reference run.

## Protocol safety

* A reply that does not match `contract/v1.json` is logged and not drawn.
* A `seq_gap` error adopts the core's `resync.last_seq`.
* After a death, the core answers `finalized`; the button is disabled by then.
* Core stderr is kept as a tail for the error log; it is never parsed.

## Tests

Python side (run by `pytest`):

* `tests/test_godot_contract.py` — the real replies match the contract; the
  launcher string in `py_bridge.gd` is extracted and run as a subprocess;
  `look` conforms before and after a step.
* `tests/test_jsonl_protocol.py` — a real stdio process: `ready`, refusal on
  protocol mismatch, `seq_gap`, `conflict`, `malformed`, `close` → `finalized`,
  `look` is read-only.
* `tests/test_godot_determinism.py` — the stdio run matches the in-process run
  hash by hash; the golden `tests/golden/godot_slice_reference.json` pins the
  scenario (46 presses, death on tick 45, first and last journal hash).

Godot side: `gdlint` (gdtoolkit 4.5.0) passes on all `.gd` files; `gdparse`
parses them.

## Not verified

* **The Godot editor and the game were NOT run in this environment.** Godot
  could not be installed here (no engine package is reachable from the sandbox).
  Everything that depends on the engine — the scene, the thread, the pipes,
  the mouse — is unverified.
* Windows and Linux builds: not built, not run. The launcher finds Python with
  Windows path rules, but this is not tested.
* Exported builds: `res://` is packed in an export, so the repository root is
  not found from it. Pass `--src=` and `--python=` explicitly.
