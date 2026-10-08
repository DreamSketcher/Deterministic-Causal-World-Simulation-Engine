"""DiseaseSystem: environmental disease load + per-agent infection/recovery.

For every alive, uninfected agent (spec §26):

    disease_load, immunity, hunger -> P(infection)
    addressable draw ``disease.infection`` per agent

If the roll passes, ONE atomic transition is created:

    infected: false -> true
    health:   X     -> X - infection_damage      (and alive -> false if lethal)

If the roll fails, no state transition exists at all. Recovery of infected
agents is drawn the same way (``disease.recovery``).

Infection transitions run at priority 2 so that, if AgentSystem proposes a
health write for the same agent in the same tick, the resolver settles the
conflict deterministically instead of double-writing.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp

INFECTION_PRIORITY = 2


class DiseaseSystem(System):
    name = "DiseaseSystem"
    priority = 20

    EXPOSURE = 0.6

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        agents = context.entities("agent:")

        # ---- environmental disease load, one transition per region --------
        for region in context.entities("region:"):
            b = context.builder("disease.environment")
            load = b.read(region, "disease_load")
            disease_base = b.read(region, "disease_base")
            infected_alive = 0
            population = 0
            for agent in agents:
                is_alive = b.read(agent, "alive")
                is_infected = b.read(agent, "infected")
                agent_region = b.read(agent, "region")
                if agent_region != region:
                    continue
                population += 1
                if is_alive and is_infected:
                    infected_alive += 1
            noise = b.draw("disease.load_noise", region)
            prevalence = infected_alive / population if population else 0.0
            # Environmental reservoir + epidemic pressure + small noise.
            new_load = clamp(
                0.75 * load
                + 0.30 * prevalence
                + 0.18 * disease_base
                + (noise.value - 0.5) * 0.02
            )
            b.write(region, "disease_load", new_load)
            out.append(b.build())

        # ---- per-agent infection / recovery --------------------------------
        for agent in agents:
            if not snapshot.get(agent, "alive"):
                continue
            region = snapshot.get(agent, "region")
            if not snapshot.get(agent, "infected"):
                transition = self._try_infect(context, agent, region)
            else:
                transition = self._try_recover(context, agent)
            if transition is not None:
                out.append(transition)
        return out

    def _try_infect(self, context, agent: str, region: str) -> Transition | None:
        b = context.builder("disease.infect", priority=INFECTION_PRIORITY)
        b.read(agent, "alive")
        b.read(agent, "infected")
        immunity = b.read(agent, "immunity")
        hunger = b.read(agent, "hunger")
        b.read(agent, "region")
        load = b.read(region, "disease_load")
        health = b.read(agent, "health")

        probability = clamp(
            load * (0.35 + 0.85 * hunger) * (1.25 - immunity) * self.EXPOSURE,
            0.0,
            0.85,
        )
        roll = b.draw("disease.infection", agent, index=0, threshold=probability)
        if not roll.outcome:
            return None  # no state transition is created (spec §26)

        damage_draw = b.draw("disease.infection", agent, index=1)
        damage = 6.0 + 10.0 * damage_draw.value
        new_health = health - damage

        b.write(agent, "infected", True)
        if new_health <= 0.0:
            b.write(agent, "health", 0.0)
            b.write(agent, "alive", False)
        else:
            b.write(agent, "health", new_health)
        return b.build()

    def _try_recover(self, context, agent: str) -> Transition | None:
        b = context.builder("disease.recover", priority=INFECTION_PRIORITY)
        b.read(agent, "alive")
        b.read(agent, "infected")
        immunity = b.read(agent, "immunity")
        hunger = b.read(agent, "hunger")

        probability = clamp(0.02 + 0.25 * immunity - 0.15 * hunger, 0.0, 0.5)
        roll = b.draw("disease.recovery", agent, threshold=probability)
        if not roll.outcome:
            return None
        b.write(agent, "infected", False)
        return b.build()
