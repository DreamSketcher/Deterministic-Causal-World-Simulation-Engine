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

import sqlite3
from typing import Iterator

from causal_world.kernel.transition import Transition, TransitionStatus
from causal_world.simulation.archive import _transition_from_row


class JournalView:
    """Read-only journal over a SqliteArchive file."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
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

    def by_id(self, transition_id: int) -> Transition:
        row = self._conn.execute(
            "SELECT * FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no transition T{transition_id} in journal")
        return _transition_from_row(row)

    def has(self, transition_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM transitions WHERE id=?", (transition_id,)
        ).fetchone()
        return row is not None

    def transitions_for_entity(self, entity: str, status: str = "COMMITTED"):
        """Committed (by default) transitions whose writes touch ``entity``."""
        for t in self:
            if t.status is not TransitionStatus[status]:
                continue
            if any(w.entity == entity for w in t.writes):
                yield t

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Read-only SQL escape hatch (the connection itself is mode=ro)."""
        return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "JournalView":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
