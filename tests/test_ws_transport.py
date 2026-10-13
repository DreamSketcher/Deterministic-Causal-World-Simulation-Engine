"""v0.6 step 5 (part 2): WebSocket transport — §5 acceptance.

The P1 claim in one test: one seed + one decision stream through a socket
produces a journal whose canonical hash and whose BiographyCard fingerprint
are IDENTICAL to the local run. Plus: mid-run reconnect with re-delivery,
conflict after reconnect, and garbage input that never touches the world.
"""

from __future__ import annotations

import json
import random
import socket
import threading

import pytest

from causal_world import create_world
from causal_world.observer.biography import build_biography
from causal_world.world.rules import get_ruleset

websockets_server = pytest.importorskip("websockets.sync.server")
pytest.importorskip("websockets.sync.client")  # both halves of the extra

from causal_world.server.client import LifeClient  # noqa: E402
from causal_world.server.ws import make_handler  # noqa: E402


def _script(n=200):
    rng = random.Random(99)
    return [
        2 if (r := rng.random()) < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6
        for _ in range(n)
    ]


def _local_run(tmp_path, actions):
    """The non-network baseline: same seed, same stream, no transport."""
    db = str(tmp_path / "local.db")
    sim = create_world(seed=7, ruleset=get_ruleset("player_life"), ticks=0,
                       regions=2, agents=60, persist=db)
    from causal_world.player import DecisionChannel, attach_player_channel

    attach_player_channel(sim, DecisionChannel(actions=list(actions)))
    for _ in actions:
        sim.step()
    h = sim.journal.hash()
    sim.journal.close()
    return db, h


@pytest.fixture()
def url(tmp_path):
    registry: dict = {}
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    srv = websockets_server.serve(
        make_handler(registry, str(tmp_path)), "127.0.0.1", port
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"ws://127.0.0.1:{port}", registry
    srv.shutdown()


# ----------------------------------------------------------------- P1: law


def test_ws_life_is_bit_identical_to_local(tmp_path, url):
    base, registry = url
    script = _script()
    client = LifeClient(base)
    w = client.hello_new(seed=7, regions=2, agents=60, max_ticks=200)
    assert w["type"] == "welcome" and w["alive"] is True

    n = 0
    for seq, a in enumerate(script, 1):
        f = client.decide(seq, a)
        assert f["type"] == "frame"
        n = seq
        if not f["alive"]:
            ev = client.next_event(timeout=5.0)
            assert ev and ev["type"] == "finished" and ev["death_tick"] == 51
            break

    card = client.bio()
    au = client.autopsy()
    closed = client.close()
    client.terminate()
    assert (n, closed["reason"]) == (52, "death")
    assert au["label"] == "acute_infection"

    local_db, local_hash = _local_run(tmp_path, script[:n])
    assert closed["hash"] == local_hash  # the archive agrees, byte canon
    assert card["fingerprint"] == build_biography(local_db, "agent:0").fingerprint()
    assert card["meta"]["committed"] >= 1000  # the whole world is in there


# ------------------------------------------------- §2 reconnect, garbage


def test_reconnect_redelivery_and_garbage(tmp_path, url):
    base, registry = url
    script = _script()
    c1 = LifeClient(base)
    w = c1.hello_new(seed=7, regions=2, agents=40, max_ticks=100)
    sid = w["session_id"]
    frames = {}
    for seq in range(1, 6):
        frames[seq] = c1.decide(seq, script[seq - 1])
    c1.terminate()  # client vanishes at the worst moment: mid-life

    c2 = LifeClient(base)
    w2 = c2.hello_resume(sid)
    assert w2["session_id"] == sid and w2["last_seq"] == 5
    assert w2["alive"] is True  # the world PAUSED; the clock never free-ran

    # the ack for seq 5 was lost with the socket: re-delivery is safe
    redelivered = c2.decide(5, script[4])
    assert redelivered == frames[5]
    # same seq with a DIFFERENT action is a conflict, never a second action
    conflict = c2.decide(5, script[4] + 100)  # any value ≠ the applied one
    assert conflict["type"] == "error" and conflict["code"] == "conflict"

    # garbage at the transport level: errors, live connection, untouched world
    c2.send_raw("this is not json")
    assert c2.recv_raw()["code"] == "malformed"
    c2.send_raw(json.dumps({"type": "nonsense"}))
    assert c2.recv_raw()["code"] == "unknown_type"

    tick_before = registry[sid].sim.state.tick
    f6 = c2.decide(6, 0)
    assert f6["tick"] == 5 and f6["type"] == "frame"
    assert registry[sid].sim.state.tick == tick_before + 1  # exactly one step

    closed = c2.close()
    assert closed["type"] == "closed"
    c2.terminate()

    # death eviction? none: finalized session still answers via the file
    c3 = LifeClient(base)
    assert c3.hello_resume(sid)["state"] == "finalized"
    assert c3.bio()["fingerprint"] == build_biography(
        registry[sid].db_path, "agent:0").fingerprint()
    c3.terminate()
