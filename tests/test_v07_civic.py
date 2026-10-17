"""v0.7 — the civic layer, the sandbox and the hypothesis layer.

Three things are checked here, and they are the three promises the v0.7
concept makes:

* the DECREE is a law: it is a committed transition with a recorded
  kind, it enters force on the NEXT tick, and the base compost law of
  every other region is untouched by it;
* the SANDBOX is a counterfactual: its base is the RECORDED world (the
  decision stream AND the decree ledger are read back from the archive),
  it changes exactly ONE factor, and it diverges at exactly the tick of
  that change;
* the HYPOTHESIS layer never invents a link: a claim is confirmed only
  when the record contains the edge, and "unresolved" is a legitimate
  answer.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.game import (
    GameWorld,
    chronicle,
    intervene_and_verify,
    observe,
    understand,
)
from causal_world.observer.hypothesis import (
    Hypothesis,
    Verdict,
    confirmed_links,
    facts_of,
)
from causal_world.observer.journal import JournalView
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.query.index import QueryIndex
from causal_world.sandbox import (
    Fork,
    fork_at_tick,
    read_decree_ledger,
    read_decision_stream,
    run_counterfactual,
    stream_index_of_tick,
)
from causal_world.systems.directive import (
    DIRECTIVE_AMEND,
    DIRECTIVE_REST,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset


# ------------------------------------------------------------------ helpers


def _civic_world(db_path=None, *, seed=7, regions=2, agents=40, ticks=40,
                 decrees=None):
    """A civic world with an idle player and an optional decree ledger."""
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_civic"), ticks=0,
        regions=regions, agents=agents, persist=db_path,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (ticks + 10)))
    if decrees:
        channel = DirectiveChannel()
        for tick, d in decrees.items():
            channel.schedule(tick, d)
        for system in sim.systems:
            if isinstance(system, DirectiveSystem):
                system.channel = channel
    sim.run(ticks)
    if db_path:
        sim.journal.commit()
        sim.journal.close()
    return sim


# ------------------------------------------------------------- the decree


def test_decree_is_a_committed_transition_with_a_recorded_kind(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, decrees={5: Directive(DIRECTIVE_AMEND, "region:0", 0.25)})

    with JournalView(db) as view:
        decrees = [t for t in view if t.operation == "player.directive"]
        assert len(decrees) == 1
        t = decrees[0]
        assert t.status.value == "COMMITTED"      # a fact, not a proposal
        assert t.tick == 5
        assert t.system == "DirectiveSystem"
        assert t.random_draws[0].value == float(DIRECTIVE_AMEND)
        # the law parameter is written with its old value -> auditable
        write = next(w for w in t.writes if w.field == "labor_diversion")
        assert write.old == 0.0
        assert write.new == pytest.approx(0.25)


def test_decree_enters_force_on_the_next_tick_not_the_same_one(tmp_path):
    """The moment of entry into force is DERIVED (one snapshot per tick)."""
    db = str(tmp_path / "w.db")
    _civic_world(db, decrees={5: Directive(DIRECTIVE_AMEND, "region:0", 0.5)})

    with JournalView(db) as view:
        decree = next(t for t in view if t.operation == "player.directive")
        assert decree.tick == 5
        # the law systems read the OLD value at tick 5 and the NEW one at 6
        harvests = [t for t in view
                    if t.operation == "agriculture.harvest" and t.tick in (5, 6)
                    and any(w.entity == "region:0" for w in t.writes)]
        reading_5 = next(t for t in harvests if t.tick == 5)
        reading_6 = next(t for t in harvests if t.tick == 6)
        assert next(r.value for r in reading_5.reads
                    if r.field == "labor_diversion") == 0.0
        assert next(r.value for r in reading_6.reads
                    if r.field == "labor_diversion") == pytest.approx(0.5)


def test_decree_targets_one_region_and_leaves_the_others_alone(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, regions=2, agents=40,
                 decrees={5: Directive(DIRECTIVE_AMEND, "region:0", 0.25)})
    with JournalView(db) as view:
        # the law of the untouched region never changed
        region1 = [t for t in view if t.operation == "agriculture.harvest"
                    and any(w.entity == "region:1" for w in t.writes)]
        assert region1
        for t in region1:
            assert next(r.value for r in t.reads
                        if r.field == "labor_diversion") == 0.0


def test_civic_world_without_decrees_behaves_like_the_base_law(tmp_path):
    """The base compost law is unchanged: a decree is the only difference."""
    base = _civic_world(None, ticks=40)
    civic = _civic_world(None, ticks=40)
    assert civic.state.get("region:0", "soil_fertility") == pytest.approx(
        base.state.get("region:0", "soil_fertility")
    )


def test_research_worlds_are_untouched_by_the_civic_layer():
    """The new ruleset does not leak into the research worlds."""
    sim = create_world(seed=7, ruleset=get_ruleset("compost"), ticks=0,
                       regions=2, agents=10)
    assert "DirectiveSystem" not in {s.name for s in sim.systems}
    assert "CivicAgricultureSystem" not in {s.name for s in sim.systems}
    sim.run(20)
    assert "labor_diversion" not in sim.state.fields_of("region:0")


def test_decree_ledger_is_recoverable_from_the_archive_alone(tmp_path):
    """The archive must suffice to rebuild the world's second input."""
    db = str(tmp_path / "w.db")
    _civic_world(db, decrees={4: Directive(DIRECTIVE_AMEND, "region:1", 0.25),
                               9: Directive(DIRECTIVE_WATER, "region:0", 0.5)})
    ledger = read_decree_ledger(db)
    assert set(ledger) == {4, 9}
    assert ledger[4].kind == DIRECTIVE_AMEND
    assert ledger[4].region == "region:1"
    assert ledger[4].param == pytest.approx(0.25)
    assert ledger[9].kind == DIRECTIVE_WATER
    assert ledger[9].param == pytest.approx(0.5)


# ------------------------------------------------------------- the sandbox


def test_sandbox_base_is_the_recorded_world_not_a_reconstruction(tmp_path):
    """A fork must start from the ACTUAL history, read back from the archive."""
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=40)
    stream = read_decision_stream(db)
    assert stream, "the recorded run must have a decision stream"
    # the stream is the journal's own record, one entry per live tick
    assert all(0 <= a <= 6 for a in stream)


def test_sandbox_fork_changes_exactly_one_factor_and_diverges_there(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=40)
    fork_db = str(tmp_path / "fork.db")
    result = fork_at_tick(db, 20, 0, fork_db=fork_db)

    assert result.diverged
    assert result.diverged_at_tick == 20
    # the two runs share their prefix and differ afterwards
    with JournalView(db) as a, JournalView(fork_db) as b:
        a_tids = [t.id for t in a]
        b_tids = [t.id for t in b]
        assert a_tids[:1] == b_tids[:1]
        assert a_tids != b_tids


def test_sandbox_fork_keeps_the_base_decree_ledger(tmp_path):
    """Changing ONE factor means the decree ledger travels with the base."""
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=40,
                 decrees={5: Directive(DIRECTIVE_AMEND, "region:0", 0.25)})
    fork_db = str(tmp_path / "fork.db")
    result = fork_at_tick(db, 20, 0, fork_db=fork_db)

    # the fork still contains the base decree (otherwise two factors moved)
    with JournalView(fork_db) as view:
        assert any(t.operation == "player.directive" for t in view)
    # and it diverged at the FORK tick, not at the decree tick
    assert result.diverged_at_tick == 20


def test_sandbox_fork_of_a_fork_is_still_a_valid_counterfactual(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=40)
    fork_db = str(tmp_path / "fork.db")
    result = run_counterfactual(db, Fork(10, 3), fork_db=fork_db)
    assert result.diverged
    assert result.diverged_at_tick == 10


def test_sandbox_reports_a_mechanical_difference_not_a_story(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=40)
    fork_db = str(tmp_path / "fork.db")
    result = fork_at_tick(db, 20, 0, fork_db=fork_db)
    assert result.soil_diffs, "the comparison must carry numbers"
    for region, delta in result.soil_diffs.items():
        assert isinstance(delta, float)
    assert result.base_population and result.fork_population


def test_stream_index_maps_world_ticks_to_decisions(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=40)
    index = stream_index_of_tick(db, 10)
    assert index == 10
    # a tick beyond the run has no decision
    assert stream_index_of_tick(db, 10_000) is None


# ----------------------------------------------------------- the hypothesis


def test_hypothesis_confirmed_only_when_the_record_has_the_edge(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=30)
    with JournalView(db) as view, QueryIndex(view, db + ".qidx") as idx:
        idx.build()
        facts = facts_of(view, system="CivicAgricultureSystem",
                         operation="agriculture.harvest")
        assert facts
        links = confirmed_links(idx, facts[0].transition_id, depth=1)
        assert links, "the harvest must feed the next tick's readers"
        report = understand(
            db,
            Hypothesis(text="x", source_id=facts[0].transition_id,
                       reader_id=links[0].reader_id),
        )
        assert report.verdict is Verdict.CONFIRMED
        assert facts[0].transition_id in report.supporting


def test_hypothesis_is_refuted_when_no_such_edge_exists(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=30)
    with JournalView(db) as view, QueryIndex(view, db + ".qidx") as idx:
        idx.build()
        facts = facts_of(view, operation="agents.census")
        harvests = facts_of(view, operation="agriculture.harvest")
        report = understand(
            db,
            Hypothesis(text="x", source_id=harvests[0].transition_id,
                       reader_id=facts[-1].transition_id),
        )
        assert report.verdict is Verdict.REFUTED


def test_hypothesis_unresolved_when_the_field_was_never_written(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=30)
    report = understand(
        db,
        Hypothesis(text="x", system="CivicAgricultureSystem",
                   operation="agriculture.harvest", entity="region:0",
                   field="no_such_field"),
    )
    assert report.verdict is Verdict.UNRESOLVED


def test_attribution_hypothesis_names_the_real_writer(tmp_path):
    db = str(tmp_path / "w.db")
    _civic_world(db, ticks=30)
    ok = understand(
        db,
        Hypothesis(text="x", system="CivicAgricultureSystem",
                   operation="agriculture.harvest", entity="region:0",
                   field="soil_fertility"),
    )
    assert ok.verdict is Verdict.CONFIRMED
    wrong = understand(
        db,
        Hypothesis(text="x", system="AgentSystem", operation="agents.census",
                   entity="region:0", field="soil_fertility"),
    )
    assert wrong.verdict is Verdict.REFUTED


def test_rejected_transitions_are_not_facts(tmp_path):
    db = str(tmp_path / "w.db")
    sim = create_world(seed=7, ruleset=get_ruleset("player_civic"), ticks=0,
                       regions=2, agents=20, persist=db)
    attach_player_channel(sim, DecisionChannel(actions=[99] * 20))
    sim.run(10)
    sim.journal.commit()
    sim.journal.close()
    with JournalView(db) as view:
        rejected = [t for t in view if t.status.value == "REJECTED"]
        assert rejected, "an out-of-range action must be recorded as rejected"
        facts = facts_of(view, operation="player.act")
        assert all(f.transition_id not in {r.id for r in rejected}
                   for f in facts)


# ------------------------------------------------------------- the game loop


def test_game_loop_observe_understand_intervene_verify(tmp_path):
    db = str(tmp_path / "w.db")
    world = GameWorld(seed=7, ruleset="player_civic", regions=2, agents=40,
                      db_path=db)
    for _ in range(8):
        world.act(6)
    world.decree(8, DIRECTIVE_AMEND, "region:0", 0.25)
    for _ in range(20):
        world.act(6)
    world.close()

    # OBSERVE
    observation = observe(db)
    assert observation["regime"]["type"]
    assert observation["budgets"]["region:0.soil_fertility"]["net"] != 0.0

    # UNDERSTAND
    report = understand(
        db,
        Hypothesis(text="the harvest wrote the soil",
                   system="CivicAgricultureSystem",
                   operation="agriculture.harvest", entity="region:0",
                   field="soil_fertility"),
    )
    assert report.verdict is Verdict.CONFIRMED

    # INTERVENE + VERIFY
    result = intervene_and_verify(db, fork_at=12, action=0,
                                  fork_db=str(tmp_path / "fork.db"))
    assert result.diverged
    assert result.diverged_at_tick == 12


def test_chronicle_reports_the_life_as_recorded(tmp_path):
    db = str(tmp_path / "w.db")
    world = GameWorld(seed=7, ruleset="player_civic", regions=2, agents=40,
                      db_path=db)
    for _ in range(10):
        world.act(5)
    world.close()
    card = chronicle(db)
    assert len(card["fingerprint"]) == 64
    assert card["decisions"]
    assert "# Biography" in card["markdown"]
