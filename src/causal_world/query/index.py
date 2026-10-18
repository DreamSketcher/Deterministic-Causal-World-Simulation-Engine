"""QueryIndex: persistent, lazily built indexes over a recorded archive.

    JournalView (raw archive, read-only)
        -> QueryIndex (derived indexes in a separate cache DB)
        -> CausalQuery (composable API, streaming results)

Design notes / deviations from the v0.5 proposal (verified against the
frozen archive schema before transcribing):

* The archive ALREADY persists three of the four proposed indexes:
  ``history(entity, field, tid)`` answers "who wrote this field",
  ``dependents(source, target)`` answers "who read what I wrote", and
  ``idx_transitions_op_status`` covers (operation, status) lookups.
  Duplicating them would waste gigabytes. The QueryIndex ATTACHes the
  archive read-only and adds ONLY what is missing:

    idx_writes(entity, field, tid, tick, delta, old, new)
        — write-level drill-down: the same operation name in two
          systems is distinguished by its ACTUAL deltas (the v0.4
          compost-vs-agriculture signal);
    idx_reads(source_tid, reader_tid, entity, field)
        — dependents refined by which entity/field was read;
    idx_entity(entity, tid, tick, role in {writer, reader})
        — per-entity timelines ("the whole life of agent X").

* The build is a SINGLE SQLite pass (INSERT .. SELECT with json_each
  over the attached archive), not a Python row loop — for a
  multi-million-transition journal this is the difference between
  minutes and hours. ``JournalView.iter_batches`` (the spec's streaming
  iterator) exists for Python-side consumers.
* Incremental: qmeta stores the last indexed transition id; build()
  indexes only ``id > last_tid``. Identity (seed / ruleset / rng /
  sizes) is verified — a cache from a different world is rebuilt, never
  mixed. Determinism guarantees the prefix of a re-run is identical, so
  incremental == full rebuild content-wise (tested).
* The cache DB is a derived artifact: it is written with
  ``synchronous=OFF`` and is fully reconstructible from the archive.
  The ARCHIVE itself is opened ``mode=ro`` — the query engine can no
  more modify the world's record than the observer could (I11).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path
from dataclasses import dataclass, field

from causal_world.observer.journal import JournalView, read_only_uri

_IDENTITY_KEYS = ("seed", "regions", "agents", "ruleset_version",
                  "rng_version", "ruleset_name")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS idx_writes (
    entity TEXT NOT NULL,
    field  TEXT NOT NULL,
    tid    INTEGER NOT NULL,
    tick   INTEGER NOT NULL,
    delta  REAL,
    old,
    new
);
CREATE INDEX IF NOT EXISTS idx_writes_ef ON idx_writes(entity, field, tick);
CREATE INDEX IF NOT EXISTS idx_writes_tid ON idx_writes(tid);
CREATE INDEX IF NOT EXISTS idx_writes_field ON idx_writes(field, tick);

CREATE TABLE IF NOT EXISTS idx_reads (
    source_tid INTEGER NOT NULL,
    reader_tid INTEGER NOT NULL,
    entity TEXT NOT NULL,
    field  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reads_src ON idx_reads(source_tid);
CREATE INDEX IF NOT EXISTS idx_reads_reader ON idx_reads(reader_tid);

CREATE TABLE IF NOT EXISTS idx_entity (
    entity TEXT NOT NULL,
    tid    INTEGER NOT NULL,
    tick   INTEGER NOT NULL,
    role   TEXT NOT NULL,
    PRIMARY KEY (entity, tid, role)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_entity_tick ON idx_entity(entity, tick);

CREATE TABLE IF NOT EXISTS qmeta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;
"""


@dataclass
class IndexStats:
    last_tid: int = 0
    transitions: int = 0
    idx_writes: int = 0
    idx_reads: int = 0
    idx_entity: int = 0
    build_seconds: float = 0.0
    incremental: bool = False
    cache_bytes: int = 0


class StaleIndexError(RuntimeError):
    """The cache was built from a different world and must be rebuilt."""


class QueryIndex:
    """Derived, persistent indexes over one recorded archive."""

    def __init__(self, view: JournalView, cache_path: str) -> None:
        self.view = view
        self.cache_path = cache_path
        # uri=True: ATTACH below takes a URI, and SQLite only honours URI
        # filenames (ATTACH included) on a connection opened with it.
        self.db = sqlite3.connect(
            Path(cache_path).resolve().as_uri(), uri=True, isolation_level=None
        )
        self.db.row_factory = sqlite3.Row
        # Derived artifact: durability is pointless, speed is not.
        self.db.execute("PRAGMA synchronous=OFF")
        self.db.execute("PRAGMA journal_mode=OFF")
        # Parameter, not string formatting: a path with quotes or a dash
        # must not change the statement.
        self.db.execute("ATTACH DATABASE ? AS arch", (read_only_uri(view.path),))
        self.db.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # identity & state
    # ------------------------------------------------------------------
    def _identity(self) -> dict[str, str]:
        # Identity is the WORLD, not the file: determinism guarantees a
        # re-run with the same identity has an identical journal prefix,
        # so a longer archive of the same world extends the cache.
        return {k: self.view.meta(k) or "" for k in _IDENTITY_KEYS}

    def _stored_identity(self) -> dict[str, str] | None:
        rows = self.db.execute(
            "SELECT value FROM qmeta WHERE key='identity'").fetchall()
        if not rows:
            return None
        import json

        return json.loads(rows[0]["value"])

    def _set_meta(self, key: str, value) -> None:
        self.db.execute(
            "INSERT INTO qmeta VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)))

    def last_indexed_tid(self) -> int:
        rows = self.db.execute(
            "SELECT value FROM qmeta WHERE key='last_tid'").fetchall()
        return int(rows[0]["value"]) if rows else 0

    def stats(self) -> IndexStats:
        s = IndexStats(last_tid=self.last_indexed_tid())
        for name in ("idx_writes", "idx_reads", "idx_entity"):
            setattr(s, name, int(self.db.execute(
                f"SELECT COUNT(*) FROM {name}").fetchone()[0]))
        s.transitions = int(self.db.execute(
            "SELECT COUNT(*) FROM arch.transitions").fetchone()[0])
        if os.path.exists(self.cache_path):
            s.cache_bytes = os.path.getsize(self.cache_path)
        return s

    def content_hash(self) -> str:
        """Order-independent hash of the index CONTENT (determinism)."""
        h = hashlib.sha256()
        for table, cols in (
                ("idx_writes", "entity, field, tid, tick, delta, old, new"),
                ("idx_reads", "source_tid, reader_tid, entity, field"),
                ("idx_entity", "entity, tid, tick, role")):
            h.update(f"## {table}\n".encode())
            cur = self.db.execute(f"SELECT {cols} FROM {table} "
                                  f"ORDER BY 1, 2, 3, 4")
            while True:
                rows = cur.fetchmany(5000)
                if not rows:
                    break
                for r in rows:
                    h.update(repr(tuple(r)).encode())
                    h.update(b"\x1f")
        return h.hexdigest()

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------
    def build(self, progress=None, force: bool = False,
              include_reads: bool = True,
              include_entity: bool = True) -> IndexStats:
        """Build or incrementally extend the indexes. One SQLite pass.

        ``include_reads`` / ``include_entity`` default to True (full
        index). The read index is by far the largest — one row per
        sourced StateRead, ~50x the transition count in dense worlds —
        and is ONLY needed for causal closures (``caused_by`` /
        ``caused`` / ``trace``). Write-level queries (budget,
        delta_profile, entropy-by-value, writers) need only idx_writes.
        Building a writes-only index is the lazy-index principle: pay
        for the provenance you actually query.
        """
        import json

        t0 = time.time()
        stored = self._stored_identity()
        ident = self._identity()
        incremental = False
        if force or (stored is not None and stored != ident):
            # different world (or forced): wipe and rebuild from zero
            self.db.executescript(
                "DELETE FROM idx_writes; DELETE FROM idx_reads; "
                "DELETE FROM idx_entity; DELETE FROM qmeta;")
            self._set_meta("identity", json.dumps(ident, sort_keys=True))
        else:
            if stored is None:
                self._set_meta("identity", json.dumps(ident, sort_keys=True))
            incremental = self.last_indexed_tid() > 0

        last = self.last_indexed_tid()
        max_id = int(self.db.execute(
            "SELECT COALESCE(MAX(id), 0) FROM arch.transitions").fetchone()[0])
        if last >= max_id and not force:
            st = self.stats()
            st.build_seconds = time.time() - t0
            st.incremental = incremental
            return st

        cur = self.db.cursor()
        cur.execute("BEGIN")

        def run(sql: str) -> None:
            cur.execute(sql, (last,))
            if progress:
                progress(cur.rowcount)

        # (system, operation) lookups use the archive's own index
        # idx_transitions_op_status via the attached read-only DB.

        run("""
        INSERT INTO idx_writes(entity, field, tid, tick, delta, old, new)
        SELECT json_extract(w.value, '$[0]'),
               json_extract(w.value, '$[1]'),
               t.id, t.tick,
               CASE WHEN json_type(w.value, '$[2]') IN ('integer','real')
                     AND json_type(w.value, '$[3]') IN ('integer','real')
                    THEN json_extract(w.value, '$[3]')
                       - json_extract(w.value, '$[2]')
               END,
               json_extract(w.value, '$[2]'),
               json_extract(w.value, '$[3]')
        FROM arch.transitions t, json_each(t.payload, '$.writes') w
        WHERE t.id > ?
        """)
        if include_reads:
            run("""
            INSERT INTO idx_reads(source_tid, reader_tid, entity, field)
            SELECT json_extract(r.value, '$[3]'), t.id,
                   json_extract(r.value, '$[0]'), json_extract(r.value, '$[1]')
            FROM arch.transitions t, json_each(t.payload, '$.reads') r
            WHERE t.id > ? AND json_type(r.value, '$[3]') = 'integer'
            """)
        if include_entity:
            run("""
            INSERT OR IGNORE INTO idx_entity(entity, tid, tick, role)
            SELECT DISTINCT json_extract(w.value, '$[0]'), t.id, t.tick,
                   'writer'
            FROM arch.transitions t, json_each(t.payload, '$.writes') w
            WHERE t.id > ?
            """)
            run("""
            INSERT OR IGNORE INTO idx_entity(entity, tid, tick, role)
            SELECT DISTINCT json_extract(r.value, '$[0]'), t.id, t.tick,
                   'reader'
            FROM arch.transitions t, json_each(t.payload, '$.reads') r
            WHERE t.id > ?
            """)

        self._set_meta("last_tid", max_id)
        cur.execute("COMMIT")
        self.db.execute("ANALYZE main")

        st = self.stats()
        st.build_seconds = time.time() - t0
        st.incremental = incremental
        return st

    # ------------------------------------------------------------------
    # low-level access (used by CausalQuery)
    # ------------------------------------------------------------------
    def sql(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.db.execute(query, params)

    def hydrate(self, tids) -> list:
        """Full kernel Transitions for the given ids, in id order."""
        from causal_world.simulation.archive import _transition_from_row

        tids = sorted(tids)
        out = []
        for i in range(0, len(tids), 400):
            chunk = tids[i:i + 400]
            marks = ",".join("?" for _ in chunk)
            rows = self.db.execute(
                f"SELECT * FROM arch.transitions WHERE id IN ({marks}) "
                f"ORDER BY id", chunk).fetchall()
            out.extend(_transition_from_row(r) for r in rows)
        return out

    def close(self) -> None:
        try:
            self.db.execute("DETACH DATABASE arch")
        except sqlite3.Error:
            pass
        self.db.close()

    def __enter__(self) -> "QueryIndex":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
