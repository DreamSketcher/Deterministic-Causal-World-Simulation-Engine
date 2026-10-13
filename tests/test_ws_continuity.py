"""v0.6 step 6 on the wire: two lives through one server, world_busy,
strict names — and the multi-life P1 claim: the whole life CHAIN played
over WebSockets is bit-identical to the same chain played locally.
"""

from __future__ import annotations

import random
import socket
import threading

import pytest

websockets_server = pytest.importorskip("websockets.sync.server")
pytest.importorskip("websockets.sync.client")

from causal_world.server.client import LifeClient  # noqa: E402
from causal_world.server.session import Session  # noqa: E402
from causal_world.server.ws import make_handler  # noqa: E402


def _script(n=60, source=99):
    rng = random.Random(source)
    return [
        2 if (r := rng.random()) < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6
        for _ in range(n)
    ]


@pytest.fixture()
def world_env(tmp_path):
    registry: dict = {}
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    srv = websockets_server.serve(
        make_handler(registry, str(tmp_path)), "127.0.0.1", port
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"ws://127.0.0.1:{port}", registry, tmp_path
    srv.shutdown()


def _life(client, script, upto):
    for seq, a in enumerate(script, 1):
        f = client.decide(seq, a)
        assert f["type"] == "frame", f
        if seq >= upto or not f["alive"]:
            break
    return seq


def test_two_lives_over_the_socket_and_busy(world_env):
    base, registry, tmp = world_env
    script = _script()
    c1 = LifeClient(base)
    w1 = c1.hello_new(world="dyn", seed=21, regions=4, agents=50, max_ticks=12)
    assert w1["type"] == "welcome"
    assert w1["life"] == {"n": 1, "agent": "agent:0", "succession": "genesis"}
    assert w1["tick"] == 0

    # a second life cannot open while the first writer is active (§9 Q2)
    c2 = LifeClient(base)
    busy = c2.hello_new(world="dyn")
    assert busy["code"] == "world_busy" and busy["session"] == w1["session_id"]
    # no shadow archive: one DB for the whole world (WAL sidecars of the
    # live writer aside)
    assert sorted(p.name for p in tmp.iterdir() if p.suffix == ".db") == ["dyn.db"]

    _life(c1, script, upto=12)
    closed1 = c1.close()  # already auto-finalized at the tick limit (Q2)
    assert closed1["reason"] == "tick_limit"
    assert closed1["note"] == "already finalized"

    # release: the NEXT hello opens the next life by the ratified rule
    ok2 = c2.hello_new(world="dyn")
    assert ok2["type"] == "welcome", ok2
    assert ok2["life"]["n"] == 2
    assert ok2["life"]["succession"] in ("lineage", "elder")
    assert ok2["tick"] == 12
    assert ok2["last_seq"] == 0  # fresh decision sequence, continued world
    _life(c2, script[20:], upto=3)
    closed2 = c2.close()
    assert closed2["hash"] != closed1["hash"]  # the world GREW, not reset
    # one file for the whole world; takeover never forks archives
    assert [p.name for p in tmp.iterdir()] == ["dyn.db"]
    c1.terminate(); c2.terminate()


def test_world_name_validation_on_the_wire(world_env):
    base, _, tmp = world_env
    c = LifeClient(base)
    for bad in ("../x", "a/b", "NAME", "ok.db", "x" * 33):
        m = c.hello_new(world=bad, seed=1)
        assert m["code"] == "malformed", (bad, m)
    # rejection is pre-filesystem: the server created NOTHING on disk
    assert list(tmp.iterdir()) == []


def test_multi_life_chain_identical_local_vs_ws(world_env, tmp_path):
    """Acceptance §7.2: seed + per-life decision streams → per-life card
    fingerprints AND the final archive hash are identical across transports
    — across TAKEOVERS, not just one life."""
    base, _, _ = world_env
    script = _script()
    # local chain: same config, same per-life streams, direct Sessions
    s1 = Session(seed=21, regions=4, agents=50, max_ticks=12,
                 db_path=str(tmp_path / "dyn.db"))
    for seq, a in enumerate(script[:12], 1):
        if s1.state != "awaiting":
            break
        s1.decide(seq, a)
    s1.close()
    fp1_local = s1.bio()["fingerprint"]  # same head as fp1_ws: life 1 only
    s2 = Session.takeover(str(tmp_path / "dyn.db"))
    for seq, a in enumerate(script[20:23], 1):
        s2.decide(seq, a)
    s2.close()
    fp2_local = s2.bio()["fingerprint"]

    # ws chain: same two lives over the socket
    c1 = LifeClient(base)
    c1.hello_new(world="dyn2", seed=21, regions=4, agents=50, max_ticks=12)
    for seq, a in enumerate(script[:12], 1):
        c1.decide(seq, a)
    fp1_ws = c1.bio()["fingerprint"]
    closed1_ws = c1.close()
    c2 = LifeClient(base)
    w2 = c2.hello_new(world="dyn2")
    for seq, a in enumerate(script[20:23], 1):
        c2.decide(seq, a)
    fp2_ws = c2.bio()["fingerprint"]  # same head as fp2_local: life 2 played
    closed2_ws = c2.close()
    c1.terminate(); c2.terminate()

    assert w2["life"] == s2.welcome()["life"]  # same heir, same succession
    assert fp1_local == fp1_ws
    assert fp2_local == fp2_ws
    assert s1.final_hash == closed1_ws["hash"]
    assert s2.final_hash == closed2_ws["hash"]  # whole chain, byte canon
