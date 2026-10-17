"""v0.7 — the civic law: a region runs its base law PLUS the directives
the player enacted for it.

This system is the counterpart of :mod:`causal_world.systems.directive`.
The directive system WRITES the law parameters of a region; this system
READS them and computes the ecology from them. One writer per field, so
the two never compete — the resolver's conflict rule is never invoked
between them, and the causal link decree -> effect is visible in the
journal as a read with a provenance pointer.

The three levers (see ``systems/directive.py`` for the rationale):

* **amend** — part of the region's labour is diverted from the field to
  making compost. Harvest falls, soil recovery rises. Structural, slow.
* **water** — irrigation: effective rainfall rises, the soil is mined
  faster (salinity). Food now, soil debt later.
* **rest** — fallow: the region stops being harvested until a tick, the
  soil heals, and the people there eat the stores meanwhile.

The base law is the v0.3.3-G compost law (the first surviving world in
the research series), so a civic world without directives behaves exactly
like a compost world — the directives are the ONLY difference, which is
what makes an experiment attributable.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import clamp
from causal_world.systems.fertility import DEGRADATION, CompostAgricultureSystem


class CivicAgricultureSystem(CompostAgricultureSystem):
    """Compost law + the player's standing directives.

    Replaces ``CompostAgricultureSystem`` in the ``player_civic`` ruleset
    (same fields written: ``food_stock`` and ``soil_fertility``) so that
    the resolver sees a single writer, exactly as in every other
    research ruleset.
    """

    name = "CivicAgricultureSystem"

    #: Compost made per DIVERTED worker per tick. Deliberately larger than
    #: the ambient per-capita waste rate (0.000018): diverted labour does
    #: ACTIVE composting, so it must beat the passive return — otherwise
    #: the lever would never be worth its harvest. At 100 workers/region
    #: and 25 % diversion this lifts the soil equilibrium from ~0.50 to
    #: ~0.76, while the harvest falls by a quarter (the trade the player
    #: is asked to make).
    AMEND_PER_WORKER = 0.00008
    #: Extra effective rainfall at full irrigation.
    WATER_RAIN_BONUS = 0.12
    #: Soil degradation multiplier at full irrigation (salinity).
    WATER_SALT_FACTOR = 0.5
    #: Soil recovery per tick of fallow.
    REST_RECOVERY = 0.003

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
            # --- the enacted law of this region -------------------------
            diversion = float(b.read(region, "labor_diversion"))
            water = float(b.read(region, "water_aid"))
            rest_until = int(b.read(region, "rest_until"))

            resting = snapshot.tick < rest_until

            spoilage = self.SPOILAGE_RATE * food
            consumption = self.CONSUMPTION_PER_CAPITA * population

            if resting:
                # Fallow: nothing is grown, the field heals, the stores are
                # eaten. The crop-variance draw is NOT consumed — an
                # unplanted field has no crop to vary.
                new_food = max(0.0, food - spoilage - consumption)
                new_soil = clamp(soil + self.REST_RECOVERY, 0.05, 1.0)
            else:
                variance_draw = b.draw("agriculture.crop_variance", region)
                crop_variance = 0.75 + 0.5 * variance_draw.value

                temp_factor = max(
                    0.0,
                    1.0 - abs(temperature - self.OPTIMAL_TEMPERATURE) / 14.0,
                )
                effective_rain = rainfall + water * self.WATER_RAIN_BONUS
                rain_factor = clamp(effective_rain / 0.55, 0.0, 1.3)
                # Labour sent to compost does not harvest.
                field_workers = workers * (1.0 - diversion)
                harvest = (
                    self.BASE_YIELD
                    * temp_factor
                    * rain_factor
                    * soil
                    * field_workers
                    * crop_variance
                )
                new_food = max(
                    0.0, food + harvest - spoilage - consumption
                )
                compost = population * self.COMPOST_PER_CAPITA * (1.0 - soil)
                compost += (
                    workers * diversion * self.AMEND_PER_WORKER * (1.0 - soil)
                )
                degradation = DEGRADATION * (1.0 + water * self.WATER_SALT_FACTOR)
                new_soil = clamp(soil - degradation + compost, 0.05, 1.0)

            b.write(region, "food_stock", new_food)
            b.write(region, "soil_fertility", new_soil)
            out.append(b.build())
        return out
