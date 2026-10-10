"""v0.3.3 fertility maintenance: can the world feed itself at the clock?

v0.3.2 closed the book on indirect mechanisms: none of fallow/storage/
rotation adds fertility WHERE farming happens, so the −0.0009/tick soil
clock decides survival. These rulesets attack the deficit directly or
behaviorally (all on the frozen kernel, stacked on immune memory):

* G ``CompostAgricultureSystem`` — every agent returns nutrients to the
  soil of its region; diminishing returns as soil approaches 1.
* H ``ThreeFieldAgricultureSystem`` — forced three-field cycle: after
  200 ticks of cultivation a region lies fallow for 100 ticks (no
  harvest, active recovery +0.003/tick). Cycles are phase-staggered per
  region at genesis, as real three-field systems were.
* I ``FertileMigrationAgentSystem`` — migration stops being a random walk:
  a migrating agent picks the best OTHER region by
  ``soil_fertility × food_stock / max(population, 1)``. The soil laws are
  untouched — this tests the information hypothesis ("the world was
  doomed by blindness, not by physics"). Combined with fallow recovery
  in the ``fertile_migration`` ruleset; a plain variant without fallow
  exists as an attribution control.

Transposition notes (the proposal was written against a degradation of
``−0.0009 × workers``; the frozen law is a flat ``−0.0009`` per region
per tick, workers-independent). The compost constant is therefore
rescaled by 1/1000, preserving the intended equilibrium structure: at
100 agents/region the balance point is soil ≈ 0.5.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.agents import AgentSystem
from causal_world.systems.agriculture import AgricultureSystem
from causal_world.systems.base import clamp

#: Flat soil degradation of the frozen law (−0.0012 + 0.0003).
DEGRADATION = 0.0009


# ----------------------------------------------------------------------
# G — compost: population-fed fertility return
# ----------------------------------------------------------------------


class CompostAgricultureSystem(AgricultureSystem):
    """Every agent returns nutrients to the soil of its region.

    ``soil_recovery = population × 0.000018 × (1 − soil_fertility)``

    — proportional to the number of agents (waste stream), with
    diminishing returns as the soil saturates. The constant is the
    proposal's 0.0018 rescaled by 1/1000: the frozen degradation is a
    flat 0.0009 per region per tick (not per worker), so at the genesis
    density of 100 agents/region the balance point is exactly the
    intended ``soil ≈ 0.5``: 100 × 0.000018 × (1 − 0.5) = 0.0009.

    Everything else — harvest, spoilage, consumption — is the frozen law.
    """

    name = "CompostAgricultureSystem"

    COMPOST_PER_CAPITA = 0.000018

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
            compost = population * self.COMPOST_PER_CAPITA * (1.0 - soil)
            new_soil = clamp(soil - DEGRADATION + compost, 0.05, 1.0)

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            out.append(b.build())
        return out


# ----------------------------------------------------------------------
# H — three-field cycle: forced rotation at the region level
# ----------------------------------------------------------------------


class ThreeFieldAgricultureSystem(AgricultureSystem):
    """A region cannot be cultivated forever: 200 ticks of farming force
    100 ticks of fallow.

    New per-region fields (created at genesis, phase-staggered):

    * ``cultivation_streak`` — ticks of consecutive cultivation;
    * ``fallow_timer`` — remaining ticks of forced fallow.

    While fallow: no harvest is produced (the field rests; the crop
    variance draw is not consumed either), agents present keep eating the
    stores, the soil recovers ``+0.003``/tick and the timer counts down.
    Otherwise the frozen soil dynamics apply and the streak grows while
    anyone farms the region; at 200 the region flips to fallow.

    The stagger at genesis (20 ticks × region index) is what makes it a
    THREE-field system: the cycles overlap so that at any moment some
    regions farm and others rest, instead of the whole world lying
    fallow in sync.
    """

    name = "ThreeFieldAgricultureSystem"

    CULTIVATION_LIMIT = 200
    FALLOW_LENGTH = 100
    FALLOW_RECOVERY = 0.003

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        for region in context.entities("region:"):
            b = context.builder("agriculture.harvest")
            soil = b.read(region, "soil_fertility")
            population = b.read(region, "population")
            food = b.read(region, "food_stock")
            streak = b.read(region, "cultivation_streak")
            timer = b.read(region, "fallow_timer")

            spoilage = self.SPOILAGE_RATE * food
            consumption = self.CONSUMPTION_PER_CAPITA * population

            # The streak is known from the snapshot, so the branch — and
            # therefore the set of recorded inputs — is decided up front.
            exhausted = population > 0 and streak + 1 >= self.CULTIVATION_LIMIT

            if timer > 0 or exhausted:
                # Forced fallow: field rests, stores are eaten, soil heals.
                # No climate reads, no crop draw: nothing is grown.
                new_food = max(0.0, food - spoilage - consumption)
                new_soil = clamp(soil + self.FALLOW_RECOVERY, 0.05, 1.0)
                new_timer = self.FALLOW_LENGTH if exhausted else timer - 1
                new_streak = 0
            else:
                temperature = b.read(region, "temperature")
                rainfall = b.read(region, "rainfall")
                workers = b.read(region, "workers")
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
                new_food = max(0.0, food + harvest - spoilage - consumption)
                new_soil = clamp(soil - 0.0012 + 0.0003, 0.05, 1.0)
                new_streak = streak + 1 if population > 0 else 0
                new_timer = 0

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            b.write(region, "cultivation_streak", new_streak)
            b.write(region, "fallow_timer", new_timer)
            out.append(b.build())
        return out


# ----------------------------------------------------------------------
# I — migration toward fertility (informed, greedy destination choice)
# ----------------------------------------------------------------------


class FertileMigrationAgentSystem(AgentSystem):
    """Migration keeps its hunger gate and its risk roll, but the
    destination becomes an informed choice.

    Frozen law: a migrating agent moves to the *next* region (cyclic) —
    a blind random walk. Here the agent picks the best OTHER region by

        soil_fertility × food_stock / max(population, 1)

    reading every region's fields from the shared snapshot. Ties resolve
    to the lowest canonical region id (sorted iteration, strict ``>``),
    so the choice is deterministic. Soil laws are untouched: this is the
    pure information experiment.
    """

    name = "FertileMigrationAgentSystem"

    def _migration(self, context, agent: str) -> Transition | None:
        snapshot = context.snapshot
        if float(snapshot.get(agent, "hunger")) < self.MIGRATION_THRESHOLD:
            return None
        risk = snapshot.get(agent, "risk_tolerance")
        roll_value = context.rng.draw(snapshot.tick, agent, "agent.decision", 0)
        if not roll_value < risk * 0.5:
            return None

        b = context.builder("agent.migrate")
        b.read(agent, "hunger")
        b.read(agent, "risk_tolerance")
        region = b.read(agent, "region")
        roll = b.draw("agent.decision", agent, threshold=risk * 0.5)
        assert roll.value == roll_value

        best, best_score = None, None
        for other in context.entities("region:"):
            if other == region:
                continue
            soil = b.read(other, "soil_fertility")
            food = b.read(other, "food_stock")
            pop = b.read(other, "population")
            score = soil * food / max(pop, 1)
            if best is None or score > best_score:
                best, best_score = other, score

        b.write(agent, "region", best)
        return b.build()
