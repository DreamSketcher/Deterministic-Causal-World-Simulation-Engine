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

Hash chain (v0.6 P3): the incremental digest is the ONLY source for
``hash()``. ``record()`` appends canonical bytes to a pending tail and
does NOT touch the committed hasher; the hasher advances exactly when a
batch COMMITs, so a rolled-back or failed transaction can never leave the
chain describing rows the database does not have. ``hash()`` is O(1) always:
a projection hasher (the committed chain plus the pending tail) is fed in
record order, exactly as before — but it can be rebuilt from the committed
hasher at any commit boundary, so it is a convenience, never an authority.
Seeding a reopened archive and recovering from an uncertain transaction
outcome recompute from the archive — rare emergency paths, never a
per-frame rescan. The canonical definition itself is untouched: sha256
over newline-joined canonical records in id order.

Single-writer contract (P3 boundary audit). Every write to the archive
goes through ONE SqliteArchive instance: engine-side it is record()/
add()/set_meta(); the observer escape hatch query() is read-only ENFORCED,
the query index builds in its own cache file, and takeover verification
opens the file only to read and hash it. The MAX(id) sentinel detects a
journal whose row COUNT or id frontier moved (foreign append, rolled-back
transaction, uncertain COMMIT); it does NOT detect an external rewrite of
existing row content, and cannot — that mutation is outside the contract,
the same way editing the bytes of any artifact file is. A second OS-process
writer is stopped by SQLite's own write lock (its statements fail, and an
uncertain COMMIT on our side triggers the recompute path), not by the
hash chain. In other words: the chain is self-healing against transaction
boundaries, and the SINGLE-WRITER property is what keeps it authoritative
against content edits.
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
    """CREATE INDEX IF NOT EXISTS idx_transitions_op_status
       ON transitions(operation, status)""",
    # v0.12/2d: a tick query is a range on this column; without the index
    # every reader parsed the WHOLE journal (0.65 s at 4k living) just to
    # pick one tick's transitions.
    """CREATE INDEX IF NOT EXISTS idx_transitions_tick
       ON transitions(tick)""",
    """CREATE TABLE IF NOT EXISTS meta(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
]

#: Periodic commit cadence. Keeps the on-disk database valid if a long run
#: dies, bounds the loss window to a few dozen ticks, and is invisible to
#: determinism (commits never change recorded content or ordering).
COMMIT_EVERY = 50_000

#: v0.12/2d: how many rows one ``executemany`` carries. Batching changes
#: WHEN statements reach SQLite, never WHAT is recorded or in which order:
#: rows are staged in the same id order and the canonical hash chain keeps
#: advancing per transition. A test pins that a batch of one row and a
#: batch of ten thousand produce the same journal hash and the same rows.
BATCH_ROWS = 4096


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
        # check_same_thread=False (v0.6 step 5): a live session may be
        # served from different per-connection threads after a reconnect.
        # Safe because there is still ONE writer — serialization is the
        # Session's lock, not sqlite's thread heuristic.
        self._conn = sqlite3.connect(
            path, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        # Crash-safe WAL mode: a killed run leaves a VALID database that
        # rolls back to the last periodic commit (journal_mode=OFF would
        # corrupt on torn writes even inside a transaction).
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("BEGIN")
        for statement in _SCHEMA:
            self._conn.execute(statement)
        # --- hash chain state (P3): see module docstring for the contract.
        self._hasher = hashlib.sha256()
        # _branch is a pure projection: hasher-at-last-commit + the pending
        # tail, maintained incrementally so hash() stays O(1) even inside a
        # long open transaction. It is rebuilt from _hasher at every flush
        # and from the archive on every reseed — it is never an authority.
        self._branch = self._hasher.copy()
        self._pending: list[bytes] = []
        self._since_commit = 0
        # --- write batches (2d). Rows are staged in record order and are
        # handed to SQLite by _drain() with executemany. They live in the
        # SAME open transaction as a single-row write did, so a reader on
        # another connection sees them exactly at commit, as before.
        self._pending_inserts: list[tuple] = []
        self._pending_latest: list[tuple[str, str, int]] = []
        self._pending_history: list[tuple[str, str, int]] = []
        self._pending_dependents: list[tuple[int, int]] = []
        #: id of the last row actually handed to SQLite (not merely staged).
        #: It lets _drain() notice that the archive lost rows it had
        #: already received — an external ROLLBACK — BEFORE new rows are
        #: added on top: the batch is dropped and the chain reseeds.
        self._inserted_id: int | None = None
        # Reopening an existing archive restores counters from the DB, so
        # len/counts/by_id work on a persisted world without re-running it.
        self._restore_counters()
        # A non-empty archive at open time must seed its hasher on first
        # use (restore-from-archive); an empty one starts from zero bytes,
        # which is already correct.
        self._needs_seed = self._total > 0

    def _restore_counters(self) -> None:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS last_id FROM transitions"
        ).fetchone()
        self._total = int(row["n"])
        self._last_id = int(row["last_id"]) or None
        self._inserted_id = self._last_id
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
    @staticmethod
    def _canonical_bytes(transition: Transition) -> bytes:
        # Journal hash: the SAME canonical definition as the in-memory
        # journal — sha256 over newline-joined canonical records, id order.
        return (canonical_json(transition_record(transition)) + "\n").encode("utf-8")

    def record(self, transition: Transition) -> None:
        if transition.id is None:
            raise ValueError("cannot record a transition without an id")
        if self._last_id is not None and transition.id <= self._last_id:
            raise ValueError(
                f"journal records must be ascending by id "
                f"(got T{transition.id} after T{self._last_id})"
            )
        # Build and validate the row BEFORE anything is recorded. The
        # single-row writer let SQLite raise NOT NULL violations inside
        # record(); a batch would defer that error to a later flush, so
        # the same constraints are checked here and the chain/counters
        # are touched only after the row is known to be recordable.
        row = (
            transition.id,
            transition.tick,
            transition.system,
            transition.operation,
            transition.priority,
            transition.status.value,
            transition.reject_reason,
            _payload_of(transition),
        )
        for index, column in ((0, "id"), (1, "tick"), (2, "system"),
                              (3, "operation"), (4, "priority"),
                              (5, "status"), (7, "payload")):
            if row[index] is None:
                raise sqlite3.IntegrityError(
                    f"NOT NULL constraint failed: transitions.{column}"
                )
        chunk = self._canonical_bytes(transition)
        self._last_id = transition.id
        # The row is staged in the open transaction; the canonical bytes
        # join the pending tail with it. The committed hasher is NOT
        # advanced here — only _flush() may do that, at the commit
        # boundary (P3 contract).
        self._pending_inserts.append(row)
        self._pending.append(chunk)
        self._branch.update(chunk)
        self._total += 1
        if transition.status is TransitionStatus.COMMITTED:
            self._committed += 1
            self._last_committed_id = transition.id
        elif transition.status is TransitionStatus.REJECTED:
            self._rejected += 1
        # The first record of a commit cycle is flushed at once: it takes
        # SQLite's write lock exactly when the single-row writer did, so a
        # second writer is still locked out at the same point. The rest of
        # the cycle is batched.
        first_in_cycle = self._since_commit == 0
        self._since_commit += 1
        if first_in_cycle or len(self._pending_inserts) >= BATCH_ROWS:
            self._drain()
        if self._since_commit >= COMMIT_EVERY:
            self._flush()

    def _drain(self) -> None:
        """Hand staged rows to SQLite, in record order, in one batch each.

        This is a transport change only. The rows are the same rows a
        single-row write produced, in the same order; the transaction is
        the same open transaction. On error the buffers are dropped and
        the chain is marked stale, exactly like an uncertain COMMIT: the
        archive, not the in-memory tail, becomes the authority.
        """
        if not (self._pending_inserts or self._pending_latest
                or self._pending_history or self._pending_dependents):
            return
        if not self._conn.in_transaction:
            # The transaction these rows were staged into is gone (an
            # external ROLLBACK, or someone called COMMIT behind our
            # back). The rows are NOT part of the archive: drop them and
            # let the chain rebuild from the file — the same self-healing
            # path an uncertain COMMIT takes.
            self._pending_inserts.clear()
            self._pending_latest.clear()
            self._pending_history.clear()
            self._pending_dependents.clear()
            self._pending.clear()
            self._since_commit = 0
            self._needs_seed = True
            return
        # Before adding rows, verify the archive still has everything we
        # already handed it (the MAX(id) frontier). A vanished row means
        # this batch was staged against a transaction that no longer
        # exists; it is not part of history and must not be inserted on
        # top of a rolled-back archive.
        frontier = int(self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM transitions"
        ).fetchone()[0])
        if frontier != (self._inserted_id or 0):
            self._pending_inserts.clear()
            self._pending_latest.clear()
            self._pending_history.clear()
            self._pending_dependents.clear()
            self._pending.clear()
            self._since_commit = 0
            self._needs_seed = True
            return
        try:
            if self._pending_inserts:
                batch = self._pending_inserts
                self._conn.executemany(
                    "INSERT INTO transitions VALUES (?,?,?,?,?,?,?,?)", batch
                )
                self._inserted_id = batch[-1][0]
                self._pending_inserts.clear()
            if self._pending_latest:
                self._conn.executemany(
                    "INSERT INTO latest_writer VALUES (?,?,?) "
                    "ON CONFLICT(entity, field) DO UPDATE SET tid=excluded.tid",
                    self._pending_latest,
                )
                self._pending_latest.clear()
            if self._pending_history:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO history VALUES (?,?,?)",
                    self._pending_history,
                )
                self._pending_history.clear()
            if self._pending_dependents:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO dependents VALUES (?,?)",
                    self._pending_dependents,
                )
                self._pending_dependents.clear()
        except sqlite3.Error:
            self._pending_inserts.clear()
            self._pending_latest.clear()
            self._pending_history.clear()
            self._pending_dependents.clear()
            self._pending.clear()
            self._since_commit = 0
            self._needs_seed = True
            raise

    def _commit_tx(self) -> None:
        self._conn.execute("COMMIT")
        self._conn.execute("BEGIN")

    def _flush(self) -> None:
        """Advance the committed hash chain AT the commit boundary: the
        hasher ingests the pending tail only after COMMIT returned without
        error. A failed/uncertain COMMIT marks the chain stale; the next
        hash() restores it from the archive."""
        self._drain()
        if not self._since_commit:
            return
        try:
            self._commit_tx()
        except sqlite3.Error:
            self._needs_seed = True
            raise
        # One update per chunk was O(records) calls into hashlib; joining
        # in bounded groups keeps the order and the bytes identical while
        # cutting the Python crossing. The canonical definition is the
        # same: sha256 over newline-joined records in id order.
        for i in range(0, len(self._pending), 1024):
            self._hasher.update(b"".join(self._pending[i:i + 1024]))
        self._pending = []
        self._since_commit = 0
        # after a successful flush the projection IS the committed chain
        self._branch = self._hasher.copy()

    def commit(self) -> None:
        """Public flush (v0.6 step 5, G1): make everything recorded so far
        durable and visible to readers. The live server calls this after
        each decided step, so a decision is ACCEPTED exactly when its
        transition survives a process kill; batch-commit remains the
        optimization, never the semantic boundary. Since P3 this is also
        the exact point where the hash chain advances."""
        self._flush()

    def _reseed_from_disk(self) -> None:
        """Restore/recover the chain: rebuild the hasher from the archive
        itself (canonical scan, id order). Runs on the first hash() of a
        reopened archive and after an uncertain transaction outcome —
        never as a per-frame operation."""
        self._drain()
        hasher = hashlib.sha256()
        for transition in self:
            hasher.update(self._canonical_bytes(transition))
        self._hasher = hasher
        self._branch = hasher.copy()
        self._pending = []
        self._restore_counters()
        self._needs_seed = False

    def _ensure_synced(self) -> None:
        self._drain()
        if not self._needs_seed:
            # O(log n) sentinel (B-tree seek on the INTEGER PRIMARY KEY):
            # if the table's id frontier no longer matches what the chain
            # describes — rolled-back rows, a foreign writer — recompute.
            row = self._conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM transitions"
            ).fetchone()
            if int(row[0]) != (self._last_id or 0):
                self._needs_seed = True
        if self._needs_seed:
            self._reseed_from_disk()

    def hash(self) -> str:
        self._ensure_synced()
        return self._branch.copy().hexdigest()

    def __len__(self) -> int:
        return self._total

    def counts(self) -> tuple[int, int, int]:
        return self._total, self._committed, self._rejected

    def has(self, transition_id: int) -> bool:
        self._drain()
        row = self._conn.execute(
            "SELECT 1 FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        return row is not None

    def by_id(self, transition_id: int) -> Transition:
        self._drain()
        row = self._conn.execute(
            "SELECT * FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no transition T{transition_id} in journal")
        return _transition_from_row(row)

    def get(self, transition_id: int) -> Transition:
        return self.by_id(transition_id)

    def __iter__(self) -> Iterator[Transition]:
        self._drain()
        cursor = self._conn.execute("SELECT * FROM transitions ORDER BY id")
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for row in rows:
                yield _transition_from_row(row)

    def committed(self) -> Iterator[Transition]:
        self._drain()
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
        self._drain()
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
        self._drain()
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE tick=? ORDER BY id", (tick,)
        ).fetchall()
        return [_transition_from_row(row) for row in rows]

    def writes_at_tick(self, tick: int) -> list[tuple[int, str, str, object]]:
        """Committed writes of one tick as ``(tid, entity, field, new)``.

        A READ PROJECTION for consumers that only apply writes (the cell
        index): it uses the tick index, skips rejected proposals and
        never builds ``Transition``/``StateRead``/``RandomDraw`` objects.
        The order is the ``at_tick()`` order — transition id, then the
        recorded write order — so an index advanced from this projection
        is the same index advanced from full transitions (pinned in
        ``tests/test_v012_journal.py``).
        """
        self._drain()
        out: list[tuple[int, str, str, object]] = []
        rows = self._conn.execute(
            "SELECT id, payload FROM transitions "
            "WHERE tick=? AND status='COMMITTED' ORDER BY id",
            (tick,),
        )
        for row in rows:
            if not row["payload"]:
                continue
            for entity, field_name, _old, new in json.loads(row["payload"])["writes"]:
                out.append((row["id"], entity, field_name, new))
        return out

    def between_ticks(self, lo: int, hi: int) -> list[Transition]:
        """Transitions of ticks ``lo..hi`` inclusive, id order (tick index)."""
        self._drain()
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE tick BETWEEN ? AND ? ORDER BY id",
            (lo, hi),
        ).fetchall()
        return [_transition_from_row(row) for row in rows]

    def transitions_for_entity(self, entity: str, status: str = "COMMITTED"):
        """Transitions that write ``entity``, id order.

        COMMITTED is answered from the derived ``history`` index — the
        same rows the sequential scan would keep, in the same order. Any
        other status falls back to the scan, because rejected proposals
        never enter the index.
        """
        self._drain()
        if status == "COMMITTED":
            rows = self._conn.execute(
                "SELECT * FROM transitions WHERE status='COMMITTED' "
                "AND id IN (SELECT tid FROM history WHERE entity=?) "
                "ORDER BY id",
                (entity,),
            ).fetchall()
            return [_transition_from_row(row) for row in rows]
        wanted = TransitionStatus[status]
        out = []
        for row in self._conn.execute("SELECT * FROM transitions ORDER BY id"):
            transition = _transition_from_row(row)
            if (transition.status is wanted
                    and any(w.entity == entity for w in transition.writes)):
                out.append(transition)
        return out

    def transitions_for_field(self, entity: str, field_name: str,
                              status: str = "COMMITTED"):
        """Transitions that write one field of one entity, id order.

        COMMITTED is answered by the ``history`` primary key; other
        statuses scan, for the same reason as above.
        """
        self._drain()
        if status == "COMMITTED":
            rows = self._conn.execute(
                "SELECT * FROM transitions WHERE status='COMMITTED' "
                "AND id IN (SELECT tid FROM history "
                "           WHERE entity=? AND field=?) ORDER BY id",
                (entity, field_name),
            ).fetchall()
            return [_transition_from_row(row) for row in rows]
        wanted = TransitionStatus[status]
        out = []
        for row in self._conn.execute("SELECT * FROM transitions ORDER BY id"):
            transition = _transition_from_row(row)
            if (transition.status is wanted
                    and any(w.entity == entity and w.field == field_name
                            for w in transition.writes)):
                out.append(transition)
        return out

    def iter_operations(self, operations) -> Iterator[Transition]:
        """Stream committed transitions of the given operations, id order."""
        self._drain()
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
            row = (w.entity, w.field, t.id)
            self._pending_latest.append(row)
            self._pending_history.append(row)
        for r in t.reads:
            if r.source_transition is not None:
                self._pending_dependents.append((r.source_transition, t.id))
        if len(self._pending_history) >= BATCH_ROWS:
            self._drain()

    # ------------------------------------------------------------------
    # Derived-index maintenance (v0.12/2d): the index is an INDEX. It can
    # be deleted and rebuilt from the journal alone; the digest is over
    # the rows, not over the journal hash, so a rebuild can be compared
    # with the incrementally maintained index without touching history.
    # ------------------------------------------------------------------
    def index_counts(self) -> dict[str, int]:
        self._drain()
        return {
            table: int(self._conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0])
            for table in ("latest_writer", "history", "dependents")
        }

    def index_digest(self) -> str:
        """SHA-256 over the derived index rows (sorted), not the journal."""
        self._drain()
        hasher = hashlib.sha256()
        for table, columns in (
            ("latest_writer", "entity, field, tid"),
            ("history", "entity, field, tid"),
            ("dependents", "source, target"),
        ):
            hasher.update((table + "\n").encode("utf-8"))
            cursor = self._conn.execute(
                f"SELECT {columns} FROM {table} ORDER BY {columns}"
            )
            for row in cursor:
                hasher.update(canonical_json([row[i] for i in range(len(row))])
                              .encode("utf-8"))
                hasher.update(b"\n")
        return hasher.hexdigest()

    def rebuild_index(self) -> dict[str, int]:
        """Drop the derived index and rebuild it from ``transitions`` only.

        Committed transitions are scanned in id order, so the last write
        of a (entity, field) is the row ``latest_writer`` ends with — the
        same result the incremental ``add()`` produces. Streamed in
        batches: a rebuild of a long archive does not materialise the
        index in Python memory.
        """
        self._drain()
        for table in ("latest_writer", "history", "dependents"):
            self._conn.execute(f"DELETE FROM {table}")
        latest: list[tuple] = []
        history: list[tuple] = []
        dependents: list[tuple] = []
        def flush() -> None:
            if latest:
                self._conn.executemany(
                    "INSERT INTO latest_writer VALUES (?,?,?) "
                    "ON CONFLICT(entity, field) DO UPDATE SET tid=excluded.tid",
                    latest,
                )
                latest.clear()
            if history:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO history VALUES (?,?,?)", history
                )
                history.clear()
            if dependents:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO dependents VALUES (?,?)", dependents
                )
                dependents.clear()

        for transition in self.committed():
            for w in transition.writes:
                latest.append((w.entity, w.field, transition.id))
                history.append((w.entity, w.field, transition.id))
            for r in transition.reads:
                if r.source_transition is not None:
                    dependents.append((r.source_transition, transition.id))
            if len(history) >= BATCH_ROWS:
                flush()
        flush()
        return self.index_counts()

    def writer_of(self, entity: str, field_name: str) -> int | None:
        self._drain()
        row = self._conn.execute(
            "SELECT tid FROM latest_writer WHERE entity=? AND field=?",
            (entity, field_name),
        ).fetchone()
        return row["tid"] if row else None

    def history_of(self, entity: str, field_name: str) -> list[int]:
        self._drain()
        rows = self._conn.execute(
            "SELECT tid FROM history WHERE entity=? AND field=? ORDER BY tid",
            (entity, field_name),
        ).fetchall()
        return [row["tid"] for row in rows]

    def dependents_of(self, transition_id: int) -> list[int]:
        self._drain()
        rows = self._conn.execute(
            "SELECT target FROM dependents WHERE source=? ORDER BY target",
            (transition_id,),
        ).fetchall()
        return [row["target"] for row in rows]

    # ------------------------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Escape hatch for read-only observer-side SQL (analysis layer).

        The simulation itself never uses this; it exists so observers can
        aggregate over the journal without reconstructing every object.
        Read-only is enforced in code (P3 boundary audit): the single-writer
        contract of the archive must not rest on convention. Multi-statement
        SQL is rejected by sqlite3 itself.
        """
        head = sql.lstrip().split(None, 1)[0].lower() if sql.strip() else ""
        if head not in ("select", "with"):
            raise ValueError(
                f"archive query() is read-only: statement must start with "
                f"SELECT or WITH (got {head!r})"
            )
        self._drain()
        return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        try:
            # Closing makes everything durable — including rows still in a
            # write batch. Flush the chain first so its bytes describe the
            # rows that are about to be committed.
            self._flush()
            try:
                self._conn.execute("COMMIT")
            except sqlite3.OperationalError:
                pass  # no transaction open (reopened archive, read-only use)
        finally:
            self._conn.close()

    def __enter__(self) -> "SqliteArchive":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
