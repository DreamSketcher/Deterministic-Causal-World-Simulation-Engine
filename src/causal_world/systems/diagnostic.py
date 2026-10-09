"""v0.3.1 structural diagnosis: systems with exactly ONE severed link each.

The v0.3 immune world still collapses (tick 573 at scale). The question is
no longer "does it collapse" but "which link of the spiral is the
bottleneck". Each system below is a surgical variant of a frozen v0.1/v0.3
system: same operation names, same draw addresses, same everything except
the one law under test. Combined into rulesets (see ``world/rules.py``):

* Experiment A "iron health" — infection never lowers health:
  - ``IronHealthDiseaseSystem``: no infection damage at all;
  - ``IronHealthAgentSystem``: no chronic −2.5/tick erosion while infected.
* Experiment B "stable soil" — the food clock is stopped:
  - ``StableSoilAgricultureSystem``: soil fertility no longer depletes.
  (The literal proposal "harvest independent of workers' health" is the
  *existing* law — harvest never reads health — so the real food-side
  bottleneck candidate is the unconditional soil depletion.)
* Experiment C "no hunger→immunity" — the hunger/susceptibility loop cut:
  - ``NoHungerDiseaseSystem``: susceptibility without the hunger factor;
  - ``NoHungerErosionAgentSystem``: immunity no longer erodes with hunger.
* Control — ``NoDiseaseRules`` runs without any disease system.

Kernel untouched throughout: these are systems + rulesets, i.e. world
content, selected via ``create_world(ruleset=...)``.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.agents import AgentSystem
from causal_world.systems.agriculture import AgricultureSystem
from causal_world.systems.base import clamp
from causal_world.systems.disease import INFECTION_PRIORITY
from causal_world.systems.immune_disease import ImmuneDiseaseSystem


# ----------------------------------------------------------------------
# Experiment A — infection never lowers health
# ----------------------------------------------------------------------


class IronHealthDiseaseSystem(ImmuneDiseaseSystem):
    """Infection is recorded and teaches memory, but deals no damage.

    Same susceptibility law and same addressable rolls as the immune
    ruleset (the index-0 infection roll is unchanged); the index-1 damage
    draw no longer exists because damage no longer exists. Writes are
    exactly ``infected=True`` and ``immune_memory`` — never ``health``,
    never ``alive``.
    """

    name = "IronHealthDiseaseSystem"

    def _try_infect(self, context, agent: str, region: str) -> Transition | None:
        snapshot: Snapshot = context.snapshot
        immunity = snapshot.get(agent, "immunity")
        hunger = snapshot.get(agent, "hunger")
        load = snapshot.get(region, "disease_load")
        memory = float(snapshot.get(agent, "immune_memory"))

        protection = self.MEMORY_PROTECTION * memory
        probability = clamp(
            load
            * (0.35 + 0.85 * hunger)
            * (1.25 - immunity)
            * self.EXPOSURE
            * (1.0 - protection),
            0.0,
            0.85,
        )
        roll_value = context.rng.draw(snapshot.tick, agent, "disease.infection", 0)
        if not roll_value < probability:
            return None

        b = context.builder("disease.infect", priority=INFECTION_PRIORITY)
        b.read(agent, "alive")
        b.read(agent, "infected")
        b.read(agent, "immunity")
        b.read(agent, "hunger")
        b.read(agent, "region")
        b.read(region, "disease_load")
        b.read(agent, "immune_memory")
        roll = b.draw("disease.infection", agent, index=0, threshold=probability)
        assert roll.value == roll_value

        new_memory = clamp(memory + self.MEMORY_GAIN_PER_INFECTION)
        b.write(agent, "infected", True)
        b.write(agent, "immune_memory", new_memory)
        # Deliberately NO health/alive writes: the severed link.
        return b.build()


class IronHealthAgentSystem(AgentSystem):
    """Chronic health dynamics without the infection term.

    The frozen law erodes health −2.5/tick while infected; here the delta
    depends on hunger alone (starvation −2.0, recovery +1.5 when well fed
    and uninfected). ``infected`` is still read because it gates recovery
    — it simply can no longer damage.
    """

    name = "IronHealthAgentSystem"

    def _health(self, context, agent: str) -> Transition | None:
        snapshot = context.snapshot
        infected = bool(snapshot.get(agent, "infected"))
        hunger = float(snapshot.get(agent, "hunger"))

        delta = 0.0
        # No `if infected: delta -= 2.5` — the severed link.
        if hunger >= self.STARVATION_THRESHOLD:
            delta -= 2.0
        if not infected and hunger < 0.25:
            delta += 1.5
        if delta == 0.0:
            return None

        b = context.builder(
            "agent.death" if self._is_lethal(snapshot, agent, delta) else "agent.health"
        )
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


# ----------------------------------------------------------------------
# Experiment B — the food clock is stopped
# ----------------------------------------------------------------------


class StableSoilAgricultureSystem(AgricultureSystem):
    """Harvest is unchanged; soil fertility no longer depletes.

    The frozen law writes ``soil_fertility := clamp(soil − 0.0012 + 0.0003)``
    every tick — an unconditional countdown (−0.0009/tick, floor 0.05).
    Here soil is read (harvest still depends on it) but never written, so
    each region keeps its genesis fertility forever. Everything else —
    climate factors, crop variance, spoilage, consumption — is identical.
    """

    name = "StableSoilAgricultureSystem"

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        for region in context.entities("region:"):
            b = context.builder("agriculture.harvest")
            temperature = b.read(region, "temperature")
            rainfall = b.read(region, "rainfall")
            soil = b.read(region, "soil_fertility")
            workers = b.read(region, "workers")
            population = b.read(region, "population")
            food = b.read(region, "food_stock")

            variance_draw = b.draw("agriculture.crop_variance", region)
            crop_variance = 0.75 + 0.5 * variance_draw.value

            temp_factor = max(0.0, 1.0 - abs(temperature - self.OPTIMAL_TEMPERATURE) / 14.0)
            rain_factor = clamp(rainfall / 0.55, 0.0, 1.3)
            harvest = (
                self.BASE_YIELD
                * temp_factor
                * rain_factor
                * soil
                * workers
                * crop_variance
            )
            spoilage = self.SPOILAGE_RATE * food
            consumption = self.CONSUMPTION_PER_CAPITA * population

            new_food = max(0.0, food + harvest - spoilage - consumption)
            b.write(region, "food_stock", new_food)
            # Deliberately NO soil_fertility write: the severed link.
            out.append(b.build())
        return out


# ----------------------------------------------------------------------
# Experiment C — the hunger -> susceptibility loop is cut
# ----------------------------------------------------------------------


class NoHungerDiseaseSystem(ImmuneDiseaseSystem):
    """Susceptibility no longer grows with hunger.

    The frozen factor ``(0.35 + 0.85·hunger)`` is replaced by its
    well-fed value ``0.35``: a starving agent is no more susceptible than
    a fed one. Everything else — damage, memory, recovery, draws — is the
    immune law. ``hunger`` is no longer read because it is no longer an
    input (causal honesty: reads reflect actual dependencies).
    """

    name = "NoHungerDiseaseSystem"

    FED_SUSCEPTIBILITY = 0.35

    def _try_infect(self, context, agent: str, region: str) -> Transition | None:
        snapshot: Snapshot = context.snapshot
        immunity = snapshot.get(agent, "immunity")
        load = snapshot.get(region, "disease_load")
        memory = float(snapshot.get(agent, "immune_memory"))

        protection = self.MEMORY_PROTECTION * memory
        probability = clamp(
            load
            * self.FED_SUSCEPTIBILITY
            * (1.25 - immunity)
            * self.EXPOSURE
            * (1.0 - protection),
            0.0,
            0.85,
        )
        roll_value = context.rng.draw(snapshot.tick, agent, "disease.infection", 0)
        if not roll_value < probability:
            return None

        b = context.builder("disease.infect", priority=INFECTION_PRIORITY)
        b.read(agent, "alive")
        b.read(agent, "infected")
        b.read(agent, "immunity")
        # Deliberately NO hunger read: the severed link.
        b.read(agent, "region")
        b.read(region, "disease_load")
        health = b.read(agent, "health")
        b.read(agent, "immune_memory")

        roll = b.draw("disease.infection", agent, index=0, threshold=probability)
        assert roll.value == roll_value
        damage_draw = b.draw("disease.infection", agent, index=1)

        damage = (6.0 + 10.0 * damage_draw.value) * (
            1.0 - self.DAMAGE_ATTENUATION * memory
        )
        new_health = health - damage
        new_memory = clamp(memory + self.MEMORY_GAIN_PER_INFECTION)

        b.write(agent, "infected", True)
        b.write(agent, "immune_memory", new_memory)
        if new_health <= 0.0:
            b.write(agent, "health", 0.0)
            b.write(agent, "alive", False)
        else:
            b.write(agent, "health", new_health)
        return b.build()


class NoHungerErosionAgentSystem(AgentSystem):
    """Immunity no longer erodes with hunger.

    The frozen metabolism law: ``immunity + 0.002 − 0.005·immunity −
    0.01·hunger``. The last term is the severed link; hunger dynamics and
    everything else are unchanged.
    """

    name = "NoHungerErosionAgentSystem"

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
        # No `− 0.01 * new_hunger` term: the severed link.
        new_immunity = clamp(immunity + 0.002 - 0.005 * immunity)

        b.write(agent, "hunger", new_hunger)
        b.write(agent, "immunity", new_immunity)
        return b.build()
