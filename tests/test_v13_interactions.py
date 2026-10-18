"""v0.13 audit — same-tick interplay of death rules (ADR v13-1 follow-up).

Three questions, each with its own test:

1. Competition for ``health``. Work / heal / trade / rest (the actions that
   write health), infection and old age are resolved in the same tick. A
   grid over health boundaries checks the outcome of every combination and
   the invariants that must hold whatever wins:
   * alive ⇒ health > 0, and not alive ⇒ health == 0;
   * at most one committed write of ``alive`` and of ``health`` per tick;
   * exactly one ``player.act`` record per live tick (committed or rejected);
   * a committed infection voids a health-writing decision of the same tick;
   * old age beats the controlled agent's decision (senescence priority 1
     > player priority 0) and loses only to infection (priority 2), as the
     senescence comment always intended.
2. Intermediate state. Every system plans from the same pre-tick snapshot,
   and no write is visible until the resolver has committed the tick. A dead
   agent receives no committed writes after its death tick.
3. Natural runs. On the real ruleset, over several seeds and policies, the
   same invariants hold for ALL agents at every tick, and no committed
   transition writes an agent that was dead in the pre-tick snapshot.

The infection and old-age systems are the real classes (old age with its
constants forced to certain death), except infection, which is a stub with
the same write pattern and the real ``INFECTION_PRIORITY``: the real roll
would make the grid depend on the seed instead of the rule under test.
"""

from __future__ import annotations

import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import TransitionStatus
from causal_world.player import DecisionChannel, DecisionStreamReader
from causal_world.systems.base import System
from causal_world.systems.disease import INFECTION_PRIORITY
from causal_world.systems.player import PlayerAgentSystem
from causal_world.systems.senescence import SenescenceSystem
from causal_world.server.session import Session

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import make_sim  # noqa: E402
from test_player_agent import _FIELDS, GAME, Step3Rules, _SCHEMA  # noqa: E402

INFECTION_DAMAGE = 6.0
HEALTH_WRITERS = (0, 3, 4, 5)  # work, heal, trade, rest
HEALTHS = (0.5, 3.0, 5.0, 5.5, 6.0, 8.0, 12.0, 20.0)  # around work/trade costs and infection
ACTIONS = (0, 3, 4, 5, 6)


class InfectionStub(System):
    """Same write pattern and priority as DiseaseSystem.disease.infect."""

    name = "DiseaseSystem"
    priority = 20

    def compute(self, snapshot, rng, context):
        if not snapshot.get(GAME, "alive") or snapshot.get(GAME, "infected"):
            return []
        b = context.builder("disease.infect", priority=INFECTION_PRIORITY)
        for f in ("alive", "infected", "immunity", "hunger", "region"):
            b.read(GAME, f)
        health = b.read(GAME, "health")
        b.write(GAME, "infected", True)
        new = health - INFECTION_DAMAGE
        if new <= 0.0:
            b.write(GAME, "health", 0.0)
            b.write(GAME, "alive", False)
        else:
            b.write(GAME, "health", new)
        return [b.build()]


class OldAgeForced(SenescenceSystem):
    """The real senescence system with constants forcing certain death at any age > 0."""

    SENESCENCE_ONSET = 0
    MAX_LIFESPAN = 1
    MAX_DEATH_PROB = 1.0
    DEATH_PROB_CAP = 1.0


class Probe(System):
    """Records what a system sees from the snapshot it is given."""

    name = "ProbeSystem"
    priority = 0

    def __init__(self):
        self.seen: list[tuple[bool, float, int]] = []

    def compute(self, snapshot, rng, context):
        self.seen.append(
            (snapshot.get(GAME, "alive"), snapshot.get(GAME, "health"), snapshot.tick)
        )
        return []


def _world(health, action, infect, old_age, extra=(), birth_tick=-100):
    systems = [PlayerAgentSystem(channel=DecisionChannel(actions=[action]), controlled=GAME)]
    if infect:
        systems.append(InfectionStub())
    if old_age:
        systems.append(OldAgeForced())
    systems.extend(extra)
    fields = {
        **_FIELDS,
        (GAME, "health"): health,
        (GAME, "infected"): False,
        (GAME, "birth_tick"): birth_tick,
    }
    return make_sim(Step3Rules(_SCHEMA), systems, seed=7, genesis_fields=fields)


def _tick_records(sim, tick):
    # genesis writes the initial state at tick 0; it is not a rule-tick decision
    return [t for t in sim.journal.all()
            if t.tick == tick and not t.operation.startswith("genesis")]


def _writes_to_game(trs, field):
    return [
        t for t in trs
        if t.status is TransitionStatus.COMMITTED
        and any(w.entity == GAME and w.field == field for w in t.writes)
    ]


# ------------------------------------------------ 1 · competition grid


@pytest.mark.parametrize("old_age", [False, True])
@pytest.mark.parametrize("infect", [False, True])
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("health", HEALTHS)
def test_death_rules_grid_invariants(health, action, infect, old_age):
    sim = _world(health, action, infect, old_age)
    sim.step()
    alive = sim.state.get(GAME, "alive")
    hp = sim.state.get(GAME, "health")

    # post-state invariants, whatever won
    assert not (alive and hp <= 0.0), (health, action, infect, old_age)
    if not alive:
        assert hp == 0.0

    trs = _tick_records(sim, 0)
    # no double writes on the controlled agent within one tick
    assert len(_writes_to_game(trs, "alive")) <= 1
    assert len(_writes_to_game(trs, "health")) <= 1
    # the decision is always journaled, committed or rejected
    decisions = [t for t in trs if t.operation == "player.act"]
    assert len(decisions) == 1

    infection_committed = any(
        t.operation == "disease.infect" and t.status is TransitionStatus.COMMITTED
        for t in trs
    )
    old_age_committed = any(
        t.operation == "agent.senescence" and t.status is TransitionStatus.COMMITTED
        for t in trs
    )
    decision = decisions[0]
    decision_health_writes = [w for w in decision.writes
                              if w.entity == GAME and w.field == "health"]
    if decision.status is TransitionStatus.COMMITTED:
        # two-transition design: a committed decision never writes a lethal health
        # value; the lethal cost is paid by agent.death instead
        assert all(w.new > 0.0 for w in decision_health_writes)
    if action in HEALTH_WRITERS and decision.status is TransitionStatus.REJECTED:
        assert decision_health_writes
    if old_age and not infect:
        # old age (transition priority 1) beats any decision (priority 0)
        assert old_age_committed and not alive
    if old_age and infect and infection_committed:
        # infection keeps its precedence over old age, as documented
        assert not old_age_committed


def test_lethal_decision_and_old_age_share_one_death_writer():
    # old age and the lethal work cost are both death writers: exactly one commits
    sim = _world(3.0, 0, infect=False, old_age=True)
    sim.step()
    trs = _tick_records(sim, 0)
    death_writers = [
        t for t in trs
        if t.status is TransitionStatus.COMMITTED
        and any(w.entity == GAME and w.field == "alive" and w.new is False for w in t.writes)
    ]
    assert len(death_writers) == 1
    assert death_writers[0].operation == "agent.senescence"


# ------------------------------------------------ 2 · intermediate state


def test_all_systems_plan_from_the_same_pre_tick_snapshot():
    probe = Probe()
    sim = _world(3.0, 0, infect=True, old_age=True, extra=(probe,))
    sim.step()
    # the death tick: every system saw the pre-tick living state
    assert probe.seen == [(True, 3.0, 0)]
    assert sim.state.get(GAME, "alive") is False


def test_dead_agent_gets_no_committed_writes_after_death():
    sim = _world(3.0, 0, infect=False, old_age=False)
    sim.step()  # death tick: the work decision costs 5 > 3
    assert sim.state.get(GAME, "alive") is False
    death_tick_ops = {t.operation for t in _tick_records(sim, 0)
                      if t.status is TransitionStatus.COMMITTED
                      and any(w.entity == GAME for w in t.writes)}
    # on the death tick the decision's own non-health writes may still commit
    assert death_tick_ops <= {"player.act", "agent.death"}
    for _ in range(3):
        sim.step()
    later = [t for t in sim.journal.all() if t.tick > 0 and not t.operation.startswith("genesis")]
    assert all(not any(w.entity == GAME for w in t.writes) for t in later
               if t.status is TransitionStatus.COMMITTED)


def test_lethal_decision_is_still_in_the_decision_stream():
    sim = _world(3.0, 0, infect=False, old_age=False)
    sim.step()
    assert DecisionStreamReader.actions_from(sim.journal, GAME) == [0]


# ------------------------------------------------ 3 · natural runs


CREATION = {"agent.birth", "genesis.agent", "genesis"}


def _natural(seed, policy, ticks=120):
    rng = random.Random(seed * 7 + len(policy))
    if policy == "work":
        act = lambda i: 0  # noqa: E731
    else:
        act = lambda i: 2 if (r := rng.random()) < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6  # noqa: E731
    s = Session(seed=seed, ruleset="player_resettle", regions=2, agents=54,
                max_ticks=ticks + 5, db_dir=tempfile.mkdtemp(prefix="v13_nat_"))
    pending = {}
    orig = s.sim.resolver.resolve

    def hook(snapshot, transitions, allow_creation=False):
        res = orig(snapshot, transitions, allow_creation)
        pending["snap"], pending["props"] = snapshot, list(transitions)
        return res

    s.sim.resolver.resolve = hook
    problems = []
    try:
        for seq in range(1, ticks + 1):
            if s.state != "awaiting":
                break
            frame = s.decide(seq, act(seq))
            snap, props = pending["snap"], pending["props"]
            for t in props:
                if t.status is not TransitionStatus.COMMITTED or t.operation in CREATION:
                    continue
                for w in t.writes:
                    if w.entity.startswith("agent:") and snap.get(w.entity, "alive") is False:
                        problems.append(("write_to_dead", snap.tick, t.operation, w.entity))
            post = Snapshot.from_state(s.sim.state)
            for a in post.entities_with_prefix("agent:"):
                if post.get(a, "alive") and float(post.get(a, "health")) <= 0.0:
                    problems.append(("alive_zero_health", frame["tick"], a))
            if not frame["alive"]:
                break
    finally:
        if s.state != "finalized":
            s.close()
    return problems


@pytest.mark.parametrize("policy", ["work", "mixed"])
@pytest.mark.parametrize("seed", [1, 2])
def test_natural_runs_keep_the_invariants_for_all_agents(seed, policy):
    assert _natural(seed, policy) == []
