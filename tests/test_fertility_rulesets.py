"""v0.3.3: fertility maintenance laws are exactly their specifications.

* G ``compost`` — soil arithmetic with the population-fed recovery term;
* H ``three_field`` — staggered genesis, 200/100 cycle mechanics, fallow
  transitions carry no climate inputs and no crop draw;
* I ``fertile_migration`` — the written destination is exactly the max
  score over the reads; combined with fallow in the ``fertile_migration``
  ruleset, plain soil laws in ``fertile_migration_only``;
* shared contracts: deterministic replay, shared addressable draw stream,
  default world still bit-identical (the genesis info dict grew again).
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.systems.base import clamp
from causal_world.world.rules import RULESETS, get_ruleset

SEED = 7
FERTILITY_RULESETS = [
    "compost",
    "three_field",
    "fertile_migration",
    "fertile_migration_only",
]


def _committed(sim, operation=None, system=None):
    for tr in sim.journal.committed():
        if operation is not None and tr.operation != operation:
            continue
        if system is not None and tr.system != system:
            continue
        yield tr


def _reads(tr):
    return {(r.entity, r.field): r.value for r in tr.reads}


def _writes(tr):
    return {(w.entity, w.field): (w.old, w.new) for w in tr.writes}


# ----------------------------------------------------------------------
# registry
# ----------------------------------------------------------------------


def test_registry_has_all_fertility_rulesets():
    pairs = zip(
        FERTILITY_RULESETS, ("0.3.3g", "0.3.3h", "0.3.3i", "0.3.3i-plain")
    )
    for name, version in pairs:
        assert name in RULESETS
        assert get_ruleset(name).ruleset_version == version


# ----------------------------------------------------------------------
# G — compost
# ----------------------------------------------------------------------


def test_compost_soil_arithmetic():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=150,
                       ruleset=get_ruleset("compost"))
    checked = 0
    for tr in _committed(sim, operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        soil = float(rd[(region, "soil_fertility")])
        population = rd[(region, "population")]
        expected = clamp(soil - 0.0009 + population * 0.000018 * (1.0 - soil),
                         0.05, 1.0)
        new_soil = _writes(tr)[(region, "soil_fertility")][1]
        assert new_soil == expected, tr.id
        checked += 1
    assert checked > 300


# ----------------------------------------------------------------------
# H — three-field
# ----------------------------------------------------------------------


def test_three_field_genesis_staggered():
    sim = create_world(seed=SEED, regions=4, agents=50,
                       ruleset=get_ruleset("three_field"))
    streaks = {}
    for tr in _committed(sim, system="GenesisSystem", operation="genesis.region"):
        w = _writes(tr)
        region = next(e for e, _ in w if e.startswith("region:"))
        streak = w[(region, "cultivation_streak")][1]
        timer = w[(region, "fallow_timer")][1]
        assert isinstance(streak, int) and isinstance(timer, int)
        assert timer == 0
        streaks[region] = streak
    # stagger: (index * 200) // region_count
    assert streaks == {f"region:{i}": (i * 200) // 4 for i in range(4)}


def test_three_field_cycle_mechanics():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=260,
                       ruleset=get_ruleset("three_field"))
    harvests: dict[tuple[str, int], object] = {}
    flips = []
    for tr in _committed(sim, system="ThreeFieldAgricultureSystem",
                         operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        harvests[(region, tr.tick)] = tr
        if _writes(tr).get((region, "fallow_timer"), (None, None))[1] == 100:
            flips.append((region, tr))
    assert flips, "expected at least one forced-fallow flip"
    for region, flip in flips:
        rd = _reads(flip)
        # the flip happens exactly when the streak reaches the limit
        assert rd[(region, "cultivation_streak")] == 199
        assert rd[(region, "population")] > 0
        # nothing is grown on the flip tick: no climate inputs, no draw
        assert (region, "temperature") not in rd
        assert all(d.purpose != "agriculture.crop_variance"
                   for d in flip.random_draws)
        w = _writes(flip)
        assert w[(region, "cultivation_streak")][1] == 0
        old_soil = rd[(region, "soil_fertility")]
        assert w[(region, "soil_fertility")][1] == clamp(old_soil + 0.003,
                                                         0.05, 1.0)
        # the following 100 ticks count down and heal, still no crop draws
        t0 = flip.tick
        for t in range(t0 + 1, t0 + 101):
            tr = harvests[(region, t)]
            rd = _reads(tr)
            timer = rd[(region, "fallow_timer")]
            assert timer == t0 + 101 - t
            assert (region, "temperature") not in rd
            assert all(d.purpose != "agriculture.crop_variance"
                       for d in tr.random_draws)
            old_soil = rd[(region, "soil_fertility")]
            assert _writes(tr)[(region, "soil_fertility")][1] == clamp(
                old_soil + 0.003, 0.05, 1.0)


def test_three_field_streak_grows_while_farmed():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=30,
                       ruleset=get_ruleset("three_field"))
    prev = {}
    for tr in _committed(sim, system="ThreeFieldAgricultureSystem",
                         operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        streak = rd[(region, "cultivation_streak")]
        population = rd[(region, "population")]
        timer = rd[(region, "fallow_timer")]
        if timer == 0 and streak < 199:
            new_streak = _writes(tr)[(region, "cultivation_streak")][1]
            expected = streak + 1 if population > 0 else 0
            assert new_streak == expected, tr.id
        prev[region] = streak
    assert prev


# ----------------------------------------------------------------------
# I — fertile migration
# ----------------------------------------------------------------------


def test_fertile_migration_destination_is_the_max_score():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=400,
                       ruleset=get_ruleset("fertile_migration"))
    checked = 0
    for tr in _committed(sim, system="FertileMigrationAgentSystem",
                         operation="agent.migrate"):
        rd = _reads(tr)
        agent = next(e for e, _ in rd if e.startswith("agent:"))
        origin = rd[(agent, "region")]
        scores = {}
        for region in {e for e, _ in rd if e.startswith("region:")}:
            if region == origin:
                continue
            score = (float(rd[(region, "soil_fertility")])
                     * float(rd[(region, "food_stock")])
                     / max(rd[(region, "population")], 1))
            scores[region] = score
        assert scores
        # strict > over sorted iteration: first max in sort order wins ties
        expected = max(sorted(scores), key=lambda r: scores[r])
        written = _writes(tr)[(agent, "region")][1]
        assert written == expected, tr.id
        # the migration gate roll is unchanged
        assert [d.index for d in tr.random_draws] == [0]
        checked += 1
    assert checked > 0


def test_fertile_migration_only_keeps_frozen_soil():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=60,
                       ruleset=get_ruleset("fertile_migration_only"))
    systems = {s.name for s in sim.systems}
    assert "AgricultureSystem" in systems
    assert "FallowAgricultureSystem" not in systems
    for tr in _committed(sim, operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        soil = float(rd[(region, "soil_fertility")])
        new_soil = _writes(tr)[(region, "soil_fertility")][1]
        assert new_soil == clamp(soil - 0.0012 + 0.0003, 0.05, 1.0), tr.id


# ----------------------------------------------------------------------
# shared contracts
# ----------------------------------------------------------------------


def test_fertility_worlds_replay_bit_identically():
    for name in FERTILITY_RULESETS:
        a = create_world(seed=SEED, regions=4, agents=50, ticks=120,
                         ruleset=get_ruleset(name))
        b = create_world(seed=SEED, regions=4, agents=50, ticks=120,
                         ruleset=get_ruleset(name))
        assert a.state.hash() == b.state.hash(), name
        assert a.journal.hash() == b.journal.hash(), name


def test_fertility_worlds_consume_the_addressable_stream():
    rules = get_ruleset("compost")
    purposes = PurposeRegistry()
    for p in sorted(rules.purposes):
        purposes.declare(p, rules.purposes[p])
    oracle = RandomSource(SEED, "blake2b-v1", purposes)
    for name in FERTILITY_RULESETS:
        sim = create_world(seed=SEED, regions=4, agents=50, ticks=80,
                           ruleset=get_ruleset(name))
        rolls = 0
        for tr in sim.journal.committed():
            for d in tr.random_draws:
                assert d.value == oracle.draw(tr.tick, d.entity, d.purpose,
                                              d.index), (
                    name, tr.id, d.purpose, d.entity, d.index
                )
                rolls += 1
        assert rolls > 0, name


def test_default_world_still_bit_identical_after_info_growth():
    sim = create_world(seed=42, ticks=100)
    assert sim.state.hash() == (
        "97d61d4274e4bfb4b6b3b2ae283d9f52fa9614d43a33e93525a960bd0f907148"
    )
    assert sim.journal.hash() == (
        "18ac15fbf7a37a31aea9698b46ec29f8405a8227449485dfb52db36dde2f30db"
    )
