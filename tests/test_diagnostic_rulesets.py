"""v0.3.1: each diagnostic ruleset severs exactly one link.

These tests pin the surgery itself — that the law change is precisely the
intended cut and nothing else:

* A ``iron_health``: no infection ever writes health/alive; infected agents
  lose no health outside starvation;
* B ``stable_soil``: soil fertility is never written after genesis;
* C ``no_hunger_immunity``: infect transitions read no hunger, and immunity
  updates follow the hunger-free law;
* control ``no_disease_control``: no disease operations at all;
* every diagnostic world is a deterministic replay of itself, consumes only
  dice drawn from the shared addressable stream, and leaves the DEFAULT
  world bit-identical (hashes pinned in test_immune_ruleset.py).
"""

from __future__ import annotations

from causal_world import create_world
from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.kernel.transition import TransitionStatus
from causal_world.systems.agents import AgentSystem
from causal_world.world.rules import RULESETS, get_ruleset

SMALL = dict(seed=7, regions=4, agents=50, ticks=250)

DIAGNOSTIC = [
    "iron_health",
    "stable_soil",
    "no_hunger_immunity",
    "no_disease_control",
]


def _committed(sim, system=None, operation=None):
    for tr in sim.journal.committed():
        if system is not None and tr.system != system:
            continue
        if operation is not None and tr.operation != operation:
            continue
        yield tr


# ----------------------------------------------------------------------
# registry
# ----------------------------------------------------------------------


def test_registry_has_all_diagnostic_rulesets():
    expected = {"default", "immune", *DIAGNOSTIC}
    assert expected <= set(RULESETS)
    versions = {name: get_ruleset(name).ruleset_version for name in expected}
    assert versions["iron_health"] == "0.3.1a"
    assert versions["stable_soil"] == "0.3.1b"
    assert versions["no_hunger_immunity"] == "0.3.1c"
    assert versions["no_disease_control"] == "0.3.1-ctrl"


# ----------------------------------------------------------------------
# experiment A — iron health
# ----------------------------------------------------------------------


def test_iron_health_infection_writes_no_health():
    sim = create_world(ruleset=get_ruleset("iron_health"), **SMALL)
    infects = list(_committed(sim, operation="disease.infect"))
    assert infects, "expected infections in the iron-health world"
    for tr in infects:
        fields = {w.field for w in tr.writes}
        assert fields == {"infected", "immune_memory"}, tr.id
        # the damage draw no longer exists — only the infection roll
        assert [d.index for d in tr.random_draws] == [0]


def test_iron_health_no_chronic_erosion_while_infected():
    sim = create_world(ruleset=get_ruleset("iron_health"), **SMALL)
    assert list(_committed(sim, operation="disease.infect")), \
        "expected infections in the iron-health world"
    health_transitions = 0
    for tr in _committed(sim, system="IronHealthAgentSystem"):
        if tr.operation not in ("agent.health", "agent.death"):
            continue
        infected = next(r.value for r in tr.reads if r.field == "infected")
        hunger = float(next(r.value for r in tr.reads if r.field == "hunger"))
        # infected and not starving => delta 0 => the frozen law would have
        # eroded −2.5, the iron law proposes nothing at all
        assert not (infected and hunger < 0.75), tr.id
        # every transition that exists is one of the hunger-driven laws
        old = float(next(r.value for r in tr.reads if r.field == "health"))
        health_write = next(w for w in tr.writes if w.field == "health")
        delta = -2.0 if hunger >= 0.75 else 1.5
        assert float(health_write.new) == max(0.0, min(100.0, old + delta)), tr.id
        health_transitions += 1
    assert health_transitions > 0


# ----------------------------------------------------------------------
# experiment B — stable soil
# ----------------------------------------------------------------------


def test_stable_soil_never_written_after_genesis():
    sim = create_world(ruleset=get_ruleset("stable_soil"), **SMALL)
    genesis_soil = {}
    for tr in _committed(sim, system="GenesisSystem"):
        for w in tr.writes:
            if w.field == "soil_fertility":
                genesis_soil[w.entity] = float(w.new)
    assert genesis_soil
    genesis_ids = {tr.id for tr in _committed(sim, system="GenesisSystem")}
    for tr in _committed(sim, operation="agriculture.harvest"):
        assert all(w.field == "food_stock" for w in tr.writes), tr.id
    for region, value in genesis_soil.items():
        assert sim.state.get(region, "soil_fertility") == value
        # provenance still points at genesis: nothing else ever wrote it
        assert sim.state.get_source(region, "soil_fertility") in genesis_ids


# ----------------------------------------------------------------------
# experiment C — no hunger -> immunity
# ----------------------------------------------------------------------


def test_no_hunger_immunity_infection_ignores_hunger():
    sim = create_world(ruleset=get_ruleset("no_hunger_immunity"), **SMALL)
    infects = list(_committed(sim, operation="disease.infect"))
    assert infects
    for tr in infects:
        assert all(r.field != "hunger" for r in tr.reads), tr.id


def test_no_hunger_immunity_immunity_law():
    sim = create_world(ruleset=get_ruleset("no_hunger_immunity"), **SMALL)

    def clamp01(x: float) -> float:
        return max(0.0, min(1.0, x))

    checked = 0
    for tr in _committed(sim, system="NoHungerErosionAgentSystem",
                         operation="agent.metabolism"):
        old = float(next(r.value for r in tr.reads if r.field == "immunity"))
        new = float(next(w.new for w in tr.writes if w.field == "immunity"))
        assert new == clamp01(old + 0.002 - 0.005 * old)
        checked += 1
    assert checked > 1000


def test_no_hunger_immunity_threshold_is_fed_constant():
    """Recompute one threshold: load * 0.35 * (1.25-imm) * 0.6 * (1-0.85m)."""
    sim = create_world(ruleset=get_ruleset("no_hunger_immunity"), **SMALL)
    tr = next(iter(_committed(sim, operation="disease.infect")))
    load = float(next(r.value for r in tr.reads if r.field == "disease_load"))
    immunity = float(next(r.value for r in tr.reads if r.field == "immunity"))
    memory = float(next(r.value for r in tr.reads if r.field == "immune_memory"))
    expected = min(0.85, load * 0.35 * (1.25 - immunity) * 0.6
                   * (1.0 - 0.85 * memory))
    roll = next(d for d in tr.random_draws if d.index == 0)
    assert roll.threshold == expected


# ----------------------------------------------------------------------
# control — no disease at all
# ----------------------------------------------------------------------


def test_no_disease_control_has_no_disease_operations():
    sim = create_world(ruleset=get_ruleset("no_disease_control"), **SMALL)
    systems = {s.name for s in sim.systems}
    assert systems == {"ClimateSystem", "AgricultureSystem", "AgentSystem"}
    assert not list(_committed(sim, operation="disease.infect"))
    assert not list(_committed(sim, operation="disease.environment"))
    for agent in sim.state.entities_with_prefix("agent:"):
        assert sim.state.get(agent, "infected") is False
        assert sim.state.get(agent, "immune_memory") is None


# ----------------------------------------------------------------------
# shared kernel properties across all diagnostic worlds
# ----------------------------------------------------------------------


def test_diagnostic_worlds_replay_bit_identically():
    for name in DIAGNOSTIC:
        a = create_world(ruleset=get_ruleset(name), **SMALL)
        b = create_world(ruleset=get_ruleset(name), **SMALL)
        assert a.state.hash() == b.state.hash(), name
        assert a.journal.hash() == b.journal.hash(), name


def test_diagnostic_worlds_consume_the_addressable_stream():
    """Every recorded draw equals the pure function of its address."""
    rules = get_ruleset("iron_health")
    purposes = PurposeRegistry()
    for p in sorted(rules.purposes):
        purposes.declare(p, rules.purposes[p])
    oracle = RandomSource(SMALL["seed"], "blake2b-v1", purposes)
    for name in DIAGNOSTIC:
        sim = create_world(ruleset=get_ruleset(name), **SMALL)
        rolls = 0
        for tr in sim.journal.committed():
            for d in tr.random_draws:
                assert d.value == oracle.draw(tr.tick, d.entity, d.purpose, d.index), (
                    name, tr.id, d.purpose, d.entity, d.index
                )
                rolls += 1
        assert rolls > 0, name


def test_immune_memory_still_teaches_in_A_and_C():
    """Memory mechanics survive the surgery in A and C (both keep memory)."""
    for name in ("iron_health", "no_hunger_immunity"):
        sim = create_world(ruleset=get_ruleset(name), **SMALL)
        grown = 0
        for tr in _committed(sim, operation="disease.infect"):
            mem = next(w for w in tr.writes if w.field == "immune_memory")
            assert float(mem.new) == min(1.0, float(mem.old) + 0.35)
            grown += 1
        assert grown > 0, name
