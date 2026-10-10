"""Atomicity: all writes or none (spec §12, tests #6, #7, #8)."""

from __future__ import annotations

import pytest

from causal_world import create_world
from causal_world.kernel.errors import SealedStateError
from causal_world.kernel.transition import (
    StateChange,
    Transition,
    TransitionStatus,
)
from causal_world.systems.base import System

from helpers import RulesForTest, make_sim

AGENT = "agent:t"
SCHEMA = {"infected": bool, "health": float}


class InfectSystem(System):
    """Proposes the atomic pair: infected F->T AND health 73 -> 58."""

    name = "InfectSystem"
    priority = 0

    def compute(self, snapshot, rng, context):
        if snapshot.get(AGENT, "infected"):
            return []
        b = context.builder("infection")
        b.read(AGENT, "infected")
        health = b.read(AGENT, "health")
        b.write(AGENT, "infected", True)
        b.write(AGENT, "health", health - 15.0)
        return [b.build()]


class GuardSystem(System):
    """Competing writer for health. Priority controls who wins."""

    name = "GuardSystem"
    new_health = 73.0

    def __init__(self, priority: int, new_health: float):
        self.priority = priority
        GuardSystem.new_health = new_health

    def compute(self, snapshot, rng, context):
        b = context.builder("guard.health")
        health = b.read(AGENT, "health")
        b.write(AGENT, "health", GuardSystem.new_health)
        return [b.build()]


def make_agent_world(systems):
    return make_sim(
        RulesForTest(SCHEMA),
        systems,
        seed=0,
        genesis_fields={(AGENT, "infected"): False, (AGENT, "health"): 73.0},
    )


def test_rejected_transition_changes_nothing_spec41():
    """Spec test #6, literal: the conflict winner keeps health at 73, so the
    rejected infection must leave BOTH infected == False AND health == 73."""
    sim = make_agent_world([InfectSystem(), GuardSystem(priority=5, new_health=73.0)])
    sim.step()

    infection = next(
        t for t in sim.journal if t.operation == "infection"
    )
    assert infection.status is TransitionStatus.REJECTED
    assert sim.state.get(AGENT, "infected") is False
    assert sim.state.get(AGENT, "health") == 73.0


def test_no_partial_application_when_winner_changes_value():
    """Winner writes health 73 -> 60: infection is rejected wholesale.
    The forbidden partial state (infected=True, health=73) never exists."""
    sim = make_agent_world([InfectSystem(), GuardSystem(priority=5, new_health=60.0)])
    sim.step()

    infection = next(t for t in sim.journal if t.operation == "infection")
    assert infection.status is TransitionStatus.REJECTED
    assert sim.state.get(AGENT, "infected") is False, (
        "partial application: infected committed while health write lost"
    )
    assert sim.state.get(AGENT, "health") == 60.0


def test_successful_transition_applies_all_writes_spec42():
    sim = make_agent_world([InfectSystem()])
    sim.step()

    infection = next(t for t in sim.journal if t.operation == "infection")
    assert infection.status is TransitionStatus.COMMITTED
    assert sim.state.get(AGENT, "infected") is True
    assert sim.state.get(AGENT, "health") == 58.0
    # Provenance of BOTH writes points at the same transition (atomic).
    assert sim.state.get_source(AGENT, "infected") == infection.id
    assert sim.state.get_source(AGENT, "health") == infection.id


def test_stale_old_value_is_rejected():
    """Spec §7: a transition claiming health 73 -> 58 against a snapshot
    holding 80 must be rejected."""

    class StaleSystem(System):
        name = "StaleSystem"

        def compute(self, snapshot, rng, context):
            return [
                Transition(
                    id=None,
                    tick=snapshot.tick,
                    system=self.name,
                    operation="stale.write",
                    reads=[],
                    writes=[StateChange(AGENT, "health", 73.0, 58.0)],
                    random_draws=[],
                )
            ]

    sim = make_sim(
        RulesForTest(SCHEMA),
        [StaleSystem()],
        seed=0,
        genesis_fields={(AGENT, "infected"): False, (AGENT, "health"): 80.0},
    )
    sim.step()
    stale = next(t for t in sim.journal if t.operation == "stale.write")
    assert stale.status is TransitionStatus.REJECTED
    assert "old_value_mismatch" in stale.reject_reason
    assert sim.state.get(AGENT, "health") == 80.0


def test_no_magic_state_changes_spec43():
    """Replay the journal: every committed write's `old` must equal the
    value that was live before it, and the replay must reproduce the final
    state exactly. No field may ever change without a committed transition."""
    sim = create_world(seed=3, ticks=40)

    expected: dict[tuple[str, str], object] = {}
    provenance: dict[tuple[str, str], int] = {}
    for t in sim.journal:
        if t.status is not TransitionStatus.COMMITTED:
            continue
        for w in sorted(t.writes, key=lambda w: (w.entity, w.field)):
            key = (w.entity, w.field)
            previous = expected.get(key)
            assert w.old == previous, (
                f"T{t.id} {w.entity}.{w.field}: old={w.old!r} but live "
                f"value was {previous!r}"
            )
            expected[key] = w.new
            provenance[key] = t.id

    assert expected == sim.state.data
    assert provenance == sim.state.provenance


def test_world_state_is_sealed_against_direct_writes():
    sim = create_world(seed=1)
    with pytest.raises(SealedStateError):
        sim.state.set("agent:0", "health", 0.0, transition_id=99999)

    # The seal survives an unsealed commit block.
    before = sim.state.hash()
    with pytest.raises(SealedStateError):
        sim.state.set("region:0", "food_stock", -1.0, transition_id=1)
    assert sim.state.hash() == before
