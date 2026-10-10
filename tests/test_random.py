"""Randomness: addressable, deterministic, order-independent (spec §8, §37)."""

from __future__ import annotations

import pytest

from causal_world.kernel.errors import UnknownPurposeError
from causal_world.kernel.random import PurposeRegistry, RandomSource


def make_rng(seed: int = 7, version: str = "blake2b-v1") -> RandomSource:
    return RandomSource(seed, version)


def test_draw_is_deterministic_for_same_seed():
    rng1, rng2 = make_rng(42), make_rng(42)
    for _ in range(2):
        assert rng1.draw(100, "agent:42", "disease.infection") == rng2.draw(
            100, "agent:42", "disease.infection"
        )


def test_draw_is_addressable_by_context():
    rng = make_rng()
    contexts = [
        (100, "agent:42", "disease.infection", 0),
        (101, "agent:42", "disease.infection", 0),
        (100, "agent:43", "disease.infection", 0),
        (100, "agent:42", "agent.decision", 0),
        (100, "agent:42", "disease.infection", 1),
    ]
    values = [rng.draw(*c) for c in contexts]
    assert len(set(values)) == len(values), "every context must address a distinct draw"


def test_order_independence_spec37():
    """draw(A), draw(B), draw(C) == draw(C), draw(A), draw(B) per agent."""
    agents = ["agent:A", "agent:B", "agent:C"]
    rng1, rng2 = make_rng(9), make_rng(9)
    first = {a: rng1.draw(100, a, "disease.infection") for a in agents}
    second = {a: rng2.draw(100, a, "disease.infection") for a in reversed(agents)}
    assert first == second


def test_removing_agent_does_not_change_others_spec37():
    """Deleting agent B must not change values for A or C."""
    rng = make_rng(11)
    with_b = {
        a: rng.draw(100, a, "disease.infection") for a in ["agent:A", "agent:B", "agent:C"]
    }
    rng_fresh = make_rng(11)
    without_b = {
        a: rng_fresh.draw(100, a, "disease.infection") for a in ["agent:A", "agent:C"]
    }
    assert without_b["agent:A"] == with_b["agent:A"]
    assert without_b["agent:C"] == with_b["agent:C"]


def test_draws_stay_in_unit_interval():
    rng = make_rng(3)
    for i in range(2000):
        value = rng.draw(i % 50, f"agent:{i % 13}", "test.purpose")
        assert 0.0 <= value < 1.0


def test_seed_changes_the_stream():
    a = RandomSource(1, "blake2b-v1").draw(5, "agent:0", "p")
    b = RandomSource(2, "blake2b-v1").draw(5, "agent:0", "p")
    assert a != b


def test_rng_version_is_part_of_the_rules():
    a = RandomSource(7, "blake2b-v1").draw(5, "agent:0", "p")
    b = RandomSource(7, "blake2b-v2").draw(5, "agent:0", "p")
    assert a != b


def test_unknown_purpose_is_rejected():
    registry = PurposeRegistry()
    registry.declare("known.purpose")
    rng = RandomSource(1, "blake2b-v1", registry)
    rng.draw(0, "agent:0", "known.purpose")  # fine
    with pytest.raises(UnknownPurposeError):
        rng.draw(0, "agent:0", "undeclared.purpose")


def test_no_hidden_sequential_state():
    """Drawing twice from the same source never advances any stream."""
    rng = make_rng(5)
    first = rng.draw(9, "agent:1", "x")
    for _ in range(10):
        assert rng.draw(9, "agent:1", "x") == first
