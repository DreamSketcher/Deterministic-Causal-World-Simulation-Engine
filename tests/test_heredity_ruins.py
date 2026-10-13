"""v0.6 step 2: heredity, world memory, exploration, senescence — mechanisms.

These are LAW tests built on ``make_sim`` (hand-built genesis state), so each
mechanism is isolated from the long-run compost ecology (the drift/extinction
dynamics are the subject of ``experiments/reports/v06_living_world.md`` and
are too slow for the suite at ~20 ms/tick). What is pinned here:

* BirthSystem: gating (maturity, capacity, food floor, pool) and EXACT
  inheritance formulas, determinism;
* RuinSystem: the ``was_alive`` state machine — activate on the TRANSITION
  into extinction, persist while repopulated (no aging), reset on
  re-extinction, and NO oscillation (the bug regression: activate once, then
  age; a starved ruin still seeds MIN_RUIN_FOOD, so it cannot insta-collapse);
* ExplorationSystem (forced scenario, Decision 3): an agent co-located with
  an active ruin explores it; the bonus and the draw-down land in the causal
  trace; exploring a ruin to empty makes it collapse and stay collapsed;
* SenescenceSystem: nobody dies before ``SENESCENCE_ONSET``; after it,
  age-death fires deterministically and writes ``alive False`` + ``health 0``;
* ruleset separation: research worlds never name the four game systems.
"""

from __future__ import annotations

import collections

from causal_world import create_world
from causal_world.systems.base import System
from causal_world.systems.birth import BirthSystem
from causal_world.systems.exploration import ExplorationSystem
from causal_world.systems.ruin import RuinSystem
from causal_world.systems.senescence import SenescenceSystem
from causal_world.world.rules import get_ruleset
from helpers import RulesForTest, make_sim

# ---------------------------------------------------------------- scaffolding

_SCENARIO_PURPOSES = {
    p: "v0.6 step-2 scenario draw"
    for p in (
        "birth.occurrence",
        "birth.select",
        "birth.parent",
        "birth.mutation",
        "agent.explore",
        "agent.senescence",
    )
}

_SCHEMA = {
    # agent
    "alive": bool,
    "region": str,
    "hunger": float,
    "health": float,
    "immune_memory": float,
    "immunity": float,
    "max_health": float,
    "risk_tolerance": float,
    "generation": int,
    "birth_tick": int,
    "parent_id": str,
    "infected": bool,
    # region
    "population": int,
    "pop_base": int,
    "soil_fertility": float,
    "food_stock": float,
    # ruin
    "active": bool,
    "was_alive": bool,
    "type": str,
    "age": int,
    "resource_food": float,
    "resource_knowledge": float,
}


class Step2Rules(RulesForTest):
    """Test ruleset carrying every purpose the v0.6 systems may draw from."""

    ruleset_version = "step2-test"
    purposes = _SCENARIO_PURPOSES


def _rules():
    return Step2Rules(_SCHEMA, non_negative={"hunger", "resource_food"})


def _agent(i, *, alive=True, region="region:0", mem=0.8, hp=90.0,
           risk=0.6, gen=0, birth_tick=0, hunger=0.2, health=100.0):
    """Full genesis field map for one agent (live or dormant placeholder)."""
    dormant = not alive and region == "none"
    return {
        (f"agent:{i}", "alive"): alive,
        (f"agent:{i}", "region"): region,
        (f"agent:{i}", "immune_memory"): mem if not dormant else 0.0,
        (f"agent:{i}", "immunity"): 0.7 if not dormant else 0.0,
        (f"agent:{i}", "max_health"): hp if not dormant else 0.0,
        (f"agent:{i}", "risk_tolerance"): risk,
        (f"agent:{i}", "generation"): gen,
        (f"agent:{i}", "birth_tick"): birth_tick,
        (f"agent:{i}", "parent_id"): "none",
        (f"agent:{i}", "infected"): False,
        (f"agent:{i}", "hunger"): hunger,
        (f"agent:{i}", "health"): health,
    }


def _region(pop=5, pop_base=5, soil=0.5, food=100.0, name="region:0"):
    return {
        (name, "population"): pop,
        (name, "pop_base"): pop_base,
        (name, "soil_fertility"): soil,
        (name, "food_stock"): food,
    }


def _ruin(active=False, was_alive=False, res=10.0, age=0, r=0,
          rtype="", rname="ruin:0:0", region="region:0"):
    return {
        (rname, "region"): region,
        (rname, "active"): active,
        (rname, "was_alive"): was_alive,
        (rname, "type"): rtype,
        (rname, "age"): age,
        (rname, "resource_food"): res,
        (rname, "resource_knowledge"): 0.0,
    }


def _ops(sim):
    # genesis transitions are not system behaviour; exclude them
    return collections.Counter(
        t.operation for t in sim.journal.all() if not t.operation.startswith("genesis")
    )


class ScriptedRegion(System):
    """Test-only census: overrides ``region:0.population`` on plan ticks."""

    name = "ScriptedRegion"
    priority = 1  # like AgentSystem's census: before RuinSystem(31)

    def __init__(self, plan: dict[int, int]):
        self.plan = dict(plan)

    def compute(self, snapshot, rng, context):
        value = self.plan.get(snapshot.tick)
        if value is None:
            return []
        b = context.builder("test.census")
        b.write("region:0", "population", value)
        return [b.build()]


def _births(sim):
    """Child field maps from committed ``agent.birth`` transitions."""
    out = []
    for t in sim.journal.all():
        if t.operation != "agent.birth":
            continue
        per = collections.defaultdict(dict)
        for c in t.writes:
            per[c.entity][c.field] = c.new
        for entity, fields in per.items():
            out.append((t.tick, entity, fields))
    return out


# --------------------------------------------------------------------- birth


def _birth_world(*, pop=5, food=100.0, dormant=2, n_parents=2):
    fields = {}
    fields.update(_region(pop=pop, pop_base=5, soil=0.5, food=food))
    for i in range(n_parents):
        fields.update(_agent(i))
    for i in range(n_parents, n_parents + dormant):
        fields.update(_agent(i, alive=False, region="none"))
    return make_sim(_rules(), [BirthSystem()], seed=7, genesis_fields=fields)


def test_birth_activates_dormant_with_exact_inheritance():
    sim = _birth_world()
    for _ in range(200):
        sim.step()
    births = _births(sim)
    assert len(births) == 2  # pool exhausted -> carrying capacity reached (O5)
    st = sim.state
    for tick, child, f in births:
        parent = f["parent_id"]
        assert parent in {"agent:0", "agent:1"}
        assert f["alive"] is True and f["region"] == "region:0"
        assert f["generation"] == 1  # parents are gen 0
        assert f["birth_tick"] == tick
        assert f["infected"] is False
        assert f["hunger"] == 0.1  # newborn
        p_mem, p_hp, p_risk = 0.8, 90.0, 0.6
        m = BirthSystem.MUT_MEMORY
        assert abs(f["immune_memory"] - p_mem * BirthSystem.MEM_HERITABILITY) <= m + 1e-9
        im = 0.30 + BirthSystem.IMMUNITY_FROM_MEMORY * p_mem
        assert abs(f["immunity"] - im) <= BirthSystem.MUT_IMMUNITY + 1e-9
        hp = 0.90 * p_hp + 0.10 * BirthSystem.MAX_HEALTH_BASE
        assert abs(f["max_health"] - hp) <= BirthSystem.MUT_MAX_HEALTH + 1e-9
        assert f["health"] == f["max_health"]  # born at full health
        lo, hi = 0.70 * p_risk, 0.70 * p_risk + 0.30
        assert lo - BirthSystem.MUT_RISK <= f["risk_tolerance"] <= hi + BirthSystem.MUT_RISK
        # the child now lives: fields are in the state, not just the journal
        assert st.get(child, "alive") is True
        assert st.get(child, "parent_id") == parent


def test_birth_maturity_gate_and_silence_before_it():
    sim = _birth_world()
    for _ in range(BirthSystem.MATURITY):
        sim.step()
    assert _ops(sim).get("agent.birth", 0) == 0  # age > 20 strictly (O1)


def test_birth_capacity_and_food_gates():
    base = _birth_world()  # capacity = round(5*(1+0.5)) = 8, food_pc = 20
    full = _birth_world(pop=8)  # pop >= capacity -> closed
    poor = _birth_world(food=15.0)  # food_pc = 3.0 <= floor -> closed
    empty = _birth_world(dormant=0)  # no free slots
    for world in (base, full, poor, empty):
        for _ in range(300):
            world.step()
    assert _ops(base).get("agent.birth", 0) >= 1
    assert _ops(full).get("agent.birth", 0) == 0
    assert _ops(poor).get("agent.birth", 0) == 0
    assert _ops(empty).get("agent.birth", 0) == 0


def test_birth_dead_agents_never_recycled():
    # a dead agent (alive False, region kept) is not a dormant slot
    fields = _region()
    fields.update(_agent(0))
    fields.update(_agent(1, alive=False, region="region:0"))
    sim = make_sim(_rules(), [BirthSystem()], seed=7, genesis_fields=fields)
    for _ in range(300):
        sim.step()
    assert _ops(sim).get("agent.birth", 0) == 0


def test_birth_determinism():
    a, b = _birth_world(), _birth_world()
    for _ in range(200):
        a.step()
        b.step()
    assert a.journal.hash() == b.journal.hash() and a.state.hash() == b.state.hash()


# ---------------------------------------------------------------------- ruin


def _ruin_world(extra_fields=None, systems=None, plan=None):
    fields = {**_region(pop=0), **_ruin()}
    if extra_fields:
        fields.update(extra_fields)
    sys_list = list(systems or [RuinSystem()])
    if plan is not None:
        sys_list.insert(0, ScriptedRegion(plan))  # census at priority 1
    return make_sim(_rules(), sys_list, seed=7, genesis_fields=fields)


def test_ruin_extinction_activates_once_then_ages_no_oscillation():
    # Regression for the 860/859 oscillation: activation must fire on the
    # TRANSITION into extinction (was_alive marker) and a starved region
    # still seeds MIN_RUIN_FOOD so the ruin cannot insta-collapse.
    sim = _ruin_world(
        extra_fields={**_ruin(was_alive=True), **_region(pop=0, food=0.0, soil=0.2)}
    )
    for _ in range(500):
        sim.step()
    ops = _ops(sim)
    assert ops.get("ruin.activate", 0) == 1
    assert ops.get("ruin.collapse", 0) == 0
    assert ops.get("ruin.age", 0) == 499
    st = sim.state
    assert st.get("ruin:0:0", "active") is True
    assert st.get("ruin:0:0", "was_alive") is False
    assert st.get("ruin:0:0", "resource_food") == RuinSystem.MIN_RUIN_FOOD
    assert st.get("ruin:0:0", "type") == "camp"  # food 0, soil 0.2 <= 0.6
    assert st.get("ruin:0:0", "age") == 499


def test_ruin_never_alive_region_stays_dormant():
    sim = make_sim(
        _rules(),
        [RuinSystem()],
        seed=7,
        genesis_fields={**_region(pop=0), **_ruin(was_alive=False)},
    )
    for _ in range(50):
        sim.step()
    assert _ops(sim) == {}  # no phantom ruin for a never-inhabited region


def test_ruin_alive_region_notes_and_persists():
    sim = make_sim(
        _rules(),
        [RuinSystem()],
        seed=7,
        genesis_fields={**_region(pop=5), **_ruin()},
    )
    for _ in range(30):
        sim.step()
    ops = _ops(sim)
    assert ops.get("ruin.note_alive", 0) == 1  # once, then silence
    assert ops.get("ruin.activate", 0) == 0
    assert sim.state.get("ruin:0:0", "was_alive") is True


def test_ruin_reextinction_resets_the_same_slot_and_alive_ruin_does_not_age():
    # Census plan keys are snapshot.tick values; a committed write becomes
    # visible to the other systems on the NEXT step. Trace (step: snapshot ->
    # committed): 1: pop5 -> note_alive | 2: pop5, plan[2]=0 -> nothing yet |
    # 3: pop5? no — census commits here, pop=0 from step 4's view |
    # 4: pop0 was_alive -> ACTIVATE (age 0) | 5: pop0 (plan[4]=5 commits) ->
    # AGE(1) | 6: pop5 -> PERSISTS, no aging, note_alive again | 7: pop5,
    # plan[6]=0 commits | 8: pop0 -> ACTIVATE AGAIN — same slot, age reset
    # (nuance 4) | 9: pop0 -> AGE(1). Final: age 1, res 10, settlement.
    sim = _ruin_world(
        extra_fields={**_ruin(), **_region(pop=5, food=40.0, soil=0.7)},
        plan={2: 0, 4: 5, 6: 0},
    )
    for _ in range(9):
        sim.step()
    ops = _ops(sim)
    assert ops.get("ruin.activate", 0) == 2
    assert ops.get("ruin.note_alive", 0) == 2
    assert ops.get("ruin.age", 0) == 2  # t4 and t8 only (alive -> no aging)
    assert ops.get("ruin.collapse", 0) == 0
    st = sim.state
    assert st.get("ruin:0:0", "type") == "settlement"  # soil 0.7 > 0.6, food 40
    assert st.get("ruin:0:0", "resource_food") == 10.0  # max(10, 0.1*40)
    assert st.get("ruin:0:0", "age") == 1  # reset by the second activation


def test_ruin_collapse_at_floor_and_stays_collapsed():
    # an exhausted reserve collapses once, and the slot then SILENTLY stays
    # dormant (was_alive False): no re-activation without a new extinction.
    sim = make_sim(
        _rules(),
        [RuinSystem()],
        seed=7,
        genesis_fields={**_region(pop=0), **_ruin(active=True, res=0.3)},
    )
    for _ in range(60):
        sim.step()
    ops = _ops(sim)
    assert ops.get("ruin.collapse", 0) == 1
    assert ops.get("ruin.activate", 0) == 0
    assert ops.get("ruin.age", 0) == 0
    st = sim.state
    assert st.get("ruin:0:0", "active") is False
    assert st.get("ruin:0:0", "type") == ""


def test_ruin_max_age_collapse():
    sim = make_sim(
        _rules(),
        [RuinSystem()],
        seed=7,
        genesis_fields={
            **_region(pop=0),
            **_ruin(active=True, res=10.0, age=RuinSystem.RUIN_MAX_AGE - 1),
        },
    )
    for _ in range(5):
        sim.step()
    ops = _ops(sim)
    # t1: new_age == MAX_AGE (not > it) -> ages; t2: collapse (age+1 written)
    assert ops.get("ruin.age", 0) == 1
    assert ops.get("ruin.collapse", 0) == 1
    assert sim.state.get("ruin:0:0", "age") == RuinSystem.RUIN_MAX_AGE + 1
    assert ops.get("ruin.activate", 0) == 0  # and silence after


# ---------------------------------------------------------------- exploration


def _explore_world(systems=None, res=50.0):
    fields = {}
    fields.update(_region(pop=4, name="region:1"))
    fields.update(_ruin(active=True, res=res, rname="ruin:1:0", region="region:1",
                        rtype="granary"))
    for i in range(4):
        fields.update(_agent(i, region="region:1", hunger=0.9, risk=0.9))
    return make_sim(
        _rules(), systems or [ExplorationSystem()], seed=7, genesis_fields=fields
    )


def test_exploration_forced_bonus_and_trace():
    # Decision 3: natural firing is rare in a healthy compost world, so the
    # MECHANISM is validated in a controlled scenario (agents co-located with
    # an active ruin).
    sim = _explore_world()
    for _ in range(200):
        sim.step()
    ops = _ops(sim)
    assert ops.get("agent.explore", 0) >= 1
    assert ops.get("ruin.deplete", 0) >= 1
    # the causal trace: every explore transition READS the ruin (biography
    # queries can point "you ate from the granary" at the ruin entity)
    strict_relief = 0
    for t in sim.journal.all():
        if t.operation == "agent.explore":
            assert any(
                r.entity == "ruin:1:0" and r.field == "resource_food"
                for r in t.reads
            )
            child = t.writes[0]
            assert child.field == "hunger" and child.new <= child.old
            if child.new < child.old:  # a full agent re-visiting gains nothing
                strict_relief += 1
    assert strict_relief >= 1
    # exploring empties the reserve: 50 units, 10 per explorer
    assert sim.state.get("ruin:1:0", "resource_food") == 0.0


def test_exploration_emptied_ruin_collapses_and_stays_collapsed():
    # joint behaviour (RuinSystem + ExplorationSystem): a ruin explored to
    # emptiness collapses next tick and cannot re-activate (was_alive False)
    # nor feed anyone else (res > 0 gate).
    sim = _explore_world(systems=[RuinSystem(), ExplorationSystem()], res=10.0)
    explores = 0
    for _ in range(200):
        sim.step()
    ops = _ops(sim)
    assert ops.get("agent.explore", 0) >= 1
    assert ops.get("ruin.collapse", 0) == 1
    assert ops.get("ruin.activate", 0) == 0  # no re-activation, no oscillation
    assert sim.state.get("ruin:1:0", "active") is False


# ----------------------------------------------------------------- senescence


def _senesce_world(n=20):
    fields = {**_region(pop=n)}
    for i in range(n):
        fields.update(_agent(i, health=100.0))
    # one dormant slot must never be touched by senescence
    fields.update(_agent(n, alive=False, region="none"))
    return make_sim(_rules(), [SenescenceSystem()], seed=7, genesis_fields=fields)


def test_senescence_silent_until_onset():
    sim = _senesce_world()
    for _ in range(SenescenceSystem.SENESCENCE_ONSET):
        sim.step()
    assert _ops(sim).get("agent.senescence", 0) == 0


def test_senescence_kills_the_old_and_records_health_zero():
    sim = _senesce_world()
    for _ in range(400):
        sim.step()
    deaths = [
        t
        for t in sim.journal.all()
        if t.operation == "agent.senescence"
    ]
    assert len(deaths) >= 1
    for t in deaths:
        w = {c.field: (c.old, c.new) for c in t.writes}
        assert w["alive"] == (True, False) and w["health"][1] == 0.0


def test_senescence_determinism():
    a, b = _senesce_world(), _senesce_world()
    for _ in range(400):
        a.step()
        b.step()
    assert a.journal.hash() == b.journal.hash() and a.state.hash() == b.state.hash()


def test_senescence_leaves_dormant_and_dead_alone():
    sim = _senesce_world()
    for _ in range(400):
        sim.step()
    assert sim.state.get("agent:20", "alive") is False
    assert sim.state.get("agent:20", "health") == 100.0  # untouched placeholder
    for t in sim.journal.all():
        if t.operation == "agent.senescence":
            assert all(c.entity != "agent:20" for c in t.writes)


# ------------------------------------------------------------ separation & sim


def test_game_systems_are_ruleset_scoped():
    game = create_world(seed=7, ruleset=get_ruleset("player_life"), ticks=0)
    game_names = {s.name for s in game.systems}
    assert {
        "BirthSystem",
        "RuinSystem",
        "ExplorationSystem",
        "SenescenceSystem",
    } <= game_names
    for name in ("default", "immune", "compost"):
        sim = create_world(seed=7, ruleset=get_ruleset(name), ticks=0)
        overlap = {s.name for s in sim.systems} & {
            "BirthSystem",
            "RuinSystem",
            "ExplorationSystem",
            "SenescenceSystem",
        }
        assert not overlap, f"research ruleset {name} sees game systems {overlap}"


def test_player_life_world_runs_and_is_deterministic():
    rules = get_ruleset("player_life")
    a = create_world(seed=7, ruleset=rules, ticks=80, regions=2, agents=40)
    b = create_world(seed=7, ruleset=rules, ticks=80, regions=2, agents=40)
    assert a.journal.hash() == b.journal.hash()
    assert a.state.hash() == b.state.hash()
    # genesis pool exists: ruin slot per region; note_alive already fired at
    # t1 (regions are alive), which arms the slot for its first extinction
    assert a.state.get("ruin:0:0", "active") is False
    assert a.state.get("ruin:0:0", "was_alive") is True
    assert a.state.get("agent:0", "generation") == 0
    assert a.state.get("agent:0", "birth_tick") == 0
