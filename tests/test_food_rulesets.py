"""v0.3.2: the three food-side mechanisms are exactly their laws.

The diagnosis (v0.3.1) put the bottleneck in the soil clock. These rulesets
keep the clock and test whether a realistic food-side law lets the world
live with it. Each test pins the law change itself:

* D ``fallow``: abandoned regions recover, farmed regions degrade as frozen;
* E ``storage``: spoilage rate follows the stock-size law, arithmetic exact;
* F ``crop_rotation``: the workforce statistic updates exactly, and the
  degradation multiplier follows the stability penalty;
* plus the shared kernel contract: deterministic replay, shared addressable
  draw stream, and the default world still bit-identical (pinned in
  test_immune_ruleset.py — the generator hook gained an ``info`` argument).
"""

from __future__ import annotations

import math

import pytest

from causal_world import create_world
from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.systems.base import clamp
from causal_world.world.rules import RULESETS, get_ruleset

SEED = 7
FOOD_RULESETS = ["fallow", "storage", "crop_rotation"]


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


def test_registry_has_all_food_rulesets():
    for name, version in zip(FOOD_RULESETS, ("0.3.2d", "0.3.2e", "0.3.2f")):
        assert name in RULESETS
        assert get_ruleset(name).ruleset_version == version


# ----------------------------------------------------------------------
# D — fallow recovery
# ----------------------------------------------------------------------


def test_fallow_unfarmed_regions_recover():
    # No agents at all: every region is abandoned from genesis.
    sim = create_world(seed=SEED, regions=4, agents=0, ticks=100,
                       ruleset=get_ruleset("fallow"))
    genesis = {}
    for tr in _committed(sim, system="GenesisSystem"):
        for w in tr.writes:
            if w.field == "soil_fertility":
                genesis[w.entity] = float(w.new)
    assert genesis
    for region, soil0 in genesis.items():
        expected = min(1.0, soil0 + 100 * 0.0015)
        assert sim.state.get(region, "soil_fertility") == pytest.approx(
            expected, abs=1e-12), region
        assert sim.state.get(region, "soil_fertility") > soil0


def test_fallow_farmed_regions_degrade_as_frozen():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=50,
                       ruleset=get_ruleset("fallow"))
    checked = 0
    for tr in _committed(sim, operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        population = rd[(region, "population")]
        old_soil = rd[(region, "soil_fertility")]
        new_soil = _writes(tr)[(region, "soil_fertility")][1]
        if population > 0:
            assert new_soil == clamp(old_soil - 0.0012 + 0.0003, 0.05, 1.0), tr.id
            checked += 1
    assert checked > 100


# ----------------------------------------------------------------------
# E — stock-dependent spoilage
# ----------------------------------------------------------------------


def test_storage_spoilage_arithmetic():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=200,
                       ruleset=get_ruleset("storage"))
    saw_full_rate = saw_reduced = saw_surplus = False
    for tr in _committed(sim, operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        food = float(rd[(region, "food_stock")])
        population = rd[(region, "population")]
        soil = float(rd[(region, "soil_fertility")])
        workers = rd[(region, "workers")]
        temperature = float(rd[(region, "temperature")])
        rainfall = float(rd[(region, "rainfall")])
        cv_draw = next(d for d in tr.random_draws
                       if d.purpose == "agriculture.crop_variance")

        temp_factor = max(0.0, 1.0 - abs(temperature - 16.0) / 14.0)
        rain_factor = clamp(rainfall / 0.55, 0.0, 1.3)
        harvest = 3.6 * temp_factor * rain_factor * soil * workers * \
            (0.75 + 0.5 * cv_draw.value)

        pop_eff = max(population, 1)
        rate = 0.02 * min(1.0, food / (pop_eff * 50.0))
        if food > 10.0 * pop_eff:
            rate = max(rate, 0.04)
        if rate >= 0.04:
            saw_surplus = True
        elif rate >= 0.02 - 1e-12:
            saw_full_rate = True
        else:
            saw_reduced = True

        expected = max(0.0, food + harvest - rate * food - 1.1 * population)
        new_food = _writes(tr)[(region, "food_stock")][1]
        assert new_food == expected, tr.id
    # the run exercises at least the surplus and reduced regimes
    assert saw_surplus and saw_reduced


# ----------------------------------------------------------------------
# F — crop rotation
# ----------------------------------------------------------------------


def test_rotation_genesis_initializes_the_statistic():
    sim = create_world(seed=SEED, regions=4, agents=50, ruleset=get_ruleset("crop_rotation"))
    for tr in _committed(sim, system="GenesisSystem", operation="genesis.region"):
        w = _writes(tr)
        region = next(e for e, _ in w if e.startswith("region:"))
        pop = float(w[(region, "population")][1])
        assert w[(region, "labor_ema")][1] == pop
        assert w[(region, "labor_ema2")][1] == pop * pop


def test_rotation_statistic_and_penalty_exact():
    sim = create_world(seed=SEED, regions=4, agents=50, ticks=120,
                       ruleset=get_ruleset("crop_rotation"))
    first_seen_penalty = None
    checked = 0
    for tr in _committed(sim, operation="agriculture.harvest"):
        rd = _reads(tr)
        region = next(e for e, _ in rd if e.startswith("region:"))
        workers = float(rd[(region, "workers")])
        population = rd[(region, "population")]
        soil = float(rd[(region, "soil_fertility")])
        ema_old = float(rd[(region, "labor_ema")])
        ema2_old = float(rd[(region, "labor_ema2")])

        ema = 0.9 * ema_old + 0.1 * workers
        ema2 = 0.9 * ema2_old + 0.1 * workers * workers
        variance = max(0.0, ema2 - ema * ema)
        cv = math.sqrt(variance) / max(ema, 1.0)
        penalty = 1.0 + 0.5 * (1.0 - min(1.0, cv))
        degradation = 0.0009 * (workers / max(population, 1)) * penalty
        expected_soil = clamp(soil - degradation + 0.0003, 0.05, 1.0)

        w = _writes(tr)
        assert w[(region, "labor_ema")][1] == ema, tr.id
        assert w[(region, "labor_ema2")][1] == ema2, tr.id
        assert w[(region, "soil_fertility")][1] == expected_soil, tr.id
        if first_seen_penalty is None:
            # born stable: cv=0, monoculture penalty at maximum
            first_seen_penalty = penalty
        checked += 1
    assert checked > 200
    assert first_seen_penalty == 1.5


# ----------------------------------------------------------------------
# shared kernel contract
# ----------------------------------------------------------------------


def test_food_worlds_replay_bit_identically():
    for name in FOOD_RULESETS:
        a = create_world(seed=SEED, regions=4, agents=50, ticks=120,
                         ruleset=get_ruleset(name))
        b = create_world(seed=SEED, regions=4, agents=50, ticks=120,
                         ruleset=get_ruleset(name))
        assert a.state.hash() == b.state.hash(), name
        assert a.journal.hash() == b.journal.hash(), name


def test_food_worlds_consume_the_addressable_stream():
    rules = get_ruleset("fallow")
    purposes = PurposeRegistry()
    for p in sorted(rules.purposes):
        purposes.declare(p, rules.purposes[p])
    oracle = RandomSource(SEED, "blake2b-v1", purposes)
    for name in FOOD_RULESETS:
        sim = create_world(seed=SEED, regions=4, agents=50, ticks=80,
                           ruleset=get_ruleset(name))
        rolls = 0
        for tr in sim.journal.committed():
            for d in tr.random_draws:
                assert d.value == oracle.draw(tr.tick, d.entity, d.purpose, d.index), (
                    name, tr.id, d.purpose, d.entity, d.index
                )
                rolls += 1
        assert rolls > 0, name


def test_default_world_still_bit_identical_after_hook_change():
    sim = create_world(seed=42, ticks=100)
    assert sim.state.hash() == (
        "97d61d4274e4bfb4b6b3b2ae283d9f52fa9614d43a33e93525a960bd0f907148"
    )
    assert sim.journal.hash() == (
        "18ac15fbf7a37a31aea9698b46ec29f8405a8227449485dfb52db36dde2f30db"
    )
