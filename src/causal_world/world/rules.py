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


class IronHealthRules(ImmuneMemoryRules):
    """v0.3.1 experiment A — "iron health".

    Hypothesis: the collapse needs infection-driven health loss (acute
    damage + chronic erosion). Law change: infection never lowers health.
    Memory still gates susceptibility and speeds recovery. If the world
    still collapses, the bottleneck is NOT the health link.
    """

    ruleset_version = "0.3.1a"
    description = (
        "Experiment A: infection deals no damage (no acute health write, "
        "no chronic erosion while infected). Memory works as in 0.3.0."
    )
    default_systems = [
        "ClimateSystem",
        "AgricultureSystem",
        "IronHealthDiseaseSystem",
        "IronHealthAgentSystem",
    ]


class StableSoilRules(ImmuneMemoryRules):
    """v0.3.1 experiment B — "stable soil" (invulnerable harvest).

    Hypothesis: the collapse is sustained by the food side. Law change:
    soil fertility no longer depletes (the frozen law's unconditional
    −0.0009/tick countdown is removed; everything else is identical).

    Note on the literal proposal "harvest independent of workers' health":
    that is already the frozen law — harvest never reads health and
    ``workers`` is a plain alive-count. The real food-side link is the
    soil clock, which is what this ruleset tests.
    """

    ruleset_version = "0.3.1b"
    description = (
        "Experiment B: soil fertility never depletes; harvest otherwise "
        "identical. Tests whether the food clock is the bottleneck."
    )
    default_systems = [
        "ClimateSystem",
        "StableSoilAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]


class NoHungerImmunityRules(ImmuneMemoryRules):
    """v0.3.1 experiment C — "no hunger→immunity".

    Hypothesis: the spiral self-sustains through hunger raising
    susceptibility. Law change cuts BOTH hunger→susceptibility links:
    infection probability at the well-fed constant (no hunger factor) and
    immunity no longer erodes with hunger. Damage, memory and recovery
    stay at the 0.3.0 laws.
    """

    ruleset_version = "0.3.1c"
    description = (
        "Experiment C: hunger no longer raises susceptibility — neither "
        "directly (infection probability) nor via immunity erosion."
    )
    default_systems = [
        "ClimateSystem",
        "AgricultureSystem",
        "NoHungerDiseaseSystem",
        "NoHungerErosionAgentSystem",
    ]


class NoDiseaseControlRules(DefaultWorldRules):
    """v0.3.1 control — the v0.1 world with no disease system at all.

    Answers the reference question: how far does the food clock alone
    carry the collapse, with no pathogens present?
    """

    ruleset_version = "0.3.1-ctrl"
    description = (
        "Control: default v0.1 laws, disease system removed entirely. "
        "Isolates the abiotic (food/soil) dynamics."
    )
    default_systems = [
        "ClimateSystem",
        "AgricultureSystem",
        "AgentSystem",
    ]


RULESETS.update(
    {
        "iron_health": IronHealthRules,
        "stable_soil": StableSoilRules,
        "no_hunger_immunity": NoHungerImmunityRules,
        "no_disease_control": NoDiseaseControlRules,
    }
)


def get_ruleset(name: str):
    try:
        return RULESETS[name]()
    except KeyError:
        raise KeyError(f"unknown ruleset {name!r}; have {sorted(RULESETS)}") from None
