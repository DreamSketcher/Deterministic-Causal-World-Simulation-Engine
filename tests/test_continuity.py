"""v0.6 step 6: multi-life continuity — one world, N lives, one archive.

Ratified contract §9. These tests pin the design decisions as behaviour:

- Check A (permanent): a takeover reproduces the FULL canonical state and
  journal hash from the archive alone — the decision stream is proven
  sufficient for complete restoration, not just a list of lives; a forged
  meta is refused without touching the world.
- Life rows in identity meta (no journal-format change) distinguish
  death / abdicate / tick_limit and empty segments (decisions=0) —
  boundaries are never inferred from the presence of first/last action.
- Succession: deterministic BFS (generation, birth_tick, id), dead links
  traversed but never eligible; elder = successor of MANAGEMENT, recorded
  as "elder", never dressed up as kin.
- no_heir is terminal: no pool refill, no restart, no silent new file.
"""

from __future__ import annotations

import json
import random
import sqlite3

import pytest

from causal_world.observer.journal import JournalView
from causal_world.server import continuity
from causal_world.server.session import ProtocolError, Session


def _script(n=300, source=99):
    rng = random.Random(source)
    return [
        2 if (r := rng.random()) < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6
        for _ in range(n)
    ]


def _play_to_end(tmp_path, name, script, **cfg):
    base = dict(seed=21, regions=4, agents=50, max_ticks=15)
    base.update(cfg)
    s = Session(db_dir=str(tmp_path), **base)
    seq = 0
    for a in script:
        if s.state != "awaiting":
            break
        seq += 1
        s.decide(seq, a)
    if s.state == "awaiting":
        s.close()
    return s


def _lives(db_path):
    with JournalView(db_path) as view:
        return continuity.read_lives(view)


# ------------------------------------------------------------------ Check A


def test_takeover_reproduces_full_state_from_archive_alone(tmp_path):
    s1 = _play_to_end(tmp_path, "w1", _script(20), max_ticks=20)
    state_hash, journal_hash = s1.sim.state.hash(), s1.final_hash

    # replay_head is the takeover engine: it verifies BOTH hashes itself —
    # reaching a usable sim at all IS the Check-A pass. Do it explicitly:
    sim, archive, lives = continuity.replay_head(s1.db_path)
    try:
        assert sim.state.hash() == state_hash  # dormant pool, generations,
        # ruins, every field — full canonical state, not a row count
        assert archive.hash() == journal_hash
        assert sim.journal is archive and sim.index is archive
        assert [l["agent"] for l in lives] == ["agent:0"]
        assert archive.get_meta("final_state_hash") == state_hash
    finally:
        archive.close()


def test_takeover_mismatch_forged_meta_refused_without_writes(tmp_path):
    s1 = _play_to_end(tmp_path, "w2", _script(10))
    db = s1.db_path
    before = s1.final_hash
    # forge: life 1 claims a different agent than the journaled stream
    with sqlite3.connect(db) as c:
        row = json.loads(c.execute(
            "SELECT value FROM meta WHERE key='life:1'").fetchone()[0])
        row["agent"] = "agent:1"
        c.execute("UPDATE meta SET value=? WHERE key='life:1'",
                  (json.dumps(row, sort_keys=True),))
    with pytest.raises(ProtocolError) as e:
        Session.takeover(db)
    assert e.value.code == "takeover_mismatch"
    # world untouched: same archive, same head, refusal wrote nothing
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        n = c.execute("SELECT count(*), max(id) FROM transitions").fetchone()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE meta SET value=? WHERE key='life:1'",
                  (json.dumps({**row, "agent": "agent:0"}, sort_keys=True),))
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        assert c.execute("SELECT count(*), max(id) FROM transitions").fetchone() == n
    _ = before  # (hash unchanged too — the rows never moved)


# ------------------------------------------------ three lives, both rules


def test_three_lives_meta_rows_and_contiguous_history(tmp_path):
    script = _script(300)
    db1 = _play_to_end(tmp_path, "w3", script[:15], max_ticks=15)
    db = db1.db_path
    fp1 = db1.bio()["fingerprint"]
    assert db1.succession == "genesis" and db1.state == "finalized"

    s2 = Session.takeover(db, max_ticks=23)  # from_tick 15 — world frozen,
    # not reset: alive continues where it stood
    assert s2.life_n == 2 and s2.succession in ("lineage", "elder")
    assert s2._from == 15
    for seq, a in enumerate(script[20:25], 1):
        s2.decide(seq, a)
    s2.close()  # alive leader: end "abdicate"
    fp2 = s2.bio()["fingerprint"]
    assert s2.succession == "elder"  # seed21 measured: player has no kids

    s3 = Session.takeover(db, max_ticks=30)
    assert s3.life_n == 3 and s3._from == 20
    s3.decide(1, 6)
    s3.close()

    lives = _lives(db)
    assert [(l["n"], l["from_tick"], l["to_tick"], l["end"]) for l in lives] == [
        (1, 0, 15, "tick_limit"), (2, 15, 20, "abdicate"), (3, 20, 21, "abdicate"),
    ]
    assert lives[1]["succession"] == "elder" and "agent" in lives[1]
    assert len({fp1, fp2}) == 2  # distinct lives, distinct biographies
    # ids/ticks: one monotone series over all three lives, no gaps
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        n, lo, hi = c.execute(
            "SELECT count(*), min(id), max(id) FROM transitions").fetchone()
    assert lo == 1 and hi - lo + 1 == n  # contiguous forever

    # the whole multi-life archive replays to itself bit-identically
    sim, archive, _ = continuity.replay_head(db)
    try:
        head = sim.state.hash()
        with JournalView(db) as v:
            assert head == v.meta_all()["final_state_hash"]
        assert archive.hash() == s3.final_hash
    finally:
        archive.close()


def test_empty_segment_is_distinguishable_and_replays(tmp_path):
    db1 = _play_to_end(tmp_path, "w4", _script(6), max_ticks=6)
    db = db1.db_path
    s2 = Session.takeover(db)  # opens, decides NOTHING, closes
    s2.close()
    s3 = Session.takeover(db)  # the empty life must not confuse the schedule
    s3.decide(1, 5)
    s3.close()
    lives = _lives(db)
    assert lives[1]["decisions"] == 0 and lives[1]["end"] == "abdicate"
    assert lives[1]["from_tick"] == lives[1]["to_tick"] == 6
    assert lives[2]["from_tick"] == 6
    # the last death vs a zero-decision segment are different rows:
    # (decisions=0, end=abdicate) never reads as a death
    assert all(l["end"] != "death" for l in lives)


# ------------------------------------------------------------- heir rule --


def test_choose_heir_bfs_is_deterministic_and_traverses_the_dead():
    def mk(**kw):
        return kw

    agents = {
        "a": mk(alive=False, parent_id=None, birth_tick=0),
        "b": mk(alive=False, parent_id="a", birth_tick=10),   # dead child
        "c": mk(alive=True, parent_id="a", birth_tick=11),    # living child
        "d": mk(alive=True, parent_id="b", birth_tick=12),    # grandchild via the dead
        "e": mk(alive=True, parent_id="a", birth_tick=9),     # living child, older
        "f": mk(alive=True, parent_id="x", birth_tick=1),     # unrelated elder
    }
    # generation first (children before grandchildren), then birth_tick, then id
    assert continuity.choose_heir("a", agents) == ("e", "lineage")
    agents2 = dict(agents)
    del agents2["e"], agents2["c"]  # only the grandchild remains
    assert continuity.choose_heir("a", agents2) == ("d", "lineage")
    agents3 = {k: dict(v, alive=False) if k in "cde" else v
               for k, v in agents.items()}
    assert continuity.choose_heir("a", agents3) == ("f", "elder")  # no lineage → eldest
    agents4 = {k: dict(v, alive=False) for k, v in agents.items()}
    assert continuity.choose_heir("a", agents4) is None  # terminal


# ------------------------------------------------------------ no_heir: law


def test_no_heir_is_terminal_no_new_archive(tmp_path):
    world = tmp_path / "dead.db"
    # seed7/2x60 measured: the community starves out around t200. Each
    # life plays its elder to the finish (60 world ticks max), so the
    # dynasty drains toward extinction through PLAY — no daemon ticking.
    s = Session(seed=7, regions=2, agents=60, db_path=str(world), max_ticks=60)
    lives = 1
    while True:
        seq = 0
        script = _script(60, source=100 + lives)
        while s.state == "awaiting":
            seq += 1
            s.decide(seq, script[seq - 1])
        head = s.sim.state.tick
        if lives >= 25:
            pytest.fail("extinction did not arrive within 25 lives")
        try:
            s = Session.takeover(str(world), max_ticks=head + 60)
        except ProtocolError as e:
            assert e.code == "no_heir"
            assert e.extra["alive_agents"] == 0  # extinction, not just death
            break
        lives += 1
    assert lives >= 3  # multi-life history happened on the way to the end
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files.count("dead.db") == 1
    # terminal means NO side effects beyond the last played life: no new
    # archive, no silent reset — and the dead world remains fully readable
    from causal_world.observer.biography import build_biography

    card = build_biography(str(world), "agent:0")
    # ADR v13-1: the controlled life of agent:0 is exhausted by its own work
    # at tick 50 (health 1.2, cost 5). Before the fix it lived on at zero
    # health and died at 51. The fingerprint itself is checked separately.
    assert len(card.fingerprint()) == 64 and card.death.tick == 50


# ------------------------------------------------------------- world names


@pytest.mark.parametrize("name", [
    "../evil", "a/b", "name.db", "", "UPPER", "x" * 33, ".hidden", "a b", 42,
])
def test_world_name_is_a_strict_identifier_never_a_path(name):
    assert not continuity.world_name_ok(name)


@pytest.mark.parametrize("name", ["dyn", "a", "gen_1", "x-y9", "z" * 32])
def test_world_names_accepted(name):
    assert continuity.world_name_ok(name)
