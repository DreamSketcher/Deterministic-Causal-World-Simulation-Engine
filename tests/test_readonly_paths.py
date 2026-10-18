"""Archive opens must work on any path and stay read-only.

Regression for "unable to open database: file:...?mode=ro" (autopsy on
Windows). The URI is built by ``read_only_uri`` (``Path.as_uri``), so spaces,
the em dash, ``#`` and ``?`` in a directory name must not change how SQLite
reads the path, and the query index's ATTACH must stay read-only.
"""

from __future__ import annotations

import sqlite3

import pytest

from causal_world.observer.journal import JournalView, read_only_uri
from causal_world.query.index import QueryIndex
from causal_world.server.dispatch import Dispatcher

HELLO = {"type": "hello", "protocol": "causal-world-jsonl/1", "seed": 7,
         "ruleset": "player_resettle", "regions": 2, "agents": 54, "max_ticks": 200}

ODD_DIRS = ["Causal World \u2014 slice", "a#b?c", "plain"]


@pytest.fixture(params=ODD_DIRS)
def archive(tmp_path, request):
    db_dir = tmp_path / request.param / "worlds"
    dispatcher = Dispatcher({}, str(db_dir))
    conn: dict = {"session": None}
    dispatcher.handle(HELLO, conn)
    for seq in range(1, 4):
        dispatcher.handle({"type": "decide", "seq": seq, "action": 0}, conn)
    path = conn["session"].db_path
    return path


def test_read_only_uri_is_a_file_uri_with_mode_ro(tmp_path):
    uri = read_only_uri(str(tmp_path / "x y \u2014 z#.db"))
    assert uri.startswith("file:")
    assert uri.endswith("?mode=ro")
    assert "#" not in uri.split("?")[0] and " " not in uri


def test_journal_view_reads_and_refuses_writes(archive):
    with JournalView(archive) as view:
        total, _, _ = view.counts()
        assert total > 0
        with pytest.raises(sqlite3.OperationalError):
            view._conn.execute("DELETE FROM transitions")


def test_query_index_attaches_read_only(archive, tmp_path):
    cache = str(tmp_path / "cache \u2014 index.db")
    with JournalView(archive) as view, QueryIndex(view, cache) as idx:
        # the archive is reachable through ATTACH ...
        assert idx.db.execute("SELECT COUNT(*) FROM arch.transitions").fetchone()[0] > 0
        # ... and not writable through it
        with pytest.raises(sqlite3.OperationalError):
            idx.db.execute("DELETE FROM arch.transitions")
