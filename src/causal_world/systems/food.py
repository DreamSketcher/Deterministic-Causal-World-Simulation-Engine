"""v0.3.2 food-side mechanisms: three agriculture variants.

The v0.3.1 diagnosis found the collapse bottleneck: the unconditional
soil-depletion clock. The disease side is not the bottleneck. These three
systems test whether the population can live WITH degradation (no magic:
the clock is never removed) through a realistic food-side law each. All
are surgical variants of the frozen ``AgricultureSystem`` — same
operation name (``agriculture.harvest``), same draw addresses, same
single-writer discipline; each changes exactly one law:

* D ``FallowAgricultureSystem`` — fallow recovery: abandoned regions
  (population 0) regain fertility (+0.0015/tick) instead of degrading.
* E ``StorageAgricultureSystem`` — stock-dependent spoilage: tiny stocks
  barely rot (eaten before spoiling), huge surpluses rot faster.
* F ``RotationAgricultureSystem`` — crop rotation: stable, maximal labor
  load degrades soil fastest; a fluctuating load lets the soil rest.
  Needs two new per-region state fields (``labor_ema``, ``labor_ema2``,
  a 10-tick-window exponential statistic of the workforce), created at
  genesis by the ruleset's hook — the kernel is untouched.
"""

from __future__ import annotations

import math

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.agriculture import AgricultureSystem
from causal_world.systems.base import clamp


# ----------------------------------------------------------------------
# D — fallow recovery (spatial dynamics)
# ----------------------------------------------------------------------


class FallowAgricultureSystem(AgricultureSystem):
    """Abandoned fields regain fertility.

    Frozen law: ``new_soil = clamp(soil − 0.0012 + 0.0003, 0.05, 1.0)``
    unconditionally — even a region with no one farming it. Here the soil
    dynamics become presence-conditional:

    * ``population > 0`` — farmed: exactly the frozen dynamics (−0.0009 net);
    * ``population == 0`` — fallow: ``soil += 0.0015`` per tick (capped),
      and no depletion, because nothing is being farmed.

    The hypothesis: abandoned regions heal while the population is pushed
    around by migration and death, and the world may find a spatial
    oscillation instead of a monotone collapse.

    Note on the literal proposal ``workers < population × 0.3``: in the
    frozen laws ``workers`` is the census alive-count, always equal to
    ``population``, so that condition can never fire. Presence is the
    meaningful signal of "abandoned", and that is what this law uses.
    """

    name = "FallowAgricultureSystem"

    FALLOW_RECOVERY = 0.0015

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
            if population > 0:
                new_soil = clamp(soil - 0.0012 + 0.0003, 0.05, 1.0)
            else:
                # Fallow: nothing is farmed, the field regains fertility.
                new_soil = clamp(soil + self.FALLOW_RECOVERY, 0.05, 1.0)

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            out.append(b.build())
        return out


# ----------------------------------------------------------------------
# E — stock-dependent spoilage (storage & rationing)
# ----------------------------------------------------------------------


class StorageAgricultureSystem(AgricultureSystem):
    """Spoilage depends on how big the stock is.

    Frozen law: ``spoilage = 0.02 × food`` regardless of scale. Here:

    * ``rate = 0.02 × min(1, food / (population × 50))`` — a small stock
      is eaten before it can rot; only a stock above 50 rations per agent
      spoils at the full 2 %;
    * additionally, a surplus above 10 rations per agent rots at 4 %
      (big granaries are themselves the storage problem).

    Soil dynamics and everything else are the frozen laws. The question:
    is the collapse driven by the AVERAGE deficit or by PEAK deficits
    (bad seasons that hit once the buffer is eaten)?
    """

    name = "StorageAgricultureSystem"

    SURPLUS_SPOILAGE_RATE = 0.04
    SURPLUS_RATIONS_PER_AGENT = 10.0
    FULL_RATE_RATIONS_PER_AGENT = 50.0

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

            # Stock-dependent spoilage (the only changed law).
            pop_eff = max(population, 1)
            rate = self.SPOILAGE_RATE * min(
                1.0, food / (pop_eff * self.FULL_RATE_RATIONS_PER_AGENT)
            )
            if food > self.SURPLUS_RATIONS_PER_AGENT * pop_eff:
                rate = max(rate, self.SURPLUS_SPOILAGE_RATE)
            spoilage = rate * food

            consumption = self.CONSUMPTION_PER_CAPITA * population
            new_food = max(0.0, food + harvest - spoilage - consumption)
            new_soil = clamp(soil - 0.0012 + 0.0003, 0.05, 1.0)

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            out.append(b.build())
        return out


# ----------------------------------------------------------------------
# F — crop rotation (temporal dynamics)
# ----------------------------------------------------------------------


class RotationAgricultureSystem(AgricultureSystem):
    """Degradation follows the labor load's stability.

    Frozen law: soil degrades 0.0009/tick no matter how it is farmed.
    Here the degradation is

        0.0009 × (workers / population) × stability_penalty

    where ``stability_penalty = 1 + 0.5 × (1 − min(1, cv))`` and ``cv``
    is the coefficient of variation of the region's workforce over a
    ~10-tick window (exponential statistic, coefficient 0.1). Constant,
    maximal exploitation (monoculture) degrades 50 % FASTER than the
    frozen clock; a genuinely fluctuating load lets the soil rest
    (down to 0.00045/tick). The natural regeneration term (+0.0003) is
    kept.

    The workforce statistic lives in two per-region fields
    (``labor_ema``, ``labor_ema2``), created at genesis by the ruleset
    and updated inside the same atomic harvest transition — the kernel
    still sees one writer per field and pure transitions.
    """

    name = "RotationAgricultureSystem"

    EMA_ALPHA = 0.1
    ROTATION_BONUS = 0.5

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
            ema_old = b.read(region, "labor_ema")
            ema2_old = b.read(region, "labor_ema2")

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

            # Workforce statistic (10-tick exponential window).
            if ema_old is None:
                ema_old = float(workers)
            if ema2_old is None:
                ema2_old = float(workers) ** 2
            ema = (1.0 - self.EMA_ALPHA) * ema_old + self.EMA_ALPHA * workers
            ema2 = (1.0 - self.EMA_ALPHA) * ema2_old + self.EMA_ALPHA * workers * workers
            variance = max(0.0, ema2 - ema * ema)
            cv = math.sqrt(variance) / max(ema, 1.0)
            stability_penalty = 1.0 + self.ROTATION_BONUS * (1.0 - min(1.0, cv))

            load = workers / max(population, 1)
            degradation = 0.0009 * load * stability_penalty
            new_soil = clamp(soil - degradation + 0.0003, 0.05, 1.0)

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            b.write(region, "labor_ema", ema)
            b.write(region, "labor_ema2", ema2)
            out.append(b.build())
        return out
