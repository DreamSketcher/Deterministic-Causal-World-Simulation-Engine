"""v0.11 tests — resettlement: using the land the player opened.

The review of v0.10 named the gap exactly: a claim creates room, but the
world's own migration fires on HUNGER and moves to a neighbour, so a fed
world never uses the land it was given. These tests pin the answer:

* a resettlement is ONE committed transition: it moves real agents
  (``agent.cell``), the source's people and food, and the destination's
  people. No partial move is representable, and no agent is duplicated
  or lost;
* the price is transport food paid by the SOURCE, growing with the
  distance, and it is written in the same transition;
* a destination must have room AND be habitable (soil, food reserve); a
  wild parcel must be claimed first; refusals are recorded facts
  (``resettle_state``) in the journal, never a silent no-op;
* the donor is chosen deterministically — most over-capacity cell of the
  SAME region, then distance, then id — and the order never empties its
  source;
* the verdict of a ``resettle`` goal accounts for BOTH sides: a move
  that depopulates the source is "resolved with cost", not a win;
* the same seed and the same orders produce the same world;
* the server offers the lever and the destination card with the SAME
  arithmetic the system applies.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.observer.goal import Goal, evaluate
from causal_world.observer.situation import (
    FieldHistory,
    StateView,
    resettle_opportunities,
)
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.systems.directive import (
    DIRECTIVE_CLAIM,
    DIRECTIVE_RESETTLE,
    Directive,
    DirectiveChannel,
)
from causal_world.systems.resettle import (
    RESETTLE_DONE,
    RESETTLE_NO_FOOD,
    RESETTLE_NO_ROOM,
    RESETTLE_WILD,
    ResettlementDirectiveSystem,
)
from causal_world.world.rules import get_ruleset


# --------------------------------------------------------------- helpers


def _world(*, seed=7, regions=2, agents=54):
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=regions, agents=agents,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * 400))
    channel = DirectiveChannel()
    system = None
    for s in sim.systems:
        if isinstance(s, ResettlementDirectiveSystem):
            s.channel = channel
            system = s
    assert system is not None
    return sim, channel, system


def _wild(sim) -> list[str]:
    return sorted(
        c for c in sim.state.entities_with_prefix("cell:")
        if not sim.state.get(c, "land_active")
    )


def _alive_by_cell(sim) -> dict[str, int]:
    out: dict[str, int] = {}
    for agent in sim.state.entities_with_prefix("agent:"):
        if not sim.state.get(agent, "alive"):
            continue
        cell = sim.state.get(agent, "cell")
        out[cell] = out.get(cell, 0) + 1
    return out


def _claim_and_resettle(sim, channel, parcel: str, movers: int = 0):
    channel.schedule(1, Directive(DIRECTIVE_CLAIM, parcel, 0))
    channel.schedule(2, Directive(DIRECTIVE_RESETTLE, parcel, movers))
    sim.step()  # tick 0
    sim.step()  # tick 1: the claim
    before = _alive_by_cell(sim)
    sim.step()  # tick 2: the resettlement
    return before


def _transition(sim, operation: str):
    for tr in sim.journal:
        if tr.operation == operation and tr.tick == 2:
            return tr
    raise AssertionError(f"no {operation} on tick 2")


# ------------------------------------------------------------- the world


def test_the_resettlement_world_has_the_lever_and_the_fields():
    sim, _channel, system = _world()
    assert system.KIND_NAMES[DIRECTIVE_RESETTLE] == "resettle"
    card = system.kinds()
    assert card[DIRECTIVE_RESETTLE] == "resettle"
    assert DIRECTIVE_CLAIM in card
    for cell in sim.state.entities_with_prefix("cell:"):
        assert sim.state.get(cell, "resettled_in") == 0
        assert sim.state.get(cell, "resettled_out") == 0
        assert sim.state.get(cell, "resettle_state") == 0
        assert sim.state.get(cell, "last_source") == "none"


def test_a_claim_then_resettle_moves_people_atomically():
    sim, channel, _system = _world()
    parcel = "cell:0:4"
    alive_before = {
        a for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    }
    before = _claim_and_resettle(sim, channel, parcel, movers=4)

    assert sim.state.get(parcel, "land_active") == 1
    moved = int(sim.state.get(parcel, "resettled_in"))
    assert moved == int(sim.state.get(parcel, "resettle_moved"))
    assert 1 <= moved <= 4
    assert sim.state.get(parcel, "resettle_state") == RESETTLE_DONE
    source = sim.state.get(parcel, "last_source")
    assert source.startswith("cell:") and source != parcel
    assert sim.state.get(parcel, "last_resettle_tick") == 2

    # the two cells lost/gained exactly the same number of people
    after = _alive_by_cell(sim)
    assert after.get(parcel, 0) == before.get(parcel, 0) + moved
    assert after.get(source, 0) == before.get(source, 0) - moved
    assert sim.state.get(parcel, "population") == after.get(parcel, 0)
    assert sim.state.get(source, "population") == after.get(source, 0)

    # no agent vanished: every life that existed before the move still
    # exists as an entity (a move changes `cell`, it never deletes)
    entities_after = set(sim.state.entities_with_prefix("agent:"))
    assert alive_before <= entities_after
    in_parcel = [
        a for a in entities_after
        if sim.state.get(a, "alive") and sim.state.get(a, "cell") == parcel
    ]
    assert len(in_parcel) == after.get(parcel, 0)


def test_the_transport_is_paid_by_the_source_in_the_same_transition():
    sim, channel, system = _world()
    parcel = "cell:0:4"
    _claim_and_resettle(sim, channel, parcel, movers=0)
    transition = _transition(sim, "player.resettle")

    moved = int(sim.state.get(parcel, "resettle_moved"))
    source = sim.state.get(parcel, "last_source")
    sx, sy = sim.state.get(source, "cell_x"), sim.state.get(source, "cell_y")
    dx, dy = sim.state.get(parcel, "cell_x"), sim.state.get(parcel, "cell_y")
    distance = abs(int(dx) - int(sx)) + abs(int(dy) - int(sy))
    cost = system.RESETTLE_FOOD_BASE + system.RESETTLE_FOOD_PER_STEP * distance

    assert sim.state.get(parcel, "resettle_cost") == pytest.approx(
        moved * cost
    )
    food_writes = [
        w for w in transition.writes
        if w.entity == source and w.field == "food_stock"
    ]
    assert len(food_writes) == 1
    spent = food_writes[0].old - food_writes[0].new
    assert spent == pytest.approx(moved * cost)


def test_the_order_moves_no_more_than_was_asked_and_zero_means_the_maximum():
    sim, channel, _system = _world()
    parcel = "cell:0:4"
    _claim_and_resettle(sim, channel, parcel, movers=2)
    assert int(sim.state.get(parcel, "resettle_moved")) == 2

    # a fresh world: 0 = as many as the cell can take
    sim2, channel2, _system2 = _world()
    _claim_and_resettle(sim2, channel2, parcel, movers=0)
    assert int(sim2.state.get(parcel, "resettle_moved")) >= 3


def test_a_resettle_into_wild_land_is_refused_as_a_fact():
    sim, channel, _system = _world()
    channel.schedule(1, Directive(DIRECTIVE_RESETTLE, "cell:0:4", 3))
    sim.step()  # tick 0
    sim.step()  # tick 1: the order enters force
    assert sim.state.get("cell:0:4", "resettle_state") == RESETTLE_WILD
    assert sim.state.get("cell:0:4", "resettled_in") == 0
    assert sim.state.get("cell:0:4", "land_active") == 0


def test_a_resettle_into_a_full_cell_is_refused():
    sim, channel, _system = _world()
    parcel = "cell:0:4"
    _claim_and_resettle(sim, channel, parcel, movers=0)
    first = int(sim.state.get(parcel, "resettled_in"))
    assert first > 0
    # the parcel is now at (or near) its capacity: another full order
    # must be refused by the world, not silently dropped
    full = int(sim.state.get(parcel, "population"))
    capacity = int(round(
        int(sim.state.get(parcel, "pop_base"))
        * (1.0 + float(sim.state.get(parcel, "soil_fertility")))
    ))
    assert full == capacity, "the first order filled the homestead"
    channel.schedule(sim.state.tick, Directive(DIRECTIVE_RESETTLE, parcel, 1))
    sim.step()
    assert sim.state.get(parcel, "resettle_state") == RESETTLE_NO_ROOM
    assert int(sim.state.get(parcel, "resettled_in")) == first


def test_a_destination_must_be_habitable_not_just_roomy():
    values = {
        ("cell:0:0", "region"): ("region:0", 1, 5),
        ("cell:0:0", "cell_x"): (0, 2, 5),
        ("cell:0:0", "cell_y"): (0, 3, 5),
        ("cell:0:0", "population"): (14, 4, 5),
        ("cell:0:0", "pop_base"): (8, 5, 5),
        ("cell:0:0", "soil_fertility"): (0.5, 6, 5),
        ("cell:0:0", "food_stock"): (200.0, 7, 5),
        ("cell:0:4", "region"): ("region:0", 8, 5),
        ("cell:0:4", "cell_x"): (0, 9, 5),
        ("cell:0:4", "cell_y"): (2, 10, 5),
        ("cell:0:4", "population"): (1, 11, 5),
        ("cell:0:4", "pop_base"): (3, 12, 5),
        ("cell:0:4", "soil_fertility"): (0.4, 13, 5),
        ("cell:0:4", "food_stock"): (30.0, 14, 5),
    }
    view = StateView(dict(values))
    rows = resettle_opportunities(view)
    row = next(r for r in rows if r["destination"] == "cell:0:4")
    assert row["feasible"] is True
    assert row["source"] == "cell:0:0"
    assert row["distance"] == 2
    assert row["cost_per_migrant"] == pytest.approx(5.0)
    assert row["max_movers"] == 3  # room = round(3*1.5) - 1 = 4 - 1

    # the same parcel with spent soil is NOT a destination
    spent = dict(values)
    spent[("cell:0:4", "soil_fertility")] = (0.2, 13, 5)
    row = next(
        r for r in resettle_opportunities(StateView(spent))
        if r["destination"] == "cell:0:4"
    )
    assert row["feasible"] is False and row["reason"] == "soil"

    # nor is a cell that cannot feed the people already there
    hungry = dict(values)
    hungry[("cell:0:4", "food_stock")] = (2.0, 14, 5)
    row = next(
        r for r in resettle_opportunities(StateView(hungry))
        if r["destination"] == "cell:0:4"
    )
    assert row["feasible"] is False and row["reason"] == "food"

    # nor is an EMPTY parcel that has not built a reserve yet: the system
    # divides the reserve by max(population, 1), so "nobody there" does
    # not mean "anybody can come" — and the card must say so first.
    empty = dict(values)
    empty[("cell:0:4", "population")] = (0, 11, 5)
    empty[("cell:0:4", "food_stock")] = (0.5, 14, 5)
    row = next(
        r for r in resettle_opportunities(StateView(empty))
        if r["destination"] == "cell:0:4"
    )
    assert row["feasible"] is False and row["reason"] == "food"

    # nor is a cell with no donor old enough to send people
    lonely = dict(values)
    lonely[("cell:0:0", "population")] = (1, 4, 5)
    row = next(
        r for r in resettle_opportunities(StateView(lonely))
        if r["destination"] == "cell:0:4"
    )
    assert row["feasible"] is False and row["reason"] == "no_donor"


def test_a_source_that_cannot_pay_moves_nobody():
    sim, channel, system = _world()
    # The price is a PARAMETER of the world (the engine copies it into
    # the system). Make the trip unaffordable: no donor can pay, so the
    # world must refuse instead of moving people for free.
    system.RESETTLE_FOOD_BASE = 10_000.0
    parcel = "cell:0:4"
    _claim_and_resettle(sim, channel, parcel, movers=3)
    assert sim.state.get(parcel, "resettle_state") == RESETTLE_NO_FOOD
    assert sim.state.get(parcel, "resettled_in") == 0


def test_the_move_is_intra_regional_and_keeps_the_region_total():
    sim, channel, _system = _world()
    parcel = "cell:0:4"
    before = sim.state.get("region:0", "population")
    _claim_and_resettle(sim, channel, parcel, movers=0)
    assert sim.state.get(parcel, "region") == "region:0"
    # the move happens inside the region, so its total is unchanged by it
    assert sim.state.get("region:0", "population") == before


def test_the_census_confirms_the_move_on_the_next_tick():
    sim, channel, _system = _world()
    _claim_and_resettle(sim, channel, "cell:0:4", movers=0)
    sim.step()  # tick 3: the census re-derives the counts
    for cell in sim.state.entities_with_prefix("cell:"):
        if not sim.state.get(cell, "land_active"):
            continue
        alive = sum(
            1 for a in sim.state.entities_with_prefix("agent:")
            if sim.state.get(a, "alive")
            and sim.state.get(a, "cell") == cell
        )
        assert int(sim.state.get(cell, "population")) == alive


def test_a_move_writes_no_capacity_and_changes_the_total_by_zero():
    sim, channel, _system = _world()
    _claim_and_resettle(sim, channel, "cell:0:4", movers=4)
    transition = _transition(sim, "player.resettle")
    fields = {w.field for w in transition.writes}
    assert "pop_base" not in fields
    assert "soil_fertility" not in fields
    assert "land_active" not in fields
    delta = sum(
        int(w.new) - int(w.old)
        for w in transition.writes
        if w.field == "population" and w.entity.startswith("cell:")
    )
    assert delta == 0


def test_the_new_ruleset_does_not_change_the_world_when_unused():
    """The freeze check: the added lever must be inert when not used."""
    from causal_world.simulation.engine import create_world as make

    def run(ruleset):
        sim = make(
            seed=7, ruleset=get_ruleset(ruleset), ticks=0,
            regions=2, agents=54,
        )
        attach_player_channel(sim, DecisionChannel(actions=[6] * 100))
        sim.run(60)
        state = sim.state
        return (
            sum(1 for a in state.entities_with_prefix("agent:")
                if state.get(a, "alive")),
            sum(1 for a in state.entities_with_prefix("agent:")),
            round(sum(float(state.get(c, "population"))
                      for c in state.entities_with_prefix("cell:")), 6),
            round(sum(float(state.get(c, "soil_fertility"))
                      for c in state.entities_with_prefix("cell:")
                      if state.get(c, "land_active")), 6),
        )

    assert run("player_spatial") == run("player_resettle")


def test_the_reading_defaults_match_the_ruleset():
    from causal_world.observer import situation
    from causal_world.world.rules import ResettlementRules

    assert situation.RESETTLE_SOIL_MIN == ResettlementRules.RESETTLE_SOIL_MIN
    assert (situation.RESETTLE_FOOD_PC_MIN
            == ResettlementRules.RESETTLE_FOOD_PC_MIN)
    assert situation.RESETTLE_FOOD_BASE == ResettlementRules.RESETTLE_FOOD_BASE
    assert (situation.RESETTLE_FOOD_PER_STEP
            == ResettlementRules.RESETTLE_FOOD_PER_STEP)
    assert (situation.RESETTLE_MAX_PER_ORDER
            == ResettlementRules.RESETTLE_MAX_PER_ORDER)

    sim, _channel, system = _world()
    assert system.RESETTLE_FOOD_BASE == ResettlementRules.RESETTLE_FOOD_BASE
    assert (system.RESETTLE_SOIL_MIN
            == ResettlementRules.RESETTLE_SOIL_MIN)


def test_the_same_seed_and_the_same_orders_produce_the_same_world():
    def run():
        sim, channel, _system = _world()
        _claim_and_resettle(sim, channel, "cell:0:4", movers=3)
        sim.run(3)
        return sim.state.hash(), sim.journal.hash()

    assert run() == run()


# --------------------------------------------------------------- verdicts


def _view_with(*cells):
    values = {}
    for index, (cell, fields) in enumerate(cells):
        for name, value in fields.items():
            values[(cell, name)] = (value, 100 + index, 5)
    return StateView(values)


def _history(dest_pop, source_open, source_close=None, *, closed=5):
    if source_close is None:
        source_close = source_open
    h = FieldHistory()
    for tick in range(0, 41):
        h.add("cell:0:4", "population", tick,
              0 if tick < closed else dest_pop)
        h.add("cell:0:4", "food_stock", tick, 40.0)
        h.add("cell:0:4", "soil_fertility", tick, 0.5)
        h.add("cell:0:4", "births_total", tick, 0)
        h.add("cell:0:2", "population", tick,
              source_open if tick < closed else source_close)
    return h


def _resettle_goal() -> Goal:
    return Goal("resettle", "cell:0:4", "abandoned", 0, 5)


def _resettle_view(source_pop: int):
    return _view_with(
        ("cell:0:4", {
            "population": 6, "pop_base": 3, "soil_fertility": 0.5,
            "food_stock": 40.0, "births_total": 0,
            "last_source": "cell:0:2", "resettled_in": 6,
            "resettle_state": 1, "land_active": 1,
            "cell_x": 0, "cell_y": 2, "region": "region:0",
        }),
        ("cell:0:2", {
            "population": source_pop, "pop_base": 8,
            "soil_fertility": 0.5, "food_stock": 100.0,
            "resettled_out": 6, "land_active": 1,
            "cell_x": 0, "cell_y": 1, "region": "region:0",
        }),
    )


def test_a_move_that_empties_the_source_is_not_a_win():
    view = _resettle_view(source_pop=5)
    verdict = evaluate(
        _resettle_goal(), _history(6, 10, 5), view, [], tick=40,
        neighbours=[],
    )
    assert verdict.status == "resolved_with_cost"
    assert "источник" in verdict.reason
    assert verdict.solved is True


def test_a_move_that_spares_the_source_can_be_resolved():
    view = _resettle_view(source_pop=9)
    verdict = evaluate(
        _resettle_goal(), _history(6, 9), view, [], tick=40,
        neighbours=[],
    )
    assert verdict.status == "resolved"


def test_the_verdict_cites_the_transition_of_the_move():
    view = _resettle_view(source_pop=9)
    verdict = evaluate(
        _resettle_goal(), _history(6, 9), view, [], tick=40,
        neighbours=[],
    )
    fields = {(e["entity"], e["field"]) for e in verdict.evidence}
    assert ("cell:0:4", "resettled_in") in fields
    assert ("cell:0:2", "population") in fields


# ----------------------------------------------------------------- server


def test_the_server_offers_resettlement_and_shows_the_card(tmp_path):
    from causal_world.server.session import Session

    session = Session(
        seed=7, ruleset="player_resettle", regions=2, agents=54,
        db_path=str(tmp_path / "resettle.db"), max_ticks=200,
    )
    try:
        welcome = session.welcome()
        assert set(welcome["decree_card"]) == {0, 1, 2, 3, 4, 5, 6}
        assert welcome["decree_card"][6] == "resettle"

        frame = session.decide(1, 6)
        cards = frame["world"]["resettle"]
        assert cards, "a living world has cells with room"
        assert all("feasible" in c and "reason" in c for c in cards)
        assert any(c["feasible"] for c in cards)

        wid = next(c["id"] for c in frame["world"]["cells"]
                   if c["land_active"] == 0)
        frame = session.decide(
            2, 6, {"kind": 4, "target": wid, "param": 0}
        )
        assert frame["decree"]["status"] == "accepted"
        frame = session.decide(3, 6)
        claimed = next(c for c in frame["world"]["cells"]
                       if c["id"] == wid)
        assert claimed["land_active"] == 1
        assert claimed["resettled_in"] == 0

        frame = session.decide(
            4, 6, {"kind": 6, "target": wid, "param": 0}
        )
        assert frame["decree"]["status"] == "accepted"
        assert frame["decree"]["name"] == "resettle"
        # the order enters force on the NEXT tick and is then a fact
        frame = session.decide(5, 6)
        done = next(c for c in frame["world"]["cells"] if c["id"] == wid)
        assert done["resettled_in"] > 0
        assert done["resettle_state"] == RESETTLE_DONE
        assert done["last_source"].startswith("cell:")
    finally:
        session.close()


def test_verdict_json_is_serializable():
    view = _resettle_view(source_pop=9)
    verdict = evaluate(
        _resettle_goal(), _history(6, 9), view, [], tick=40,
        neighbours=[],
    )
    payload = verdict.to_dict()
    assert payload["status"] == "resolved"
    assert payload["confidence"] == "established"
    assert payload["scope"] == "cell:0:4"
    assert payload["kind"] == "resettle"
