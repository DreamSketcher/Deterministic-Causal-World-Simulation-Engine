"""SqliteArchive: identical semantics and hashes to the in-memory stores."""

from __future__ import annotations

import os
import tempfile

import pytest

from causal_world import create_world
from causal_world.causal.trace import trace_back, trace_record
from causal_world.kernel.transition import TransitionStatus
from causal_world.simulation.archive import SqliteArchive


@pytest.fixture()
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_memory_and_archive_runs_are_identical(db_path):
    memory = create_world(seed=42, ticks=25)
    archived = create_world(seed=42, ticks=25, persist=db_path)

    assert memory.state.hash() == archived.state.hash()
    assert memory.state.data == archived.state.data
    assert memory.journal.hash() == archived.journal.hash()
    assert memory.journal.counts() == archived.journal.counts()
    archived.journal.close()


def test_archive_transition_roundtrip(db_path):
    memory = create_world(seed=42, ticks=15)
    archived = create_world(seed=42, ticks=15, persist=db_path)

    sample_ids = [1, 2, 12] + [memory.journal.last_committed_id()]
    for tid in sample_ids:
        m = memory.journal.by_id(tid)
        a = archived.journal.by_id(tid)
        assert m.system == a.system and m.operation == a.operation
        assert m.tick == a.tick and m.status == a.status
        assert m.reads == a.reads
        assert m.writes == a.writes
        assert m.random_draws == a.random_draws
        assert m.reject_reason == a.reject_reason
    archived.journal.close()


def test_archive_causal_index_matches_memory(db_path):
    memory = create_world(seed=42, ticks=25)
    archived = create_world(seed=42, ticks=25, persist=db_path)

    climate_tid = next(
        t.id for t in memory.journal.committed() if t.operation == "climate.step"
    )
    assert memory.index.dependents_of(climate_tid) == archived.index.dependents_of(
        climate_tid
    )
    assert memory.index.writer_of(
        "region:0", "temperature"
    ) == archived.index.writer_of("region:0", "temperature")
    assert memory.index.history_of(
        "region:0", "food_stock"
    ) == archived.index.history_of("region:0", "food_stock")

    death = next(
        (
            t
            for t in memory.journal.committed()
            if any(w.field == "alive" and w.new is False for w in t.writes)
        ),
        None,
    )
    target = death.id if death else memory.journal.last_committed_id()
    assert trace_record(trace_back(memory.index, target, 6)) == trace_record(
        trace_back(archived.index, target, 6)
    )
    archived.journal.close()


def test_archived_replay_is_deterministic(db_path):
    path_a = db_path
    fd, path_b = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path_b)
    try:
        run1 = create_world(seed=5, ticks=20, persist=path_a)
        run2 = create_world(seed=5, ticks=20, persist=path_b)
        assert run1.state.hash() == run2.state.hash()
        assert run1.journal.hash() == run2.journal.hash()
        run1.journal.close()
        run2.journal.close()
    finally:
        if os.path.exists(path_b):
            os.remove(path_b)


def test_iter_operations_parity(db_path):
    memory = create_world(seed=4, ticks=20)
    archived = create_world(seed=4, ticks=20, persist=db_path)
    ops = {"agent.metabolism", "disease.infect", "climate.step"}
    mem_ids = [t.id for t in memory.journal.iter_operations(ops)]
    arc_ids = [t.id for t in archived.journal.iter_operations(ops)]
    assert mem_ids == arc_ids
    archived.journal.close()


def test_archive_survives_reopen(db_path):
    """Periodic commits keep the on-disk database valid across reopens."""
    run1 = create_world(seed=6, ticks=15, persist=db_path)
    first_hash = run1.journal.hash()
    first_state = run1.state.hash()
    run1.journal.close()

    from causal_world.simulation.archive import SqliteArchive

    reopened = SqliteArchive(db_path)
    assert len(reopened) > 0
    assert reopened.by_id(1).system == "GenesisSystem"
    reopened.close()


def test_archive_rejects_out_of_order_records(db_path):
    archive = SqliteArchive(db_path)
    world = create_world(seed=1, ticks=1)
    transitions = world.journal.all()
    archive.record(transitions[0])
    with pytest.raises(ValueError):
        archive.record(transitions[0])  # same id twice
    archive.close()


def test_archive_streaming_iteration(db_path):
    memory = create_world(seed=3, ticks=15)
    archived = create_world(seed=3, ticks=15, persist=db_path)
    assert [t.id for t in memory.journal] == [t.id for t in archived.journal]
    assert [t.id for t in memory.journal.committed()] == [
        t.id for t in archived.journal.committed()
    ]
    assert [t.id for t in memory.journal.rejected()] == [
        t.id for t in archived.journal.rejected()
    ]
    assert sum(1 for t in archived.journal if t.status is TransitionStatus.REJECTED) \
        == len(memory.journal.rejected())
    archived.journal.close()
