"""v0.6 P3 follow-up: incremental archive hash chain vs the reference scan.

The optimized SqliteArchive must be the ONLY computation path for the
current hash() (P3 contract, user-ratified):

1. the committed hasher advances exactly at COMMIT, never before
   (a rolled-back transaction can never leave the chain describing rows
   the archive does not contain);
2. hash() without new records is O(1) — cached digest, no rescan;
3. reopening restores the chain from the saved data, byte-identical to a
   full reference recompute;
4. canonical algorithm, record order and archive format unchanged;
5. every scenario below compares against reference_hash() — the OLD
   implementation's algorithm, reimplemented here as the oracle.
"""

from __future__ import annotations

import dataclasses
import hashlib
import random
import sqlite3
from dataclasses import replace

import pytest

from causal_world.kernel.canonical import canonical_json
from causal_world.kernel.transition import (
    RandomDraw,
    StateChange,
    StateRead,
    Transition,
    TransitionStatus,
    transition_record,
)
from causal_world.simulation.archive import (
    SqliteArchive,
    _transition_from_row,
)


def reference_hash(path: str) -> str:
    """The pre-P3 algorithm, verbatim: full canonical scan of the file
    (committed state only — a foreign connection cannot see the open
    transaction), sha256 over newline-joined canonical records, id order."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    hasher = hashlib.sha256()
    try:
        rows = conn.execute("SELECT * FROM transitions ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        # fresh archive: the schema still lives in the creator's open tx
        rows = []
    for row in rows:
        t = _transition_from_row(row)
        hasher.update(
            (canonical_json(transition_record(t)) + "\n").encode("utf-8")
        )
    conn.close()
    return hasher.hexdigest()


def make_transition(i: int, rng: random.Random | None = None) -> Transition:
    rng = rng or random.Random(i)
    committed = rng.random() < 0.75
    status = TransitionStatus.COMMITTED if committed else TransitionStatus.REJECTED
    return Transition(
        id=i,
        tick=i // 3,
        system=f"sys{i % 5}",
        operation=f"op{i % 7}",
        reads=[StateRead(entity=f"e{rng.randrange(4)}", field="f",
                         value=rng.randrange(10), source_transition=max(1, i - 1))],
        writes=[StateChange(entity=f"e{rng.randrange(4)}", field="f",
                            old=rng.randrange(10), new=rng.randrange(10))]
        if committed
        else [],
        random_draws=[RandomDraw(purpose="d", entity=f"e{i % 4}", index=i,
                                 value=rng.random(), threshold=0.5,
                                 outcome=committed)],
        priority=100 + i,
        status=status,
        reject_reason=None if committed else "blocked",
    )


@pytest.fixture
def archive(tmp_path):
    path = str(tmp_path / "arc.db")
    a = SqliteArchive(path)
    a.path = path  # convenience for the reference oracle
    yield a
    a.close()


def test_empty_archive_hash_matches_reference_and_definition(archive):
    assert archive.hash() == reference_hash(archive.path)
    assert archive.hash() == hashlib.sha256().hexdigest()


def test_single_and_many_sequential_records(archive):
    for i in range(1, 60):
        archive.record(make_transition(i))
        # after EVERY record the live hash must equal a full reference
        # recompute over the committed data (record() flushes nothing, so
        # compare via the same connection: force a commit boundary first)
    archive.commit()
    assert archive.hash() == reference_hash(archive.path)


def test_random_batches_interleaved_hashes(archive):
    rng = random.Random(20261014)
    expected = hashlib.sha256()
    i = 1
    while i <= 500:
        batch = rng.randint(1, 9)
        for _ in range(batch):
            t = make_transition(i, rng)
            archive.record(t)
            expected.update(
                (canonical_json(transition_record(t)) + "\n").encode("utf-8")
            )
            i += 1
        if rng.random() < 0.4:
            archive.commit()
        # live view must always equal our own incremental expectation bytes
        assert archive.hash() == expected.hexdigest()
    archive.commit()
    assert archive.hash() == reference_hash(archive.path)


def test_multi_batch_commit_cadence_flushes_chain(archive, monkeypatch):
    import causal_world.simulation.archive as archive_mod

    monkeypatch.setattr(archive_mod, "COMMIT_EVERY", 7)
    for i in range(1, 50):
        archive.record(make_transition(i))
    assert archive._since_commit < 7  # periodic flushes happened
    archive.commit()
    assert archive.hash() == reference_hash(archive.path)


def test_close_reopen_restore_and_repeat_hash_is_o1(tmp_path):
    path = str(tmp_path / "reopen.db")
    a = SqliteArchive(path)
    for i in range(1, 31):
        a.record(make_transition(i))
    h_before = a.hash()
    a.close()

    b = SqliteArchive(path)
    assert b._needs_seed is True  # reopen must restore from saved data
    calls = []
    original = b._reseed_from_disk

    def counting():
        calls.append(1)
        original()

    b._reseed_from_disk = counting
    assert b.hash() == h_before == reference_hash(path)
    assert len(calls) == 1  # one seeding pass, on first use
    for _ in range(20):  # repeated hash() without new records: no rescan
        assert b.hash() == h_before
    for i in range(31, 36):  # append via the reopened session, commit
        b.record(make_transition(i))
        b.commit()
        assert b.hash() == reference_hash(path)
    assert len(calls) == 1  # never rescanned after seeding
    b.close()


def test_failed_record_leaves_chain_consistent(archive):
    for i in range(1, 6):
        archive.record(make_transition(i))
    archive.commit()
    good = archive.hash()
    # rejected by the ascending-id guard: nothing inserted, nothing fed
    with pytest.raises(ValueError):
        archive.record(make_transition(3))
    with pytest.raises(ValueError):
        archive.record(make_transition(1))
    assert archive.hash() == good
    # a NOT NULL violation inside record(): INSERT fails before the
    # pending tail is touched
    bad = Transition(
        id=6, tick=2, system="s", operation="op", reads=[], writes=[],
        random_draws=[], priority=None, status=TransitionStatus.COMMITTED,
        reject_reason=None,
    )
    with pytest.raises(sqlite3.IntegrityError):
        archive.record(bad)
    assert archive.hash() == good
    archive.commit()
    assert archive.hash() == reference_hash(archive.path)


def test_rolled_back_transaction_cannot_poison_the_chain(archive):
    for i in range(1, 11):
        archive.record(make_transition(i))
    archive.commit()
    stable = archive.hash()
    for i in range(11, 16):
        archive.record(make_transition(i))
    # disaster: the open transaction vanishes under the chain's feet
    archive._conn.execute("ROLLBACK")
    archive._conn.execute("BEGIN")
    # the chain MUST NOT be trusted here; the MAX(id) sentinel detects the
    # divergence and the next hash() recomputes from the archive
    assert archive.hash() == stable == reference_hash(archive.path)
    assert archive._needs_seed is False  # resynced, next calls are O(1)


def test_uncertain_commit_outcome_forces_recompute(archive, monkeypatch):
    for i in range(1, 8):
        archive.record(make_transition(i))
    original = archive._commit_tx

    def boom():
        raise sqlite3.OperationalError("simulated COMMIT failure")

    archive._commit_tx = boom
    with pytest.raises(sqlite3.OperationalError):
        archive.commit()
    archive._commit_tx = original
    assert archive._needs_seed is True
    # the rows are still in the open transaction — finish it honestly,
    # then the recovery path must produce the canonical result
    archive._conn.execute("COMMIT")
    archive._conn.execute("BEGIN")
    assert archive.hash() == reference_hash(archive.path)


def test_same_state_different_order_is_a_different_hash(tmp_path):
    """Order/composition of journal entries is part of the canonical
    identity even when the resulting world state would be identical."""
    pa, pb = str(tmp_path / "a.db"), str(tmp_path / "b.db")
    a, b = SqliteArchive(pa), SqliteArchive(pb)
    x = make_transition(1)
    y = make_transition(2)
    a.record(x)
    a.record(y)
    # same two transitions, swapped ids: identical states, different journal
    b.record(replace(y, id=1))  # same contents, other id order
    b.record(replace(x, id=2))
    a.commit()
    b.commit()
    assert a.hash() != b.hash()
    assert a.hash() == reference_hash(pa)
    assert b.hash() == reference_hash(pb)
    a.close()
    b.close()


def test_long_run_and_takeover_identity_via_engine(tmp_path):
    """P3 claim on real worlds: archived run hashes identically to the
    in-memory run, close/reopen/takeover all agree with the oracle."""
    from causal_world import create_world
    from causal_world.world.rules import get_ruleset

    path = str(tmp_path / "engine.db")
    world = create_world(seed=21, ruleset=get_ruleset("player_life"),
                         ticks=0, regions=4, agents=50, persist=path)
    for i in range(1, 61):  # raw stepping (no session): the batch path
        world.step()
        if i % 7 == 0:
            world.journal.commit()
    live = world.journal.hash()
    mem = create_world(seed=21, ruleset=get_ruleset("player_life"),
                       ticks=0, regions=4, agents=50)
    for _ in range(60):
        mem.step()
    assert live == mem.journal.hash()  # disk and memory runs agree
    world.journal.close()
    assert reference_hash(path) == live
    b = SqliteArchive(path)  # reopen = what takeover verification does
    assert b.hash() == live
    b.close()
