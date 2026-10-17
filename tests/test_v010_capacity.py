"""v0.10 tests — the capacity policy: priced land, terraces, honest limits.

The review of v0.9 named the architectural risk of a capacity policy: it
must not become a free way to raise the population for better-looking
metrics. These tests pin the answer:

* wild land exists in the STATE from genesis (not as a config change) and
  is invisible to the ecology, the census, births, migration and the
  situation feed until it is claimed;
* a claim and a terrace are ordinary committed ``player.directive``
  transitions, and their PRICE (food, soil) is written in the same
  transition for the archive to check;
* when the world cannot pay, it does not pretend: the refusal is recorded
  in the cell's own state and in the journal;
* the world can say WHICH limit blocks growth (capacity / food / soil),
  instead of "capacity or food";
* a birth-stall goal is read from ``births_total`` and is only resolved
  when births resume AND the population actually grows;
* ``transferred`` carries ``confidence = "hypothesis"``, and the settle
  window is a measurable parameter, not a hidden constant.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.observer.goal import episodes, evaluate, goals
from causal_world.observer.situation import (
    LIMIT_ADULTS,
    LIMIT_CAPACITY,
    LIMIT_FOOD,
    LIMIT_NONE,
    LIMIT_POOL,
    LIMIT_SOIL,
    FieldHistory,
    StateView,
    growth_limit,
    situations,
)
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.systems.capacity import (
    CLAIM_ALREADY,
    CLAIM_DONE,
    CLAIM_NO_FOOD,
    TERRACE_DONE,
    TERRACE_MAXED,
    TERRACE_NO_FOOD,
    TERRACE_WILD,
    CapacityDirectiveSystem,
)
from causal_world.systems.directive import (
    DIRECTIVE_CLAIM,
    DIRECTIVE_TERRACE,
    Directive,
    DirectiveChannel,
)
from causal_world.world.rules import get_ruleset


# --------------------------------------------------------------- helpers


def _capacity_world(db_path=None, *, seed=7, regions=2, agents=54, ticks=0):
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_capacity"), ticks=0,
        regions=regions, agents=agents, persist=db_path,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * 400))
    channel = DirectiveChannel()
    system = None
    for s in sim.systems:
        if isinstance(s, CapacityDirectiveSystem):
            s.channel = channel
            system = s
    assert system is not None
    if ticks:
        sim.run(ticks)
    return sim, channel, system


def _wild(sim) -> list[str]:
    return sorted(
        c for c in sim.state.entities_with_prefix("cell:")
        if not sim.state.get(c, "land_active")
    )


def _active(sim) -> list[str]:
    return sorted(
        c for c in sim.state.entities_with_prefix("cell:")
        if sim.state.get(c, "land_active")
    )


# ------------------------------------------------------------- wild land


def test_the_capacity_world_has_active_cells_and_wild_land():
    sim, _channel, _system = _capacity_world()
    assert len(_active(sim)) == 8
    assert len(_wild(sim)) == 4  # two parcels per region
    for parcel in _wild(sim):
        assert sim.state.get(parcel, "population") == 0
        assert sim.state.get(parcel, "pop_base") == 0
        assert sim.state.get(parcel, "land_active") == 0


def test_the_v08_world_has_no_wild_land():
    """The capacity reserve is opt-in: player_spatial keeps its 8 cells."""
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_spatial"), ticks=0,
        regions=2, agents=54,
    )
    assert len(sim.state.entities_with_prefix("cell:")) == 8
    assert all(sim.state.get(c, "land_active") == 1
               for c in sim.state.entities_with_prefix("cell:"))


def test_wild_land_is_not_a_cell_for_the_world():
    """No alerts, no people, no births on land nobody has claimed."""
    sim, _channel, _system = _capacity_world()
    sim.run(60)
    wild = set(_wild(sim))
    for parcel in wild:
        assert sim.state.get(parcel, "population") == 0
        assert sim.state.get(parcel, "births_total") == 0
        assert sim.state.get(parcel, "empty_since") == 0
    view = StateView.from_state(sim.state)
    alerts = situations(view, current_tick=sim.state.tick)
    assert not any(a.scope in wild for a in alerts)


# ----------------------------------------------------------------- claim


def test_a_claim_activates_the_parcel_and_pays_from_the_region():
    sim, channel, _system = _capacity_world()
    sim.run(3)
    parcel = _wild(sim)[0]
    region = sim.state.get(parcel, "region")
    donors = [c for c in _active(sim) if sim.state.get(c, "region") == region]
    before = {c: float(sim.state.get(c, "food_stock")) for c in donors}
    richest = max(before, key=lambda c: (before[c], c))

    answer = channel.schedule(4, Directive(DIRECTIVE_CLAIM, parcel, 0))
    assert answer.accepted
    sim.run(2)

    assert sim.state.get(parcel, "land_active") == 1
    assert sim.state.get(parcel, "pop_base") == 3
    assert sim.state.get(parcel, "claim_state") == CLAIM_DONE
    assert sim.state.get(parcel, "food_stock") == pytest.approx(25.0)
    assert sim.state.get(parcel, "land_cost") == pytest.approx(90.0)
    assert float(sim.state.get(richest, "food_stock")) < before[richest]


def test_a_claim_without_food_is_refused_visibly_not_silently():
    sim, channel, system = _capacity_world()
    sim.run(3)
    parcel = _wild(sim)[0]
    system.CLAIM_COST = 10_000.0  # an economy that cannot pay
    channel.schedule(4, Directive(DIRECTIVE_CLAIM, parcel, 0))
    sim.run(2)

    assert sim.state.get(parcel, "land_active") == 0
    assert sim.state.get(parcel, "claim_state") == CLAIM_NO_FOOD
    # the refusal is a committed transition, not a missing one
    rows = [
        t for t in sim.journal
        if t.operation == "player.directive" and t.status.value == "COMMITTED"
    ]
    assert rows and any(
        w.field == "claim_state" and int(w.new) == CLAIM_NO_FOOD
        for t in rows for w in t.writes
    )


def test_a_second_claim_on_the_same_parcel_is_recorded_as_already():
    sim, channel, _system = _capacity_world()
    sim.run(3)
    parcel = _wild(sim)[0]
    channel.schedule(4, Directive(DIRECTIVE_CLAIM, parcel, 0))
    channel.schedule(6, Directive(DIRECTIVE_CLAIM, parcel, 0))
    sim.run(5)
    assert sim.state.get(parcel, "land_active") == 1
    assert sim.state.get(parcel, "claim_state") == CLAIM_ALREADY


# --------------------------------------------------------------- terrace


def test_a_terrace_buys_capacity_with_food_and_soil():
    sim, channel, _system = _capacity_world()
    sim.run(5)
    cell = _active(sim)[0]
    base = int(sim.state.get(cell, "pop_base"))
    food = float(sim.state.get(cell, "food_stock"))

    channel.schedule(6, Directive(DIRECTIVE_TERRACE, cell, 0))
    sim.run(2)

    assert int(sim.state.get(cell, "pop_base")) == base + 2
    assert int(sim.state.get(cell, "terraces")) == 1
    assert int(sim.state.get(cell, "terrace_state")) == TERRACE_DONE
    assert float(sim.state.get(cell, "food_stock")) < food

    # the PRICE is readable from the journal: the same transition that
    # raised pop_base lowered food and soil
    terrace = [
        t for t in sim.journal
        if t.operation == "player.directive"
        and any(w.field == "terrace_state" and int(w.new) == TERRACE_DONE
                for w in t.writes)
    ][0]
    writes = {(w.field): (w.old, w.new) for w in terrace.writes}
    assert writes["pop_base"] == (base, base + 2)
    # the price is the difference the SAME transition applied
    assert writes["food_stock"][0] - writes["food_stock"][1] == pytest.approx(60.0)
    assert writes["soil_fertility"][0] - writes["soil_fertility"][1] == pytest.approx(0.04)


def test_terrace_on_wild_land_is_refused():
    sim, channel, _system = _capacity_world()
    sim.run(3)
    parcel = _wild(sim)[0]
    channel.schedule(4, Directive(DIRECTIVE_TERRACE, parcel, 0))
    sim.run(2)
    assert sim.state.get(parcel, "terrace_state") == TERRACE_WILD
    assert sim.state.get(parcel, "pop_base") == 0


def test_terrace_without_food_is_refused():
    sim, channel, system = _capacity_world()
    sim.run(3)
    cell = _active(sim)[0]
    system.TERRACE_COST = 10_000.0
    channel.schedule(4, Directive(DIRECTIVE_TERRACE, cell, 0))
    sim.run(2)
    assert sim.state.get(cell, "terrace_state") == TERRACE_NO_FOOD
    assert int(sim.state.get(cell, "terraces")) == 0


def test_terraces_are_bounded():
    sim, channel, _system = _capacity_world()
    cell = _active(sim)[0]
    for tick in range(2, 12):
        channel.schedule(tick, Directive(DIRECTIVE_TERRACE, cell, 0))
    sim.run(12)
    assert int(sim.state.get(cell, "terraces")) <= 3
    assert sim.state.get(cell, "terrace_state") in (
        TERRACE_MAXED, TERRACE_NO_FOOD,
    )


# ----------------------------------------------------------- the limit


def _view(**cells) -> StateView:
    values = {}
    for index, (cell, fields) in enumerate(cells.items()):
        for name, value in fields.items():
            values[(cell, name)] = (value, 100 + index, 5)
    return StateView(values)


def test_the_limit_of_growth_is_named_not_guessed():
    # at the ceiling
    out = growth_limit(_view(**{"cell:0:0": {
        "population": 15, "pop_base": 10, "soil_fertility": 0.5,
        "food_stock": 200.0}}), "cell:0:0")
    assert out["limit"] == LIMIT_CAPACITY
    assert out["capacity"] == pytest.approx(15.0)

    # room, but the stores are too thin for the birth law
    out = growth_limit(_view(**{"cell:0:0": {
        "population": 5, "pop_base": 10, "soil_fertility": 0.5,
        "food_stock": 10.0}}), "cell:0:0")
    assert out["limit"] == LIMIT_FOOD

    # food and room, but the land is spent
    out = growth_limit(_view(**{"cell:0:0": {
        "population": 5, "pop_base": 10, "soil_fertility": 0.2,
        "food_stock": 500.0}}), "cell:0:0")
    assert out["limit"] == LIMIT_SOIL

    # nothing in the law blocks a birth
    out = growth_limit(_view(**{"cell:0:0": {
        "population": 5, "pop_base": 10, "soil_fertility": 0.5,
        "food_stock": 500.0}}), "cell:0:0")
    assert out["limit"] == LIMIT_NONE


def test_the_limit_uses_the_rounding_of_the_birth_law():
    """The law computes round(pop_base x (1+soil)); the observer must too."""
    # 10 x 1.24 = 12.4 -> the law rounds to 12, so 12 people IS the ceiling
    out = growth_limit(_view(**{"cell:0:0": {
        "population": 12, "pop_base": 10, "soil_fertility": 0.24,
        "food_stock": 500.0}}), "cell:0:0")
    assert out["limit"] == LIMIT_CAPACITY
    assert out["capacity"] == 12


def test_a_cell_without_adults_says_so():
    values = {
        ("cell:0:0", "population"): (3, 1, 5),
        ("cell:0:0", "pop_base"): (10, 2, 5),
        ("cell:0:0", "soil_fertility"): (0.5, 3, 5),
        ("cell:0:0", "food_stock"): (200.0, 4, 5),
        ("agent:0", "alive"): (True, 10, 5),
        ("agent:0", "cell"): ("cell:0:0", 11, 5),
        ("agent:0", "birth_tick"): (4, 12, 5),
        ("agent:0", "region"): ("region:0", 13, 5),
    }
    out = growth_limit(StateView(values), "cell:0:0", tick=8)
    assert out["limit"] == LIMIT_ADULTS

    # the same cell, but the agent is mature and the world has no free
    # lives left
    values[("agent:0", "birth_tick")] = (0, 12, 5)
    out = growth_limit(StateView(values), "cell:0:0", tick=40)
    assert out["limit"] == LIMIT_POOL


def test_the_birth_stall_alert_carries_the_limit_in_its_detail():
    sim, _channel, _system = _capacity_world()
    sim.run(80)
    view = StateView.from_state(sim.state)
    alerts = situations(view, current_tick=sim.state.tick)
    stalls = [a for a in alerts if a.kind == "birth_stall"]
    assert stalls  # the young world fills quickly
    for alert in stalls:
        assert alert.detail["limit"] in (
            LIMIT_CAPACITY, LIMIT_FOOD, LIMIT_SOIL, LIMIT_NONE
        )
        assert "предел:" in alert.message


# ------------------------------------------------------------- goals


def _history(ticks, *, populations, births, food=None, soil=None):
    h = FieldHistory()
    for tick in ticks:
        h.add("cell:0:0", "population", tick, populations[tick])
        h.add("cell:0:0", "births_total", tick, births[tick])
        h.add("cell:0:0", "food_stock", tick,
              (food or {}).get(tick, 200.0))
        h.add("cell:0:0", "soil_fertility", tick,
              (soil or {}).get(tick, 0.5))
    return h


def test_a_birth_stall_is_an_episode_read_from_births_total():
    ticks = list(range(80))
    births = [0] * 60 + [1] * 20  # first child at tick 60
    populations = [10] * 80
    h = _history(ticks, populations=populations, births=births)
    eps = episodes(h, "cell:0:0", "renew")
    assert eps, "a stall of 40+ ticks must open an episode"
    goal = eps[0]
    assert goal.opened_tick <= 20
    assert goal.closed_tick == 60


def test_a_birth_stall_is_resolved_only_when_the_population_grows():
    ticks = list(range(80))
    births = [0] * 60 + [1] * 20
    h = _history(ticks, populations=[10] * 80, births=births)
    goal = episodes(h, "cell:0:0", "renew")[0]
    view = _view(**{"cell:0:0": {
        "population": 10, "pop_base": 12, "soil_fertility": 0.5,
        "food_stock": 200.0, "births_total": 1}})
    verdict = evaluate(goal, h, view, [], tick=85)
    assert verdict.status == "resolved_with_cost"
    assert verdict.solved is True
    assert verdict.births_close > verdict.births_open

    h2 = _history(ticks, populations=[10] * 60 + [12] * 20, births=births)
    verdict2 = evaluate(goal, h2, view, [], tick=85)
    assert verdict2.status == "resolved"


def test_a_renew_goal_never_becomes_transferred():
    """A birth stall is not a problem that "moves next door"."""
    ticks = list(range(80))
    births = [0] * 60 + [1] * 20
    pops = [10] * 60 + [12] * 20
    h = _history(ticks, populations=pops, births=births)
    goal = episodes(h, "cell:0:0", "renew")[0]
    view = _view(**{
        "cell:0:0": {"population": 12, "region": "region:0",
                     "cell_x": 0, "cell_y": 0},
        "cell:0:1": {"population": 10, "region": "region:0",
                     "cell_x": 1, "cell_y": 0},
    })
    from causal_world.observer.situation import Alert

    next_door = Alert(kind="birth_stall", scope="cell:0:1", severity=0.5,
                      since_tick=50, message="stall next door")
    verdict = evaluate(goal, h, view, [next_door], tick=85)
    assert verdict.status == "resolved"
    assert verdict.confidence == "established"


def test_the_settle_window_changes_the_verdict_and_that_is_measurable():
    """The v0.9 window is a parameter; the experiment can vary it."""
    pops = [10] * 20
    food = {t: (5.0 if t < 8 else 100.0) for t in range(20)}
    h = _history(list(range(20)), populations=pops,
                 births=[0] * 20, food=food)
    goal = episodes(h, "cell:0:0", "feed")[0]
    view = _view(**{"cell:0:0": {
        "population": 10, "pop_base": 10, "soil_fertility": 0.5,
        "food_stock": 100.0}})
    closed = goal.closed_tick
    early = evaluate(goal, h, view, [], tick=closed + 5, settle_ticks=20)
    late = evaluate(goal, h, view, [], tick=closed + 5, settle_ticks=50)
    assert early.status == "settling"
    assert late.status == "settling"  # neither has passed its own window
    at40 = evaluate(goal, h, view, [], tick=closed + 40, settle_ticks=20)
    at40_wide = evaluate(goal, h, view, [], tick=closed + 40, settle_ticks=50)
    assert at40.status == "resolved"
    assert at40_wide.status == "settling"


def test_transferred_is_marked_as_a_hypothesis():
    pops = [10] * 20
    food = {t: (5.0 if t < 8 else 100.0) for t in range(20)}
    h = _history(list(range(20)), populations=pops,
                 births=[0] * 20, food=food)
    goal = episodes(h, "cell:0:0", "feed")[0]
    view = _view(**{
        "cell:0:0": {"population": 10, "region": "region:0",
                     "cell_x": 0, "cell_y": 0},
        "cell:0:1": {"population": 10, "region": "region:0",
                     "cell_x": 1, "cell_y": 0},
    })
    from causal_world.observer.situation import Alert

    moved = Alert(kind="famine", scope="cell:0:1", severity=0.9,
                  since_tick=12, message="famine next door")
    verdict = evaluate(goal, h, view, [moved], tick=60)
    assert verdict.status == "transferred"
    assert verdict.confidence == "hypothesis"
    assert verdict.solved is False
    assert "не доказано" in verdict.to_dict()["reason"]


# ------------------------------------------------------------ the server


def test_the_server_offers_the_capacity_levers_and_shows_wild_land(tmp_path):
    from causal_world.server.session import Session

    session = Session(
        seed=7, ruleset="player_capacity", regions=2, agents=54,
        db_path=str(tmp_path / "cap.db"), max_ticks=200,
    )
    try:
        welcome = session.welcome()
        assert set(welcome["decree_card"]) == {0, 1, 2, 3, 4, 5}
        frame = session.decide(1, 6)
        world = frame["world"]
        assert len(world["cells"]) == 12
        wild = [c for c in world["cells"] if c["land_active"] == 0]
        assert len(wild) == 4
        assert all(c["capacity"] == 0 for c in wild)
        active = [c for c in world["cells"] if c["land_active"] == 1]
        assert all("limit" in c for c in active)
        assert isinstance(world["situations"], list)

        parcel = wild[0]["id"]
        frame = session.decide(
            2, 6, {"kind": 4, "target": parcel, "param": 0}
        )
        assert frame["decree"]["status"] == "accepted"
        assert frame["decree"]["name"] == "claim"
        frame = session.decide(3, 6)
        claimed = next(c for c in frame["world"]["cells"]
                       if c["id"] == parcel)
        assert claimed["land_active"] == 1
        assert claimed["capacity"] > 0
    finally:
        session.close()


def test_goals_feed_ignores_wild_land():
    sim, _channel, _system = _capacity_world()
    sim.run(60)
    view = StateView.from_state(sim.state)
    history = FieldHistory()
    for parcel in sim.state.entities_with_prefix("cell:"):
        for tick in range(0, sim.state.tick):
            for field_name in ("population", "food_stock",
                               "soil_fertility", "births_total"):
                history.add(parcel, field_name, tick,
                            sim.state.get(parcel, field_name))
    verdicts = goals(history, view, [], tick=sim.state.tick - 1)
    assert not any(v.goal.scope in set(_wild(sim)) for v in verdicts)
