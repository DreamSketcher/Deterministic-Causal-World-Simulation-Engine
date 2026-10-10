"""Tests for the v0.4 observer layers (L1-L4).

Everything here runs on SMALL in-memory worlds (fast, deterministic) and
on tiny persisted archives (to exercise the read-only JournalView and the
SQL budget path). The observer must never modify the archive it reads.
"""

from __future__ import annotations

import hashlib
import os

import pytest

from causal_world import create_world
from causal_world.kernel.transition import (
    StateChange,
    Transition,
    TransitionStatus,
)
from causal_world.world.rules import get_ruleset


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _mk_transition(tid, tick, system, operation, writes, status=TransitionStatus.COMMITTED):
    return Transition(
        id=tid,
        tick=tick,
        system=system,
        operation=operation,
        reads=[],
        writes=writes,
        random_draws=[],
        priority=0,
        status=status,
    )


# ----------------------------------------------------------------------
# L1: CausalBudget
# ----------------------------------------------------------------------

def test_budget_splits_inflows_outflows_and_net():
    from causal_world.observer.budget import CausalBudget

    journal = [
        _mk_transition(1, 0, "Agri", "harvest",
                       [StateChange("region:0", "soil", 0.5, 0.4991)]),
        _mk_transition(2, 1, "Agri", "harvest",
                       [StateChange("region:0", "soil", 0.4991, 0.4982)]),
        _mk_transition(3, 1, "Agri", "compost",
                       [StateChange("region:0", "soil", 0.4982, 0.5)]),
        # a REJECTED transition must be ignored
        _mk_transition(4, 2, "Agri", "harvest",
                       [StateChange("region:0", "soil", 0.5, 0.0)],
                       status=TransitionStatus.REJECTED),
        # non-numeric write is skipped
        _mk_transition(5, 2, "Agent", "move",
                       [StateChange("agent:0", "region", "region:0",
                                    "region:1")]),
    ]
    report = CausalBudget(journal).analyze("region:0", "soil")
    assert report.net == pytest.approx(0.0, abs=1e-12)
    assert [f"{e.system}.{e.operation}" for e in report.inflows] == [
        "Agri.compost"]
    assert [f"{e.system}.{e.operation}" for e in report.outflows] == [
        "Agri.harvest"]
    assert report.outflows[0].count == 2
    assert report.outflows[0].total_delta == pytest.approx(-0.0018)
    assert report.outflows[0].mean_delta == pytest.approx(-0.0009)
    assert report.dominant_inflow() == "compost"
    assert report.dominant_outflow() == "harvest"


def test_budget_is_deterministic():
    from causal_world.observer.budget import CausalBudget

    journal = [
        _mk_transition(i, i, "Agri", "harvest",
                       [StateChange("region:0", "soil", 0.5, 0.499)])
        for i in range(1, 6)
    ]
    a = CausalBudget(list(journal)).analyze("region:0", "soil")
    b = CausalBudget(list(journal)).analyze("region:0", "soil")
    assert a == b


def test_budget_on_real_world_shows_soil_outflow():
    """In the default world soil only ever degrades: net < 0, no inflow."""
    from causal_world.observer.budget import CausalBudget

    sim = create_world(seed=7, regions=2, agents=10, ticks=30)
    report = CausalBudget(sim.journal).analyze("region:0", "soil_fertility")
    assert report.net < 0
    assert report.inflows == ()
    assert report.dominant_outflow() is not None


def test_budget_respects_tick_window():
    from causal_world.observer.budget import CausalBudget

    journal = [
        _mk_transition(1, 0, "S", "op",
                       [StateChange("region:0", "soil", 0.5, 0.4)]),
        _mk_transition(2, 10, "S", "op",
                       [StateChange("region:0", "soil", 0.4, 0.35)]),
    ]
    budget = CausalBudget(journal)
    early = budget.analyze("region:0", "soil", 0, 5)
    assert early.net == pytest.approx(-0.1)
    late = budget.analyze("region:0", "soil", 6, 20)
    assert late.net == pytest.approx(-0.05)


# ----------------------------------------------------------------------
# JournalView: read-only over a persisted archive
# ----------------------------------------------------------------------

@pytest.fixture()
def small_archive(tmp_path):
    db = str(tmp_path / "world.db")
    sim = create_world(seed=7, regions=2, agents=10, ticks=250,
                       ruleset=get_ruleset("immune"), persist=db)
    sim.journal.close()  # commits the journal transaction (observer needs it)
    return db


def test_journal_view_is_read_only(small_archive):
    from causal_world.observer.journal import JournalView

    before = _file_hash(small_archive)
    with JournalView(small_archive) as view:
        total, committed, rejected = view.counts()
        assert total == committed + rejected
        assert committed > 0
        lo, hi = view.tick_range()
        assert lo == 0 and hi >= 20
        # read-only enforcement: any write must fail
        import sqlite3

        with pytest.raises(sqlite3.OperationalError):
            view.query("INSERT INTO meta VALUES ('x', 'y')")
    # The db file (and its WAL checkpoint state) must be unchanged in
    # content: reopen as a fresh read-only view and re-hash the pages.
    after = _file_hash(small_archive)
    assert before == after


def test_budget_sql_path_matches_python_path(small_archive):
    from causal_world.observer.budget import CausalBudget
    from causal_world.observer.journal import JournalView

    with JournalView(small_archive) as view:
        sql_report = CausalBudget(view).analyze("region:0", "soil_fertility")
        py_report = CausalBudget(list(view.committed())).analyze(
            "region:0", "soil_fertility")
    assert sql_report.net == pytest.approx(py_report.net, abs=1e-12)
    assert [ (e.system, e.operation, e.count) for e in sql_report.outflows ] == \
           [ (e.system, e.operation, e.count) for e in py_report.outflows ]


# ----------------------------------------------------------------------
# L2: RegimeClassifier
# ----------------------------------------------------------------------

def _population_series_from(points):
    """Build a synthetic series object with the shape the classifier uses."""
    from causal_world.observer.series import TimeSeries

    s = TimeSeries(sample_every=1)
    s.population = list(points)
    s.total_agents = points[0][1]
    s.last_tick = points[-1][0]
    return s


class _StubJournal:
    """Minimal journal stand-in: no deaths, no query()."""

    def __iter__(self):
        return iter([])


def test_classifier_detects_collapse():
    from causal_world.observer.regime import RegimeClassifier, RegimeType

    series = _population_series_from(
        [(t, max(0, 100 - t)) for t in range(0, 120)])
    report = RegimeClassifier(_StubJournal(), series=series).classify()
    assert report.type is RegimeType.COLLAPSE


def test_classifier_detects_equilibrium():
    from causal_world.observer.regime import RegimeClassifier, RegimeType

    pts = [(t, 100 if t < 20 else 95) for t in range(0, 120)]
    series = _population_series_from(pts)
    report = RegimeClassifier(_StubJournal(), series=series).classify()
    assert report.type is RegimeType.EQUILIBRIUM
    assert report.equilibrium_population == pytest.approx(95)


def test_classifier_detects_oscillation_not_trend():
    from causal_world.observer.regime import RegimeClassifier, RegimeType
    import math

    period = 40
    pts = [(t, 100 + 30 * math.sin(2 * math.pi * t / period))
           for t in range(0, 400)]
    series = _population_series_from(pts)
    report = RegimeClassifier(_StubJournal(), series=series).classify()
    assert report.type is RegimeType.OSCILLATION
    assert report.oscillation_period is not None
    assert abs(report.oscillation_period - period) <= 5

    # a pure monotone decline must NOT register as oscillation
    decline = _population_series_from(
        [(t, int(200 - 0.4 * t)) for t in range(0, 400)])
    rep2 = RegimeClassifier(_StubJournal(), series=decline).classify()
    assert rep2.type is not RegimeType.OSCILLATION


def test_classifier_on_real_collapse_world(small_archive):
    """The immune world at this scale collapses: classifier must agree."""
    from causal_world.observer.journal import JournalView
    from causal_world.observer.regime import RegimeClassifier, RegimeType

    with JournalView(small_archive) as view:
        report = RegimeClassifier(view, sample_every=1,
                                  total_agents=10).classify()
    assert report.type is RegimeType.COLLAPSE
    assert report.extinction_tick is not None
    assert report.soil_trajectory in ("monotonic_decline", "convergent",
                                      "recovering", "unknown")


def test_classifier_never_reads_ruleset_meta(small_archive):
    """The regime classifier must classify from the journal alone."""
    from causal_world.observer.journal import JournalView
    from causal_world.observer.regime import RegimeClassifier

    class NoMetaView:
        """JournalView that explodes if anyone asks for meta."""

        def __init__(self, inner):
            self._inner = inner

        def meta(self, *_a):
            raise AssertionError("classifier read ruleset meta")

        def meta_all(self):
            raise AssertionError("classifier read ruleset meta")

        def __getattr__(self, item):
            return getattr(self._inner, item)

    with JournalView(small_archive) as view:
        report = RegimeClassifier(NoMetaView(view), sample_every=1,
                                  total_agents=10).classify()
    assert report.type.value == "collapse"


# ----------------------------------------------------------------------
# L3: CausalComparator
# ----------------------------------------------------------------------

def test_comparator_finds_missing_inflow():
    from causal_world.observer.compare import CausalComparator

    # Regime A: soil only degrades. Regime B: degradation + compost inflow.
    a = [
        _mk_transition(i, i, "Agri", "harvest",
                       [StateChange("region:0", "soil", 0.5, 0.4991)])
        for i in range(1, 11)
    ]
    b = []
    for i in range(1, 11):
        b.append(_mk_transition(i, i, "Agri", "harvest",
                                [StateChange("region:0", "soil", 0.5, 0.4991)]))
        b.append(_mk_transition(100 + i, i, "Agri", "compost",
                                [StateChange("region:0", "soil", 0.4991, 0.5)]))

    cmp = CausalComparator(a, b, name_a="collapse", name_b="compost")
    diff = cmp.compare_field("region:0", "soil")
    assert "Agri.compost" in diff.missing_inflows
    assert diff.missing_outflows == []
    assert diff.budget_deltas["soil"] > 0
    assert "compost" in diff.causal_loop_diff


def test_migration_stats_entropy():
    from causal_world.observer.compare import migration_stats

    # all moves to one region -> entropy 0
    herd = [
        _mk_transition(i, i, "Agent", "agent.migrate",
                       [StateChange(f"agent:{i}", "region", "region:0",
                                    "region:1")])
        for i in range(4)
    ]
    stats = migration_stats(herd)
    assert stats["moves"] == 4
    assert stats["entropy_bits"] == pytest.approx(0.0)
    assert stats["top_destination"] == "region:1"

    # split evenly across two destinations -> entropy 1 bit
    split = [
        _mk_transition(1, 0, "Agent", "agent.migrate",
                       [StateChange("agent:0", "region", "region:0",
                                    "region:1")]),
        _mk_transition(2, 0, "Agent", "agent.migrate",
                       [StateChange("agent:1", "region", "region:0",
                                    "region:2")]),
    ]
    assert migration_stats(split)["entropy_bits"] == pytest.approx(1.0)


# ----------------------------------------------------------------------
# L4: NarrativeCompressor
# ----------------------------------------------------------------------

def test_narrative_explains_death_or_reports_alive(small_archive):
    from causal_world.observer.compress import NarrativeCompressor
    from causal_world.observer.journal import JournalView

    with JournalView(small_archive) as view:
        compressor = NarrativeCompressor()
        # find a deceased agent, else use a live one
        dead_agent = None
        for t in view.committed():
            if t.operation == "agent.death":
                for w in t.writes:
                    if w.entity.startswith("agent:") and w.field == "alive":
                        dead_agent = w.entity
                        break
            if dead_agent:
                break
        if dead_agent:
            text = compressor.explain_death(dead_agent, view, depth=6)
            assert dead_agent in f"{text}" or "agent.death" in text
            assert "t" in text
        # a certainly-alive agent
        alive_text = compressor.explain_death("agent:does-not-exist", view)
        assert "alive" in alive_text


def test_narrative_llm_hook_is_used_when_provided(small_archive):
    from causal_world.observer.compress import NarrativeCompressor
    from causal_world.observer.journal import JournalView

    class FakeLLM:
        def compress(self, structured):
            return f"LLM saw {len(structured)} steps"

    with JournalView(small_archive) as view:
        dead_agent = None
        for t in view.committed():
            if t.operation == "agent.death":
                dead_agent = next(w.entity for w in t.writes
                                  if w.field == "alive")
                break
        if dead_agent is None:
            pytest.skip("no deaths in this small world")
        compressor = NarrativeCompressor(llm=FakeLLM())
        out = compressor.explain_death(dead_agent, view, depth=4)
        assert out.startswith("LLM saw")
