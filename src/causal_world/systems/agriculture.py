"""AgricultureSystem: climate x soil x labor -> food stock.

A simple but genuinely causal model (spec §25):

    climate_factor x soil_fertility x workers x crop_variance = harvest
    food_stock + harvest - spoilage - consumption = new food_stock

Single writer for ``food_stock`` and ``soil_fertility`` per region, so the
field-ownership design avoids accidental write conflicts.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class AgricultureSystem(System):
    name = "AgricultureSystem"
    priority = 0

    OPTIMAL_TEMPERATURE = 16.0
    BASE_YIELD = 3.6
    SPOILAGE_RATE = 0.02
    CONSUMPTION_PER_CAPITA = 1.1

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
            new_soil = clamp(soil - 0.0012 + 0.0003, 0.05, 1.0)

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            out.append(b.build())
        return out
