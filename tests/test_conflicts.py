"""Conflict resolution: explicit, deterministic, order-independent,
never rewriting computed values (spec §14, §15)."""

from __future__ import annotations

import itertools

from causal_world.kernel.transition import TransitionStatus
from causal_world.systems.base import System

from helpers import RulesForTest, make_sim

REGION = "region:0"
SCHEMA = {"food_stock": float}


class FoodWriter(System):
    """Writes food_stock 100 -> new_value.

    ``system_priority`` feeds the resolver's system-level tie-break;
    ``transition_priority`` is stamped on the proposed transition itself.
    """

    def __init__(
        self,
        name: str,
        new_value: float,
        system_priority: int = 0,
        transition_priority: int = 0,
    ):
        self.name = name
        self.new_value = new_value
        self.priority = system_priority
        self.transition_priority = transition_priority

    def compute(self, snapshot, rng, context):
        b = context.builder(f"{self.name}.write", priority=self.transition_priority)
        b.read(REGION, "food_stock")
        b.write(REGION, "food_stock", self.new_value)
        return [b.build()]


def run_conflict(systems):
    sim = make_sim(
        RulesForTest(SCHEMA),
        systems,
        seed=0,
        genesis_fields={(REGION, "food_stock"): 100.0},
    )
    sim.step()
    return sim


def test_exactly_one_writer_survives():
    sim = run_conflict([FoodWriter("SysA", 70.0), FoodWriter("SysB", 50.0)])
    writers = [t for t in sim.journal if t.operation.endswith(".write")]
    committed = [t for t in writers if t.status is TransitionStatus.COMMITTED]
    rejected = [t for t in writers if t.status is TransitionStatus.REJECTED]
    assert len(committed) == 1
    assert len(rejected) == 1
    assert rejected[0].reject_reason.startswith("conflict:")
    assert f"T{committed[0].id}" in rejected[0].reject_reason
    assert sim.state.get(REGION, "food_stock") == committed[0].writes[0].new


def test_conflict_result_is_independent_of_system_order():
    sim_ab = run_conflict([FoodWriter("SysA", 70.0), FoodWriter("SysB", 50.0)])
    sim_ba = run_conflict([FoodWriter("SysB", 50.0), FoodWriter("SysA", 70.0)])

    assert sim_ab.state.hash() == sim_ba.state.hash()
    assert sim_ab.journal.hash() == sim_ba.journal.hash()

    winner_ab = next(
        t for t in sim_ab.journal if t.status is TransitionStatus.COMMITTED
    )
    winner_ba = next(
        t for t in sim_ba.journal if t.status is TransitionStatus.COMMITTED
    )
    assert winner_ab.system == winner_ba.system
    assert winner_ab.writes[0].new == winner_ba.writes[0].new


def test_transition_priority_beats_everything():
    sim = run_conflict(
        [
            FoodWriter("SysA", 70.0, system_priority=0, transition_priority=9),
            FoodWriter("SysB", 50.0, system_priority=100, transition_priority=1),
        ]
    )
    winner = next(
        t for t in sim.journal
        if t.status is TransitionStatus.COMMITTED and t.operation.endswith(".write")
    )
    assert winner.system == "SysA"  # transition priority outranks system priority
    assert sim.state.get(REGION, "food_stock") == 70.0


def test_system_priority_breaks_transition_priority_ties():
    for order in (
        [
            FoodWriter("SysA", 70.0, system_priority=1),
            FoodWriter("SysB", 50.0, system_priority=100),
        ],
        [
            FoodWriter("SysB", 50.0, system_priority=100),
            FoodWriter("SysA", 70.0, system_priority=1),
        ],
    ):
        sim = run_conflict(order)
        winner = next(
            t for t in sim.journal
            if t.status is TransitionStatus.COMMITTED and t.operation.endswith(".write")
        )
        assert winner.system == "SysB"


def test_id_breaks_full_ties_deterministically():
    sim = run_conflict([FoodWriter("SysA", 70.0), FoodWriter("SysB", 50.0)])
    writer_ops = lambda t: t.operation.endswith(".write")
    winner = next(t for t in sim.journal if t.status is TransitionStatus.COMMITTED and writer_ops(t))
    loser = next(t for t in sim.journal if t.status is TransitionStatus.REJECTED and writer_ops(t))
    assert winner.id < loser.id, "equal priorities must break toward the lower id"


def test_values_are_never_rewritten_spec15():
    """The resolver must choose a winner; it must never bend a transition's
    computed `new` value into a partial allocation."""
    sim = run_conflict([FoodWriter("SysA", 70.0), FoodWriter("SysB", 50.0)])
    winner = next(
        t for t in sim.journal
        if t.status is TransitionStatus.COMMITTED and t.operation.endswith(".write")
    )
    proposed_news = {70.0, 50.0}
    assert winner.writes[0].new in proposed_news
    assert winner.writes[0].old == 100.0
    assert sim.state.get(REGION, "food_stock") == winner.writes[0].new


def test_resolver_is_pure_with_shuffled_inputs():
    """Resolve the same proposal set in every input order: identical result."""
    from causal_world.kernel.transition import StateChange, Transition
    from causal_world.simulation.resolver import Resolver

    rules = RulesForTest(SCHEMA)
    # Build a real snapshot through a simulation.
    sim = make_sim(
        rules, [], seed=0, genesis_fields={(REGION, "food_stock"): 100.0}
    )
    snapshot = sim.snapshot()

    def make(tid, system, new):
        return Transition(
            id=tid,
            tick=snapshot.tick,
            system=system,
            operation="probe",
            reads=[],
            writes=[StateChange(REGION, "food_stock", 100.0, new)],
            random_draws=[],
            priority=0,
            status=TransitionStatus.PROPOSED,
        )

    proposals_template = [
        (21, "SysA", 70.0),
        (22, "SysB", 50.0),
        (23, "SysC", 90.0),
    ]
    outcomes = set()
    for perm in itertools.permutations(proposals_template):
        resolver = Resolver(rules, {"SysA": 0, "SysB": 0, "SysC": 0})
        transitions = [make(*args) for args in perm]
        resolution = resolver.resolve(snapshot, transitions)
        assert len(resolution.committed) == 1
        outcome = (
            resolution.committed[0].id,
            tuple(sorted((t.id, t.status.value) for t in resolution.rejected)),
        )
        outcomes.add(outcome)
    assert len(outcomes) == 1, f"conflict resolution must be order-independent: {outcomes}"

def test_atomic_conflicts_are_resolved_globally_not_field_by_field():
    """A losing multi-field proposal must not suppress an unrelated valid writer."""
    from causal_world.kernel.transition import StateChange, Transition
    from causal_world.simulation.resolver import Resolver

    rules = RulesForTest({"x": float, "y": float})
    sim = make_sim(
        rules,
        [],
        seed=0,
        genesis_fields={("region:0", "x"): 0.0, ("region:0", "y"): 0.0},
    )
    snapshot = sim.snapshot()

    # A conflicts with B on x and C on y. C outranks A; A outranks B.
    # The globally consistent result is C + B, not C alone.
    proposals = [
        Transition(
            id=1, tick=snapshot.tick, system="A", operation="multi",
            writes=[
                StateChange("region:0", "x", 0.0, 1.0),
                StateChange("region:0", "y", 0.0, 1.0),
            ],
            priority=5,
        ),
        Transition(
            id=2, tick=snapshot.tick, system="B", operation="x-only",
            writes=[StateChange("region:0", "x", 0.0, 2.0)],
            priority=1,
        ),
        Transition(
            id=3, tick=snapshot.tick, system="C", operation="y-only",
            writes=[StateChange("region:0", "y", 0.0, 3.0)],
            priority=10,
        ),
    ]

    outcomes = set()
    for permutation in itertools.permutations(proposals):
        # Resolver mutates status, so recreate pristine proposal objects per run.
        fresh = []
        for t in permutation:
            fresh.append(
                Transition(
                    id=t.id, tick=t.tick, system=t.system, operation=t.operation,
                    reads=list(t.reads), writes=list(t.writes),
                    random_draws=list(t.random_draws), priority=t.priority,
                )
            )
        resolution = Resolver(rules, {"A": 0, "B": 0, "C": 0}).resolve(
            snapshot, fresh
        )
        outcomes.add(tuple(sorted(t.system for t in resolution.committed)))
    assert outcomes == {("B", "C")}

