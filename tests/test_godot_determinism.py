"""v0.13 — determinism of the Godot slice, checked with control hashes.

The slice's only player action is ``work`` (action 0), one per button press.
This test plays that exact script (until the life ends) in three ways and
requires the same journal hash after every tick:

1. in process, through ``Session`` (the core as the tests of v0.6-v0.12 use it);
2. in a child process over the stdio JSON Lines transport (what Godot runs);
3. against the committed golden ``tests/golden/godot_slice_reference.json``.

Regenerate the golden ONLY after an intended change of the rules or of the
kernel (``python tests/test_godot_determinism.py --regen``) and say so in the
commit message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from causal_world.server.session import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_jsonl_protocol import HELLO, Child  # noqa: E402

GOLDEN = Path(__file__).parent / "golden" / "godot_slice_reference.json"
MAX_PRESSES = 80  # the life ends by death well before this (tick 45 at seed 7)


def _in_process(db_dir: Path) -> list[dict]:
    s = Session(seed=7, ruleset="player_resettle", regions=2, agents=54,
                max_ticks=200, db_dir=str(db_dir))
    rows = []
    try:
        for seq in range(1, MAX_PRESSES + 1):
            frame = s.decide(seq, 0)
            rows.append({"seq": seq, "tick": frame["tick"],
                         "journal_hash": frame["journal"]["hash"],
                         "committed": frame["journal"]["committed"],
                         "alive": frame["alive"]})
            if not frame["alive"]:
                break
    finally:
        if s.state != "finalized":
            s.close()
    return rows


def _over_stdio(db_dir: Path) -> tuple[list[dict], dict | None]:
    child = Child(db_dir)
    try:
        child.recv()  # ready
        assert child.ask(HELLO)["type"] == "welcome"
        rows: list[dict] = []
        finished = None
        for seq in range(1, MAX_PRESSES + 1):
            frame = child.ask({"type": "decide", "seq": seq, "action": 0})
            assert frame["type"] == "frame", frame
            rows.append({"seq": seq, "tick": frame["tick"],
                         "journal_hash": frame["journal"]["hash"],
                         "committed": frame["journal"]["committed"],
                         "alive": frame["alive"]})
            if "finished" in frame:
                finished = frame["finished"]
            if not frame["alive"]:
                break
        assert child.ask({"type": "shutdown"})["type"] == "bye"
        assert child.finish() == 0
        return rows, finished
    finally:
        if child.proc.poll() is None:
            child.proc.kill()


def test_stdio_life_equals_in_process_life_hash_by_hash(tmp_path):
    local = _in_process(tmp_path / "local")
    remote, _ = _over_stdio(tmp_path / "remote")
    assert len(local) == len(remote) > 40
    assert remote == local


def test_slice_life_matches_the_committed_golden(tmp_path):
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["config"] == {"seed": 7, "ruleset": "player_resettle",
                                "regions": 2, "agents": 54, "action": "work"}
    rows, finished = _over_stdio(tmp_path / "golden")
    assert rows == golden["ticks"]
    assert finished is not None and finished["reason"] == "death"
    assert finished["death_tick"] == golden["death_tick"]


def test_two_independent_runs_agree(tmp_path):
    a, _ = _over_stdio(tmp_path / "a")
    b, _ = _over_stdio(tmp_path / "b")
    assert a == b


def regenerate() -> None:  # pragma: no cover - maintenance entry point
    rows, finished = _over_stdio(Path("/tmp/godot_golden_regen"))
    payload = {
        "config": {"seed": 7, "ruleset": "player_resettle", "regions": 2,
                   "agents": 54, "action": "work"},
        "ticks": rows,
        "death_tick": None if finished is None else finished["death_tick"],
    }
    GOLDEN.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN} ({len(rows)} presses)")


if __name__ == "__main__":  # pragma: no cover
    if "--regen" in sys.argv:
        regenerate()
