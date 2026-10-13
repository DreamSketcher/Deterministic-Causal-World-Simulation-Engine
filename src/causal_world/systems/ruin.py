"""RuinSystem: world memory (v0.6 step 2).

One dormant ruin slot per region (``ruin:{r}:{s}``, pre-allocated at genesis
with ``active=False``) commemorates the death of its region. A ``was_alive``
marker makes activation fire on the TRANSITION into extinction (region was
alive, now ``population == 0``) rather than on merely being extinct — without
it a permanently-empty region would re-activate its slot every tick after
each collapse (the oscillation bug found in the first diagnostic: 860
activations / 859 collapses in 1800 ticks).

State machine per slot, from the region's population and the slot's
(``active``, ``was_alive``):

* **region alive (pop > 0):** note ``was_alive=True`` once. An active ruin
  PERSISTS without aging — an ancestral granary later settlers can explore
  ("the world remembers"); it does not fade while the region lives.
* **region extinct (pop == 0) and ``was_alive``:** a fresh (or re-)extinction
  -> activate/reset the slot (``active=True``, ``type`` derived from the
  region's state, ``age=0``, a food reserve, ``was_alive=False``). This is
  nuance 4: one slot per region, reset on re-extinction, never duplicated.
* **region extinct and slot active (not ``was_alive``):** ongoing extinction
  -> age the ruin; collapse (``active=False``) past ``RUIN_MAX_AGE`` or once
  the reserve is gone (``resource_food <= RUIN_FOOD_FLOOR``, depleted by
  ExplorationSystem). The slot then stays dormant (``was_alive=False``) so it
  does NOT re-activate until the region lives and dies again.

Conflict discipline: ``resource_food`` is written ONLY on activation/reset
(when the slot is being (re-)born) — ExplorationSystem owns depletion while
active. So the two never write ``resource_food`` in the same tick. Determinism:
activation/aging/collapse are pure functions of the snapshot (no draws).
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class RuinSystem(System):
    name = "RuinSystem"
    #: After BirthSystem(30); before ExplorationSystem(40).
    priority = 31

    RUIN_MAX_AGE = 1200  # collapse past this age (ticks extinct)
    RUIN_FOOD_FLOOR = 0.5  # collapse once the reserve falls to this
    RUIN_FOOD_FRACTION = 0.1  # reserve seeded from 10% of the region's stock
    MIN_RUIN_FOOD = 10.0  # floor on the seeded reserve (a starved camp still leaves scraps)
    RUIN_FOOD_CAP = 500.0  # cap on the seeded reserve
    GRANARY_FOOD = 50.0  # region food_stock above this at extinction -> granary
    SETTLEMENT_SOIL = 0.6  # else soil_fertility above this -> settlement

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        for ruin in context.entities("ruin:"):
            region = snapshot.get(ruin, "region")
            active = bool(snapshot.get(ruin, "active"))
            was_alive = bool(snapshot.get(ruin, "was_alive"))
            pop = int(snapshot.get(region, "population")) if region else 0

            if pop > 0:
                # Region alive: note it (so a later extinction activates the
                # slot); an active ruin persists WITHOUT aging (time doesn't
                # erode an ancestral granary the settlement still keeps).
                # But a ruin explored down to its floor is spent — it
                # collapses regardless of region state, and does not come
                # back until the region lives and dies again.
                if not was_alive:
                    out.append(self._note_alive(context, ruin, region))
                if active and float(snapshot.get(ruin, "resource_food")) <= (
                    self.RUIN_FOOD_FLOOR
                ):
                    out.append(self._collapse(context, ruin, None))
                continue

            # Region extinct (pop == 0).
            if was_alive:
                # Transition INTO extinction (or re-extinction): fresh ruin.
                out.append(self._activate(context, ruin, region))
            elif active:
                # Ongoing extinction: age, maybe collapse.
                age = int(snapshot.get(ruin, "age"))
                res = float(snapshot.get(ruin, "resource_food"))
                new_age = age + 1
                if new_age > self.RUIN_MAX_AGE or res <= self.RUIN_FOOD_FLOOR:
                    out.append(self._collapse(context, ruin, new_age))
                else:
                    out.append(self._age(context, ruin, new_age))
            # else: dormant and already commemorated -> nothing (no oscillation).
        return out

    # ------------------------------------------------------------------
    def _note_alive(self, context, ruin: str, region: str) -> Transition:
        b = context.builder("ruin.note_alive")
        b.read(ruin, "was_alive")
        b.read(region, "population")
        b.write(ruin, "was_alive", True)
        return b.build()

    def _activate(self, context, ruin: str, region: str) -> Transition:
        snapshot = context.snapshot
        food = float(snapshot.get(region, "food_stock"))
        soil = float(snapshot.get(region, "soil_fertility"))
        reserve = clamp(food * self.RUIN_FOOD_FRACTION, self.MIN_RUIN_FOOD, self.RUIN_FOOD_CAP)
        b = context.builder("ruin.activate")
        b.read(ruin, "active")
        b.read(ruin, "was_alive")
        b.read(region, "population")
        b.read(region, "food_stock")
        b.read(region, "soil_fertility")
        b.write(ruin, "active", True)
        b.write(ruin, "was_alive", False)
        b.write(ruin, "type", self._derive_type(food, soil))
        b.write(ruin, "age", 0)
        b.write(ruin, "resource_food", reserve)
        b.write(ruin, "resource_knowledge", 0.0)
        return b.build()

    def _age(self, context, ruin: str, new_age: int) -> Transition:
        b = context.builder("ruin.age")
        b.read(ruin, "active")
        b.read(ruin, "age")
        b.write(ruin, "age", new_age)
        return b.build()

    def _collapse(self, context, ruin: str, new_age) -> Transition:
        # ``new_age`` is None for a collapse in a LIVE region (no aging
        # there, so age must not tick); the extinction branch passes age+1.
        b = context.builder("ruin.collapse")
        b.read(ruin, "active")
        b.read(ruin, "age")
        b.read(ruin, "resource_food")
        b.write(ruin, "active", False)
        b.write(ruin, "type", "")
        if new_age is not None:
            b.write(ruin, "age", new_age)
        # resource_food is left as-is (already <= floor); the next activation
        # overwrites it. Not writing it here keeps this conflict-free with a
        # same-tick exploration depletion.
        return b.build()

    @classmethod
    def _derive_type(cls, food: float, soil: float) -> str:
        # O4, adapted: at extinction ``population == 0`` (the trigger) and the
        # schema has no ``metal``, so the literal settlement/mine branches can
        # never fire. We derive from the attributes still meaningful then —
        # the food stock (a granary) and the soil (a farming settlement).
        if food > cls.GRANARY_FOOD:
            return "granary"
        if soil > cls.SETTLEMENT_SOIL:
            return "settlement"
        return "camp"
