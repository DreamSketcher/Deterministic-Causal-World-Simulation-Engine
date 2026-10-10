"""ClimateSystem: mean-reverting temperature/rainfall with addressable noise.

Reads (all recorded): previous temperature/rainfall + region parameters.
Random: climate.temperature_noise, climate.rain (one draw per region).
Writes: temperature, rainfall — visible to other systems NEXT tick only.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class ClimateSystem(System):
    name = "ClimateSystem"
    priority = 0

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        for region in context.entities("region:"):
            b = context.builder("climate.step")
            temperature = b.read(region, "temperature")
            rainfall = b.read(region, "rainfall")
            temp_base = b.read(region, "temperature_base")
            rain_base = b.read(region, "rainfall_base")
            volatility = b.read(region, "climate_volatility")

            noise_t = b.draw("climate.temperature_noise", region)
            noise_r = b.draw("climate.rain", region)

            new_temperature = (
                temperature
                + 0.25 * (temp_base - temperature)
                + volatility * (noise_t.value - 0.5) * 2.5
            )
            new_rainfall = clamp(
                rainfall + 0.2 * (rain_base - rainfall) + (noise_r.value - 0.5) * 0.12
            )

            b.write(region, "temperature", new_temperature)
            b.write(region, "rainfall", new_rainfall)
            out.append(b.build())
        return out
