"""Default world ruleset: versions, random purposes, schema, invariants.

Changing anything in this module is a RULESET change: a world run under a
different ruleset is a different world, even with an identical seed. The
run fingerprint records ruleset_version and rng_version (spec §32).
"""

from __future__ import annotations

from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.kernel.validation import WorldRuleValidator

RULESET_VERSION = "0.1.0"
RNG_VERSION = "blake2b-v1"

#: Random purposes are part of the rules of the world (spec §9).
PURPOSES: dict[str, str] = {
    "genesis.attribute": "procedural generation of initial region/agent attributes",
    "climate.temperature_noise": "stochastic temperature drift component",
    "climate.rain": "stochastic rainfall drift component",
    "agriculture.crop_variance": "per-region harvest multiplier variance",
    "disease.infection": "per-agent infection roll (index 0) and damage (index 1)",
    "disease.recovery": "per-agent recovery roll",
    "disease.load_noise": "environmental disease load noise",
    "agent.decision": "behavioural decision roll (migration)",
    "agent.movement": "reserved for future movement target selection",
}

#: Field schema: field name -> exact expected type (spec §13.3).
FIELD_TYPES: dict[str, type] = {
    # region fields
    "temperature": float,
    "rainfall": float,
    "temperature_base": float,
    "rainfall_base": float,
    "climate_volatility": float,
    "soil_fertility": float,
    "food_stock": float,
    "disease_load": float,
    "disease_base": float,
    "population": int,
    "workers": int,
    # agent fields
    "alive": bool,
    "health": float,
    "hunger": float,
    "immunity": float,
    "infected": bool,
    "risk_tolerance": float,
    "region": str,
}

#: Fields that must never become negative (spec §13.4).
NON_NEGATIVE_FIELDS = {
    "food_stock",
    "health",
    "population",
    "workers",
    "soil_fertility",
    "disease_load",
}

#: Fields constrained to the unit interval.
UNIT_INTERVAL_FIELDS = {
    "rainfall",
    "soil_fertility",
    "hunger",
    "immunity",
    "risk_tolerance",
    "disease_load",
    "disease_base",
}


class DefaultWorldRules(WorldRuleValidator):
    """The MVP world laws. Pure, deterministic, kernel-agnostic."""

    ruleset_version = RULESET_VERSION
    rng_version = RNG_VERSION
    purposes = PURPOSES

    def field_type(self, field_name: str) -> type | None:
        return FIELD_TYPES.get(field_name)

    def validate_transition(
        self, transition: Transition, snapshot: Snapshot
    ) -> list[str]:
        violations: list[str] = []
        for w in transition.writes:
            if w.field in NON_NEGATIVE_FIELDS and isinstance(w.new, (int, float)):
                if w.new < 0:
                    violations.append(
                        f"invariant_violation:{w.entity}.{w.field}_must_be_>=_0"
                    )
            if w.field in UNIT_INTERVAL_FIELDS and isinstance(w.new, (int, float)):
                if not 0.0 <= w.new <= 1.0:
                    violations.append(
                        f"invariant_violation:{w.entity}.{w.field}_must_be_in_[0,1]"
                    )
            if w.field == "temperature" and isinstance(w.new, (int, float)):
                if not -60.0 <= w.new <= 60.0:
                    violations.append(
                        f"invariant_violation:{w.entity}.temperature_out_of_range"
                    )
        return violations


class ImmuneMemoryRules(DefaultWorldRules):
    """v0.3 ruleset: the v0.1 world + one new law — adaptive immune memory.

    The kernel is frozen; this is a proposal implemented purely as rules:

    * new agent field ``immune_memory`` in [0, 1] (naive, 0.0, at genesis);
    * infection probability is scaled by ``1 - 0.85 * immune_memory``;
    * infection damage is attenuated by ``1 - 0.60 * immune_memory``;
    * every infection teaches: memory grows +0.35, atomically inside the
      SAME transition that writes ``infected`` and ``health``;
    * recovery is faster with memory: ``+0.20 * immune_memory``.

    Addressable draws are NOT changed: the immune world consumes the exact
    same roll stream as the 0.1.0 world under the same seed (same purposes,
    same (tick, entity, purpose, index) addresses, same rng_version), so any
    divergence is attributable to the laws alone — not to different dice.
    """

    ruleset_version = "0.3.0"

    #: Duck-typed by ``create_world``: which systems the world runs.
    default_systems = [
        "ClimateSystem",
        "AgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]

    def __init__(self) -> None:
        super().__init__()
        # Rulesets may extend the schema: immune_memory is an agent field.
        self._field_types = dict(FIELD_TYPES)
        self._field_types["immune_memory"] = float

    def field_type(self, field_name: str) -> type | None:
        return self._field_types.get(field_name)

    def validate_transition(
        self, transition: Transition, snapshot: Snapshot
    ) -> list[str]:
        violations = super().validate_transition(transition, snapshot)
        for w in transition.writes:
            if w.field == "immune_memory" and isinstance(w.new, (int, float)):
                if not 0.0 <= w.new <= 1.0:
                    violations.append(
                        f"invariant_violation:{w.entity}.immune_memory_must_be_in_[0,1]"
                    )
        return violations

    def extra_genesis_fields(self, kind, rng, tick, entity):
        """Duck-typed hook used by the world generator (spec-free)."""
        if kind == "agent":
            # Naive immune system at genesis: no draw consumed, so the
            # genesis draw stream of the default world stays untouched.
            return [("immune_memory", 0.0)]
        return []


RULESETS: dict[str, type] = {
    "default": DefaultWorldRules,
    "immune": ImmuneMemoryRules,
}


def get_ruleset(name: str):
    try:
        return RULESETS[name]()
    except KeyError:
        raise KeyError(f"unknown ruleset {name!r}; have {sorted(RULESETS)}") from None
