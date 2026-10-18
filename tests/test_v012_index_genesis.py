"""v0.12/3: the observer index does not re-apply the genesis batch.

Before this change ``WorldIndex.advance(journal, 0)`` applied every committed
write of tick 0. Tick 0 holds the genesis batch AND the first step, and the
index had just been built from a state that already contained the genesis
batch. So the whole genesis was applied twice, and the second pass kept its
data alive as observer structures (~207 MB at 20k agents).

The old tests did not catch this: applying a write twice leaves the index
unchanged, so comparing final facts passes. The regression tests here count
the calls to ``apply_write`` and check that exactly the new writes arrive.

Covered:

1. a new world: the first advance after genesis applies nothing; the first
   advance after a step applies the step's writes and no genesis write;
2. the incremental index equals a full rebuild after every tick, on the
   facts a frame reads AND on the cell slice built from each of them;
3. a restarted world: the index built from the restored state applies
   nothing old, and the next tick applies only its own writes.

Provenance is not stored in the index; the slice reads it from the state.
It is compared anyway, because a frame shows it.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.slice import CellSlice, WorldIndex
from causal_world.server import continuity
from causal_world.server.session import Session
from causal_world.world.rules import get_ruleset



def _index_facts(index: WorldIndex, state) -> dict:
    """Everything the frame reads, as plain comparable data (as in 2c)."""
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


def _committed_writes(transitions) -> int:
    return sum(len(t.writes) for t in transitions
               if t.status is TransitionStatus.COMMITTED)


def _count_apply_write(monkeypatch) -> dict:
    counter = {"n": 0}
    original = WorldIndex.apply_write

    def counted(self, write):
        counter["n"] += 1
        return original(self, write)

    monkeypatch.setattr(WorldIndex, "apply_write", counted)
    return counter


def _slice_facts(state, index) -> dict:
    view = CellSlice.from_state(state, index)
    values = dict(view._values)
    return {
        "cells": view.cells,
        "regions": view.regions,
        "complete": view.complete,
        "values": values,
        "provenance": {key: state.get_source(*key) for key in values},
        "alive": view.alive_agents,
        "total": view.total_agents,
        "pool": view.pool_stats(),
        "by_cell": {c: view.agents_in_cell(c) for c in view.cells},
    }


# ----------------------------------------------- 1. a new world: no genesis

def test_genesis_is_not_applied_again_on_the_first_advance(tmp_path, monkeypatch):
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=54, persist=str(tmp_path / "genesis.db"),
    )
    genesis = sim.journal.at_tick(0)
    genesis_writes = _committed_writes(genesis)
    genesis_max_id = max(t.id for t in genesis)
    assert genesis_writes > 1000  # the batch is big: a duplicate would show

    index = WorldIndex.from_state(sim.state, journal=sim.journal)
    counter = _count_apply_write(monkeypatch)

    # the state is still at genesis and holds it: nothing to apply
    index.advance(sim.journal, 0)
    assert counter["n"] == 0

    sim.step()
    step_writes = sum(
        len(t.writes) for t in sim.journal.at_tick(0)
        if t.status is TransitionStatus.COMMITTED and t.id > genesis_max_id
    )
    counter["n"] = 0
    index.advance(sim.journal, 0)
    # exactly the step's writes: no genesis write was decoded or applied
    assert counter["n"] == step_writes
    assert step_writes < genesis_writes
    sim.journal.close()


def test_genesis_is_not_decoded_on_the_first_advance(tmp_path, monkeypatch):
    """The archive must not be asked for the genesis writes at all."""
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=54, persist=str(tmp_path / "decode.db"),
    )
    genesis_ids = {t.id for t in sim.journal.at_tick(0)}
    index = WorldIndex.from_state(sim.state, journal=sim.journal)
    sim.step()

    decoded: list[int] = []
    original = sim.journal.iter_writes_at_tick

    def spy(tick, after_id=0):
        for row in original(tick, after_id):
            decoded.append(row[0])
            yield row

    monkeypatch.setattr(sim.journal, "iter_writes_at_tick", spy)
    index.advance(sim.journal, 0)
    assert decoded  # the step wrote something
    assert not (set(decoded) & genesis_ids)
    sim.journal.close()


# ------------------------------------- 2. incremental equals rebuild, per tick

@pytest.mark.parametrize("ruleset", ["player_resettle", "player_civic"])
def test_incremental_equals_rebuild_on_facts_and_slices(ruleset: str) -> None:
    sim = create_world(seed=7, ruleset=get_ruleset(ruleset), ticks=0,
                       regions=2, agents=54)
    incremental = WorldIndex.from_state(sim.state, journal=sim.journal)
    for _ in range(8):
        sim.step()
        incremental.advance(sim.journal, sim.state.tick - 1)
        rebuilt = WorldIndex.from_state(sim.state, journal=sim.journal)
        assert _index_facts(incremental, sim.state) == \
            _index_facts(rebuilt, sim.state), f"facts diverged at {ruleset}"
        assert _slice_facts(sim.state, incremental) == \
            _slice_facts(sim.state, rebuilt), f"slices diverged at {ruleset}"


# ------------------------------------------ 3. restart: state, index, next tick

def test_a_restarted_world_applies_only_its_own_writes(tmp_path, monkeypatch):
    session = Session(
        seed=7, ruleset="player_resettle", regions=2, agents=54,
        max_ticks=200, db_dir=str(tmp_path),
    )
    for seq in range(1, 5):
        session.decide(seq, 6)
    db_path = session.db_path
    session.close()

    sim, archive, _lives = continuity.replay_head(db_path)
    try:
        restored_tick = sim.state.tick
        index = WorldIndex.from_state(sim.state, journal=archive)
        counter = _count_apply_write(monkeypatch)
        # everything up to the restored tick is already in the state
        index.advance(archive, restored_tick - 1)
        assert counter["n"] == 0

        sim.step()
        step_writes = _committed_writes(archive.at_tick(restored_tick))
        counter["n"] = 0
        index.advance(archive, restored_tick)
        assert counter["n"] == step_writes

        rebuilt = WorldIndex.from_state(sim.state, journal=archive)
        assert _index_facts(index, sim.state) == _index_facts(rebuilt, sim.state)
        assert _slice_facts(sim.state, index) == _slice_facts(sim.state, rebuilt)
    finally:
        archive.close()
