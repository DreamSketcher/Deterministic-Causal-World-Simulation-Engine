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
