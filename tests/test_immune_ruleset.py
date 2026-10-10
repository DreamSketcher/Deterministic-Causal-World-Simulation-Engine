"""v0.3: the immune-memory ruleset is a change of LAWS, not of kernel.

The frozen v0.1 kernel must run the immune world without modification;
everything below pins that contract:

* the DEFAULT world stays bit-identical (state and journal hashes) —
  the genesis hook adds nothing when the ruleset declares nothing;
* the immune world is a fully deterministic replay of itself;
* ``immune_memory`` is born naive (0.0), grows by exactly +0.35 per
  infection, atomically inside the SAME committed transition that writes
  ``infected``/``health`` (provenance points back to it);
* regions never acquire the field;
* both rulesets consume the SAME addressable draw stream under one seed —
  same purposes, same (tick, entity, purpose, index) addresses;
* the schema invariant (immune_memory in [0, 1]) rejects rogue writes.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.kernel.transition import (
    StateChange,
    Transition,
    TransitionStatus,
)
from causal_world.world.rules import (
    RULESETS,
    DefaultWorldRules,
    ImmuneMemoryRules,
    get_ruleset,
)

# Pinned identity of the default world (seed 42, 2x10, 100 ticks) as of the
# v0.2 freeze commit fb59a2c. Any hook that leaks into the default world
# breaks these.
DEFAULT_STATE_HASH = (
    "97d61d4274e4bfb4b6b3b2ae283d9f52fa9614d43a33e93525a960bd0f907148"
)
DEFAULT_JOURNAL_HASH = (
    "18ac15fbf7a37a31aea9698b46ec29f8405a8227449485dfb52db36dde2f30db"
)


def _immune_world(ticks: int = 600):
    return create_world(
        seed=7, regions=4, agents=50, ticks=ticks, ruleset=get_ruleset("immune")
    )


# ----------------------------------------------------------------------
# the ruleset registry
# ----------------------------------------------------------------------


def test_ruleset_registry():
    assert {"default", "immune"} <= set(RULESETS)
    assert isinstance(get_ruleset("default"), DefaultWorldRules)
    assert isinstance(get_ruleset("immune"), ImmuneMemoryRules)
    assert get_ruleset("immune").ruleset_version == "0.3.0"
    with pytest.raises(KeyError):
        get_ruleset("does-not-exist")


def test_immune_world_runs_the_immune_disease_system():
    sim = _immune_world(ticks=10)
    names = [s.name for s in sim.systems]
    assert "ImmuneDiseaseSystem" in names
    assert "DiseaseSystem" not in names


# ----------------------------------------------------------------------
# the default world must not notice the hook
# ----------------------------------------------------------------------


def test_default_world_bit_identical():
    sim = create_world(seed=42, ticks=100)
    assert sim.state.hash() == DEFAULT_STATE_HASH
    assert sim.journal.hash() == DEFAULT_JOURNAL_HASH


def test_default_genesis_has_no_immune_memory():
    sim = create_world(seed=42, ticks=10)
    for entity in sim.state.entities_with_prefix("agent:"):
        assert sim.state.get(entity, "immune_memory") is None


# ----------------------------------------------------------------------
# determinism of the immune world itself
# ----------------------------------------------------------------------


def test_immune_world_replay_identical():
    sim1 = _immune_world(ticks=300)
    sim2 = _immune_world(ticks=300)
    assert sim1.state.hash() == sim2.state.hash()
    assert sim1.journal.hash() == sim2.journal.hash()
    assert sim1.state.provenance == sim2.state.provenance


# ----------------------------------------------------------------------
# immune memory mechanics
# ----------------------------------------------------------------------


def test_genesis_is_naive_and_regions_fieldless():
    sim = create_world(
        seed=7, regions=4, agents=50, ruleset=get_ruleset("immune")
    )  # ticks=0: genesis only, nothing has happened yet
    agents = sorted(sim.state.entities_with_prefix("agent:"))
    assert len(agents) == 50
    for a in agents:
        assert sim.state.get(a, "immune_memory") == 0.0
    # the genesis transitions committed immune_memory=0.0 for every agent
    genesis_writes = 0
    for tr in sim.journal.all():
        if tr.system == "GenesisSystem" and tr.operation == "genesis.agent":
            mem = [w for w in tr.writes if w.field == "immune_memory"]
            assert len(mem) == 1 and mem[0].new == 0.0
            genesis_writes += 1
    assert genesis_writes == 50
    for r in sim.state.entities_with_prefix("region:"):
        assert sim.state.get(r, "immune_memory") is None


def test_memory_grows_atomically_in_the_infect_transition():
    sim = _immune_world()
    infects = [
        tr
        for tr in sim.journal.committed()
        if tr.system == "ImmuneDiseaseSystem" and tr.operation == "disease.infect"
    ]
    assert infects, "expected infections in the immune world"
    last_writer: dict[str, int] = {}
    for tr in infects:
        by_field = {w.field: w for w in tr.writes}
        assert by_field["infected"].new is True
        assert "health" in by_field
        mem = by_field["immune_memory"]
        expected = min(1.0, float(mem.old) + 0.35)
        assert mem.new == pytest.approx(expected)
        owner = by_field["infected"].entity
        last_writer[owner] = tr.id
    # provenance: each surviving memory points back at its last writer
    for owner, tr_id in last_writer.items():
        if sim.state.get(owner, "alive"):
            assert sim.state.provenance[(owner, "immune_memory")] == tr_id


def test_memory_monotone_and_bounded_per_agent():
    sim = _immune_world()
    series: dict[str, list[float]] = {}
    for tr in sim.journal.committed():
        if tr.system != "ImmuneDiseaseSystem" or tr.operation != "disease.infect":
            continue
        for w in tr.writes:
            if w.field == "immune_memory":
                series.setdefault(w.entity, []).append(float(w.new))
    assert series
    for entity, values in series.items():
        assert all(0.0 <= v <= 1.0 for v in values), entity
        assert all(b >= a for a, b in zip(values, values[1:])), entity
        assert values[0] == pytest.approx(0.35)


def test_memory_attenuates_damage_relative_to_naive_law():
    """Same damage draw, memory m: damage * (1 - 0.60 m) <= naive damage."""
    sim = _immune_world()
    checked = 0
    for tr in sim.journal.committed():
        if tr.system != "ImmuneDiseaseSystem" or tr.operation != "disease.infect":
            continue
        mem_old = next(
            float(r.value) for r in tr.reads if r.field == "immune_memory"
        )
        if mem_old <= 0.0:
            continue
        damage_draw = next(d for d in tr.random_draws if d.index == 1)
        health_write = next(w for w in tr.writes if w.field == "health")
        health_read = next(r for r in tr.reads if r.field == "health")
        if float(health_write.new) == 0.0:
            continue  # lethal hit clamps health; damage itself is unobservable
        naive = (6.0 + 10.0 * damage_draw.value)
        actual = float(health_read.value) - float(health_write.new)
        expected = naive * (1.0 - 0.60 * mem_old)
        assert actual == pytest.approx(expected, abs=1e-9)
        assert actual <= naive + 1e-12
        checked += 1
    assert checked > 0


# ----------------------------------------------------------------------
# same dice, different laws
# ----------------------------------------------------------------------


def test_same_draw_stream_as_the_baseline_ruleset():
    default_rules, immune_rules = get_ruleset("default"), get_ruleset("immune")
    assert default_rules.rng_version == immune_rules.rng_version == "blake2b-v1"
    # every purpose the immune world draws from exists in BOTH rulesets
    for purpose in sorted(immune_rules.purposes):
        assert purpose in default_rules.purposes

    def source(rules):
        purposes = PurposeRegistry()
        for purpose in sorted(rules.purposes):
            purposes.declare(purpose, rules.purposes[purpose])
        return RandomSource(7, rules.rng_version, purposes)

    r_default, r_immune = source(default_rules), source(immune_rules)
    for tick in (1, 5, 42):
        for entity in ("agent:0", "agent:13", "region:1"):
            for purpose in ("disease.infection", "disease.recovery"):
                for index in (0, 1):
                    assert r_default.draw(tick, entity, purpose, index) == \
                        r_immune.draw(tick, entity, purpose, index)


def test_immune_world_consumes_the_baseline_draw_stream():
    """Every recorded roll in the immune world equals the pure addressable
    function blake2b(seed|tick|entity|purpose|index) — i.e. the immune world
    consumes exactly the stream the baseline world would consume. Outcomes
    still diverge (thresholds/history change with the laws); that divergence
    is precisely attributable to the laws, not to different dice."""
    purposes = PurposeRegistry()
    for p in sorted(get_ruleset("immune").purposes):
        purposes.declare(p, get_ruleset("immune").purposes[p])
    oracle = RandomSource(7, "blake2b-v1", purposes)

    sim = _immune_world()
    rolls_checked = 0
    for tr in sim.journal.committed():
        for d in tr.random_draws:
            assert d.value == oracle.draw(tr.tick, d.entity, d.purpose, d.index), (
                tr.id, d.purpose, d.entity, d.index
            )
            rolls_checked += 1
    assert rolls_checked > 1000


# ----------------------------------------------------------------------
# schema invariant enforced by the ruleset, not the kernel
# ----------------------------------------------------------------------


def test_immune_memory_out_of_range_is_rejected_by_the_ruleset():
    sim = _immune_world(ticks=5)
    rules = sim.rules
    rogue = Transition(
        id=None,
        tick=sim.state.tick + 1,
        system="disease",
        operation="infect",
        writes=[
            StateChange(entity="agent:0", field="immune_memory",
                        old=0.7, new=1.5),
        ],
    )
    violations = rules.validate_transition(rogue, sim.snapshot())
    assert any("immune_memory" in v for v in violations)

    legal = Transition(
        id=None,
        tick=sim.state.tick + 1,
        system="disease",
        operation="infect",
        writes=[
            StateChange(entity="agent:0", field="immune_memory",
                        old=0.7, new=1.0),
        ],
    )
    assert not [v for v in rules.validate_transition(legal, sim.snapshot())
                if "immune_memory" in v]


def test_default_ruleset_does_not_know_immune_memory():
    """The frozen default rules keep their original schema: the new field
    belongs to the proposal, not to the baseline world."""
    assert DefaultWorldRules().field_type("immune_memory") is None
    assert ImmuneMemoryRules().field_type("immune_memory") is float
