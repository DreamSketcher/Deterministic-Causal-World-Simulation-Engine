"""v0.13 — the stdio JSON Lines transport, driven as a real child process.

These tests start ``python -m causal_world.server.jsonl`` exactly as the Godot
client does (pipes, one JSON object per line) and check the wire contract:
the ready line, version refusal, one reply per request, malformed input,
shutdown and EOF, and that stdout carries nothing but protocol lines.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from causal_world.observer.journal import JournalView
from causal_world.server.jsonl import PROTOCOL

SRC = Path(__file__).resolve().parents[1] / "src"


class Child:
    """One running ``causal_world.server.jsonl`` process."""

    def __init__(self, db_dir: Path) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "causal_world.server.jsonl", "--db-dir", str(db_dir)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=str(SRC),
        )

    def send(self, obj) -> None:
        line = obj if isinstance(obj, str) else json.dumps(obj)
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def recv(self) -> dict:
        line = self.proc.stdout.readline()
        assert line, f"child closed stdout; stderr: {self.proc.stderr.read()}"
        return json.loads(line)  # must be a JSON object on every line

    def ask(self, obj) -> dict:
        self.send(obj)
        return self.recv()

    def finish(self) -> int:
        try:
            self.proc.stdin.close()
        except BrokenPipeError:  # pragma: no cover
            pass
        return self.proc.wait(timeout=60)


HELLO = {"type": "hello", "protocol": PROTOCOL, "seed": 7,
         "ruleset": "player_resettle", "regions": 2, "agents": 54,
         "max_ticks": 200}


@pytest.fixture()
def child(tmp_path):
    c = Child(tmp_path / "worlds")
    yield c
    if c.proc.poll() is None:
        c.proc.kill()
        c.proc.wait()


def test_ready_line_first_and_stdout_is_only_json(child, tmp_path):
    ready = child.recv()
    assert ready["type"] == "ready"
    assert ready["protocol"] == PROTOCOL
    assert isinstance(ready["pid"], int)
    welcome = child.ask(HELLO)
    assert welcome["type"] == "welcome"
    assert welcome["protocol"] == PROTOCOL
    assert welcome["config"]["ruleset"] == "player_resettle"
    assert child.ask({"type": "shutdown"}) == {"type": "bye", "reason": "shutdown"}
    assert child.finish() == 0
    stderr = child.proc.stderr.read()
    assert "session" in stderr  # logs go to stderr, never to the protocol


def test_protocol_version_is_refused_before_anything_is_created(child, tmp_path):
    child.recv()  # ready
    reply = child.ask(dict(HELLO, protocol="causal-world-jsonl/0"))
    assert reply["type"] == "error" and reply["code"] == "protocol_mismatch"
    # refused: no session exists, a decision is still "send hello first"
    assert child.ask({"type": "decide", "seq": 1, "action": 0})["code"] == "not_awaiting"
    assert child.finish() == 0
    assert not (tmp_path / "worlds").exists() or not any((tmp_path / "worlds").iterdir())


def test_decisions_gaps_conflicts_and_malformed_input(child):
    child.recv()
    child.ask(HELLO)
    f1 = child.ask({"type": "decide", "seq": 1, "action": 0})
    assert f1["type"] == "frame" and f1["seq"] == 1 and f1["tick"] == 0
    assert f1["applied"] is True

    # redelivery of an applied seq: the same frame, the world is not stepped
    assert child.ask({"type": "decide", "seq": 1, "action": 0}) == f1

    gap = child.ask({"type": "decide", "seq": 5, "action": 0})
    assert gap["code"] == "seq_gap" and gap["resync"] == {"last_seq": 1}
    conflict = child.ask({"type": "decide", "seq": 1, "action": 6})
    assert conflict["code"] == "conflict"

    assert child.ask("this is not json")["code"] == "malformed"
    assert child.ask("[1, 2]")["code"] == "malformed"
    assert child.ask({"type": "decide", "seq": "1", "action": 0})["code"] == "malformed"
    assert child.ask({"type": "teleport"})["code"] == "unknown_type"

    # none of the refusals stepped the world: the next valid seq is still 2
    f2 = child.ask({"type": "decide", "seq": 2, "action": 0})
    assert f2["type"] == "frame" and f2["tick"] == 1
    assert child.ask({"type": "shutdown"})["type"] == "bye"
    assert child.finish() == 0


def test_blank_lines_are_ignored(child):
    child.recv()
    child.send("")
    child.send("   ")
    assert child.ask(HELLO)["type"] == "welcome"
    assert child.ask({"type": "shutdown"})["type"] == "bye"
    assert child.finish() == 0


def test_eof_keeps_the_archive_readable_and_the_life_open(child, tmp_path):
    """EOF is not a life end: the journal is committed, the life stays open.

    Ending a life is the explicit ``close`` message. Consequence (documented
    in the contract): a NAMED world whose life was left open on EOF refuses a
    takeover (``world_busy``) until its life is closed. The Godot slice does
    not name worlds, so each run has its own archive.
    """
    child.recv()
    named = dict(HELLO, world="slice-eof")
    assert child.ask(named)["type"] == "welcome"
    for seq in (1, 2, 3):
        assert child.ask({"type": "decide", "seq": seq, "action": 0})["type"] == "frame"
    assert child.finish() == 0  # EOF, no close

    db = tmp_path / "worlds" / "slice-eof.db"
    with JournalView(str(db)) as view:
        total, committed, rejected = view.counts()
        assert committed > 0
        life = json.loads(view.meta("life:1"))
        assert life["end"] is None  # still open

    again = Child(tmp_path / "worlds")
    try:
        again.recv()
        reply = again.ask(named)
        assert reply["type"] == "error" and reply["code"] == "world_busy"
        assert again.ask({"type": "shutdown"})["type"] == "bye"
        assert again.finish() == 0
    finally:
        if again.proc.poll() is None:
            again.proc.kill()


def test_close_ends_the_life_and_returns_the_hash(child):
    child.recv()
    child.ask(HELLO)
    child.ask({"type": "decide", "seq": 1, "action": 0})
    closed = child.ask({"type": "close"})
    assert closed["type"] == "closed" and closed["reason"] == "abdicate"
    assert len(closed["hash"]) == 64
    # after close the life is over: a decision is refused, nothing is stepped
    after = child.ask({"type": "decide", "seq": 2, "action": 0})
    assert after["type"] == "error" and after["code"] == "finalized"
    assert child.finish() == 0


def test_look_is_read_only_and_needs_hello(child):
    child.recv()
    assert child.ask({"type": "look"})["code"] == "not_awaiting"
    child.ask(HELLO)
    view = child.ask({"type": "look"})
    assert view["type"] == "view" and view["tick"] == -1
    assert len(view["world"]["cells"]) == 12
    again = child.ask({"type": "look"})
    assert again["journal"] == view["journal"]  # no step, no write
    frame = child.ask({"type": "decide", "seq": 1, "action": 0})
    assert frame["tick"] == 0
    assert child.ask({"type": "shutdown"})["type"] == "bye"
    assert child.finish() == 0
