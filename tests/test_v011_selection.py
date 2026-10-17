"""v0.11 — the two choices inside a resettlement order, pinned.

A resettlement order is not one decision but three, and only the first
belongs to the player: WHERE (the destination), HOW MANY (the count) and
WHO (the world's donor and mover policy). The v0.11 report measured the
first two. This module pins the third before the v0.12 scaling work, as
the review asked: the extreme cases must be facts in tests, not
assumptions in prose.

What is pinned here:

* the mover policy of the world is "least hungry first, ties by id", and
  it does not look at age — so a child can be sent (a measured
  limitation, not an accident);
* the donor policy is a total order: largest surplus, then shortest
  distance, then id, and a cell with one person is never a donor;
* an order never empties its source: the source keeps at least one
  person even when the order asks for everybody;
* the default policy is one method (``_choose_movers``), so an
  experiment can compare another policy by overriding ONE thing.
"""

from __future__ import annotations

from causal_world import create_world
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.systems.directive import (
    DIRECTIVE_CLAIM,
    DIRECTIVE_RESETTLE,
    Directive,
    DirectiveChannel,
)
from causal_world.systems.resettle import ResettlementDirectiveSystem
from causal_world.world.rules import get_ruleset


# --------------------------------------------------------------- helpers


class _Snap:
    """The read API the policies use: ``get(entity, field)``."""

    def __init__(self, rows: dict[tuple[str, str], object]):
        self.rows = rows

    def get(self, entity: str, field: str, default=None):
        return self.rows.get((entity, field), default)


class _Ctx:
    """The only part of SystemContext the donor policy touches."""

    def __init__(self, cells: list[str]):
        self._cells = cells

    def entities(self, prefix: str) -> list[str]:
        return [c for c in self._cells if c.startswith(prefix)]


def _cell(rows, cell, *, region="region:0", x=0, y=0, population=4,
          pop_base=3, soil=0.5, food=100.0, active=1):
    rows[(cell, "region")] = region
    rows[(cell, "cell_x")] = x
    rows[(cell, "cell_y")] = y
    rows[(cell, "population")] = population
    rows[(cell, "pop_base")] = pop_base
    rows[(cell, "soil_fertility")] = soil
    rows[(cell, "food_stock")] = food
    rows[(cell, "land_active")] = active


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


def _pops(sim) -> dict[str, int]:
    return {
        c: int(sim.state.get(c, "population"))
        for c in sim.state.entities_with_prefix("cell:")
    }


def _claim_and_resettle(sim, channel, parcel: str, movers: int = 0):
    channel.schedule(1, Directive(DIRECTIVE_CLAIM, parcel, 0))
    channel.schedule(2, Directive(DIRECTIVE_RESETTLE, parcel, movers))
    sim.step()  # tick 0
    sim.step()  # tick 1: the claim
    before = _pops(sim)
    sim.step()  # tick 2: the resettlement
    return before


# ------------------------------------------------------- the mover policy


def test_the_default_mover_policy_is_least_hungry_then_id():
    system = ResettlementDirectiveSystem()
    snapshot = _Snap({
        ("agent:0", "hunger"): 0.9,
        ("agent:1", "hunger"): 0.2,
        ("agent:2", "hunger"): 0.2,
        ("agent:3", "hunger"): 0.5,
    })
    order = system._choose_movers(
        ["agent:0", "agent:1", "agent:2", "agent:3"], snapshot
    )
    assert order == ["agent:1", "agent:2", "agent:3", "agent:0"]


def test_the_mover_policy_does_not_look_at_age_so_a_child_can_be_sent():
    system = ResettlementDirectiveSystem()
    rows = {
        ("agent:child", "hunger"): 0.1,
        ("agent:adult", "hunger"): 0.8,
        # birth_tick exists but the policy must not need it
        ("agent:child", "birth_tick"): 90,
        ("agent:adult", "birth_tick"): 0,
    }
    snapshot = _Snap(rows)
    order = system._choose_movers(["agent:adult", "agent:child"], snapshot)
    assert order == ["agent:child", "agent:adult"]
    # and the answer does not depend on the tick: age is not an input
    snapshot.rows[("agent:child", "birth_tick")] = 100
    assert system._choose_movers(
        ["agent:adult", "agent:child"], snapshot
    ) == ["agent:child", "agent:adult"]


def test_the_policy_is_one_method_so_an_experiment_can_override_it():
    system = ResettlementDirectiveSystem()
    snapshot = _Snap({
        ("agent:0", "hunger"): 0.9,
        ("agent:1", "hunger"): 0.2,
    })
    assert system._choose_movers(["agent:0", "agent:1"], snapshot) == [
        "agent:1", "agent:0"
    ]
    # the experiment's policy: the hungriest first (a deliberately bad
    # rule) — one method, no change to the world's default
    system._choose_movers = lambda agents, snap: sorted(
        agents, key=lambda a: (-float(snap.get(a, "hunger") or 0.0), a)
    )
    assert system._choose_movers(["agent:0", "agent:1"], snapshot) == [
        "agent:0", "agent:1"
    ]


# ------------------------------------------------------- the donor policy


def _donor_order(rows, cells, target="cell:0:9", region="region:0"):
    system = ResettlementDirectiveSystem()
    _cell(rows, target, region=region, x=0, y=0, population=0, pop_base=3,
          soil=0.5, food=100.0)
    return system._donors(_Snap(rows), region, target, _Ctx(cells + [target]))


def test_the_donor_ranking_is_surplus_then_distance_then_id():
    rows: dict[tuple[str, str], object] = {}
    cells = []
    # a: surplus 1, distance 1
    _cell(rows, "cell:0:0", x=1, y=0, population=4, pop_base=3, soil=0.0)
    # b: surplus 3, distance 3
    _cell(rows, "cell:0:1", x=3, y=0, population=6, pop_base=3, soil=0.0)
    # c: surplus 3, distance 3 (same as b, larger id)
    _cell(rows, "cell:0:2", x=0, y=3, population=6, pop_base=3, soil=0.0)
    # d: surplus 3, distance 2
    _cell(rows, "cell:0:3", x=0, y=2, population=6, pop_base=3, soil=0.0)
    cells = ["cell:0:0", "cell:0:1", "cell:0:2", "cell:0:3"]
    order = _donor_order(rows, cells)
    assert [row[0] for row in order] == [
        "cell:0:3",  # same surplus, shortest distance
        "cell:0:1",  # same surplus and distance as cell:0:2, smaller id
        "cell:0:2",
        "cell:0:0",
    ]


def test_a_cell_with_one_person_is_never_a_donor():
    rows: dict[tuple[str, str], object] = {}
    _cell(rows, "cell:0:0", x=1, y=0, population=1, pop_base=0, soil=0.0)
    _cell(rows, "cell:0:1", x=2, y=0, population=2, pop_base=0, soil=0.0)
    order = _donor_order(rows, ["cell:0:0", "cell:0:1"])
    assert [row[0] for row in order] == ["cell:0:1"]


def test_a_cell_outside_the_region_is_never_a_donor():
    rows: dict[tuple[str, str], object] = {}
    _cell(rows, "cell:1:0", region="region:1", x=1, y=0, population=9,
          pop_base=3, soil=0.0)
    order = _donor_order(rows, ["cell:1:0"])
    assert order == []


# ---------------------------------------------------- the order's invariant


def test_an_order_never_empties_its_source_even_when_it_asks_for_all():
    sim, channel, _system = _world()
    parcel = "cell:0:4"
    before = _claim_and_resettle(sim, channel, parcel, movers=999)
    moved = int(sim.state.get(parcel, "resettle_moved"))
    source = sim.state.get(parcel, "last_source")
    assert moved >= 1
    assert source in before
    assert before[source] - moved >= 1
    assert int(sim.state.get(source, "population")) >= 1
    # the move is exactly what the source lost (no hidden loss elsewhere)
    assert int(sim.state.get(source, "population")) == before[source] - moved


def test_the_source_that_pays_is_recorded_and_recoverable():
    sim, channel, _system = _world()
    parcel = "cell:0:4"
    _claim_and_resettle(sim, channel, parcel, movers=0)
    source = sim.state.get(parcel, "last_source")
    assert source.startswith("cell:")
    assert int(sim.state.get(source, "resettled_out")) >= 1
    assert int(sim.state.get(parcel, "resettled_in")) >= 1
