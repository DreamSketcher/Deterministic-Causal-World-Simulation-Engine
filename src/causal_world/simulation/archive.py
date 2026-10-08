"""SqliteArchive: disk-backed journal + causal index for long runs.

The v0.1 kernel keeps the full journal and causal index in memory, which
bounds run length by RAM. The archive moves both to a single SQLite file
with NO semantic change:

* the journal is still the full, unfiltered truth (committed AND rejected
  transitions, in id order);
* the causal index is still rebuilt only from recorded reads;
* every query result is deterministic;
* the journal hash uses the exact same canonical definition as the
  in-memory journal, so a memory run and an archived run of the same world
  produce IDENTICAL state and journal hashes.

Writes stay inside one transaction for the lifetime of the archive —
experiment artifacts are reproducible by rerunning, so durability of a
crashed run is not the point.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Iterator

from causal_world.kernel.canonical import canonical_json
from causal_world.kernel.transition import (
    RandomDraw,
    StateChange,
    StateRead,
    Transition,
    TransitionStatus,
    transition_record,
)

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS transitions(
        id INTEGER PRIMARY KEY,
        tick INTEGER NOT NULL,
        system TEXT NOT NULL,
        operation TEXT NOT NULL,
        priority INTEGER NOT NULL,
        status TEXT NOT NULL,
        reject_reason TEXT,
        payload TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS latest_writer(
        entity TEXT NOT NULL,
        field TEXT NOT NULL,
        tid INTEGER NOT NULL,
        PRIMARY KEY(entity, field)
    )""",
    """CREATE TABLE IF NOT EXISTS history(
        entity TEXT NOT NULL,
        field TEXT NOT NULL,
        tid INTEGER NOT NULL,
        PRIMARY KEY(entity, field, tid)
    )""",
    """CREATE TABLE IF NOT EXISTS dependents(
        source INTEGER NOT NULL,
        target INTEGER NOT NULL,
        PRIMARY KEY(source, target)
    )""",
]

#: Periodic commit cadence. Keeps the on-disk database valid if a long run
#: dies, bounds the loss window to a few dozen ticks, and is invisible to
#: determinism (commits never change recorded content or ordering).
COMMIT_EVERY = 50_000


def _payload_of(t: Transition) -> str:
    reads = [[r.entity, r.field, r.value, r.source_transition] for r in t.reads]
    writes = [[w.entity, w.field, w.old, w.new] for w in t.writes]
    draws = [
        [d.purpose, d.entity, d.index, d.value, d.threshold, d.outcome]
        for d in t.random_draws
    ]
    return canonical_json({"reads": reads, "writes": writes, "draws": draws})


def _transition_from_row(row: sqlite3.Row) -> Transition:
    payload = json.loads(row["payload"])
    reads = [
        StateRead(entity=entity, field=field, value=value, source_transition=source)
        for entity, field, value, source in payload["reads"]
    ]
    writes = [
        StateChange(entity=entity, field=field, old=old, new=new)
        for entity, field, old, new in payload["writes"]
    ]
    draws = [
        RandomDraw(
            purpose=purpose,
            entity=entity,
            index=index,
            value=value,
            threshold=threshold,
            outcome=outcome,
        )
        for purpose, entity, index, value, threshold, outcome in payload["draws"]
    ]
    return Transition(
        id=row["id"],
        tick=row["tick"],
        system=row["system"],
        operation=row["operation"],
        reads=reads,
        writes=writes,
        random_draws=draws,
        priority=row["priority"],
        status=TransitionStatus(row["status"]),
        reject_reason=row["reject_reason"],
    )


class SqliteArchive:
    """Implements both the journal and the causal-index interfaces."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn = sqlite3.connect(path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=OFF")
        self._conn.execute("PRAGMA synchronous=OFF")
        self._conn.execute("BEGIN")
        for statement in _SCHEMA:
            self._conn.execute(statement)
        self._hasher = hashlib.sha256()
        self._since_commit = 0
        self._new_records = 0
        self._hash_cache: str | None = None
        # Reopening an existing archive restores counters from the DB, so
        # len/counts/by_id work on a persisted world without re-running it.
        row = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS last_id FROM transitions"
        ).fetchone()
        self._total_at_open = int(row["n"])
        self._total = int(row["n"])
        self._last_id = int(row["last_id"]) or None
        committed_row = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS last_id "
            "FROM transitions WHERE status='COMMITTED'"
        ).fetchone()
        self._committed = int(committed_row["n"])
        self._last_committed_id = int(committed_row["last_id"]) or None
        rejected_row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM transitions WHERE status='REJECTED'"
        ).fetchone()
        self._rejected = int(rejected_row["n"])

    # ------------------------------------------------------------------
    # Journal interface
    # ------------------------------------------------------------------
    def record(self, transition: Transition) -> None:
        if transition.id is None:
            raise ValueError("cannot record a transition without an id")
        if self._last_id is not None and transition.id <= self._last_id:
            raise ValueError(
                f"journal records must be ascending by id "
                f"(got T{transition.id} after T{self._last_id})"
            )
        self._last_id = transition.id
        self._conn.execute(
            "INSERT INTO transitions VALUES (?,?,?,?,?,?,?,?)",
            (
                transition.id,
                transition.tick,
                transition.system,
                transition.operation,
                transition.priority,
                transition.status.value,
                transition.reject_reason,
                _payload_of(transition),
            ),
        )
        # Journal hash: the SAME canonical definition as the in-memory
        # journal — sha256 over newline-joined canonical records, id order.
        self._hasher.update(
            (canonical_json(transition_record(transition)) + "\n").encode("utf-8")
        )
        self._total += 1
        self._new_records += 1
        if transition.status is TransitionStatus.COMMITTED:
            self._committed += 1
            self._last_committed_id = transition.id
        elif transition.status is TransitionStatus.REJECTED:
            self._rejected += 1
        self._since_commit += 1
        if self._since_commit >= COMMIT_EVERY:
            self._conn.execute("COMMIT")
            self._conn.execute("BEGIN")
            self._since_commit = 0

    def hash(self) -> str:
        if self._total_at_open:
            # Reopened archive: the incremental hasher only saw records
            # added after reopening, so recompute from disk (canonical
            # definition unchanged). Cached until new records arrive.
            if self._hash_cache is None:
                hasher = hashlib.sha256()
                for transition in self:
                    hasher.update(
                        (canonical_json(transition_record(transition)) + "\n").encode(
                            "utf-8"
                        )
                    )
                self._hash_cache = hasher.hexdigest()
                self._cached_at_new_records = self._new_records
            elif getattr(self, "_cached_at_new_records", 0) != self._new_records:
                self._hash_cache = None
                return self.hash()
            return self._hash_cache
        return self._hasher.copy().hexdigest()

    def __len__(self) -> int:
        return self._total

    def counts(self) -> tuple[int, int, int]:
        return self._total, self._committed, self._rejected

    def has(self, transition_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        return row is not None

    def by_id(self, transition_id: int) -> Transition:
        row = self._conn.execute(
            "SELECT * FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no transition T{transition_id} in journal")
        return _transition_from_row(row)

    def get(self, transition_id: int) -> Transition:
        return self.by_id(transition_id)

    def __iter__(self) -> Iterator[Transition]:
        cursor = self._conn.execute("SELECT * FROM transitions ORDER BY id")
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for row in rows:
                yield _transition_from_row(row)

    def committed(self) -> Iterator[Transition]:
        cursor = self._conn.execute(
            "SELECT * FROM transitions WHERE status='COMMITTED' ORDER BY id"
        )
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for row in rows:
                yield _transition_from_row(row)

    def rejected(self) -> Iterator[Transition]:
        cursor = self._conn.execute(
            "SELECT * FROM transitions WHERE status='REJECTED' ORDER BY id"
        )
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for row in rows:
                yield _transition_from_row(row)

    def at_tick(self, tick: int) -> list[Transition]:
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE tick=? ORDER BY id", (tick,)
        ).fetchall()
        return [_transition_from_row(row) for row in rows]

    def iter_operations(self, operations) -> Iterator[Transition]:
        """Stream committed transitions of the given operations, id order."""
        ops = sorted(operations)
        marks = ",".join("?" for _ in ops)
        cursor = self._conn.execute(
            f"SELECT * FROM transitions WHERE status='COMMITTED' "
            f"AND operation IN ({marks}) ORDER BY id",
            ops,
        )
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for row in rows:
                yield _transition_from_row(row)

    def all(self) -> list[Transition]:
        """Materializes the whole journal — use only on small runs."""
        return list(self)

    def last_committed_id(self) -> int | None:
        return self._last_committed_id

    # ------------------------------------------------------------------
    # Causal-index interface
    # ------------------------------------------------------------------
    def add(self, t: Transition) -> None:
        if t.status is not TransitionStatus.COMMITTED:
            return  # rejected transitions never wrote state (spec §17)
        for w in t.writes:
            self._conn.execute(
                "INSERT INTO latest_writer VALUES (?,?,?) "
                "ON CONFLICT(entity, field) DO UPDATE SET tid=excluded.tid",
                (w.entity, w.field, t.id),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO history VALUES (?,?,?)",
                (w.entity, w.field, t.id),
            )
        for r in t.reads:
            if r.source_transition is not None:
                self._conn.execute(
                    "INSERT OR IGNORE INTO dependents VALUES (?,?)",
                    (r.source_transition, t.id),
                )

    def writer_of(self, entity: str, field_name: str) -> int | None:
        row = self._conn.execute(
            "SELECT tid FROM latest_writer WHERE entity=? AND field=?",
            (entity, field_name),
        ).fetchone()
        return row["tid"] if row else None

    def history_of(self, entity: str, field_name: str) -> list[int]:
        rows = self._conn.execute(
            "SELECT tid FROM history WHERE entity=? AND field=? ORDER BY tid",
            (entity, field_name),
        ).fetchall()
        return [row["tid"] for row in rows]

    def dependents_of(self, transition_id: int) -> list[int]:
        rows = self._conn.execute(
            "SELECT target FROM dependents WHERE source=? ORDER BY target",
            (transition_id,),
        ).fetchall()
        return [row["target"] for row in rows]

    # ------------------------------------------------------------------
    def close(self) -> None:
        try:
            self._conn.execute("COMMIT")
        except sqlite3.OperationalError:
            pass  # no transaction open (e.g. reopened archive, read-only use)
        self._conn.close()

    def __enter__(self) -> "SqliteArchive":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
