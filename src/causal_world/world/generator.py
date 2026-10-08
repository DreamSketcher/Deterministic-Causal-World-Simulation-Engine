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
) -> list[Transition]:
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
        transitions.append(
            _genesis_transition(tick, entity, "genesis.agent", fields, draws)
        )

    return transitions
