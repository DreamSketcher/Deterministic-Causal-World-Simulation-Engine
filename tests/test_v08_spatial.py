"""v0.8 — the spatial world: cells, a stable horizon, the situation layer.

Four promises are checked here, and they are the four the v0.8 concept
makes:

* **the spatial model is correct** — the genesis creates a GRID of cells
  with their own soil, rain, people and law; food is local; a person
  moves to a better NEIGHBOURING cell;
* **the horizon is stable** — the soil equilibrium is a property of the
  LABOUR, not of the head count: a cell whose people died keeps its
  soil (the death spiral of v0.7 is gone by construction), and the
  supply of newborns scales with the number of adults;
* **an intervention is one factor** — a decree changes the law of ONE
  cell, it enters force on the next tick, and the conception threshold
  it moves is visible in the journal (the nursery doubles the
  per-adult probability of a child);
* **the world speaks about itself** — the situation layer reports a
  famine, an abandoned cell and a birth stall with the transition ids
  the claim rests on, and it says WHEN the problem started.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.observer.journal import JournalView
from causal_world.observer.situation import (
    FieldHistory,
    StateView,
    situations,
)
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.systems.directive import (
    DIRECTIVE_AMEND,
    DIRECTIVE_NURSERY,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset


# ------------------------------------------------------------------ helpers


def _spatial_world(
    db_path=None,
    *,
    seed=7,
    regions=2,
    agents=54,
    ticks=40,
    decrees=None,
    ruleset="player_spatial",
):
    """A spatial world with an idle player and an optional decree ledger."""
    sim = create_world(
        seed=seed, ruleset=get_ruleset(ruleset), ticks=0,
        regions=regions, agents=agents, persist=db_path,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (ticks + 10)))
    if decrees:
        channel = DirectiveChannel()
        for tick, decree in decrees.items():
            channel.schedule(tick, decree)
        for system in sim.systems:
            if isinstance(system, DirectiveSystem):
                system.channel = channel
    sim.run(ticks)
    if db_path:
        sim.journal.commit()
        sim.journal.close()
    return sim


def _cells(sim) -> list[str]:
    return sorted(sim.state.entities_with_prefix("cell:"))


# ------------------------------------------------------- the spatial genesis


def test_the_genesis_creates_a_grid_of_cells():
    """A region owns a GRID of cells; every cell is a world entity."""
    sim = _spatial_world(regions=2, agents=54)
    cells = _cells(sim)
    assert cells == [f"cell:{r}:{c}" for r in range(2) for c in range(4)]

    assert "cell:1:2" in sim.state.entities()
    for field in (
        "region", "cell_x", "cell_y", "soil_fertility", "rain_factor",
        "food_stock", "population", "workers", "pop_base",
        "labor_diversion", "water_aid", "rest_until", "nursery",
        "empty_since", "births_total", "last_birth_tick",
    ):
        assert field in sim.state.fields_of("cell:1:2"), field

    # the cell knows its region and its place on the strip
    assert sim.state.get("cell:1:2", "region") == "region:1"
    assert sim.state.get("cell:1:2", "cell_x") == 2
    assert sim.state.get("cell:1:2", "cell_y") == 1


def test_the_people_live_in_the_cells():
    """Every living person is counted in exactly one cell."""
    sim = _spatial_world(regions=2, agents=54)
    live = [
        a for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    ]
    assert live
    counted = sum(
        int(sim.state.get(c, "population")) for c in _cells(sim)
    )
    # The census is a snapshot of the tick: the people who moved during
    # the LAST tick are counted in the cell they left (the next census
    # counts them where they are). The lag is exactly the movers.
    last_tick = sim.state.tick - 1   # the last tick the journal holds
    movers = sum(
        1 for t in sim.journal
        if t.tick == last_tick
        and (
            t.operation == "agent.migrate"
            or any(w.field == "cell" for w in t.writes)
        )
    )
    assert 0 <= len(live) - counted <= movers
    for agent in live:
        assert sim.state.get(agent, "cell") in _cells(sim)
    # the reserve of lives is not in any cell
    dormant = [
        a for a in sim.state.entities_with_prefix("agent:")
        if not sim.state.get(a, "alive")
    ]
    assert dormant
    assert all(sim.state.get(a, "cell") == "none" for a in dormant)


def test_the_cells_are_not_identical():
    """The map is heterogeneous: the rain and the soil differ per cell."""
    sim = _spatial_world(regions=2, agents=54)
    rains = {sim.state.get(c, "rain_factor") for c in _cells(sim)}
    soils = {round(sim.state.get(c, "soil_fertility"), 6) for c in _cells(sim)}
    assert len(rains) > 1
    assert len(soils) > 1


def test_food_is_local_a_cell_harvests_from_its_own_soil_and_rain():
    """The cell's harvest reads the CELL, not the region."""
    sim = _spatial_world(ticks=12)
    harvests = [
        t for t in sim.journal
        if t.operation == "agriculture.harvest"
        and any(w.entity == "cell:0:1" for w in t.writes)
    ]
    assert harvests
    reads = {(r.entity, r.field) for r in harvests[0].reads}
    assert ("cell:0:1", "soil_fertility") in reads
    assert ("cell:0:1", "rain_factor") in reads


# ------------------------------------------------------ the stable horizon


def test_the_soil_equilibrium_does_not_depend_on_the_head_count():
    """The fix of the v0.7 death spiral, measured.

    In the v0.7 law the nutrient return was proportional to the
    POPULATION while the degradation was flat, so a cell that lost
    people lost its soil (and starved the rest). In v0.8 both terms
    scale with the labour, so the equilibrium soil is the same for a
    thriving cell and for a cell whose people have all died.
    """
    sim = _spatial_world(regions=2, agents=54, ticks=200)
    soils = {
        c: sim.state.get(c, "soil_fertility") for c in _cells(sim)
    }
    pops = {c: int(sim.state.get(c, "population")) for c in _cells(sim)}
    living = [c for c in _cells(sim) if pops[c] > 0]
    dead = [c for c in _cells(sim) if pops[c] == 0]
    assert living and dead, "the run must contain both a living and a dead cell"

    for cell in living:
        assert soils[cell] == pytest.approx(0.47, abs=0.03)
    for cell in dead:
        # the land of a dead cell keeps its balance: no spiral
        assert soils[cell] == pytest.approx(0.47, abs=0.03)


def test_the_supply_of_newborns_scales_with_the_number_of_adults():
    """Per-adult reproduction, not the per-region Bernoulli of v0.7."""
    small = _spatial_world(agents=54, ticks=200)
    large = _spatial_world(agents=108, ticks=200)

    def births(sim) -> int:
        return sum(
            1 for t in sim.journal
            if t.operation == "agent.birth" and t.status.value == "COMMITTED"
        )

    assert births(large) > 1.5 * births(small)


def test_a_birth_is_never_rejected_as_a_duplicate_write():
    """One transition per child: a builder that carried two children
    would write the same field twice and be rejected."""
    sim = _spatial_world(ticks=120)
    rejected = [
        t for t in sim.journal
        if t.operation == "agent.birth" and t.status.value != "COMMITTED"
    ]
    assert rejected == []


def test_the_world_survives_its_horizon_when_the_player_tends_it():
    """The vertical slice: the player's laws turn a dying world into a
    stable one. The same seed, the same world, one difference."""
    decrees = {}
    for i, cell in enumerate(("cell:1:0", "cell:1:1", "cell:1:2", "cell:1:3")):
        decrees[20 + i] = Directive(DIRECTIVE_AMEND, cell, 0.15)
    for i, cell in enumerate(("cell:1:0", "cell:1:1", "cell:1:2", "cell:1:3")):
        decrees[24 + i] = Directive(DIRECTIVE_WATER, cell, 1.0)

    def alive(sim) -> int:
        return sum(
            1 for a in sim.state.entities_with_prefix("agent:")
            if sim.state.get(a, "alive")
        )

    base = _spatial_world(ticks=300)
    tended = _spatial_world(ticks=300, decrees=decrees)
    assert alive(tended) > alive(base)
    # the poor region survives under the player's laws
    poor = [c for c in _cells(base) if c.startswith("cell:1:")]
    assert sum(int(tended.state.get(c, "population")) for c in poor) > 0
    assert sum(int(base.state.get(c, "population")) for c in poor) == 0


# ------------------------------------------------------------- the decrees


def test_a_decree_changes_the_law_of_one_cell_only(tmp_path):
    db = str(tmp_path / "w.db")
    _spatial_world(db, regions=2, agents=54,
                   decrees={5: Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15)})
    with JournalView(db) as view:
        decrees = [t for t in view if t.operation == "player.directive"]
        assert len(decrees) == 1
        t = decrees[0]
        assert t.status.value == "COMMITTED"
        assert t.tick == 5
        assert t.random_draws[0].value == float(DIRECTIVE_AMEND)
        write = next(w for w in t.writes if w.field == "labor_diversion")
        assert write.entity == "cell:0:0"
        assert write.old == 0.0
        assert write.new == pytest.approx(0.15)
        # no other cell was touched by the decree
        assert [w.entity for w in t.writes] == ["cell:0:0"]


def test_the_decree_enters_force_on_the_next_tick(tmp_path):
    """One snapshot per tick: the law is read with the OLD value on the
    decree tick and with the NEW one on the next."""
    db = str(tmp_path / "w.db")
    _spatial_world(db, ticks=12,
                   decrees={5: Directive(DIRECTIVE_AMEND, "cell:0:0", 0.15)})
    with JournalView(db) as view:
        harvests = [
            t for t in view
            if t.operation == "agriculture.harvest" and t.tick in (5, 6)
            and any(w.entity == "cell:0:0" for w in t.writes)
        ]
        at_5 = next(t for t in harvests if t.tick == 5)
        at_6 = next(t for t in harvests if t.tick == 6)
        assert next(r.value for r in at_5.reads
                    if r.field == "labor_diversion") == 0.0
        assert next(r.value for r in at_6.reads
                    if r.field == "labor_diversion") == pytest.approx(0.15)


def test_the_nursery_doubles_the_per_adult_chance_of_a_child(tmp_path):
    """The nursery is a MODEL policy: it moves the conception
    probability, and the journal shows the new threshold."""
    db = str(tmp_path / "w.db")
    _spatial_world(db, ticks=80,
                   decrees={5: Directive(DIRECTIVE_NURSERY, "cell:0:0", 1.0)})
    with JournalView(db) as view:
        thresholds = {}
        for t in view:
            if t.operation != "agent.birth" or t.status.value != "COMMITTED":
                continue
            cell = next((w.new for w in t.writes if w.field == "cell"), None)
            for draw in t.random_draws:
                if draw.purpose == "birth.conceive":
                    thresholds.setdefault(cell, set()).add(round(draw.threshold, 6))
    assert thresholds["cell:0:0"] == {0.04}   # 0.02 x (1 + 1.0)
    assert 0.02 in thresholds["cell:0:1"]     # the neighbour is untouched


def test_a_decree_to_a_cell_that_does_not_exist_is_not_enacted(tmp_path):
    db = str(tmp_path / "w.db")
    _spatial_world(db, ticks=10,
                   decrees={5: Directive(DIRECTIVE_AMEND, "cell:9:9", 0.15)})
    with JournalView(db) as view:
        assert [t for t in view if t.operation == "player.directive"] == []


# ---------------------------------------------------------------- migration


def test_a_hungry_person_moves_to_a_better_neighbouring_cell():
    """Migration is informed and local: the destination is a NEIGHBOUR
    with more food per head — and never a cell of another region."""
    sim = _spatial_world(ticks=120)
    moves = [t for t in sim.journal if t.operation == "agent.migrate"]
    assert moves, "a hungry world must move its people"
    for t in moves:
        write = next(w for w in t.writes if w.field == "cell")
        source = next(r.value for r in t.reads
                      if r.field == "cell" and r.entity == write.entity)
        assert source in _cells(sim)
        assert write.new in _cells(sim)
        assert sim.state.get(write.new, "region") == \
            sim.state.get(source, "region")
        # the move goes to a neighbour
        sx = int(sim.state.get(source, "cell_x"))
        sy = int(sim.state.get(source, "cell_y"))
        dx = int(sim.state.get(write.new, "cell_x"))
        dy = int(sim.state.get(write.new, "cell_y"))
        assert abs(sx - dx) + abs(sy - dy) == 1


# -------------------------------------------------------- the situation layer


def test_the_situation_layer_reports_an_abandoned_cell_with_its_evidence():
    """The world's own reading of itself, with the transitions it rests
    on."""
    sim = _spatial_world(ticks=200)
    view = StateView.from_state(sim.state, tick_of=lambda tid: None)
    alerts = situations(view, current_tick=sim.state.tick)
    abandoned = [a for a in alerts if a.kind == "abandoned"]
    assert abandoned
    alert = abandoned[0]
    assert alert.scope.startswith("cell:")
    assert alert.severity == 1.0
    assert alert.since_tick > 0          # the world knows WHEN it emptied
    # the evidence is a real transition id of the record
    tids = {t.id for t in sim.journal}
    for item in alert.evidence:
        assert item["tid"] in tids
        assert item["entity"] == alert.scope


def test_the_situation_layer_says_when_a_famine_started():
    """The famine alert is not a mood: it starts at the tick the cell
    ran out of food."""
    view = StateView({
        ("cell:0:0", "population"): (10, 5, 200),
        ("cell:0:0", "food_stock"): (1.0, 6, 200),
        ("cell:0:0", "soil_fertility"): (0.5, 7, 200),
    })
    history = FieldHistory()
    history.add("cell:0:0", "food_stock", 10, 100.0)
    history.add("cell:0:0", "population", 10, 10)
    history.add("cell:0:0", "food_stock", 200, 1.0)
    history.add("cell:0:0", "population", 200, 10)
    view.history = history

    alerts = situations(view, current_tick=200)
    famine = [a for a in alerts if a.kind == "famine"]
    assert famine
    assert famine[0].scope == "cell:0:0"
    assert famine[0].since_tick == 11   # the tick after the last full store
    assert famine[0].evidence           # the numbers it rests on


def test_a_collapsing_world_tells_the_player_what_is_wrong():
    """The real run: the dying region produces alerts, the healthy one
    does not."""
    sim = _spatial_world(ticks=200)
    view = StateView.from_state(sim.state, tick_of=lambda tid: None)
    alerts = situations(view, current_tick=sim.state.tick)
    kinds = {a.kind for a in alerts}
    assert kinds & {"famine", "hunger", "abandoned"}
    scopes = {a.scope for a in alerts}
    assert all(s.startswith("cell:") for s in scopes)


def test_the_situation_layer_of_a_healthy_world_is_silent():
    """A world without a problem produces no alerts: the feed is never
    padded."""
    sim = _spatial_world(ticks=20)
    view = StateView.from_state(sim.state, tick_of=lambda tid: None)
    alerts = situations(view, current_tick=sim.state.tick)
    assert alerts == []


def test_the_situation_layer_reads_a_recorded_archive(tmp_path):
    """The read-only path: the same alerts out of the archive."""
    db = str(tmp_path / "w.db")
    _spatial_world(db, ticks=120)
    with JournalView(db) as view:
        alerts = situations(view)
    assert alerts
    assert all(a.scope.startswith(("cell:", "region:")) for a in alerts)
    assert all(a.message for a in alerts)


# ---------------------------------------------------------------- the server


def test_the_server_frame_carries_the_cells_and_the_situations(tmp_path):
    from causal_world.server.session import ProtocolError, Session

    db = str(tmp_path / "s.db")
    session = Session(seed=7, ruleset="player_spatial", regions=2, agents=54,
                      db_path=db, max_ticks=200)
    try:
        welcome = session.welcome()
        assert set(welcome["decree_card"]) == {0, 1, 2, 3}  # + nursery
        frame = session.decide(1, 6)
        world = frame["world"]
        assert len(world["cells"]) == 8
        # a young world has no famine and no abandoned cell yet
        assert {s["kind"] for s in world["situations"]} <= {
            "thin_soil", "surplus", "hunger"
        }
        assert all(s["scope"].startswith("cell:") for s in world["situations"])
        cell = world["cells"][0]
        for key in ("id", "region", "x", "y", "population", "workers",
                    "soil_fertility", "food_stock", "rain_factor", "law"):
            assert key in cell

        # a decree to a cell is accepted and enters force on the next tick
        session.decide(2, 6, {"kind": 0, "target": "cell:1:0", "param": 0.15})
        frame = session.decide(3, 6)
        law = next(c for c in frame["world"]["cells"] if c["id"] == "cell:1:0")
        assert law["law"]["labor_diversion"] == pytest.approx(0.15)

        # a target that does not exist is refused, and the decision slot
        # stays open
        with pytest.raises(ProtocolError) as err:
            session.decide(4, 6, {"kind": 0, "target": "cell:9:9", "param": 0.1})
        assert err.value.code == "unknown_target"
        session.decide(4, 6)
    finally:
        session.close()


# ------------------------------------------------------------- the freeze


def test_the_v06_world_is_bit_identical():
    """The v0.8 additions must not touch the v0.6 world: the state and
    the journal of the pinned run are the recorded ones."""
    sim = create_world(seed=7, ruleset=get_ruleset("player_life"), ticks=0,
                       regions=2, agents=100)
    for _ in range(120):
        sim.step()
    assert sim.state.hash() == (
        "b86cd45c8006438bc258d8530e86a98cd2ae34b8b88ac171bce2534b5a79095f"
    )
    assert sim.journal.hash() == (
        "d334341468e37ecfb0eb3486581c3ad2be45a6b60246fa4c41a1d4f12b38a59c"
    )


def test_the_v07_civic_world_does_not_know_about_cells():
    """The spatial layer is a NEW ruleset, not a patch on the old ones."""
    sim = create_world(seed=7, ruleset=get_ruleset("player_civic"), ticks=0,
                       regions=2, agents=40)
    names = {s.name for s in sim.systems}
    assert not any(n.startswith("Spatial") for n in names)
    assert "cell" not in sim.state.fields_of("region:0")
    sim.run(10)
    assert sim.state.entities_with_prefix("cell:") == []
