"""Procedural genesis: 2 regions + 10 agents, fully deterministic.

Every generated value comes from the addressable RNG
(``draw(tick=0, entity, purpose, index)``) — never from a global random
stream. The generator emits *transitions* (system "GenesisSystem"); they go
through the normal resolve/commit path, so even the initial state has
provenance (spec §28).
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.transition import (
    RandomDraw,
    StateChange,
    Transition,
)

REGION_COUNT = 2
AGENT_COUNT = 10
GENESIS_SYSTEM = "GenesisSystem"
GENESIS_PURPOSE = "genesis.attribute"

#: Stable defaults. The RNG context is (tick=0, entity, purpose, index), so
#: adding/removing OTHER entities never shifts an entity's attributes (I8):
#: a world with 1000 agents gives agent:0..agent:9 exactly the same genesis
#: values as the default 10-agent world.
DEFAULT_REGION_COUNT = REGION_COUNT
DEFAULT_AGENT_COUNT = AGENT_COUNT


def _attr(
    rng: RandomSource,
    tick: int,
    entity: str,
    index: int,
    draws: list[RandomDraw],
) -> float:
    value = rng.draw(tick, entity, GENESIS_PURPOSE, index)
    draws.append(
        RandomDraw(
            purpose=GENESIS_PURPOSE,
            value=value,
            threshold=None,
            outcome=value,
            entity=entity,
            index=index,
        )
    )
    return value


def _genesis_transition(
    tick: int,
    entity: str,
    operation: str,
    fields: list[tuple[str, object]],
    draws: list[RandomDraw],
) -> Transition:
    return Transition(
        id=None,
        tick=tick,
        system=GENESIS_SYSTEM,
        operation=operation,
        reads=[],
        writes=[
            StateChange(entity=entity, field=name, old=None, new=value)
            for name, value in fields
        ],
        random_draws=list(draws),
        priority=0,
    )


def generate_genesis(
    rng: RandomSource,
    tick: int = 0,
    region_count: int = DEFAULT_REGION_COUNT,
    agent_count: int = DEFAULT_AGENT_COUNT,
    rules=None,
) -> list[Transition]:
    """Genesis transitions for the initial state.

    ``rules`` may provide an optional duck-typed hook
    ``extra_genesis_fields(kind, rng, tick, entity, info) -> [(field, value)]``
    so that a ruleset variant (e.g. the v0.3 immune-memory world) can add
    fields without touching the kernel. ``info`` carries facts the
    generator already computed (for regions: ``{"population": N}``).
    Rulesets that declare nothing keep the genesis of the default world
    bit-identical.
    """
    extra = getattr(rules, "extra_genesis_fields", None)

    def extra_fields(kind: str, entity: str, info: dict) -> list[tuple[str, object]]:
        if extra is None:
            return []
        return list(extra(kind, rng, tick, entity, info))

    transitions: list[Transition] = []

    agents_per_region: dict[str, int] = {}
    for i in range(agent_count):
        region = f"region:{i % region_count}"
        agents_per_region[region] = agents_per_region.get(region, 0) + 1

    # ---- regions -------------------------------------------------------
    for r in range(region_count):
        entity = f"region:{r}"
        draws: list[RandomDraw] = []
        temperature_base = 8.0 + 14.0 * _attr(rng, tick, entity, 0, draws)
        rainfall_base = 0.35 + 0.45 * _attr(rng, tick, entity, 1, draws)
        soil_fertility = 0.45 + 0.45 * _attr(rng, tick, entity, 2, draws)
        climate_volatility = 0.5 + 1.0 * _attr(rng, tick, entity, 3, draws)
        temperature = temperature_base + (_attr(rng, tick, entity, 4, draws) - 0.5) * 4.0
        rainfall = min(
            1.0, max(0.0, rainfall_base + (_attr(rng, tick, entity, 5, draws) - 0.5) * 0.2)
        )
        disease_base = 0.15 + 0.20 * _attr(rng, tick, entity, 6, draws)
        population = agents_per_region.get(entity, 0)
        # Food buffer is an EXTENSIVE initial condition: it scales with the
        # number of agents that must eat it, keeping the per-capita world
        # equivalent to the default one. The default 2-region/10-agent world
        # (5 agents per region) keeps factor 1.0 -> bit-identical genesis.
        buffer_scale = max(1.0, population / float(DEFAULT_AGENT_COUNT / REGION_COUNT))
        food_stock = (60.0 + 40.0 * _attr(rng, tick, entity, 7, draws)) * buffer_scale

        fields: list[tuple[str, object]] = [
            ("temperature_base", temperature_base),
            ("rainfall_base", rainfall_base),
            ("soil_fertility", soil_fertility),
            ("climate_volatility", climate_volatility),
            ("temperature", temperature),
            ("rainfall", rainfall),
            ("disease_base", disease_base),
            ("disease_load", disease_base * 0.6),
            ("food_stock", food_stock),
            ("population", population),
            ("workers", population),
        ]
        fields.extend(
            extra_fields(
                "region",
                entity,
                {"population": population, "index": r, "region_count": region_count},
            )
        )
        transitions.append(
            _genesis_transition(tick, entity, "genesis.region", fields, draws)
        )

    # ---- agents ---------------------------------------------------------
    for i in range(agent_count):
        entity = f"agent:{i}"
        draws = []
        health = 65.0 + 30.0 * _attr(rng, tick, entity, 0, draws)
        hunger = 0.1 + 0.3 * _attr(rng, tick, entity, 1, draws)
        immunity = 0.25 + 0.55 * _attr(rng, tick, entity, 2, draws)
        risk_tolerance = _attr(rng, tick, entity, 3, draws)

        fields = [
            ("region", f"region:{i % region_count}"),
            ("alive", True),
            ("infected", False),
            ("health", health),
            ("hunger", hunger),
            ("immunity", immunity),
            ("risk_tolerance", risk_tolerance),
        ]
        fields.extend(extra_fields("agent", entity, {}))
        transitions.append(
            _genesis_transition(tick, entity, "genesis.agent", fields, draws)
        )

    # ---- dormant agent pool (v0.6 heredity, opt-in) ---------------------
    # A ruleset may pre-allocate inactive agent slots that a BirthSystem
    # later ACTIVATES by writes (the resolver forbids creating fields mid-run
    # — allow_creation is False in step() — so every future field must exist
    # at genesis). Duck-typed ``dormant_pool_ratio`` (pool = ratio x
    # agent_count); absent -> 0 -> the default/research worlds are unchanged
    # and stay bit-identical. Dormant slots consume NO genesis draws (blank
    # slates: their real attributes come from inheritance at birth), and
    # because draws are addressable per entity (I8) adding agent:{N}.. never
    # shifts the genesis of agent:0..{N-1}.
    dormant_pool = int(
        round(agent_count * float(getattr(rules, "dormant_pool_ratio", 0.0)))
    )
    for j in range(dormant_pool):
        entity = f"agent:{agent_count + j}"
        fields = [
            ("region", "none"),
            ("alive", False),
            ("infected", False),
            ("health", 0.0),
            ("hunger", 0.0),
            ("immunity", 0.0),
            ("risk_tolerance", 0.0),
        ]
        # ``{"dormant": True}`` lets the ruleset hook give blank placeholders
        # (e.g. max_health 0.0) instead of live genesis values.
        fields.extend(extra_fields("agent", entity, {"dormant": True}))
        transitions.append(
            _genesis_transition(tick, entity, "genesis.agent.dormant", fields, [])
        )

    # ---- ruin slots (v0.6 world-memory, opt-in) -------------------------
    # One dormant ruin slot per region (x ``ruin_slots_per_region``). A
    # RuinSystem activates the slot when its region goes extinct; the slot is
    # reused (updated, never duplicated) on re-extinction. All ruin fields
    # come from the ruleset hook, so the generator stays schema-agnostic.
    ruin_slots = int(getattr(rules, "ruin_slots_per_region", 0))
    for r in range(region_count):
        for s in range(ruin_slots):
            entity = f"ruin:{r}:{s}"
            fields = extra_fields(
                "ruin",
                entity,
                {"region": f"region:{r}", "index": s, "region_index": r},
            )
            if fields:
                transitions.append(
                    _genesis_transition(tick, entity, "genesis.ruin", fields, [])
                )

    return transitions
