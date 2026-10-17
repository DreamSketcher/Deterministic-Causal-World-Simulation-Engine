"""v0.12, stage 2d — the journal: same history, cheaper storage and reads.

The acceptance is split into three independent groups, and every test
below belongs to exactly one of them:

1. LOGICAL HISTORY — ids, ticks, statuses, causal sources, values and
   the canonical ``journal.hash()`` do not move. ``journal.hash()`` is
   checked against the golden reference AFTER EVERY TICK, and every
   transition is compared with the in-memory journal field by field, so
   an index error that the hash cannot see is still caught.
2. PHYSICAL STORAGE — batches and indexes lose no records; the derived
   index can be rebuilt from the journal alone and matches the
   incrementally maintained one after every tick.
3. ACCESS — indexed queries return the same rows in the same order as
   the sequential search, a replay to a given tick reproduces both the
   state and the journal prefix, and a restart restores the index
   without diverging from an uninterrupted run.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from causal_world import create_world
from causal_world.kernel.transition import TransitionStatus, transition_record
from causal_world.observer.journal import JournalView
from causal_world.observer.slice import WorldIndex
from causal_world.server import continuity
from causal_world.server.session import Session
from causal_world.simulation.archive import SqliteArchive
from causal_world.world.rules import get_ruleset

GOLDEN = Path(__file__).parent / "golden" / "v012_reference.json"
COMMITTED = TransitionStatus.COMMITTED
REJECTED = TransitionStatus.REJECTED


def _world(agents: int, *, persist: str | None = None):
    return create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents, persist=persist,
    )


def _run(agents: int, ticks: int, persist: str | None = None):
    sim = _world(agents, persist=persist)
    commit = getattr(sim.journal, "commit", None)
    for _ in range(ticks):
        sim.step()
        if commit is not None:  # the in-memory journal needs no commit
            commit()
    return sim


def _ids(transitions) -> list[int]:
    return [t.id for t in transitions]


# ---------------------------------------------------------------- history
def test_archived_golden_matches_after_every_tick(tmp_path) -> None:
    """The physical journal reproduces the reference run tick by tick."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cfg = golden["config"]
    sim = create_world(
        seed=cfg["seed"], ruleset=get_ruleset(cfg["ruleset"]), ticks=0,
        regions=cfg["regions"], agents=cfg["agents"],
        persist=str(tmp_path / "golden.db"),
    )
    archive = sim.journal
    head = golden["ticks"][0]
    assert (sim.state.hash(), archive.hash(), len(archive)) == (
        head["state_hash"], head["journal_hash"], head["transitions"]
    )
    for expected in golden["ticks"][1:]:
        sim.step()
        archive.commit()
        assert sim.state.hash() == expected["state_hash"]
        assert archive.hash() == expected["journal_hash"]
        assert len(archive) == expected["transitions"]
    final = golden["final"]
    assert archive.counts() == (
        final["transitions_total"], final["committed"], final["rejected"]
    )


def test_every_transition_survives_the_archive_round_trip(tmp_path) -> None:
    """Not only the hash: each recorded transition equals the memory one."""
    memory = _run(200, 4)
    archived = _run(200, 4, persist=str(tmp_path / "roundtrip.db"))
    assert archived.journal.hash() == memory.journal.hash()
    assert archived.journal.counts() == memory.journal.counts()
    assert len(archived.journal) == len(memory.journal)

    for stored, kept in zip(archived.journal, memory.journal):
        assert transition_record(stored) == transition_record(kept)
    for tick in range(4):
        assert _ids(archived.journal.at_tick(tick)) == _ids(
            memory.journal.at_tick(tick)
        )


def test_batch_of_one_and_batch_of_many_are_the_same_journal(
    tmp_path, monkeypatch
) -> None:
    """Batching is transport: the rows and the hash do not depend on it."""
    from causal_world.simulation import archive as archive_module

    def run(name: str, batch: int):
        monkeypatch.setattr(archive_module, "BATCH_ROWS", batch)
        sim = _run(200, 3, persist=str(tmp_path / f"{name}.db"))
        return (
            sim.journal.hash(),
            [transition_record(t) for t in sim.journal],
            sim.journal.index_digest(),
        )

    small = run("batch-one", 1)
    large = run("batch-many", 1_000_000)
    assert small == large


# ------------------------------------------------------------------ index
def test_index_rebuild_equals_incremental_after_every_tick(tmp_path) -> None:
    sim = _world(400, persist=str(tmp_path / "rebuild.db"))
    archive = sim.journal
    for _ in range(3):
        sim.step()
        archive.commit()
        historical = archive.hash()
        incremental = archive.index_digest()
        counts = archive.index_counts()
        rebuilt_counts = archive.rebuild_index()
        assert rebuilt_counts == counts
        assert archive.index_counts() == counts
        assert archive.index_digest() == incremental
        assert archive.hash() == historical  # the journal was not touched


def test_reopened_archive_restores_the_index_without_a_rebuild(tmp_path) -> None:
    sim = _run(400, 3, persist=str(tmp_path / "restore.db"))
    path = sim.journal.path
    digest = sim.journal.index_digest()
    counts = sim.journal.index_counts()
    journal_hash = sim.journal.hash()
    sim.journal.close()

    reopened = SqliteArchive(path)
    try:
        assert reopened.index_digest() == digest
        assert reopened.index_counts() == counts
        assert reopened.hash() == journal_hash
    finally:
        reopened.close()


def test_rejected_transitions_stay_in_the_journal_but_not_in_the_index(
    tmp_path,
) -> None:
    sim = _run(200, 5, persist=str(tmp_path / "rejected.db"))
    archive = sim.journal
    rejected = [t for t in archive if t.status is REJECTED]
    assert rejected, "the world must reject some proposals for this test"
    for transition in rejected[:10]:
        for write in transition.writes:
            assert transition.id not in archive.history_of(
                write.entity, write.field
            )
            assert archive.writer_of(write.entity, write.field) != transition.id
            assert transition.id not in _ids(
                archive.transitions_for_entity(write.entity)
            )
            assert transition.id in _ids(
                archive.transitions_for_entity(write.entity, "REJECTED")
            )


# ----------------------------------------------------------------- access
def test_indexed_queries_match_the_sequential_scan_in_order(tmp_path) -> None:
    sim = _run(200, 5, persist=str(tmp_path / "queries.db"))
    archive = sim.journal
    everything = list(archive)

    for tick in range(5):
        assert _ids(archive.at_tick(tick)) == [
            t.id for t in everything if t.tick == tick
        ]
    assert _ids(archive.between_ticks(1, 3)) == [
        t.id for t in everything if 1 <= t.tick <= 3
    ]

    entities = sorted({w.entity for t in everything for w in t.writes})
    sample = entities[:: max(1, len(entities) // 5)][:5]
    for entity in sample:
        for status, wanted in (("COMMITTED", COMMITTED), ("REJECTED", REJECTED)):
            expected = [
                t.id for t in everything
                if t.status is wanted
                and any(w.entity == entity for w in t.writes)
            ]
            assert _ids(archive.transitions_for_entity(entity, status)) == expected

    pairs = []
    for transition in everything:
        for write in transition.writes:
            pair = (write.entity, write.field)
            if pair not in pairs:
                pairs.append(pair)
    for entity, field_name in pairs[:5]:
        expected = [
            t.id for t in everything
            if t.status is COMMITTED
            and any(w.entity == entity and w.field == field_name
                    for w in t.writes)
        ]
        assert _ids(archive.transitions_for_field(entity, field_name)) == expected

    # the read-only observer path returns the same rows in the same order
    with JournalView(archive.path) as view:
        assert _ids(view.at_tick(2)) == _ids(archive.at_tick(2))
        assert _ids(view.between_ticks(1, 3)) == _ids(archive.between_ticks(1, 3))
        for entity in sample:
            assert _ids(view.transitions_for_entity(entity)) == _ids(
                archive.transitions_for_entity(entity)
            )
        for entity, field_name in pairs[:5]:
            assert _ids(view.transitions_for_field(entity, field_name)) == _ids(
                archive.transitions_for_field(entity, field_name)
            )
            assert view.history_of(entity, field_name) == archive.history_of(
                entity, field_name
            )


def test_a_batch_is_invisible_until_the_commit(tmp_path) -> None:
    """Commit stays the acceptance point, exactly as with single writes."""
    sim = _world(120, persist=str(tmp_path / "commit.db"))
    archive = sim.journal
    archive.commit()
    total = archive.counts()[0]
    sim.step()
    with JournalView(archive.path) as view:
        assert view.counts()[0] == total
    archive.commit()
    with JournalView(archive.path) as view:
        assert view.counts()[0] == archive.counts()[0]


def test_replay_to_a_tick_matches_state_and_journal_prefix(tmp_path) -> None:
    session = Session(
        seed=7, ruleset="player_resettle", regions=2, agents=54,
        db_dir=str(tmp_path), max_ticks=100,
    )
    hashes = []
    for seq in range(1, 9):
        session.decide(seq, 6)
        hashes.append(session.sim.state.hash())
    db_path = session.db_path
    head_hash = session.sim.journal.hash()
    initial_hash = session.sim.initial_state_hash
    session.close()

    zero, zero_prefix = continuity.replay_until(db_path, 0)
    assert zero.state.tick == 0
    assert zero.state.hash() == initial_hash
    assert zero.journal.hash() == zero_prefix

    sim, prefix = continuity.replay_until(db_path, 5)
    assert sim.state.tick == 5
    assert sim.state.hash() == hashes[4]
    assert prefix == continuity.journal_prefix_hash(db_path, 5)
    assert sim.journal.hash() == prefix
    assert sim.journal.hash() != head_hash

    whole, archive, _lives = continuity.replay_head(db_path)
    try:
        assert whole.state.hash() == hashes[-1]
        assert whole.journal.hash() == archive.hash() == head_hash
    finally:
        archive.close()


def test_restart_restores_the_index_and_keeps_writing_in_step(tmp_path) -> None:
    def session(name: str) -> Session:
        return Session(
            seed=7, ruleset="player_resettle", regions=2, agents=54,
            max_ticks=200, db_dir=str(tmp_path / name),
        )

    first = session("first")
    for seq in range(1, 9):
        first.decide(seq, 6)
    db_path = first.db_path
    saved_digest = first.sim.journal.index_digest()
    saved_hash = first.sim.journal.hash()
    first.close()

    resumed, archive, _lives = continuity.replay_head(db_path)
    try:
        assert archive.index_digest() == saved_digest
        assert archive.hash() == saved_hash

        after_restart = []
        for _ in range(3):
            resumed.step()
            archive.commit()
            after_restart.append(
                (resumed.state.hash(), archive.hash(), archive.index_digest())
            )
    finally:
        archive.close()

    continuous = session("continuous")
    expected = []
    for seq in range(1, 12):
        continuous.decide(seq, 6)
        if seq >= 9:
            expected.append((
                continuous.sim.state.hash(),
                continuous.sim.journal.hash(),
                continuous.sim.journal.index_digest(),
            ))
    assert after_restart == expected


def test_writes_after_a_sqlite_rollback_do_not_resurrect_rows(tmp_path) -> None:
    """A lost transaction is not history: the batch is dropped, the chain
    reseeds from the archive (the same healing path as an uncertain COMMIT)."""
    sim = _world(150, persist=str(tmp_path / "rollback.db"))
    archive = sim.journal
    try:
        for _ in range(2):
            sim.step()
            archive.commit()
        stable = archive.hash()
        sim.step()  # rows staged; the first one took the write lock
        archive._conn.execute("ROLLBACK")
        archive._conn.execute("BEGIN")
        assert archive.hash() == stable
        assert archive._needs_seed is False
    finally:
        archive.close()


def test_write_projection_equals_the_full_transitions(tmp_path) -> None:
    """The frame path's projection carries exactly the committed writes."""
    sim = _run(200, 5, persist=str(tmp_path / "writes.db"))
    archive = sim.journal
    for tick in range(5):
        expected = [
            (transition.id, write.entity, write.field, write.new)
            for transition in archive.at_tick(tick)
            if transition.status is COMMITTED
            for write in transition.writes
        ]
        assert archive.writes_at_tick(tick) == expected
        with JournalView(archive.path) as view:
            assert view.writes_at_tick(tick) == expected


def test_cell_index_advance_from_the_projection_equals_a_rebuild(tmp_path) -> None:
    sim = _world(300, persist=str(tmp_path / "slice.db"))
    index = WorldIndex.from_state(sim.state, journal=sim.journal)
    for _ in range(3):
        sim.step()
        sim.journal.commit()
        index.advance(sim.journal, sim.state.tick - 1)
        fresh = WorldIndex.from_state(sim.state, journal=sim.journal)
        assert index.entities("agent:") == fresh.entities("agent:")
        assert index.entities("cell:") == fresh.entities("cell:")
        assert index.alive_count == fresh.alive_count
        assert index.agent_count == fresh.agent_count
        assert index.pool_stats == fresh.pool_stats
        for cell in fresh.entities("cell:"):
            assert index.agents_in_cell(cell) == fresh.agents_in_cell(cell)


def test_index_rebuilds_from_the_saved_journal_after_restart(tmp_path) -> None:
    """If the derived tables are lost, the journal alone restores them."""
    sim = _run(300, 4, persist=str(tmp_path / "lost-index.db"))
    path = sim.journal.path
    digest = sim.journal.index_digest()
    counts = sim.journal.index_counts()
    journal_hash = sim.journal.hash()
    sim.journal.close()

    with sqlite3.connect(path) as conn:
        for table in ("latest_writer", "history", "dependents"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

    reopened = SqliteArchive(path)
    try:
        assert reopened.index_counts() == {
            "latest_writer": 0, "history": 0, "dependents": 0
        }
        assert reopened.rebuild_index() == counts
        assert reopened.index_digest() == digest
        assert reopened.hash() == journal_hash
    finally:
        reopened.close()
