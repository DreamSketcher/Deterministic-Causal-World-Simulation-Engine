"""The core's debug trace is read-only and never changes the world.

Runs the same short life twice through the dispatcher: once plain, once with
``trace=True``. The journal hashes and the replies must be identical; the
trace must write only ASCII lines that name each step's transitions.
"""

from __future__ import annotations

from causal_world.server.dispatch import Dispatcher

HELLO = {"type": "hello", "protocol": "causal-world-jsonl/1", "seed": 7,
         "ruleset": "player_resettle", "regions": 2, "agents": 54, "max_ticks": 200}


def _play(tmp_path, trace: bool, steps: int = 3):
    lines: list[str] = []
    registry: dict = {}
    dispatcher = Dispatcher(registry, str(tmp_path), log=lines.append, trace=trace)
    conn: dict = {"session": None}
    replies = [dispatcher.handle(HELLO, conn)]
    for seq in range(1, steps + 1):
        replies.append(dispatcher.handle({"type": "decide", "seq": seq, "action": 0}, conn))
    hashes = [r["journal"]["hash"] for r in replies if r.get("type") == "frame"]
    return replies, hashes, lines


def test_trace_does_not_change_the_world(tmp_path):
    plain, plain_hashes, _ = _play(tmp_path / "plain", trace=False)
    traced, traced_hashes, lines = _play(tmp_path / "traced", trace=True)
    assert traced_hashes == plain_hashes
    assert [r.get("tick") for r in traced] == [r.get("tick") for r in plain]
    assert [r.get("type") for r in traced] == [r.get("type") for r in plain]
    assert len(traced_hashes) == 3


def test_trace_names_each_step_and_stays_ascii(tmp_path):
    _, _, lines = _play(tmp_path, trace=True)
    assert any(line.startswith("[proto] << decide seq=1") for line in lines)
    assert any(line.startswith("[proto] >> frame seq=3") for line in lines)
    step_headers = [line for line in lines if line.startswith("[journal] step tick=")]
    assert len(step_headers) == 3
    # the first step's transitions are the ones after the genesis records
    transitions = [line for line in lines if line.startswith("[journal]   T")]
    assert transitions and all(" COMMITTED " in t or " REJECTED " in t for t in transitions)
    for line in lines:
        line.encode("ascii")  # the Godot client reads these lines as ASCII


def test_trace_failure_never_reaches_the_protocol(tmp_path, monkeypatch):
    from causal_world.server import trace as trace_module

    def broken(self, *args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(trace_module.Tracer, "step", broken)
    lines: list[str] = []
    dispatcher = Dispatcher({}, str(tmp_path), log=lines.append, trace=True)
    conn: dict = {"session": None}
    dispatcher.handle(HELLO, conn)
    reply = dispatcher.handle({"type": "decide", "seq": 1, "action": 0}, conn)
    assert reply["type"] == "frame" and reply["applied"] is True
    assert any("[trace] failed: RuntimeError: boom" in line for line in lines)
