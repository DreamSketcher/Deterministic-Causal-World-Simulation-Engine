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


class PlayerLifeRules(CompostRules):
    """v0.6 game ruleset — the LIFE-phase world (proposal v06-01, step 2).

    A playable, *living* world: the compost survival base (O6 — agents
    persist; disease and ``immune_memory`` present) extended with HEREDITY
    and WORLD-MEMORY, composed entirely as rules over the frozen kernel:

    * **Heredity (``BirthSystem``).** A dormant pool of inactive agents is
      pre-allocated at genesis (``dormant_pool_ratio``); births ACTIVATE a
      dormant slot by writes (the resolver forbids mid-run field creation —
      ``allow_creation=False`` in ``step()`` — so every future field exists
      at genesis as a placeholder). A newborn inherits ``immune_memory``,
      ``immunity``, ``max_health`` and ``risk_tolerance`` from a random MATURE
      alive parent of its region, plus addressable mutation. Because
      survivors accumulate ``immune_memory`` and pass it on, the average
      memory of newborns RISES with generation depth — emergent evolution,
      not a programmed trend. Generation is a state field (U2), so drift is
      one ``avg(immune_memory) GROUP BY generation`` query.
    * **World memory (``RuinSystem`` + ``ExplorationSystem``).** One dormant
      ruin slot per region (``ruin_slots_per_region``) activates when the
      region goes extinct (``population == 0``), recording a ``type`` derived
      from the region's state and a food reserve; it degrades with age and
      collapses past a threshold, and is UPDATED (never duplicated) on
      re-extinction. Alive agents may explore an active ruin for a food bonus
      that lands in their causal trace.

    A world WITH a player is a different ruleset (``0.6.0``) and therefore a
    different fingerprint from the NPC research worlds — research and game
    over one frozen kernel. ``player.decision`` draws carry a SUPPLIED value
    (the chosen action index as a float), never a seed-derived roll, so dice
    cannot veto an explicit choice (step 1, ``v06_player_input_draw.md``);
    exploration is its OWN action (U3), wired to the decision card in step 3.

    The default/research worlds define none of ``dormant_pool_ratio`` /
    ``ruin_slots_per_region`` and run none of the four new systems, so their
    genesis and journals stay bit-identical (the freeze we proved at
    ``0960a67``). See ``v06_heredity_ruins_design.md``.
    """

    ruleset_version = "0.6.0"
    description = (
        "v0.6 game ruleset: compost survival world + heredity (dormant pool, "
        "BirthSystem) + world memory (RuinSystem, ExplorationSystem) + "
        "player.decision purpose for player-supplied choices (LIFE phase)."
    )

    #: Genesis capacity of a newborn's health (BirthSystem mean-reverts
    #: max_health toward this baseline; keep in sync with BirthSystem).
    MAX_HEALTH_BASE = 100.0

    #: Opt-in dormant pool + ruin slots (duck-typed by the generator).
    #: O5: pool == live count (2N total); one ruin slot per region (nuance 4).
    dormant_pool_ratio = 1.0
    ruin_slots_per_region = 1

    #: Which systems the world runs (duck-typed by create_world). Compost
    #: base (O6) + the four v0.6 systems; execution order is by priority
    #: (AgentSystem census 1 → Senescence 25 → Birth 30 → Ruin 31 →
    #: Exploration 40), so Birth/Ruin see the census and Exploration sees
    #: this tick's ruin activation.
    default_systems = [
        "ClimateSystem",
        "CompostAgricultureSystem",
        "ImmuneDiseaseSystem",
        "AgentSystem",
        "SenescenceSystem",  # game-only: generational turnover (Decision 1)
        "BirthSystem",
        "RuinSystem",
        "ExplorationSystem",
        "PlayerAgentSystem",  # game-only: one agent answers to a human (step 3)
    ]

    purposes = {
        **PURPOSES,
        "player.decision": (
            "player-supplied action for the controlled agent; value is the "
            "chosen action index (float), not a probability"
        ),
        "birth.occurrence": (
            "per-region birth-occasion roll; threshold is the food-driven "
            "birth rate (U1), so a region yields ~1 birth per 20-50 ticks"
        ),
        "birth.select": (
            "which dormant pool slot is activated: index into the SORTED free "
            "list (nuance 2 — addressable, not pool[0], not random.choice)"
        ),
        "birth.parent": (
            "which mature alive agent of the region is the parent: index into "
            "the SORTED list (nuance 3 — random alive for v0.6)"
        ),
        "birth.mutation": (
            "heredity draws for one newborn, keyed by the child entity: "
            "0=immune_memory mutation, 1=immunity mutation, 2=max_health "
            "mutation, 3=risk_tolerance re-roll, 4=risk_tolerance mutation"
        ),
        "agent.explore": (
            "per-agent ruin-exploration roll, gated by risk_tolerance (the "
            "player's explore is a player.decision action — U3, step 3)"
        ),
        "agent.senescence": (
            "age-based death roll for agents past SENESCENCE_ONSET (game "
            "ruleset only — Decision 1); threshold rises linearly to "
            "MAX_DEATH_PROB at MAX_LIFESPAN"
        ),
    }

    #: Game-only fields that must stay >= 0 (checked in validate_transition).
    _NON_NEGATIVE_GAME = frozenset(
        {
            "max_health",
            "generation",
            "birth_tick",
            "pop_base",
            "age",
            "resource_food",
            "resource_knowledge",
        }
    )

    def __init__(self) -> None:
        super().__init__()  # ImmuneMemoryRules adds ``immune_memory`` (float)
        # Schema extension for heredity + world memory (kernel untouched).
        self._field_types.update(
            {
                # agent heredity
                "parent_id": str,
                "max_health": float,
                "generation": int,
                "birth_tick": int,
                # region: genesis population, fixed (carrying-capacity base)
                "pop_base": int,
                # ruin slot (``region`` is already a str field)
                "active": bool,
                "was_alive": bool,
                "type": str,
                "age": int,
                "resource_food": float,
                "resource_knowledge": float,
                # player control (step 3): the per-tick decision record that
                # makes the journal a lossless replay stream
                "last_action": int,
            }
        )

    def extra_genesis_fields(self, kind, rng, tick, entity, info=None):
        """Genesis hook: heredity fields for agents (live + dormant), the
        fixed ``pop_base`` for regions, and the full ruin-slot schema."""
        fields = super().extra_genesis_fields(kind, rng, tick, entity, info)
        info = info or {}
        if kind == "agent":
            dormant = bool(info.get("dormant", False))
            fields.extend(
                [
                    ("parent_id", "none"),  # gen 0 has no parent
                    # live agents start at full capacity; dormant are blank
                    # placeholders (overwritten by inheritance at birth)
                    ("max_health", 0.0 if dormant else self.MAX_HEALTH_BASE),
                    ("generation", 0),
                    ("birth_tick", 0),
                    # step 3: -1 sentinel = "no decision recorded yet"; the
                    # per-tick record makes the journal a lossless replay
                    # stream (DecisionStreamReader)
                    ("last_action", -1),
                ]
            )
        elif kind == "region":
            fields.append(("pop_base", int(info.get("population", 0))))
        elif kind == "ruin":
            fields.extend(
                [
                    ("active", False),
                    ("was_alive", False),
                    ("region", info.get("region", "")),
                    ("type", ""),
                    ("age", 0),
                    ("resource_food", 0.0),
                    ("resource_knowledge", 0.0),
                ]
            )
        return fields

    def validate_transition(
        self, transition: Transition, snapshot: Snapshot
    ) -> list[str]:
        violations = super().validate_transition(transition, snapshot)
        for w in transition.writes:
            if (
                w.field in self._NON_NEGATIVE_GAME
                and isinstance(w.new, (int, float))
                and w.new < 0
            ):
                violations.append(
                    f"invariant_violation:{w.entity}.{w.field}_must_be_>=_0"
                )
        return violations


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
        "player_life": PlayerLifeRules,
    }
)


def get_ruleset(name: str):
    try:
        return RULESETS[name]()
    except KeyError:
        raise KeyError(f"unknown ruleset {name!r}; have {sorted(RULESETS)}") from None
