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


class CivicRules(PlayerLifeRules):
    """v0.7 game ruleset — the CIVIC world: the player steers the world.

    v0.6's ``player_life`` made the player an agent inside a world: seven
    personal actions (work / migrate / explore / heal / trade / rest /
    idle), one decision per live tick, recorded in the journal and
    replayable. That is a survival game. The v0.7 direction is different:
    the WORLD is the object, and the player is steward, researcher and
    law-maker at once.

    This ruleset keeps the v0.6 world intact (compost survival base +
    heredity + world memory + the personal action card) and adds exactly
    one thing: **the civic layer** —

    * ``DirectiveSystem`` (priority 45) enacts the player's DECREES. A
      decree names a region and a lever (amend / water / rest) and is
      committed as an ordinary transition ``player.directive`` that writes
      the region's law parameters. The player is therefore a law-maker
      whose laws are auditable like any other cause.
    * ``CivicAgricultureSystem`` computes each region's ecology from its
      base law PLUS the decrees enacted for it (one writer per field:
      decrees write the parameters, the law reads them).

    The base law stays the v0.3.3-G compost law, so a civic world with no
    decrees behaves exactly like a compost world. Every difference in an
    experiment is therefore attributable to the DECREES and not to a
    different physics — the attribution discipline of the whole repo.

    The three law parameters (``labor_diversion``, ``water_aid``,
    ``rest_until``) are created at GENESIS, because the resolver forbids
    creating fields mid-run (I3: every future field exists as a
    placeholder). The moment a decree enters force is DERIVED, not
    configured: a decree enacted at tick T is visible to the law from
    tick T+1, because all systems of a tick read the same snapshot
    (I4/I5). The law in force at tick t is therefore
    ``base ruleset version + the region's decree ledger up to t-1`` —
    reconstructible, hence comparable across runs.

    Research worlds are untouched: they declare neither the new fields
    nor the new systems, so their genesis and journals stay
    bit-identical.
    """

    ruleset_version = "0.7.0"
    description = (
        "v0.7 game ruleset: the v0.6 living world + the civic layer — the "
        "player enacts region-scoped laws (amend / water / rest) that enter "
        "force on the next tick; the base compost law is unchanged."
    )

    default_systems = [
        "ClimateSystem",
        "CivicAgricultureSystem",  # base compost law + the enacted decrees
        "ImmuneDiseaseSystem",
        "AgentSystem",
        "SenescenceSystem",
        "BirthSystem",
        "RuinSystem",
        "ExplorationSystem",
        "PlayerAgentSystem",  # the personal card (v0.6) still exists
        "DirectiveSystem",  # the civic layer (v0.7)
    ]

    purposes = {
        **PlayerLifeRules.purposes,
        "player.directive": (
            "player-enacted civic decree; value is the directive KIND "
            "(amend / water / rest), never a probability — the magnitude "
            "lives in the written law parameter (old -> new)"
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._field_types.update(
            {
                # region law parameters written by DirectiveSystem
                "labor_diversion": float,
                "water_aid": float,
                "rest_until": int,
            }
        )

    def extra_genesis_fields(self, kind, rng, tick, entity, info=None):
        fields = super().extra_genesis_fields(kind, rng, tick, entity, info)
        if kind == "region":
            # Neutral law: no diversion, no irrigation, no fallow.
            fields.extend(
                [
                    ("labor_diversion", 0.0),
                    ("water_aid", 0.0),
                    ("rest_until", 0),
                ]
            )
        return fields

    def validate_transition(
        self, transition: Transition, snapshot: Snapshot
    ) -> list[str]:
        violations = super().validate_transition(transition, snapshot)
        for w in transition.writes:
            if w.field in ("labor_diversion", "water_aid") and isinstance(
                w.new, (int, float)
            ):
                if not 0.0 <= w.new <= 1.0:
                    violations.append(
                        f"invariant_violation:{w.entity}.{w.field}_must_be_in_[0,1]"
                    )
            if w.field == "rest_until" and isinstance(w.new, int):
                if w.new < 0:
                    violations.append(
                        f"invariant_violation:{w.entity}.rest_until_must_be_>=_0"
                    )
        return violations

class SpatialRules(PlayerLifeRules):
    """v0.8 game ruleset — the SPATIAL living world (the vertical slice).

    The v0.7 civic world made the WORLD the object of the game, but it
    was a world of REGIONS: one soil, one food stock, one population per
    region, and the map could only show blocks. The measured diagnosis
    (``experiments/reports/v08_demography.md``) also showed the world
    could not survive its own horizon: the birth supply was a
    per-REGION event, and the compost law returned nutrients in
    proportion to the POPULATION while the degradation was flat — so
    every death lowered the soil, which starved the survivors. The world
    died at ~tick 250 no matter what the player did.

    v0.8 is therefore a MODEL change, composed as rules over the frozen
    kernel:

    * **Cells.** A region owns a GRID of cells; each cell has its own
      soil, food, people, climate factor and LAW. Cells differ in
      rainfall (a genesis draw), so the map is heterogeneous and the
      player's choices are spatial. Food is local: a cell's people eat
      that cell's stores, and migration moves people to a better
      neighbouring cell.
    * **Soil per worker, not per region.** Degradation and the nutrient
      return both scale with the labour applied to the field, so the
      equilibrium soil is a property of the labour regime and NOT of the
      head count — the death spiral of v0.7 is gone by construction.
    * **Births per adult.** Conception is a per-adult probability gated
      by the cell's food and carrying capacity, so the supply of
      newborns scales with the number of reproductive adults.
    * **A nursery policy** (``nursery``): more conceptions and healthier
      children in a cell. It changes reproduction and child health, not
      the death rate — a policy inside the model, not a compensation
      bolted onto mortality.
    * **The reserve of lives.** The dormant pool that births activate is
      sized for the horizon (ratio 4): with a per-adult birth law the
      pool must cover the turnover of a long run, and its exhaustion is
      an observable end-state ("the world is full").

    The v0.6/v0.7 worlds are untouched: they name neither the new
    systems nor the new fields, so their genesis and journals stay
    bit-identical (the freeze).
    """

    ruleset_version = "0.8.0"
    description = (
        "v0.8 game ruleset: the spatial living world — a grid of cells "
        "with its own soil, food, people and law; a per-worker soil law; "
        "a per-adult birth law; the nursery policy."
    )

    #: The grid of cells inside one region.
    GRID_W = 2
    GRID_H = 2

    #: The reserve of lives (the dormant pool births activate). Sized for
    #: the horizon: with a per-adult birth law, the pool must cover the
    #: turnover of a long run. Measured: a stable world replaces ~0.25
    #: of its population per 100 ticks, so 6x the genesis head count
    #: covers ~2400 ticks of play. Its exhaustion is an observable end
    #: state ("the world is full"), not a silent failure.
    dormant_pool_ratio = 6.0

    #: The world starts AFTER a plague: the survivors carry the memory of
    #: it, so the first wave is a threat and not an instant massacre.
    IMMUNE_MEMORY_BASELINE = 0.45

    #: Which systems the world runs. The spatial law replaces the
    #: region-level one; the disease, the ruins, the exploration and the
    #: personal card of v0.6 stay.
    default_systems = [
        "ClimateSystem",
        "SpatialAgricultureSystem",  # per-cell ecology (v0.8 soil law)
        "ImmuneDiseaseSystem",
        "SpatialAgentSystem",  # per-cell census, metabolism, migration
        "SenescenceSystem",
        "SpatialBirthSystem",  # per-adult conception (v0.8 demography)
        "RuinSystem",
        "ExplorationSystem",
        "SpatialPlayerAgentSystem",  # the v0.6 card, taught to live in a cell
        "SpatialDirectiveSystem",  # the cell laws (amend/water/rest/nursery)
    ]

    purposes = {
        **PlayerLifeRules.purposes,
        "player.directive": (
            "player-enacted civic decree; value is the directive KIND "
            "(amend / water / rest / nursery), never a probability — the "
            "magnitude lives in the written law parameter (old -> new)"
        ),
        "birth.conceive": (
            "per-adult conception roll in a cell; threshold is the "
            "per-adult conception probability (food- and nursery-gated), "
            "so the supply of newborns scales with the adults"
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._field_types.update(
            {
                # cell fields
                "cell": str,  # an agent's cell
                "cell_x": int,
                "cell_y": int,
                "rain_factor": float,
                "nursery": float,
                # the memory of the cell: when it was emptied, when it
                # last produced a child
                "empty_since": int,
                "births_total": int,
                "last_birth_tick": int,
                # the law parameters of a cell (written by the decrees)
                "labor_diversion": float,
                "water_aid": float,
                "rest_until": int,
                # v0.10 capacity policy: is the parcel part of the world
                # (1) or wild land waiting for a claim (0); what the world
                # answered to the last claim / terrace order; how many
                # terraces a cell carries and what the last one cost.
                "land_active": int,
                "claim_state": int,
                "terraces": int,
                "terrace_state": int,
                "land_cost": float,
            }
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _cell_of(self, agent_index: int, region_count: int) -> str:
        """The cell an agent is born in (must match the generator).

        The generator assigns agents to regions round-robin
        (``region:i % region_count``); the cells of a region are filled
        in the same order, so the assignment is a pure function of the
        agent index — no draws, no state.
        """
        region = agent_index % max(1, region_count)
        cell_index = (agent_index // max(1, region_count)) % (self.GRID_W * self.GRID_H)
        return f"cell:{region}:{cell_index}"

    def extra_genesis_entities(self, rng, tick, region_count, agent_count):
        """The cells of the spatial world (a new entity kind at genesis).

        The cells are born through the normal genesis path — ordinary
        transitions with recorded draws — so they carry provenance from
        tick 0 like every other entity. Their soil and rainfall are
        addressable draws of the cell itself, so adding a cell never
        shifts another entity's genesis (invariant I8).
        """
        head_count: dict[str, int] = {}
        for i in range(agent_count):
            cell = self._cell_of(i, region_count)
            head_count[cell] = head_count.get(cell, 0) + 1

        transitions = []
        for r in range(region_count):
            for c in range(self.GRID_W * self.GRID_H):
                entity = f"cell:{r}:{c}"
                transitions.append(
                    self._genesis_cell(
                        rng, tick, entity, r, c,
                        x=r * self.GRID_W + (c % self.GRID_W),
                        y=c // self.GRID_W,
                        population=head_count.get(entity, 0),
                        active=True,
                    )
                )
        return transitions

    def _genesis_cell(self, rng, tick, entity, region_index, index, *,
                      x, y, population, active, extra_fields=()):
        """One cell's genesis transition (also used for reserve land).

        ``extra_fields`` lets a descendant ruleset add ITS fields to the
        same genesis transition without changing the fields of this
        ruleset: the v0.6/v0.8/v0.10 genesis transitions stay identical.
        """
        from causal_world.world.generator import genesis_attr, genesis_transition

        draws: list = []
        soil = 0.25 + 0.45 * genesis_attr(rng, tick, entity, 0, draws)
        rain = 0.85 + 0.30 * genesis_attr(rng, tick, entity, 1, draws)
        # The food buffer is EXTENSIVE: it scales with the people the cell
        # must feed (the same convention as the regions).
        buffer_scale = max(1.0, population / 5.0)
        food = (
            90.0 + 60.0 * genesis_attr(rng, tick, entity, 2, draws)
        ) * buffer_scale
        pop_base = population if active else 0
        fields = [
            ("region", f"region:{region_index}"),
            # The cells of the regions form ONE strip: the global x of a
            # cell is region_index * GRID_W + local x, so the border cells
            # of two regions are neighbours and people can walk across a
            # regional border.
            ("cell_x", x),
            ("cell_y", y),
            ("soil_fertility", soil),
            ("rain_factor", rain),
            ("food_stock", food if active else 0.0),
            ("population", population),
            ("workers", population),
            ("pop_base", pop_base),
            # the neutral law of a cell
            ("labor_diversion", 0.0),
            ("water_aid", 0.0),
            ("rest_until", 0),
            ("nursery", 0.0),
            # the memory of the cell (v0.8): the situation layer reads
            # these to say WHEN a problem started
            ("empty_since", 0),
            ("births_total", 0),
            ("last_birth_tick", 0),
            # v0.10 capacity policy: wild land is part of the world's
            # state from genesis, not a config change at claim time.
            ("land_active", 1 if active else 0),
            ("claim_state", 0),
            ("terraces", 0),
            ("terrace_state", 0),
            ("land_cost", 0.0),
        ]
        fields.extend(extra_fields)
        return genesis_transition(tick, entity, "genesis.cell", fields, draws)

    def extra_genesis_fields(self, kind, rng, tick, entity, info=None):
        fields = super().extra_genesis_fields(kind, rng, tick, entity, info)
        info = info or {}
        if kind == "agent":
            dormant = bool(info.get("dormant", False))
            if dormant:
                fields.append(("cell", "none"))
            else:
                fields.append(
                    (
                        "cell",
                        self._cell_of(
                            int(info.get("index", 0)),
                            int(info.get("region_count", 1)),
                        ),
                    )
                )
            # The world starts after a plague: replace the naive immune
            # memory of the v0.6 hook with the memory of the survivors.
            fields = [f for f in fields if f[0] != "immune_memory"]
            fields.append(
                (
                    "immune_memory",
                    0.0 if dormant else self.IMMUNE_MEMORY_BASELINE,
                )
            )
        return fields

    def validate_transition(
        self, transition: Transition, snapshot: Snapshot
    ) -> list[str]:
        violations = super().validate_transition(transition, snapshot)
        for w in transition.writes:
            if w.field in ("labor_diversion", "water_aid", "nursery") and isinstance(
                w.new, (int, float)
            ):
                if not 0.0 <= w.new <= 1.0:
                    violations.append(
                        f"invariant_violation:{w.entity}.{w.field}_must_be_in_[0,1]"
                    )
            if w.field == "rest_until" and isinstance(w.new, int):
                if w.new < 0:
                    violations.append(
                        f"invariant_violation:{w.entity}.rest_until_must_be_>=_0"
                    )
        return violations


class SpatialRules3(SpatialRules):
    """The v0.8 spatial world on a 3x3 grid of cells per region.

    A different world shape is a different ruleset (the version is part
    of the fingerprint), so the comparison of a 2x2 and a 3x3 world is
    an experiment, not a configuration change.
    """

    ruleset_version = "0.8.0-s3"
    description = (
        "v0.8 game ruleset: the spatial living world on a 3x3 grid of "
        "cells per region."
    )

    GRID_W = 3
    GRID_H = 3


class CapacityRules(SpatialRules):
    """v0.10 — the capacity world: land that can be claimed, terraces.

    v0.9 measured the wall every demographic lever hits: a cell cannot
    grow past ``pop_base x (1 + soil)``. A nursery in a saturated world
    bought +1 birth in 100 ticks. This ruleset makes the wall itself a
    policy object, with a PRICE:

    * **Reserve land.** Every region owns one row of WILD parcels
      (``active = 0``). They exist in the state from genesis, with their
      own soil, so claiming one is an ordinary committed transition —
      never a hidden config change. Unclaimed land is ignored by the
      ecology, the census, births, migration and the situation feed: it
      is not a cell yet, it is land.
    * **``claim``** activates a wild parcel: it becomes a real cell with
      a small ``pop_base`` (a homestead, not a city), and the claim is
      PAID from the region's richest cell. Insufficient stores do not
      silently cancel the order: the world records the refusal in
      ``claim_state`` and the journal, so the player sees WHY.
    * **``terrace``** raises the capacity of a working cell
      (``pop_base``) at a cost in food and soil: capacity is bought, not
      granted. A cell can be terraced a bounded number of times.

    Both levers are ordinary directives of the civic layer, so they
    enter force on T+1, are versioned by the journal, and can be forked
    in a counterfactual like every other law.
    """

    ruleset_version = "0.10.0"
    description = (
        "v0.10 game ruleset: the spatial living world plus a priced "
        "capacity policy — claimable wild land and terraces."
    )

    #: Wild parcels per region (one row below the cultivated grid).
    RESERVE_PER_REGION = 2
    #: What a claimed parcel starts with: a homestead, not a city.
    RESERVE_POP_BASE = 3
    RESERVE_FOOD = 25.0
    #: Price of a claim, paid from the richest working cell of the region.
    CLAIM_COST = 90.0
    #: Price of a terrace: food now, and the construction damages soil.
    TERRACE_GAIN = 2
    TERRACE_COST = 60.0
    TERRACE_SOIL_COST = 0.04
    #: How many terraces one cell may carry (a bounded lever).
    TERRACE_MAX = 3

    default_systems = [
        "ClimateSystem",
        "SpatialAgricultureSystem",
        "ImmuneDiseaseSystem",
        "SpatialAgentSystem",
        "SenescenceSystem",
        "SpatialBirthSystem",
        "RuinSystem",
        "ExplorationSystem",
        "SpatialPlayerAgentSystem",
        "CapacityDirectiveSystem",  # the v0.10 levers (claim / terrace)
    ]

    #: The prices of the capacity levers, as ruleset parameters: an
    #: experiment varies the PRICE, never the system's code. The engine
    #: copies only declared constants into the named system.
    system_parameters = {
        "CapacityDirectiveSystem": {
            "CLAIM_COST": CLAIM_COST,
            "TERRACE_COST": TERRACE_COST,
            "TERRACE_GAIN": TERRACE_GAIN,
            "TERRACE_SOIL_COST": TERRACE_SOIL_COST,
            "TERRACE_MAX": TERRACE_MAX,
            "RESERVE_POP_BASE": RESERVE_POP_BASE,
            "RESERVE_FOOD": RESERVE_FOOD,
        },
    }

    purposes = {
        **SpatialRules.purposes,
        "player.claim": (
            "player enacting a CLAIM of wild land; the written fields on "
            "the parcel (active, claim_state, pop_base) are the claim "
            "itself, the price is a write on the donor cell"
        ),
        "player.terrace": (
            "player building a TERRACE; the written fields on the cell "
            "(pop_base, terraces, soil_fertility) are the build, the "
            "price is a write on the same cell's stores"
        ),
    }

    def extra_genesis_entities(self, rng, tick, region_count, agent_count):
        transitions = super().extra_genesis_entities(
            rng, tick, region_count, agent_count
        )
        # Wild land: one row below the cultivated grid of every region.
        # It is a cell-shaped entity with active=0, so a claim is a write
        # on an entity that has existed (and been journaled) since tick 0.
        for r in range(region_count):
            for k in range(self.RESERVE_PER_REGION):
                index = self.GRID_W * self.GRID_H + k
                entity = f"cell:{r}:{index}"
                transitions.append(
                    self._genesis_cell(
                        rng, tick, entity, r, index,
                        x=r * self.GRID_W + k,
                        y=self.GRID_H,
                        population=0,
                        active=False,
                    )
                )
        return transitions


class ResettlementRules(CapacityRules):
    """v0.11 — resettlement: using the land the player opened.

    v0.10 ended on a measured failure: a claim creates room, but the
    people do not come, because the world's own migration fires on
    hunger and moves to a neighbouring cell. Capability CREATION and
    capability USE were two mechanisms, and only one existed.

    This ruleset adds the second, inside the capacity world:

    * the ``resettle`` order names a destination cell and a count
      (0 = as many as the cell can take). The world picks the donor
      deterministically — the most over-capacity cell of the SAME
      region, then the shortest distance, then the id;
    * one committed transition moves the agents (``agent.cell``), the
      source's population and food, and the destination's population;
      the price is transport food per migrant, growing with distance;
    * a destination must be habitable BEFORE it receives people: room,
      soil and a food reserve of its own;
    * fields written by the system (``resettled_in``, ``resettled_out``,
      ``resettle_state``, ``resettle_moved``, ``resettle_cost``,
      ``last_source``, ``last_resettle_tick``) exist from genesis, so
      every write is a change of an existing fact, never a creation.

    Scope limit, stated in the code rather than discovered in a report:
    resettlement is INTRA-regional in v0.11. A cross-region caravan
    needs trade and corridors, which the model does not have yet; faking
    it would also make the region totals stale for a tick.
    """

    ruleset_version = "0.11.0"
    description = (
        "v0.11 game ruleset: the capacity world plus resettlement — a "
        "priced, atomic, intra-regional move of people into habitable "
        "cells, with the source's loss recorded."
    )

    #: The prices of the resettlement order (a transport price per head).
    RESETTLE_FOOD_BASE = 4.0
    RESETTLE_FOOD_PER_STEP = 0.5
    RESETTLE_SOIL_MIN = 0.35
    RESETTLE_FOOD_PC_MIN = 3.0
    RESETTLE_MAX_PER_ORDER = 12

    default_systems = [
        "ClimateSystem",
        "SpatialAgricultureSystem",
        "ImmuneDiseaseSystem",
        "SpatialAgentSystem",
        "SenescenceSystem",
        "SpatialBirthSystem",
        "RuinSystem",
        "ExplorationSystem",
        "SpatialPlayerAgentSystem",
        "ResettlementDirectiveSystem",  # v0.10 levers + resettle
    ]

    system_parameters = {
        **CapacityRules.system_parameters,
        "ResettlementDirectiveSystem": {
            "CLAIM_COST": CapacityRules.CLAIM_COST,
            "TERRACE_COST": CapacityRules.TERRACE_COST,
            "TERRACE_GAIN": CapacityRules.TERRACE_GAIN,
            "TERRACE_SOIL_COST": CapacityRules.TERRACE_SOIL_COST,
            "TERRACE_MAX": CapacityRules.TERRACE_MAX,
            "RESERVE_POP_BASE": CapacityRules.RESERVE_POP_BASE,
            "RESERVE_FOOD": CapacityRules.RESERVE_FOOD,
            "RESETTLE_FOOD_BASE": RESETTLE_FOOD_BASE,
            "RESETTLE_FOOD_PER_STEP": RESETTLE_FOOD_PER_STEP,
            "RESETTLE_SOIL_MIN": RESETTLE_SOIL_MIN,
            "RESETTLE_FOOD_PC_MIN": RESETTLE_FOOD_PC_MIN,
            "RESETTLE_MAX_PER_ORDER": RESETTLE_MAX_PER_ORDER,
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self._field_types.update(
            {
                # v0.11 resettlement: the counters and the last answer.
                "resettled_in": int,
                "resettled_out": int,
                "resettle_state": int,
                "resettle_moved": int,
                "resettle_cost": float,
                "last_source": str,
                "last_resettle_tick": int,
            }
        )

    def _genesis_cell(self, *args, **kwargs):
        """Add the resettlement facts to every cell at genesis.

        A field written later must exist from tick 0 (the kernel forbids
        mid-run creation), and wild parcels are cells too: they can be a
        destination the moment they are claimed.
        """
        return super()._genesis_cell(
            *args,
            extra_fields=(
                ("resettled_in", 0),
                ("resettled_out", 0),
                ("resettle_state", 0),
                ("resettle_moved", 0),
                ("resettle_cost", 0.0),
                ("last_source", "none"),
                ("last_resettle_tick", 0),
            ),
            **kwargs,
        )


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
        "player_civic": CivicRules,
        "player_spatial": SpatialRules,
        "player_spatial3": SpatialRules3,
        "player_capacity": CapacityRules,
        "player_resettle": ResettlementRules,
    }
)


def get_ruleset(name: str):
    try:
        return RULESETS[name]()
    except KeyError:
        raise KeyError(f"unknown ruleset {name!r}; have {sorted(RULESETS)}") from None
