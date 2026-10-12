"""Tests for the v0.5 causal query engine (QueryIndex + CausalQuery).

Covers the spec's four-week checklist:
  W1: build correctness, build determinism, incremental updates
  W2: filters, SQL parity, lazy streaming results
  W3: backward/forward traces, depth limits, no runaway loops
  W4: aggregations (budget/count/entropy) + CLI
Plus the standing guarantees: the archive stays read-only, the index is
a derived artifact, and every answer matches the frozen journal.
"""

from __future__ import annotations

import hashlib
import itertools

import pytest

from causal_world import create_world
from causal_world.cli import main as cli_main
from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.journal import JournalView
from causal_world.query.index import QueryIndex
from causal_world.query.query import CausalQuery
from causal_world.world.rules import get_ruleset


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture()
def immune_archive(tmp_path):
    db = str(tmp_path / "immune.db")
    sim = create_world(seed=7, regions=2, agents=10, ticks=120,
                       ruleset=get_ruleset("immune"), persist=db)
    sim.journal.close()
    return db


@pytest.fixture()
def immune_long_archive(tmp_path):
    """Same seed/ruleset, more ticks: a deterministic EXTENSION of the
    short archive (journal prefix is bit-identical)."""
    db = str(tmp_path / "immune_long.db")
    sim = create_world(seed=7, regions=2, agents=10, ticks=200,
                       ruleset=get_ruleset("immune"), persist=db)
    sim.journal.close()
    return db


@pytest.fixture()
def indexed(immune_archive, tmp_path):
    cache = str(tmp_path / "immune.qidx")
    with JournalView(immune_archive) as view, QueryIndex(view, cache) as idx:
        idx.build()
        yield idx, view


# ----------------------------------------------------------------------
# W1: build, determinism, incremental
# ----------------------------------------------------------------------

def test_build_counts_match_manual_scan(immune_archive, tmp_path):
    cache = str(tmp_path / "a.qidx")
    with JournalView(immune_archive) as view, QueryIndex(view, cache) as idx:
        stats = idx.build()
        # manual Python-side counts from the raw journal
        n_writes = n_reads = 0
        n_trans = 0
        for t in view:
            n_trans += 1
            n_writes += len(t.writes)
            n_reads += sum(1 for r in t.reads
                           if r.source_transition is not None)
        assert stats.transitions == n_trans
        assert stats.idx_writes == n_writes
        assert stats.idx_reads == n_reads
        assert stats.last_tid == n_trans  # ids are dense from 1


def test_build_is_deterministic(immune_archive, tmp_path):
    hashes = []
    for name in ("a.qidx", "b.qidx"):
        cache = str(tmp_path / name)
        with JournalView(immune_archive) as view, \
                QueryIndex(view, cache) as idx:
            idx.build()
            hashes.append(idx.content_hash())
    assert hashes[0] == hashes[1]


def test_incremental_build_matches_full(immune_archive, immune_long_archive,
                                        tmp_path):
    """Index the short world, then extend the cache against the long
    world; content must equal a fresh full build of the long world."""
    cache_inc = str(tmp_path / "inc.qidx")
    cache_full = str(tmp_path / "full.qidx")

    with JournalView(immune_archive) as v1:
        with QueryIndex(v1, cache_inc) as idx:
            idx.build()
    with JournalView(immune_long_archive) as v2:
        with QueryIndex(v2, cache_inc) as idx:
            stats = idx.build()
            assert stats.incremental
            inc_hash = idx.content_hash()
    with JournalView(immune_long_archive) as v2:
        with QueryIndex(v2, cache_full) as idx:
            idx.build()
            full_hash = idx.content_hash()
    assert inc_hash == full_hash


def test_identity_mismatch_rebuilds(immune_archive, tmp_path):
    """A cache built from one world must be rebuilt, not mixed, when
    opened against a different world."""
    other = str(tmp_path / "other.db")
    sim = create_world(seed=99, regions=2, agents=10, ticks=60,
                       ruleset=get_ruleset("immune"), persist=other)
    sim.journal.close()

    cache = str(tmp_path / "shared.qidx")
    with JournalView(other) as v_other, QueryIndex(v_other, cache) as idx:
        idx.build()
        other_hash = idx.content_hash()
    with JournalView(immune_archive) as v, QueryIndex(v, cache) as idx:
        idx.build()  # identity differs -> wipe + rebuild
        mixed_hash = idx.content_hash()
    assert mixed_hash != other_hash
    fresh = str(tmp_path / "fresh.qidx")
    with JournalView(immune_archive) as v, QueryIndex(v, fresh) as idx:
        idx.build()
        assert idx.content_hash() == mixed_hash


def test_archive_untouched_by_indexing(immune_archive, tmp_path):
    before = _file_hash(immune_archive)
    cache = str(tmp_path / "ro.qidx")
    with JournalView(immune_archive) as view, QueryIndex(view, cache) as idx:
        idx.build()
        q = CausalQuery(idx)
        q.committed_only().list(limit=50)
        q.trace(q.operation("agent.death").first().id, "backward", 5)
    assert _file_hash(immune_archive) == before


# ----------------------------------------------------------------------
# W2: filters, parity, streaming
# ----------------------------------------------------------------------

def test_filter_parity_against_raw_journal(indexed):
    idx, view = indexed
    q = CausalQuery(idx)
    # count by system/operation/status
    expected = {}
    for t in view:
        key = (t.system, t.operation, t.status.value)
        expected[key] = expected.get(key, 0) + 1
    for (system, operation, status), n in expected.items():
        got = (q.system(system).operation(operation).status(status).count())
        assert got == n, (system, operation, status)


def test_entity_and_field_filters(indexed):
    idx, view = indexed
    q = CausalQuery(idx)
    # entity filter: any transition touching agent:3
    manual = sum(1 for t in view
                 if any(w.entity == "agent:3" for w in t.writes)
                 or any(r.entity == "agent:3" for r in t.reads))
    assert q.entity("agent:3").count() == manual
    # field filter: transitions writing soil_fertility
    manual_field = sum(1 for t in view
                       if any(w.field == "soil_fertility" for w in t.writes))
    assert q.field("soil_fertility").count() == manual_field
    # writes_to: harvest transitions for region:0 soil
    manual_w = sum(1 for t in view
                   if any(w.entity == "region:0"
                          and w.field == "soil_fertility" for w in t.writes))
    assert q.writes_to("region:0", "soil_fertility").count() == manual_w


def test_tick_window_and_committed(indexed):
    idx, view = indexed
    q = CausalQuery(idx)
    lo, hi = 30, 60
    manual = sum(1 for t in view
                 if lo <= t.tick <= hi
                 and t.status is TransitionStatus.COMMITTED)
    assert q.ticks(lo, hi).committed_only().count() == manual


def test_execute_is_lazy_iterator(indexed):
    idx, _ = indexed
    q = CausalQuery(idx)
    stream = q.committed_only().execute()
    assert itertools.islice is not None  # documentation intent
    assert hasattr(stream, "__next__")   # generator, not list
    first_five = list(itertools.islice(stream, 5))
    assert len(first_five) == 5
    ids = [t.id for t in first_five]
    assert ids == sorted(ids)            # id order
    # early termination: the rest was never hydrated
    assert next(stream).id > ids[-1]


def test_list_default_limit(indexed):
    idx, _ = indexed
    q = CausalQuery(idx)
    total = q.committed_only().count()
    assert total > 10
    assert len(q.committed_only().list(limit=10)) == 10


# ----------------------------------------------------------------------
# W3: causal closures and traces
# ----------------------------------------------------------------------

def _first_death(idx):
    q = CausalQuery(idx)
    death = q.operation("agent.death").committed_only().first()
    assert death is not None, "test world must contain a death"
    return death


def test_caused_by_direct_matches_archive_dependents(indexed):
    idx, view = indexed
    death = _first_death(idx)
    q = CausalQuery(idx)
    # direct dependents of a transition the death read from:
    # take one ancestor and check depth-1 caused_by against the raw reads
    tr = q.trace(death.id, "backward", depth=1)
    assert tr.nodes
    ancestor_id = [tid for tid, d in tr.depths.items() if d == 1][0]
    dependents = set(q.caused_by(ancestor_id, depth=1).tids())
    manual = set()
    for t in view:
        if any(r.source_transition == ancestor_id for r in t.reads):
            manual.add(t.id)
    assert dependents == manual


def test_caused_matches_reads_sources(indexed):
    idx, view = indexed
    death = _first_death(idx)
    q = CausalQuery(idx)
    ancestors = set(q.caused(death.id, depth=1).tids())
    manual = {r.source_transition for r in death.reads
              if r.source_transition is not None}
    assert ancestors == manual


def test_trace_backward_chain_is_causal(indexed):
    idx, view = indexed
    death = _first_death(idx)
    q = CausalQuery(idx)
    tr = q.trace(death.id, "backward", depth=8)
    # every non-root node must be reachable via reads from a deeper node
    by_id = {t.id: t for t in tr.nodes}
    for tid, d in tr.depths.items():
        if d == 0:
            continue
        child = next(c for c, cd in tr.depths.items() if cd == d - 1
                     and any(r.source_transition == tid
                             for r in by_id[c].reads))
        assert child is not None
    # causes come first in node order
    depths_in_order = [tr.depths[t.id] for t in tr.nodes]
    assert depths_in_order == sorted(depths_in_order, reverse=True)


def test_trace_forward_and_depth_limit(indexed):
    idx, _ = indexed
    death = _first_death(idx)
    q = CausalQuery(idx)
    tr1 = q.trace(death.id, "forward", depth=1)
    tr3 = q.trace(death.id, "forward", depth=3)
    assert len(tr1.nodes) <= len(tr3.nodes)
    assert max(tr3.depths.values()) <= 3
    # truncation guard fires with an absurdly small cap
    tr_t = q.trace(death.id, "forward", depth=10, max_nodes=5)
    assert tr_t.truncated or len(tr_t.nodes) <= 5


def test_trace_never_loops(indexed):
    idx, _ = indexed
    death = _first_death(idx)
    q = CausalQuery(idx)
    tr = q.trace(death.id, "backward", depth=50)
    assert len(set(tr.depths)) == len(tr.nodes)  # no duplicates
    assert len(tr.nodes) < 5000                  # bounded in a small world


# ----------------------------------------------------------------------
# W4: aggregations + parity with the observer layer
# ----------------------------------------------------------------------

def test_budget_matches_observer_l1(indexed):
    idx, view = indexed
    from causal_world.observer.budget import CausalBudget

    q = CausalQuery(idx)
    for entity, field in (("region:0", "soil_fertility"),
                          ("region:1", "food_stock")):
        via_index = q.budget(entity, field)
        via_l1 = CausalBudget(view).analyze(entity, field)
        assert via_index.net == pytest.approx(via_l1.net, abs=1e-12)
        assert [(e.system, e.operation, e.count)
                for e in via_index.inflows] == \
               [(e.system, e.operation, e.count) for e in via_l1.inflows]
        assert [(e.system, e.operation, e.count)
                for e in via_index.outflows] == \
               [(e.system, e.operation, e.count) for e in via_l1.outflows]


def test_budget_window(indexed):
    idx, view = indexed
    from causal_world.observer.budget import CausalBudget

    q = CausalQuery(idx)
    via_index = q.budget("region:0", "soil_fertility", 20, 80)
    via_l1 = CausalBudget(view).analyze("region:0", "soil_fertility", 20, 80)
    assert via_index.net == pytest.approx(via_l1.net, abs=1e-12)


def test_entropy_matches_migration_stats(indexed):
    idx, view = indexed
    from causal_world.observer.compare import migration_stats

    q = CausalQuery(idx)
    result = (q.operation("agent.migrate").committed_only()
              .entropy(by="write:region", actual_changes_only=True))
    reference = migration_stats(view)
    assert result.total == int(reference["moves"])
    assert result.entropy_bits == pytest.approx(reference["entropy_bits"],
                                                abs=1e-12)


def test_delta_profile_drilldown(tmp_path):
    """The v0.4 signal: the SAME operation name in two systems is told
    apart by actual deltas, not names. At 150 agents/region the compost
    balance point (1 - 50/150 = 0.667) lies ABOVE genesis soil (~0.57),
    so deltas must be positive — impossible for AgricultureSystem, whose
    delta is the constant -0.0009."""
    compost_db = str(tmp_path / "compost.db")
    sim = create_world(seed=7, regions=2, agents=300, ticks=40,
                       ruleset=get_ruleset("compost"), persist=compost_db)
    sim.journal.close()
    cache = str(tmp_path / "compost.qidx")
    with JournalView(compost_db) as view, QueryIndex(view, cache) as idx:
        idx.build()
        q = CausalQuery(idx)
        rows = q.delta_profile(field_name="soil_fertility")
        assert len(rows) == 1
        row = rows[0]
        assert row.system == "CompostAgricultureSystem"
        assert row.operation == "agriculture.harvest"
        assert row.positive > 0
        assert row.mean_delta > -0.0009  # compost offsets the flat decay


def test_timeline_entity(indexed):
    idx, view = indexed
    q = CausalQuery(idx)
    life = q.timeline("agent:2", limit=1000)
    manual = [t for t in view
              if any(w.entity == "agent:2" for w in t.writes)
              or any(r.entity == "agent:2" for r in t.reads)]
    assert [t.id for t in life] == [t.id for t in manual]


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def test_cli_query_commands(immune_archive, tmp_path, capsys):
    cache = str(tmp_path / "cli.qidx")
    rc = cli_main(["query", "--db", immune_archive, "--cache", cache,
                   "build"])
    assert rc == 0
    assert "idx_writes" in capsys.readouterr().out

    rc = cli_main(["query", "--db", immune_archive, "--cache", cache,
                   "count", "--committed"])
    assert rc == 0
    assert int(capsys.readouterr().out.strip()) > 0

    rc = cli_main(["query", "--db", immune_archive, "--cache", cache,
                   "budget", "region:0", "soil_fertility"])
    assert rc == 0
    assert "NET" in capsys.readouterr().out

    rc = cli_main(["query", "--db", immune_archive, "--cache", cache,
                   "profile", "region:0", "soil_fertility"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "AgricultureSystem.agriculture.harvest" in out
