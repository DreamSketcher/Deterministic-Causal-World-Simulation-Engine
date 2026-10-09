"""ImmuneDiseaseSystem: disease dynamics with adaptive immune memory.

The v0.3 ruleset's disease system. Everything structural is inherited from
the frozen v0.1 ``DiseaseSystem`` (operations, priorities, draw
addresses); only the LAWS differ:

* susceptibility is scaled by ``1 - MEMORY_PROTECTION * immune_memory``;
* infection damage is attenuated by ``1 - DAMAGE_ATTENUATION * immune_memory``;
* every infection teaches: memory grows inside the SAME atomic transition
  that writes ``infected`` and ``health``;
* recovery probability gains ``RECOVERY_MEMORY_BONUS * immune_memory``.

Draw discipline is unchanged on purpose: the roll uses the same
addressable context (tick, agent, "disease.infection", 0) as the baseline
ruleset, and so does the damage draw (index 1). Two worlds run under the
same seed therefore consume the SAME random realizations; anything they
do differently is attributable to the laws, not to the dice.
"""

from __future__ import annotations

from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import clamp
from causal_world.systems.disease import INFECTION_PRIORITY, DiseaseSystem


class ImmuneDiseaseSystem(DiseaseSystem):
    name = "ImmuneDiseaseSystem"
    priority = DiseaseSystem.priority

    MEMORY_GAIN_PER_INFECTION = 0.35
    MEMORY_PROTECTION = 0.85
    DAMAGE_ATTENUATION = 0.60
    RECOVERY_MEMORY_BONUS = 0.20

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
        # Same addressable draw as the baseline ruleset.
        roll_value = context.rng.draw(snapshot.tick, agent, "disease.infection", 0)
        if not roll_value < probability:
            return None  # failed rolls still create no transition (spec §26)

        b = context.builder("disease.infect", priority=INFECTION_PRIORITY)
        b.read(agent, "alive")
        b.read(agent, "infected")
        b.read(agent, "immunity")
        b.read(agent, "hunger")
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

        # Atomic: infection, immune learning and health damage commit
        # together or not at all (invariant I3).
        b.write(agent, "infected", True)
        b.write(agent, "immune_memory", new_memory)
        if new_health <= 0.0:
            b.write(agent, "health", 0.0)
            b.write(agent, "alive", False)
        else:
            b.write(agent, "health", new_health)
        return b.build()

    def _try_recover(self, context, agent: str) -> Transition | None:
        snapshot: Snapshot = context.snapshot
        immunity = snapshot.get(agent, "immunity")
        hunger = snapshot.get(agent, "hunger")
        memory = float(snapshot.get(agent, "immune_memory"))

        probability = clamp(
            0.02
            + 0.25 * immunity
            + self.RECOVERY_MEMORY_BONUS * memory
            - 0.15 * hunger,
            0.0,
            0.5,
        )
        # Same addressable draw as the baseline ruleset.
        roll_value = context.rng.draw(snapshot.tick, agent, "disease.recovery", 0)
        if not roll_value < probability:
            return None

        b = context.builder("disease.recover", priority=INFECTION_PRIORITY)
        b.read(agent, "alive")
        b.read(agent, "infected")
        b.read(agent, "immunity")
        b.read(agent, "hunger")
        b.read(agent, "immune_memory")
        roll = b.draw("disease.recovery", agent, threshold=probability)
        assert roll.value == roll_value
        b.write(agent, "infected", False)
        return b.build()
