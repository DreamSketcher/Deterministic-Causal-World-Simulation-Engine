"""AgentSystem: census, metabolism, health/death and migration.

MVP behaviour model (spec §27): state -> perception -> decision -> action ->
consequences, without complex AI.

Emitted transitions (all computed from the shared snapshot):

* ``agents.census``    per region: population/workers = alive agents
* ``agent.metabolism`` per agent: hunger and immunity dynamics
* ``agent.health``     per agent: health delta from infection/starvation
* ``agent.death``      per agent: atomic (alive -> false, health -> 0)
* ``agent.migrate``    hungry agents may move, gated by risk_tolerance

Health writes here use priority 0; DiseaseSystem infection writes use
priority 2, so same-tick conflicts resolve deterministically toward the
infection transition (never by mutating computed ``new`` values, spec §15).
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class AgentSystem(System):
    name = "AgentSystem"
    priority = 10

    HUNGER_RATE = 0.07
    INTAKE_RELIEF = 0.1
    STARVATION_THRESHOLD = 0.75
    MIGRATION_THRESHOLD = 0.55

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        agents = context.entities("agent:")

        out.extend(self._census(context, agents))

        for agent in agents:
            if not snapshot.get(agent, "alive"):
                continue
            metabolism = self._metabolism(context, agent)
            if metabolism is not None:
                out.append(metabolism)
            health = self._health(context, agent)
            if health is not None:
                out.append(health)
            migration = self._migration(context, agent)
            if migration is not None:
                out.append(migration)
        return out

    # ------------------------------------------------------------------
    def _census(self, context, agents: list[str]) -> list[Transition]:
        out: list[Transition] = []
        for region in context.entities("region:"):
            b = context.builder("agents.census", priority=1)
            alive_count = 0
            for agent in agents:
                agent_region = b.read(agent, "region")
                is_alive = b.read(agent, "alive")
                if agent_region == region and is_alive:
                    alive_count += 1
            b.write(region, "population", alive_count)
            b.write(region, "workers", alive_count)
            out.append(b.build())
        return out

    # ------------------------------------------------------------------
    def _metabolism(self, context, agent: str) -> Transition | None:
        region = context.snapshot.get(agent, "region")
        b = context.builder("agent.metabolism")
        hunger = b.read(agent, "hunger")
        immunity = b.read(agent, "immunity")
        b.read(agent, "region")
        food = b.read(region, "food_stock")
        population = b.read(region, "population")

        food_per_capita = food / max(population, 1)
        eaten = min(1.0, food_per_capita)
        new_hunger = clamp(hunger + self.HUNGER_RATE - self.INTAKE_RELIEF * eaten)
        # Immunity mean-reverts and erodes with hunger (never saturates at 1).
        new_immunity = clamp(immunity + 0.002 - 0.005 * immunity - 0.01 * new_hunger)

        b.write(agent, "hunger", new_hunger)
        b.write(agent, "immunity", new_immunity)
        return b.build()

    # ------------------------------------------------------------------
    def _health(self, context, agent: str) -> Transition | None:
        snapshot = context.snapshot
        infected = bool(snapshot.get(agent, "infected"))
        hunger = float(snapshot.get(agent, "hunger"))

        delta = 0.0
        if infected:
            delta -= 2.5
        if hunger >= self.STARVATION_THRESHOLD:
            delta -= 2.0
        if not infected and hunger < 0.25:
            delta += 1.5
        if delta == 0.0:
            return None

        b = context.builder("agent.death" if self._is_lethal(snapshot, agent, delta) else "agent.health")
        b.read(agent, "alive")
        health = b.read(agent, "health")
        b.read(agent, "infected")
        b.read(agent, "hunger")

        new_health = clamp(health + delta, 0.0, 100.0)
        if new_health <= 0.0:
            b.write(agent, "alive", False)
            b.write(agent, "health", 0.0)
        else:
            b.write(agent, "health", new_health)
        return b.build()

    @staticmethod
    def _is_lethal(snapshot: Snapshot, agent: str, delta: float) -> bool:
        health = float(snapshot.get(agent, "health"))
        return clamp(health + delta, 0.0, 100.0) <= 0.0

    # ------------------------------------------------------------------
    def _migration(self, context, agent: str) -> Transition | None:
        snapshot = context.snapshot
        if float(snapshot.get(agent, "hunger")) < self.MIGRATION_THRESHOLD:
            return None
        b = context.builder("agent.migrate")
        b.read(agent, "hunger")
        risk = b.read(agent, "risk_tolerance")
        region = b.read(agent, "region")

        roll = b.draw("agent.decision", agent, threshold=risk * 0.5)
        if not roll.outcome:
            return None
        destination = "region:1" if region == "region:0" else "region:0"
        b.write(agent, "region", destination)
        return b.build()
