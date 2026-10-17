"""v0.12, stage 2c — four invariants, and a restart that must not lose them.

The review fixed the invariants of the state/snapshot stage. They are
tests here, against a reference run recorded BEFORE any representation
change (`tests/golden/v012_reference.json`, written by
``experiments/v012_reference.py``):

1. state identity — after the same transitions ``state.hash()`` matches;
2. journal identity — ``journal.hash()`` and the transition id sequence
   do not move when the state representation is rebuilt;
3. deterministic replay — the same seed and commands give the same state
   at EVERY checked tick, not only at the end;
4. derived-index consistency — a full rebuild from the state and an
   incremental update through the journal agree, after every tick.

Plus the recovery case the project has already lived through: the index
must rebuild from the saved state and journal after a restart, and the
replayed world must continue exactly like the one that never stopped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from causal_world import create_world
from causal_world.observer.slice import WorldIndex
from causal_world.server import continuity
from causal_world.server.session import Session
from causal_world.world.rules import get_ruleset

GOLDEN = Path(__file__).parent / "golden" / "v012_reference.json"


# ---------------------------------------------------------------- helpers

def _reference(config: dict) -> dict:
    sim = create_world(
        seed=config["seed"], ruleset=get_ruleset(config["ruleset"]), ticks=0,
        regions=config["regions"], agents=config["agents"],
    )
    ticks = [{
        "tick": sim.state.tick,
        "state_hash": sim.state.hash(),
        "journal_hash": sim.journal.hash(),
        "transitions": len(sim.journal),
    }]
    for _ in range(config["ticks"]):
        sim.step()
        ticks.append({
            "tick": sim.state.tick,
            "state_hash": sim.state.hash(),
            "journal_hash": sim.journal.hash(),
            "transitions": len(sim.journal),
        })
    total, committed, rejected = sim.journal.counts()
    return {
        "config": config,
        "ticks": ticks,
        "final": {
            "state_hash": sim.state.hash(),
            "journal_hash": sim.journal.hash(),
            "transitions_total": total,
            "committed": committed,
            "rejected": rejected,
        },
    }


def _index_facts(index: WorldIndex, state) -> dict:
    """Everything the frame reads, as plain comparable data."""
    return {
        "agents": index.entities("agent:"),
        "cells": index.entities("cell:"),
        "regions": index.entities("region:"),
        "fields": {
            entity: index.fields_of(entity)
            for entity in index.entities("cell:") + index.entities("region:")
        },
        "alive": index.alive_count,
        "agent_count": index.agent_count,
        "pool": index.pool_stats,
        "agents_by_cell": {
            cell: index.agents_in_cell(cell)
            for cell in index.entities("cell:")
        },
    }


# ------------------------------------------------- 1-3. identity and replay

def test_the_recorded_reference_still_runs_identically() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    current = _reference(golden["config"])
    assert current["ticks"] == golden["ticks"]
    assert current["final"] == golden["final"]


def test_two_runs_agree_at_every_tick_not_only_at_the_end() -> None:
    config = {"seed": 7, "ruleset": "player_resettle", "regions": 2,
              "agents": 54, "ticks": 12}
    first, second = _reference(config), _reference(config)
    assert [t["state_hash"] for t in first["ticks"]] == \
        [t["state_hash"] for t in second["ticks"]]
    # an intermediate tick is a real checkpoint: a bug that drifts and
    # comes back would pass a final-only comparison
    assert first["ticks"][6]["state_hash"] == second["ticks"][6]["state_hash"]
    assert first["ticks"][6]["state_hash"] != first["ticks"][5]["state_hash"]


def test_the_journal_id_sequence_is_stable() -> None:
    def ids(config):
        sim = create_world(
            seed=config["seed"], ruleset=get_ruleset(config["ruleset"]),
            ticks=0, regions=config["regions"], agents=config["agents"],
        )
        seen = []
        for _ in range(config["ticks"]):
            sim.step()
            seen.append([(t.id, t.tick) for t in sim.journal])
        return sim.journal.hash(), seen[-1]

    config = {"seed": 11, "ruleset": "player_resettle", "regions": 2,
              "agents": 54, "ticks": 6}
    first = ids(config)
    second = ids(config)
    assert first == second
    journal_ids = [tid for tid, _ in first[1]]
    assert journal_ids == sorted(journal_ids)
    assert len(journal_ids) == len(set(journal_ids))


# --------------------------------------- 4. derived index consistency

@pytest.mark.parametrize("ruleset", ["player_resettle", "player_civic"])
def test_full_rebuild_and_incremental_update_agree_every_tick(ruleset: str) -> None:
    sim = create_world(
        seed=7, ruleset=get_ruleset(ruleset), ticks=0,
        regions=2, agents=54,
    )
    incremental = WorldIndex.from_state(sim.state, journal=sim.journal)
    for _ in range(8):
        sim.step()
        incremental.advance(sim.journal, sim.state.tick - 1)
        rebuilt = WorldIndex.from_state(sim.state, journal=sim.journal)
        assert _index_facts(incremental, sim.state) == \
            _index_facts(rebuilt, sim.state), f"index diverged at {ruleset}"


# ------------------------------- restart: state, journal, index, replay

def test_the_world_restarts_without_losing_state_or_journal(tmp_path) -> None:
    session = Session(
        seed=7, ruleset="player_resettle", regions=2, agents=54,
        max_ticks=200, db_dir=str(tmp_path),
    )
    for seq in range(1, 13):
        session.decide(seq, 6)
    live = session.sim
    live_state_hash = live.state.hash()
    live_journal_hash = live.journal.hash()
    live_index = _index_facts(
        WorldIndex.from_state(live.state, journal=live.journal), live.state
    )
    db_path = session.db_path
    session.close()  # writes the final state hash and the life row

    sim, archive, lives = continuity.replay_head(db_path)
    try:
        # invariant 1 and 2 after a restart
        assert sim.state.hash() == live_state_hash
        assert archive.hash() == live_journal_hash
        # invariant 4 after a restart: the index rebuilds from the saved
        # state and the saved journal, and says the same thing
        restored = _index_facts(
            WorldIndex.from_state(sim.state, journal=archive), sim.state
        )
        assert restored == live_index
        assert lives and lives[-1]["end"] is not None
    finally:
        archive.close()


def test_a_restarted_world_continues_like_one_that_never_stopped(tmp_path) -> None:
    def make_session(name: str) -> Session:
        return Session(
            seed=7, ruleset="player_resettle", regions=2, agents=54,
            max_ticks=200, db_dir=str(tmp_path / name),
        )

    # A: run 12 ticks, close, restart, run 4 more
    a = make_session("a")
    for seq in range(1, 13):
        a.decide(seq, 6)
    db_path = a.db_path
    a.close()
    sim, archive, _lives = continuity.replay_head(db_path)
    try:
        after_restart = []
        for seq in range(13, 17):
            # the archive IS the journal of the restored sim
            sim.step()
            sim.journal.commit()
            after_restart.append(sim.state.hash())
        archive.close()
    finally:
        pass

    # B: the same world with no restart at all
    b = make_session("b")
    live = []
    for seq in range(1, 17):
        b.decide(seq, 6)
        if seq >= 13:
            live.append(b.sim.state.hash())

    assert after_restart == live


# ------------------------------------------------- state's derived groups
#
# The snapshot cache became cheap only because the state itself keeps the
# entity groups up to date as pairs are written. These pin that the index
# is a pure cache: same answers as a scan, new entities appear with their
# first pair, and identity/equality never see it.

def test_state_groups_answer_like_a_scan() -> None:
    from causal_world.kernel.state import WorldState

    data = {
        ("agent:a", "alive"): True,
        ("agent:a", "age"): 3,
        ("agent:b", "alive"): False,
        ("cell:0,0", "food"): 12.0,
        ("region:north", "mouths"): 2,
    }
    state = WorldState(tick=5, data=dict(data))
    scanned = sorted({entity for entity, _ in data})
    assert state.entities() == scanned
    for prefix in ("agent:", "cell:", "region:", "region:missing"):
        assert state.entities_with_prefix(prefix) == [
            entity for entity in scanned if entity.startswith(prefix)
        ]
    # a prefix that is not a group scans the entities, not the pairs
    assert state.entities_with_prefix("agent:") == ["agent:a", "agent:b"]
    assert state.entities_with_prefix("agent:a") == ["agent:a"]

    previous = state.hash()
    with state.unsealed():
        state.set("agent:probe", "alive", True, 1)
    assert state.entities_with_prefix("agent:") == [
        "agent:a", "agent:b", "agent:probe"
    ]
    assert len(state.entities()) == len(scanned) + 1
    assert state.hash() != previous


def test_snapshot_groups_are_a_copy_not_a_window_into_the_state() -> None:
    from causal_world.kernel.snapshot import Snapshot
    from causal_world.kernel.state import WorldState

    state = WorldState(tick=2, data={
        ("agent:a", "alive"): True,
        ("cell:0,0", "food"): 4.0,
    })
    snapshot = Snapshot.from_state(state)
    assert snapshot.entities_with_prefix("agent:") == ["agent:a"]
    with state.unsealed():
        state.set("agent:b", "alive", True, 7)
    assert snapshot.entities_with_prefix("agent:") == ["agent:a"]
    # the cache is frozen with the snapshot, too: a fresh state at the
    # same tick still sees the pair that did not exist when it was taken
    assert state.entities_with_prefix("agent:") == ["agent:a", "agent:b"]
    assert snapshot.get("agent:b", "alive") is None


def test_state_groups_are_not_part_of_identity() -> None:
    from causal_world.kernel.state import WorldState

    pairs = {("agent:a", "alive"): True, ("cell:0,0", "food"): 4.0}
    left = WorldState(tick=1, data=dict(pairs))
    right = WorldState(tick=1, data=dict(pairs))
    assert left == right
    assert left.hash() == right.hash()
    # even a wrong cache changes no hash: it is derived data, excluded
    # from equality and from the canonical payload by construction
    right._groups.clear()
    assert left == right
    assert left.hash() == right.hash()
