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

    def extra_genesis_fields(self, kind, rng, tick, entity, info=None):
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


class FallowRules(ImmuneMemoryRules):
    """v0.3.2 experiment D — fallow recovery.

    The soil clock keeps ticking WHERE fields are farmed; but abandoned
    regions (population 0) recover +0.0015/tick instead of degrading.
    Hypothesis: spatial dynamics (death + migration emptying regions)
    can produce a self-sustaining oscillation — the first emergent
    pattern with no director.
    """

    ruleset_version = "0.3.2d"
    description = (
        "Experiment D (fallow): soil of abandoned regions recovers "
        "+0.0015/tick; farmed regions degrade exactly as in 0.3.0."
    )
    default_systems = [
        "ClimateSystem",
        "FallowAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]


class StorageRules(ImmuneMemoryRules):
    """v0.3.2 experiment E — stock-dependent spoilage.

    Spoilage is 2 % only for stocks above 50 rations per agent, tends to
    zero for small stocks (eaten before rotting), and rises to 4 % for a
    surplus above 10 rations per agent. Soil degrades exactly as in
    0.3.0. Tests whether the collapse is an AVERAGE deficit or a PEAK
    deficit (bad seasons hitting an empty buffer).
    """

    ruleset_version = "0.3.2e"
    description = (
        "Experiment E (storage): spoilage depends on stock size — tiny "
        "stocks barely rot, surpluses above 10 rations/agent rot at 4 %."
    )
    default_systems = [
        "ClimateSystem",
        "StorageAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]


class CropRotationRules(ImmuneMemoryRules):
    """v0.3.2 experiment F — crop rotation via labor-load fluctuation.

    Degradation = 0.0009 × (workers/population) × stability_penalty,
    where the penalty grows (up to ×1.5) when the region's workforce is
    constant (monoculture) and shrinks (down to ×0.5) when the load
    fluctuates (~10-tick exponential window). A negative feedback: stable
    exploitation degrades faster, forcing fluctuations that let the soil
    rest. Adds two per-region fields (labor_ema, labor_ema2) through the
    genesis hook — kernel untouched.
    """

    ruleset_version = "0.3.2f"
    description = (
        "Experiment F (crop rotation): stable maximal labor load "
        "degrades soil 50 % faster; a fluctuating load lets it rest."
    )
    default_systems = [
        "ClimateSystem",
        "RotationAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]

    def __init__(self) -> None:
        super().__init__()
        # The rotation statistic is part of THIS proposal's schema.
        self._field_types["labor_ema"] = float
        self._field_types["labor_ema2"] = float

    def extra_genesis_fields(self, kind, rng, tick, entity, info=None):
        fields = super().extra_genesis_fields(kind, rng, tick, entity, info)
        if kind == "region":
            pop = float((info or {}).get("population", 0))
            # Born "stable": the field has been monocultured forever.
            fields.extend([("labor_ema", pop), ("labor_ema2", pop * pop)])
        return fields


class CompostRules(ImmuneMemoryRules):
    """v0.3.3 experiment G — compost: direct fertility return.

    Every agent returns nutrients to the soil of its region:
    ``recovery = population × 0.000018 × (1 − soil)`` (diminishing
    returns). The constant is the proposal's 0.0018 rescaled by 1/1000:
    the frozen degradation is a flat 0.0009 per region per tick, not
    per worker, so at 100 agents/region the balance point is the
    intended soil ≈ 0.5. Tests whether a trivial nutrient cycle is
    enough — i.e. whether the original model's fatal flaw was the
    absence of any matter cycle.
    """

    ruleset_version = "0.3.3g"
    description = (
        "Experiment G (compost): every agent returns nutrients to its "
        "region's soil; balance point ≈ soil 0.5 at genesis density."
    )
    default_systems = [
        "ClimateSystem",
        "CompostAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]


class ThreeFieldRules(ImmuneMemoryRules):
    """v0.3.3 experiment H — forced three-field cycle.

    After 200 ticks of cultivation a region lies fallow for 100 ticks:
    no harvest, active recovery +0.003/tick. New per-region fields
    ``cultivation_streak``/``fallow_timer`` (ints, created at genesis,
    phase-staggered by 20 × region index so the cycles overlap like a
    real three-field system instead of falling fallow in sync).
    """

    ruleset_version = "0.3.3h"
    description = (
        "Experiment H (three-field): 200 ticks of cultivation force 100 "
        "ticks of fallow (+0.003 soil/tick), cycles phase-staggered."
    )
    default_systems = [
        "ClimateSystem",
        "ThreeFieldAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
    ]

    #: Lengths must match ThreeFieldAgricultureSystem's constants.
    CULTIVATION_LIMIT = 200

    def __init__(self) -> None:
        super().__init__()
        self._field_types["cultivation_streak"] = int
        self._field_types["fallow_timer"] = int

    def extra_genesis_fields(self, kind, rng, tick, entity, info=None):
        fields = super().extra_genesis_fields(kind, rng, tick, entity, info)
        if kind == "region":
            index = int((info or {}).get("index", 0))
            region_count = max(int((info or {}).get("region_count", 1)), 1)
            stagger = (index * self.CULTIVATION_LIMIT) // region_count
            fields.extend([("cultivation_streak", stagger), ("fallow_timer", 0)])
        return fields


class FertileMigrationRules(ImmuneMemoryRules):
    """v0.3.3 experiment I — migration toward fertility, WITH fallow.

    Soil laws are the v0.3.2-D laws (abandoned regions heal); the change
    is the agents' information: a migrating agent picks the best other
    region by ``soil × food_stock / max(population, 1)`` instead of the
    blind next-region walk. Tests the information hypothesis: was the
    collapse physics or blindness?
    """

    ruleset_version = "0.3.3i"
    description = (
        "Experiment I (fertile migration + fallow): migration targets "
        "the most fertile, least crowded region; abandoned soil heals."
    )
    default_systems = [
        "ClimateSystem",
        "FallowAgricultureSystem",
        "ImmuneDiseaseSystem",
        "FertileMigrationAgentSystem",
    ]


class FertileMigrationOnlyRules(ImmuneMemoryRules):
    """v0.3.3 experiment I-attribution control — informed migration on
    the FROZEN soil laws (no fallow recovery). If I survives and this
    one does not, survival needed the nutrient side too, not just sight.
    """

    ruleset_version = "0.3.3i-plain"
    description = (
        "Experiment I control: informed migration alone, soil laws "
        "frozen (no fallow recovery)."
    )
    default_systems = [
        "ClimateSystem",
        "AgricultureSystem",
        "ImmuneDiseaseSystem",
        "FertileMigrationAgentSystem",
    ]


RULESETS.update(
    {
        "iron_health": IronHealthRules,
        "stable_soil": StableSoilRules,
        "no_hunger_immunity": NoHungerImmunityRules,
        "no_disease_control": NoDiseaseControlRules,
        "fallow": FallowRules,
        "storage": StorageRules,
        "crop_rotation": CropRotationRules,
        "compost": CompostRules,
        "three_field": ThreeFieldRules,
        "fertile_migration": FertileMigrationRules,
        "fertile_migration_only": FertileMigrationOnlyRules,
    }
)


def get_ruleset(name: str):
    try:
        return RULESETS[name]()
    except KeyError:
        raise KeyError(f"unknown ruleset {name!r}; have {sorted(RULESETS)}") from None
