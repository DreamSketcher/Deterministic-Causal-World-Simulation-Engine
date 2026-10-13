"""v0.6 step 5 (part 1): the session state machine — protocol without
sockets. Contract: experiments/proposals/v06_step5_protocol_contract.md.

Everything the transport guarantees is enforced HERE (ws.py only parses):
accept-on-commit, client_seq idempotency, conflict/gap errors that never
touch the world, death-without-eviction lifecycle, results read from the
archive. If these pass, no client can break the contract.
"""

from __future__ import annotations

import random

import pytest

from causal_world.server.session import ProtocolError, Session


def _sess(tmp_path, **kw):
    cfg = dict(seed=7, regions=2, agents=40, max_ticks=200)
    cfg.update(kw)
    return Session(db_dir=str(tmp_path), **cfg)


def _script(n=200, source=99):
    rng = random.Random(source)
    out = []
    for _ in range(n):
        r = rng.random()
        out.append(2 if r < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6)
    return out


# ------------------------------------------------------- §1 order, §2 idem


def test_decision_cycle_idempotency_and_errors(tmp_path):
    s = _sess(tmp_path)
    f1 = s.decide(1, 0)
    assert f1["type"] == "frame" and f1["seq"] == 1 and f1["tick"] == 0
    assert f1["applied"] is True and f1["journal"]["committed"] > 0

    # re-delivery of an applied seq: identical frame, world NOT re-stepped
    again = s.decide(1, 0)
    assert again == f1
    assert s.sim.state.tick == 1

    with pytest.raises(ProtocolError) as e:
        s.decide(1, 2)  # same seq, different payload
    assert e.value.code == "conflict"

    with pytest.raises(ProtocolError) as g:
        s.decide(9, 0)  # gap: client lost track
    assert g.value.code == "seq_gap" and g.value.extra["resync"]["last_seq"] == 1

    # out-of-range action: protocol accepts, the WORLD refuses (Q1/journal)
    f2 = s.decide(2, 99)
    assert f2["applied"] is False and f2["reject"] == "out_of_range"
    assert f2["tick"] == 1  # it still drove one step

    # results are readable mid-life (archive-first, every step committed)
    b = s.bio()
    assert len(b["fingerprint"]) == 64 and b["meta"]["alive_at_end"] is True
    with pytest.raises(ProtocolError) as a:
        s.autopsy()
    assert a.value.code == "alive"


# ---------------------------------------------------------------- §4 cycle


def test_life_to_death_and_results_survive_close(tmp_path):
    s = _sess(tmp_path, agents=60)  # rng99 world: death at T51
    seq = 0
    last = None
    for a in _script(200):
        seq += 1
        last = s.decide(seq, a)
        if not last["alive"]:
            break
    assert (last["tick"], s.death_tick, seq) == (51, 51, 52)
    # step 6 (Q2): death auto-finalizes; the finished event carries the
    # verdict so the client needs no live writer to know how it ended
    ev = s.take_finished_event()
    assert ev["reason"] == "death" and ev["death_tick"] == 51
    assert ev["life"] == {"n": 1, "agent": "agent:0", "succession": "genesis"}
    assert ev["autopsy"]["label"] == "acute_infection"
    assert len(ev["bio_fingerprint"]) == 64
    assert s.take_finished_event() is None  # one-shot
    assert s.state == "finalized"

    with pytest.raises(ProtocolError) as d:
        s.decide(seq + 1, 0)
    assert d.value.code == "finalized"  # decisions refused…

    au = s.autopsy()  # …results are not (same file, same reader)
    assert au["death_tick"] == 51 and au["operation"] == "disease.infect"
    assert au["label"] == "acute_infection"  # DeathClassifier over the archive
    assert au["die"]["roll"] < au["die"]["threshold"]
    assert au["causes"]["depth_limit"] == 24
    card_fp = s.bio()["fingerprint"]
    assert au["bio_fingerprint"] == card_fp == ev["bio_fingerprint"]

    again = s.close()  # the auto-close already finalized: idempotent replay
    assert again["note"] == "already finalized"
    assert again["hash"] == s.final_hash and len(again["hash"]) == 64

    # finalized: reader path is the file alone; results identical
    after = s.bio(md=True)
    assert after["fingerprint"] == card_fp
    assert "## Necessary causes" in after["md"]


def test_tick_limit_finishes_a_life_still_alive(tmp_path):
    s = _sess(tmp_path, max_ticks=3)
    for seq in (1, 2, 3):
        s.decide(seq, 6)
    # ended while alive: auto-finalized with reason, life row says tick_limit
    assert s.state == "finalized" and s.finish_reason == "tick_limit"
    au = s.autopsy()
    assert au["alive"] is True and au["death_tick"] is None
    assert au["life_end"] == "tick_limit"
    with pytest.raises(ProtocolError) as e:
        s.decide(4, 0)
    assert e.value.code == "finalized"


def test_tail_ticks_run_epilogue_without_decisions(tmp_path):
    s = _sess(tmp_path, tail_ticks=3)
    script = _script()
    seq = 0
    while s.state == "awaiting":
        seq += 1
        f = s.decide(seq, script[seq - 1])
        if not f["alive"]:
            break
    assert s.state == "finalized" and s.finish_reason == "death"
    # death at tick d → d+1 steps consumed it, then exactly tail more
    assert s.sim.state.tick == s.death_tick + 1 + 3


# ------------------------------------------------------- §3 server is head


def test_welcome_echoes_authoritative_config(tmp_path):
    s = _sess(tmp_path, agents=17)
    w = s.welcome()
    assert w["config"]["agents"] == 17 and w["config"]["seed"] == 7
    assert w["session_id"] == s.session_id and w["last_seq"] == 0
    assert set(w["action_card"]) == set(range(7))
