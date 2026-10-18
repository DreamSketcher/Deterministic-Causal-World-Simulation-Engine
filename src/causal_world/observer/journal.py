"""JournalView: a STRICTLY READ-ONLY window onto a recorded archive.

The observer layer (invariant I11) may derive anything from the journal
but must never modify it. This class enforces that at the connection
level: the SQLite database is opened with ``mode=ro``, so ANY accidental
write raises ``sqlite3.OperationalError`` instead of silently touching
the world's record.

A JournalView exposes the same iteration vocabulary the in-memory journal
and the archive use (``__iter__``, ``by_id``, ``meta``, ``query``), so
every observer layer works over recorded runs without re-running them.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator

from causal_world.kernel.transition import Transition, TransitionStatus
from causal_world.simulation.archive import _transition_from_row


def read_only_uri(path: str) -> str:
    """SQLite URI that opens ``path`` with ``mode=ro``, for any path.

    Built with ``Path.as_uri()`` so spaces, non-ASCII characters (e.g. the
    em dash in ``Causal World — slice``) and Windows drive letters are
    percent-encoded correctly. A hand-written ``file:{path}?mode=ro`` is
    not: SQLite refuses it on Windows ("unable to open database").
    """
    return Path(path).resolve().as_uri() + "?mode=ro"


class JournalView:
    """Read-only journal over a SqliteArchive file."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn = sqlite3.connect(read_only_uri(path), uri=True)
        self._conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------
    # meta
    # ------------------------------------------------------------------
    def meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def meta_all(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM meta").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def tick_range(self) -> tuple[int, int]:
        row = self._conn.execute(
            "SELECT COALESCE(MIN(tick), 0) AS lo, COALESCE(MAX(tick), 0) AS hi "
            "FROM transitions"
        ).fetchone()
        return int(row["lo"]), int(row["hi"])

    def counts(self) -> tuple[int, int, int]:
        total = int(
            self._conn.execute("SELECT COUNT(*) AS n FROM transitions")
            .fetchone()["n"]
        )
        committed = int(
            self._conn.execute(
                "SELECT COUNT(*) AS n FROM transitions WHERE status='COMMITTED'"
            ).fetchone()["n"]
        )
        return total, committed, total - committed

    # ------------------------------------------------------------------
    # transition access
    # ------------------------------------------------------------------
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

    def since(self, transition_id: int) -> Iterator[Transition]:
        """Transitions with id > ``transition_id`` in id order (read-only).

        Used to read one decision's records after the journal was closed:
        the archive file is still there, the writer is not.
        """
        cursor = self._conn.execute(
            "SELECT * FROM transitions WHERE id > ? ORDER BY id",
            (transition_id,),
        )
        while True:
            rows = cursor.fetchmany(500)
            if not rows:
                break
            for row in rows:
                yield _transition_from_row(row)

    def by_id(self, transition_id: int) -> Transition:
        row = self._conn.execute(
            "SELECT * FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no transition T{transition_id} in journal")
        return _transition_from_row(row)

    def get_transition(self, transition_id: int) -> Transition | None:
        """Point lookup by primary key; None when absent (v0.5 API)."""
        row = self._conn.execute(
            "SELECT * FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        return _transition_from_row(row) if row is not None else None

    def iter_batches(self, batch_size: int = 10000) -> Iterator[list]:
        """Streaming pass over the journal in id order (never materializes
        the whole journal; a 16 GB archive iterates in constant memory)."""
        cursor = self._conn.execute("SELECT * FROM transitions ORDER BY id")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield [_transition_from_row(row) for row in rows]

    def has(self, transition_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        return row is not None

    def at_tick(self, tick: int) -> list[Transition]:
        """All transitions of one tick, id order (uses the tick index when
        the archive was written by a 2d-or-later kernel)."""
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE tick=? ORDER BY id", (tick,)
        ).fetchall()
        return [_transition_from_row(row) for row in rows]

    def writes_at_tick(self, tick: int) -> list[tuple[int, str, str, object]]:
        """Committed writes of one tick, as a list (see the archive)."""
        return list(self.iter_writes_at_tick(tick))

    def iter_writes_at_tick(self, tick: int, after_id: int = 0):
        """The read-only twin of ``SqliteArchive.iter_writes_at_tick``."""
        rows = self._conn.execute(
            "SELECT id, payload FROM transitions "
            "WHERE tick=? AND status='COMMITTED' AND id>? ORDER BY id",
            (tick, after_id),
        )
        for row in rows:
            for entity, field_name, _old, new in json.loads(row["payload"])["writes"]:
                yield (row["id"], entity, field_name, new)

    def max_id_through_tick(self, tick: int) -> int:
        """The read-only twin of ``SqliteArchive.max_id_through_tick``."""
        row = self._conn.execute(
            "SELECT COALESCE(MAX(id), 0) FROM transitions WHERE tick<=?",
            (tick,),
        ).fetchone()
        return int(row[0])

    def between_ticks(self, lo: int, hi: int) -> list[Transition]:
        """Transitions of ticks ``lo..hi`` inclusive, id order."""
        rows = self._conn.execute(
            "SELECT * FROM transitions WHERE tick BETWEEN ? AND ? ORDER BY id",
            (lo, hi),
        ).fetchall()
        return [_transition_from_row(row) for row in rows]

    def transitions_for_entity(self, entity: str, status: str = "COMMITTED"):
        """Transitions whose writes touch ``entity``, id order.

        COMMITTED is answered by the derived ``history`` index; other
        statuses scan, since the index holds committed writes only.
        """
        if status == "COMMITTED":
            rows = self._conn.execute(
                "SELECT * FROM transitions WHERE status='COMMITTED' "
                "AND id IN (SELECT tid FROM history WHERE entity=?) "
                "ORDER BY id",
                (entity,),
            ).fetchall()
            for row in rows:
                yield _transition_from_row(row)
            return
        wanted = TransitionStatus[status]
        for t in self:
            if t.status is wanted and any(w.entity == entity for w in t.writes):
                yield t

    def transitions_for_field(self, entity: str, field_name: str,
                              status: str = "COMMITTED"):
        """Transitions that write one field of one entity, id order."""
        if status == "COMMITTED":
            rows = self._conn.execute(
                "SELECT * FROM transitions WHERE status='COMMITTED' "
                "AND id IN (SELECT tid FROM history "
                "           WHERE entity=? AND field=?) ORDER BY id",
                (entity, field_name),
            ).fetchall()
            for row in rows:
                yield _transition_from_row(row)
            return
        wanted = TransitionStatus[status]
        for t in self:
            if (t.status is wanted
                    and any(w.entity == entity and w.field == field_name
                            for w in t.writes)):
                yield t

    def history_of(self, entity: str, field_name: str) -> list[int]:
        rows = self._conn.execute(
            "SELECT tid FROM history WHERE entity=? AND field=? ORDER BY tid",
            (entity, field_name),
        ).fetchall()
        return [row["tid"] for row in rows]

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Read-only SQL escape hatch (the connection itself is mode=ro)."""
        return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "JournalView":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
