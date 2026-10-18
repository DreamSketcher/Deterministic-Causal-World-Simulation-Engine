"""v0.13 — the Godot client contract (client/godot/contract/v1.json).

The JSON file lists the fields the client reads. This test checks that the
REAL replies of the core have them with the declared types, and that the
validator itself rejects a missing or mistyped field (otherwise the check
could pass vacuously).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from causal_world.server.dispatch import Dispatcher
from causal_world.server.jsonl import PROTOCOL
from causal_world.server.session import ProtocolError, Session

CONTRACT = Path(__file__).resolve().parents[1] / "client" / "godot" / "contract" / "v1.json"
SPEC = json.loads(CONTRACT.read_text(encoding="utf-8"))

_TYPES = {
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "string": lambda v: isinstance(v, str),
    "bool": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def check(obj, spec_name: str) -> list[str]:
    """Return a list of contract violations (empty = conforms)."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return [f"{spec_name}: not an object"]
    for key, declared in SPEC[spec_name].items():
        if key not in obj:
            errors.append(f"{spec_name}.{key}: missing")
            continue
        alternatives = declared.split("|")
        if not any(_TYPES[alt](obj[key]) for alt in alternatives):
            errors.append(
                f"{spec_name}.{key}: expected {declared}, got {type(obj[key]).__name__}"
            )
    return errors


def check_frame(frame: dict) -> list[str]:
    """A frame or a view: both carry the world section the client draws."""
    errors = check(frame, "view" if frame.get("type") == "view" else "frame")
    errors += check(frame.get("you"), "frame.you")
    errors += check(frame.get("journal"), "frame.journal")
    world = frame.get("world") or {}
    errors += check(world, "frame.world")
    for row in world.get("cells", []):
        errors += check(row, "frame.world.cell")
    for row in world.get("regions", []):
        errors += check(row, "frame.world.region")
    for row in world.get("situations", []):
        errors += check(row, "frame.world.situation")
    return errors


# ------------------------------------------------------------- the validator

def test_contract_protocol_name_matches_the_server():
    assert SPEC["protocol"] == PROTOCOL


def test_validator_rejects_missing_and_mistyped_fields():
    frame_ok = {k: None for k in SPEC["frame"]}
    frame_ok.update(type="frame", seq=1, tick=0, applied=True, reject=None,
                    alive=True, you={}, world={}, decree=None, orders={},
                    journal={})
    missing = dict(frame_ok)
    del missing["tick"]
    assert any("frame.tick: missing" in e for e in check(missing, "frame"))
    wrong = dict(frame_ok, seq="1")
    assert any("frame.seq" in e for e in check(wrong, "frame"))
    boolean_is_not_int = dict(frame_ok, seq=True)
    assert any("frame.seq" in e for e in check(boolean_is_not_int, "frame"))
    assert check({"type": "error", "code": "x", "msg": "y"}, "error") == []


# ------------------------------------------------- the real replies conform

@pytest.fixture()
def live(tmp_path):
    s = Session(seed=7, ruleset="player_resettle", regions=2, agents=54,
                max_ticks=200, db_dir=str(tmp_path))
    yield s
    if s.state != "finalized":
        s.close()


def test_welcome_conforms(tmp_path):
    registry: dict = {}
    d = Dispatcher(registry, str(tmp_path))
    conn: dict = {"session": None}
    reply = d.handle({"type": "hello", "seed": 7, "ruleset": "player_resettle",
                      "regions": 2, "agents": 54}, conn)
    reply = dict(reply, protocol=PROTOCOL, kernel_version="0.1.0")  # as jsonl does
    # over the wire JSON turns the int keys of the card into strings: the
    # client sees "0".."6", so check the wire form, not the Python form
    wire = json.loads(json.dumps(reply))
    assert check(wire, "welcome") == []
    assert wire["action_card"]["0"] == "work"  # the card the client shows


def test_every_frame_of_a_life_conforms(live):
    """Every frame the client can receive, including the death frame."""
    seen_alive_false = False
    for seq in range(1, 80):
        frame = live.decide(seq, 0)
        assert check_frame(frame) == [], (seq, check_frame(frame))
        assert frame["tick"] == seq - 1
        if not frame["alive"]:
            seen_alive_false = True
            break
    assert seen_alive_false, "the scripted life should end in the window"


def test_cells_carry_grid_coordinates_and_provenance_fields(live):
    frame = live.decide(1, 0)
    cells = frame["world"]["cells"]
    assert len(cells) == 12  # 2 regions x 6 cells, a fixed grid
    coords = {(c["x"], c["y"]) for c in cells}
    assert len(coords) == len(cells)  # no two cells share a grid square
    assert all(isinstance(c["last_source"], (int, str)) or c["last_source"] is None
               for c in cells)


def test_rejected_action_still_conforms(live):
    frame = live.decide(1, 99)
    assert frame["applied"] is False and frame["reject"] == "out_of_range"
    assert check_frame(frame) == []


def test_view_conforms_before_and_after_a_step(live):
    """``look`` reads the world with no step: the map exists before any action."""
    before = live.look()
    assert check_frame(before) == []
    assert before["tick"] == -1 and before["type"] == "view"
    assert len(before["world"]["cells"]) == 12
    journal_before = before["journal"]["hash"]
    assert live.look()["journal"]["hash"] == journal_before  # read-only
    assert live.sim.state.tick == 0
    live.decide(1, 0)
    after = live.look()
    assert check_frame(after) == [] and after["tick"] == 0


def test_error_replies_conform(live):
    d = Dispatcher({}, ".")
    for msg in ({"type": "decide", "seq": 5, "action": 0},  # seq_gap: world untouched
                {"type": "nope"}, "not-a-dict", {"no": "type"}):
        conn: dict = {"session": live}
        reply = d.handle(msg, conn) if not isinstance(msg, str) else d.handle_raw(
            json.dumps(msg), conn)
        if reply.get("type") == "error":
            assert check(reply, "error") == [], reply
    with pytest.raises(ProtocolError):
        live.decide(9, 0)  # gap; the world is untouched
    assert live.sim.state.tick == 0


ROOT = Path(__file__).resolve().parents[1]
GD_BRIDGE = ROOT / "client/godot/scripts/protocol/py_bridge.gd"


def test_godot_launcher_string_starts_the_core(tmp_path):
    """The `python -c` line in py_bridge.gd is the one that is run.

    The string is read from the GDScript source, so the test fails if the
    launcher drifts from the module it names. Godot itself is not run here.
    """
    import re
    import subprocess
    import sys

    source = GD_BRIDGE.read_text(encoding="utf-8")
    block = re.search(r"var args: PackedStringArray = PackedStringArray\(\[(.*?)\n\t*\]\)", source, re.S)
    assert block, "launcher not found in py_bridge.gd"
    literals = re.findall(r'"((?:[^"\\]|\\.)*)"', block.group(1))
    at = literals.index("-c") + 1  # the program is the literals after "-c"
    code = "".join(literals[at:at + 3])  # import, path insert, main call
    assert "sys.path.insert(0, sys.argv[1])" in code
    assert "from causal_world.server.jsonl import main" in code
    assert "sys.exit(main(" in code
    proc = subprocess.Popen(
        [sys.executable, "-c", code, str(ROOT / "src"), str(tmp_path / "worlds")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    ready = json.loads(proc.stdout.readline())
    assert ready["type"] == "ready" and ready["protocol"] == "causal-world-jsonl/1"
    # non-ASCII input is refused and logged: both pipes must stay ASCII
    proc.stdin.write("почва: не JSON\n")
    proc.stdin.flush()
    refusal = json.loads(proc.stdout.readline())
    assert refusal["type"] == "error" and refusal["code"] == "malformed"
    out, err = proc.communicate('{"type": "shutdown"}\n', timeout=60)
    assert json.loads(out.strip().splitlines()[-1])["type"] == "bye"
    assert proc.returncode == 0
    out.encode("ascii")
    err.encode("ascii")  # would raise if a Cyrillic log line leaked through


def test_gdscript_private_names_are_declared():
    """Every `_name` used in a .gd file is declared there (or is a parameter).

    gdparse checks syntax only; Godot reports an undeclared identifier as a
    parse error when the project loads. This catches that case without Godot.
    """
    import re

    for path in sorted((ROOT / "client/godot").rglob("*.gd")):
        src = re.sub(r"#.*", "", path.read_text(encoding="utf-8"))  # code only
        declared = set(re.findall(
            r"^\s*(?:static\s+)?(?:var|func|const|signal|class)\s+(\w+)", src, re.M))
        params = set()
        for signature in re.findall(r"func\s+\w+\s*\((.*?)\)", src, re.S):
            params.update(re.findall(r"(_\w+)", signature))
        loop_vars = set(re.findall(r"for\s+(\w+)", src))
        used = set(re.findall(r"(?<![\w.])(_\w+)", src))
        missing = sorted(used - declared - params - loop_vars)
        assert not missing, f"{path.name}: undeclared {missing}"
