"""Shared helpers for building tiny custom worlds in tests."""

from __future__ import annotations

from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import StateChange, Transition
from causal_world.kernel.validation import WorldRuleValidator
from causal_world.simulation.engine import Simulation
from causal_world.systems.base import System


class RulesForTest(WorldRuleValidator):
    """Minimal configurable ruleset for synthetic tests."""

    ruleset_version = "test-0.1"
    rng_version = "blake2b-v1"
    purposes = {"test.draw": "generic test purpose"}

    def __init__(self, schema: dict[str, type], non_negative: set[str] | None = None):
        self.schema = dict(schema)
        self.non_negative = set(non_negative or set())

    def field_type(self, field_name: str) -> type | None:
        return self.schema.get(field_name)

    def validate_transition(self, transition: Transition, snapshot: Snapshot) -> list[str]:
        violations = []
        for w in transition.writes:
            if w.field in self.non_negative and isinstance(w.new, (int, float)) and w.new < 0:
                violations.append(f"invariant_violation:{w.entity}.{w.field}_must_be_>=_0")
        return violations


def genesis_transition(
    fields: dict[tuple[str, str], object],
    system: str = "GenesisTest",
    operation: str = "genesis.test",
) -> Transition:
    return Transition(
        id=None,
        tick=0,
        system=system,
        operation=operation,
        reads=[],
        writes=[
            StateChange(entity=entity, field=field, old=None, new=value)
            for (entity, field), value in sorted(fields.items())
        ],
        random_draws=[],
        priority=0,
    )


def make_sim(
    rules: WorldRuleValidator,
    systems: list[System],
    seed: int = 0,
    genesis_fields: dict[tuple[str, str], object] | None = None,
) -> Simulation:
    purposes = PurposeRegistry()
    for purpose in sorted(rules.purposes):
        purposes.declare(purpose, rules.purposes[purpose])
    rng = RandomSource(seed, rules.rng_version, purposes)
    simulation = Simulation(seed, systems, rules, rng)
    if genesis_fields is not None:
        simulation.initialize([genesis_transition(genesis_fields)])
    return simulation
