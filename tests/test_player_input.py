"""v0.6 step 1: player-supplied decision draws — the ``draw(value=)`` mechanism.

Game contract (proposal ``experiments/proposals/v06_player_input_draw.md``):
a player's explicit choice is a first-class causal node whose value comes
from the player, not the seed, so dice can never veto it. Determinism
becomes "given the decision stream": same seed + same supplied values ->
bit-identical journal. The kernel is untouched; only ``systems/base.py``
(the builder) and ``world/rules.py`` (purpose + game-ruleset seed) change.
"""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.kernel.canonical import canonical_token
from causal_world.kernel.errors import UnknownPurposeError
from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.systems.base import System
from causal_world.world.rules import RULESETS, get_ruleset

from helpers import RulesForTest, make_sim

AGENT = "agent:p"
SCHEMA = {"hunger": float, "region": str}
PURPOSE = "test.draw"            # declared by RulesForTest
GENESIS = {(AGENT, "hunger"): 0.5, (AGENT, "region"): "region:0"}


class DecideSystem(System):
    """One decision per tick: read hunger, draw (rng or supplied), move."""

    name = "DecideSystem"
    priority = 0

    def __init__(self, value=None, purpose=PURPOSE, threshold=None):
        self.value = value
        self.purpose = purpose
        self.threshold = threshold

    def compute(self, snapshot, rng, context):
        b = context.builder("test.decide")
        b.read(AGENT, "hunger")
        b.draw(self.purpose, AGENT, threshold=self.threshold, value=self.value)
        b.write(AGENT, "region", "region:1")
        return [b.build()]


def _decide(system, seed=7):
    """Run one tick; return (the decision transition, the sim)."""
    sim = make_sim(RulesForTest(SCHEMA), [system], seed=seed,
                   genesis_fields=dict(GENESIS))
    sim.step()
    tr = next(t for t in sim.journal.committed()
              if t.operation == "test.decide")
    return tr, sim


def _oracle(seed=7):
    purposes = PurposeRegistry()
    for p in sorted(RulesForTest.purposes):
        purposes.declare(p, RulesForTest.purposes[p])
    return RandomSource(seed, "blake2b-v1", purposes)


# 1 — backward compatibility: value=None is the unchanged rng draw.
def test_draw_value_none_is_backward_compatible():
    tr, _ = _decide(DecideSystem(value=None, threshold=0.5))
    d = tr.random_draws[0]
    oracle = _oracle()
    assert d.value == oracle.draw(tr.tick, AGENT, PURPOSE, 0)
    assert d.threshold == 0.5
    assert d.outcome == (d.value < 0.5)


# 2 — a supplied value bypasses rng and is recorded verbatim.
def test_draw_supplied_value_bypasses_rng():
    tr, _ = _decide(DecideSystem(value=2.0))
    d = tr.random_draws[0]
    assert d.value == 2.0
    assert d.threshold is None
    assert d.outcome == 2.0                              # threshold None -> outcome=value
    assert d.value != _oracle().draw(tr.tick, AGENT, PURPOSE, 0)   # not the seed roll


# 3 — the purpose is enforced even for a supplied draw.
def test_supplied_value_requires_declared_purpose():
    sim = make_sim(RulesForTest(SCHEMA),
                   [DecideSystem(value=1.0, purpose="undeclared.purpose")],
                   seed=7, genesis_fields=dict(GENESIS))
    with pytest.raises(UnknownPurposeError):
        sim.step()


# 4 — determinism given the decision stream.
def test_determinism_given_decision_stream():
    tr1, sim1 = _decide(DecideSystem(value=3.0), seed=7)
    tr2, sim2 = _decide(DecideSystem(value=3.0), seed=7)
    assert tr1.random_draws[0].value == tr2.random_draws[0].value == 3.0
    assert sim1.journal.hash() == sim2.journal.hash()
    assert sim1.state.hash() == sim2.state.hash()


# 5 — supplied value diverges from rng (proves the VALUE is what is recorded).
def test_supplied_value_diverges_from_rng():
    tr_s, sim_s = _decide(DecideSystem(value=0.12345), seed=7)
    tr_r, sim_r = _decide(DecideSystem(value=None), seed=7)
    assert tr_s.random_draws[0].value == 0.12345
    assert tr_r.random_draws[0].value != 0.12345
    assert sim_s.journal.hash() != sim_r.journal.hash()


# 6 — the value-type convention is pinned (canonical type tags differ).
def test_value_type_canonical_convention():
    assert canonical_token(2.0) != canonical_token(2)     # "f:2.0" vs "i:2"
    _, sim_a = _decide(DecideSystem(value=2.0), seed=7)
    _, sim_b = _decide(DecideSystem(value=2.0), seed=7)
    assert sim_a.journal.hash() == sim_b.journal.hash()   # same float -> same hash


# 7 — the game ruleset declares the purpose, runs deterministically, and is
#     distinct from the compost base it inherits.
def test_player_life_ruleset_seed():
    assert "player_life" in RULESETS
    rules = get_ruleset("player_life")
    assert "player.decision" in rules.purposes
    assert rules.ruleset_version == "0.6.0"
    compost = get_ruleset("compost")
    assert "player.decision" not in compost.purposes
    assert compost.ruleset_version != rules.ruleset_version
    # runs bit-identically (all-NPC for now; PlayerAgentSystem is step 3)
    small = dict(seed=7, regions=3, agents=30, ticks=40)
    a = create_world(ruleset=get_ruleset("player_life"), **small)
    b = create_world(ruleset=get_ruleset("player_life"), **small)
    assert a.state.hash() == b.state.hash()
    assert a.journal.hash() == b.journal.hash()
