"""v0.10 — the CAPACITY policy: wild land and terraces, with a price.

The v0.9 measurements named the wall: a cell cannot grow past
``pop_base x (1 + soil)``, and in a saturated world the nursery bought
+1 birth in 100 ticks. The review of v0.9 put the architectural risk in
one sentence: a capacity policy must not become a free way to raise the
population for better-looking metrics. This module is the answer, and
it is deliberately small:

* **Wild land exists from genesis.** ``CapacityRules`` pre-creates one
  row of parcels per region with ``land_active = 0``. They are written by an
  ordinary genesis transition, so the land has provenance from tick 0.
  Systems ignore them until a claim activates them: a wild parcel is
  not a cell, and the map can draw it as land waiting.
* **``claim``** activates one parcel. The new homestead starts small
  (``RESERVE_POP_BASE``) and is PAID for from the richest working cell
  of the same region. If the stores cannot pay, the world does not
  pretend the order worked: it writes the refusal into ``claim_state``
  and the journal, with the reason encoded in the state value.
* **``terrace``** raises a working cell's ``pop_base``. The price is
  food and soil (construction damages the field), and a cell can carry
  a bounded number of terraces. Capacity is bought; it is never granted.

Both levers are ordinary directives: they enter force on T+1, are
recorded as ``player.directive`` transitions, and a counterfactual can
fork them like any other law.

State values recorded in ``claim_state`` / ``terrace_state`` (so the
refusal is a FACT in the journal, not a message):

    0  no attempt yet
    1  done (land claimed / terrace built)
   -1  refused: not enough stores
   -2  refused: the parcel is already active / the cell is wild land
   -3  refused: the cell already carries the maximum number of terraces
"""

from __future__ import annotations

from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import clamp
from causal_world.systems.directive import (
    DIRECTIVE_CLAIM,
    DIRECTIVE_TERRACE,
    DirectiveSystem,
)
from causal_world.systems.spatial import (
    CELL_PREFIX,
    SpatialDirectiveSystem,
    is_active,
)

#: The encoded answers of the world (they live in the written fields).
CLAIM_DONE = 1
CLAIM_NO_FOOD = -1
CLAIM_ALREADY = -2
TERRACE_DONE = 1
TERRACE_NO_FOOD = -1
TERRACE_WILD = -2
TERRACE_MAXED = -3


class CapacityDirectiveSystem(SpatialDirectiveSystem):
    """The v0.8 cell laws plus the two capacity levers.

    The base system keeps amend / water / rest / nursery untouched; this
    one handles ``claim`` and ``terrace`` and delegates the rest. One
    directive per tick, one committed transition — the same contract as
    every other law of the world.
    """

    name = "CapacityDirectiveSystem"

    #: The card of the capacity world: four v0.8 levers + two new ones.
    KIND_NAMES = {
        **SpatialDirectiveSystem.KIND_NAMES,
        DIRECTIVE_CLAIM: "claim",
        DIRECTIVE_TERRACE: "terrace",
    }
    TARGET_PREFIX = CELL_PREFIX

    #: Prices and bounds come from the ruleset, but the system needs a
    #: default when it is constructed outside a ruleset (tests).
    CLAIM_COST = 90.0
    TERRACE_COST = 60.0
    TERRACE_GAIN = 2
    TERRACE_SOIL_COST = 0.04
    TERRACE_MAX = 3
    RESERVE_POP_BASE = 3
    RESERVE_FOOD = 25.0

    def compute(
        self, snapshot: Snapshot, rng, context
    ) -> list[Transition]:
        if self.channel is None:
            return []
        directive = self.channel.at(snapshot.tick)
        if directive is None:
            return []
        if directive.kind not in self.KIND_NAMES:
            return []
        target = directive.region
        if not target.startswith(self.TARGET_PREFIX):
            return []
        if target not in context.entities(self.TARGET_PREFIX):
            return []
        if directive.kind == DIRECTIVE_CLAIM:
            return [self._claim(snapshot, directive.kind, target, context)]
        if directive.kind == DIRECTIVE_TERRACE:
            return [self._terrace(snapshot, directive.kind, target, context)]
        return super().compute(snapshot, rng, context)

    # ------------------------------------------------------------------
    def _directive_builder(self, context, target: str, kind: int):
        b = context.builder(self.OPERATION)
        # The draw carries the KIND (the same convention as v0.7), so the
        # journal alone reproduces which lever was pulled and where.
        b.draw("player.directive", target, index=0, value=float(kind))
        return b

    def _claim(self, snapshot, kind: int, parcel: str, context) -> Transition:
        """Activate one wild parcel, paid for by the region's richest cell."""
        b = self._directive_builder(context, parcel, kind)
        region = b.read(parcel, "region")
        active = int(b.read(parcel, "land_active") or 0)
        if active:
            b.write(parcel, "claim_state", CLAIM_ALREADY)
            return b.build()

        donor = self._richest_cell(snapshot, region, parcel, context)
        food = float(b.read(donor, "food_stock")) if donor else 0.0
        if donor is None or food < self.CLAIM_COST:
            # The order was accepted by the protocol and enacted by the
            # world — and REFUSED by the economy. The refusal is a fact
            # in the journal, not a silent no-op.
            b.write(parcel, "claim_state", CLAIM_NO_FOOD)
            return b.build()

        b.write(donor, "food_stock", food - self.CLAIM_COST)
        b.write(parcel, "land_active", 1)
        b.write(parcel, "pop_base", self.RESERVE_POP_BASE)
        b.write(parcel, "food_stock", self.RESERVE_FOOD)
        b.write(parcel, "claim_state", CLAIM_DONE)
        b.write(parcel, "land_cost", self.CLAIM_COST)
        return b.build()

    def _terrace(self, snapshot, kind: int, cell: str, context) -> Transition:
        """Buy extra capacity for a working cell: food now, soil later."""
        b = self._directive_builder(context, cell, kind)
        if not is_active(snapshot, cell):
            b.write(cell, "terrace_state", TERRACE_WILD)
            return b.build()
        terraces = int(b.read(cell, "terraces") or 0)
        if terraces >= self.TERRACE_MAX:
            b.write(cell, "terrace_state", TERRACE_MAXED)
            return b.build()
        food = float(b.read(cell, "food_stock"))
        if food < self.TERRACE_COST:
            b.write(cell, "terrace_state", TERRACE_NO_FOOD)
            return b.build()

        base = int(b.read(cell, "pop_base"))
        soil = float(b.read(cell, "soil_fertility"))
        b.write(cell, "food_stock", food - self.TERRACE_COST)
        b.write(cell, "pop_base", base + self.TERRACE_GAIN)
        b.write(cell, "soil_fertility",
                clamp(soil - self.TERRACE_SOIL_COST, 0.05, 1.0))
        b.write(cell, "terraces", terraces + 1)
        b.write(cell, "terrace_state", TERRACE_DONE)
        return b.build()

    @staticmethod
    def _richest_cell(snapshot, region: str, exclude: str,
                      context) -> str | None:
        """The region's cell with the most stores (deterministic tie-break)."""
        best, best_food = None, -1.0
        for cell in context.entities(CELL_PREFIX):
            if cell == exclude or not is_active(snapshot, cell):
                continue
            if snapshot.get(cell, "region") != region:
                continue
            food = float(snapshot.get(cell, "food_stock") or 0.0)
            if food > best_food or (food == best_food and best is not None
                                    and cell < best):
                best, best_food = cell, food
        return best


__all__ = [
    "CapacityDirectiveSystem",
    "CLAIM_DONE",
    "CLAIM_NO_FOOD",
    "CLAIM_ALREADY",
    "TERRACE_DONE",
    "TERRACE_NO_FOOD",
    "TERRACE_WILD",
    "TERRACE_MAXED",
    "DirectiveSystem",
]
