"""v0.11 — resettlement: using the possibilities the player opened.

The v0.10 measurement left one honest failure on the table. A claim
creates room, but the people do not come: the world's own migration
fires on HUNGER and moves to a NEIGHBOUR, so a fed world never uses the
land it has just been given. Capability creation and capability use were
two mechanisms, and only one of them existed.

This module adds the second one, under the rules the review of v0.10
set:

* **The order names a DESTINATION, not a route.** It says "move up to N
  people into this cell; 0 means as many as the cell can take". The
  world chooses the donor deterministically (most over-capacity cell of
  the same region, then distance, then id) and records WHICH cell paid.
  A decree is a goal, not a teleport instruction: the journal shows what
  actually happened.
* **One committed transition moves people AND resources.** The moved
  agents get a new ``cell``; the source loses population and food; the
  destination gains population and records the price. The resolver
  commits the whole transition or none of it, so a partial move is not
  representable.
* **The price is real and local.** Transport costs food at the source
  cell, paid per migrant, growing with the distance. A cell that cannot
  pay does not move anybody and says so in ``resettle_state``.
* **No parallel demography.** The system does not invent a "migrants"
  pool: it writes ``agent.cell`` and the same cell fields the census
  maintains. ``population`` is a derived count, re-derived by the census
  on the next tick; the transition writes its own arithmetic so the
  journal records the move itself.
* **Scope: one region.** Land, food and people of a region are one
  economy; a cross-region caravan needs trade and corridors, which are
  not in the model yet. Refusing to fake them is part of the honest
  limit, and it keeps the region aggregate exact (no stale totals).

Answers written into ``resettle_state`` (a fact in the journal, not a
message to the UI):

    0   no attempt yet
    1   done: N people moved
   -1   refused: the destination has no room
   -2   refused: the destination is wild land (claim it first)
   -3   refused: the destination is not habitable (soil/food reserve)
   -4   refused: the source cannot pay the transport
   -5   refused: the region has no cell that can send people
"""

from __future__ import annotations

from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.capacity import CapacityDirectiveSystem
from causal_world.systems.directive import DIRECTIVE_RESETTLE
from causal_world.systems.spatial import CELL_PREFIX, is_active

#: The encoded answers of the world (they live in the written fields).
RESETTLE_DONE = 1
RESETTLE_NO_ROOM = -1
RESETTLE_WILD = -2
RESETTLE_UNSUITABLE = -3
RESETTLE_NO_FOOD = -4
RESETTLE_NO_DONOR = -5


class ResettlementDirectiveSystem(CapacityDirectiveSystem):
    """The v0.10 cell laws plus the resettlement order.

    Everything the capacity world already knows (amend / water / rest /
    nursery / claim / terrace) is delegated to the parent. This class
    answers one more kind and never touches the others.
    """

    name = "ResettlementDirectiveSystem"

    #: The card of the resettlement world: the capacity levers + one more.
    KIND_NAMES = {
        **CapacityDirectiveSystem.KIND_NAMES,
        DIRECTIVE_RESETTLE: "resettle",
    }

    #: Transport price per migrant: a base plus a per-cell-step term.
    RESETTLE_FOOD_BASE = 4.0
    RESETTLE_FOOD_PER_STEP = 0.5
    #: A destination must be habitable BEFORE it receives people: room is
    #: not enough (the review: "наличие свободных мест ещё не означает,
    #: что клетка пригодна").
    RESETTLE_SOIL_MIN = 0.35
    RESETTLE_FOOD_PC_MIN = 3.0
    #: One order is a caravan, not a century: bound it.
    RESETTLE_MAX_PER_ORDER = 12

    def compute(
        self, snapshot: Snapshot, rng, context
    ) -> list[Transition]:
        if self.channel is None:
            return []
        directive = self.channel.at(snapshot.tick)
        if directive is None:
            return []
        if directive.kind != DIRECTIVE_RESETTLE:
            return super().compute(snapshot, rng, context)
        target = directive.region
        if not target.startswith(CELL_PREFIX):
            return []
        if target not in context.entities(CELL_PREFIX):
            return []
        return [self._resettle(snapshot, directive, target, context)]

    # ------------------------------------------------------------------
    def _resettle(self, snapshot, directive, target: str,
                  context) -> Transition:
        # Priority 2: the move is a fact about people, and the census of
        # this tick (priority 1) was computed before the snapshot knew
        # about it. The census re-derives the count at T+1.
        b = context.builder("player.resettle", priority=2)
        b.draw("player.directive", target, index=0,
               value=float(DIRECTIVE_RESETTLE))

        region = b.read(target, "region")
        if not is_active(snapshot, target):
            b.read(target, "land_active")
            b.write(target, "resettle_state", RESETTLE_WILD)
            return b.build()

        population = int(b.read(target, "population"))
        soil = float(b.read(target, "soil_fertility"))
        food = float(b.read(target, "food_stock"))
        pop_base = int(b.read(target, "pop_base"))
        capacity = int(round(pop_base * (1.0 + soil)))
        room = capacity - population
        if room < 1:
            b.write(target, "resettle_state", RESETTLE_NO_ROOM)
            return b.build()

        food_pc = food / max(population, 1)
        if soil < self.RESETTLE_SOIL_MIN or food_pc < self.RESETTLE_FOOD_PC_MIN:
            b.write(target, "resettle_state", RESETTLE_UNSUITABLE)
            return b.build()

        donors = self._donors(snapshot, region, target, context)
        if not donors:
            b.write(target, "resettle_state", RESETTLE_NO_DONOR)
            return b.build()
        paying = [d for d in donors if d[3] >= 1]
        if not paying:
            b.write(target, "resettle_state", RESETTLE_NO_FOOD)
            return b.build()
        source, distance, cost, affordable, source_pop, source_food = paying[0]

        requested = int(round(float(directive.param)))
        if requested <= 0:
            requested = room
        movers = min(requested, room, source_pop - 1, affordable,
                     self.RESETTLE_MAX_PER_ORDER)
        if movers < 1:
            b.write(target, "resettle_state", RESETTLE_NO_DONOR)
            return b.build()

        # WHO goes: the least hungry first (they can survive the trip),
        # ties by id. An explicit sort, never collection order. The rule
        # lives in one overridable method so an experiment can measure a
        # DIFFERENT policy without touching the world's default law.
        agents = [
            a for a in context.entities("agent:")
            if snapshot.get(a, "alive") and snapshot.get(a, "cell") == source
        ]
        agents = self._choose_movers(agents, snapshot)
        movers = min(movers, len(agents))
        if movers < 1:
            b.write(target, "resettle_state", RESETTLE_NO_DONOR)
            return b.build()
        moved = agents[:movers]
        for agent in moved:
            b.read(agent, "cell")
            b.write(agent, "cell", target)

        total_cost = movers * cost
        b.write(source, "population", source_pop - movers)
        b.write(source, "workers", source_pop - movers)
        b.write(source, "food_stock", source_food - total_cost)
        b.write(source, "resettled_out",
                int(b.read(source, "resettled_out") or 0) + movers)

        b.write(target, "population", population + movers)
        b.write(target, "workers", population + movers)
        b.write(target, "resettled_in",
                int(b.read(target, "resettled_in") or 0) + movers)
        b.write(target, "resettle_state", RESETTLE_DONE)
        b.write(target, "resettle_moved", movers)
        b.write(target, "resettle_cost", total_cost)
        b.write(target, "last_source", source)
        b.write(target, "last_resettle_tick", int(snapshot.tick))
        return b.build()

    # ------------------------------------------------------------------
    def _choose_movers(self, agents: list[str], snapshot) -> list[str]:
        """Order the candidates of one source; the first N are the movers.

        Default: the least hungry first (they can survive the trip), ties
        by id. Deterministic and independent of collection order. This is
        the world's law, not a suggestion: an experiment that wants to
        compare another policy must override THIS method and say so in
        its report. The default is kept as a method (and not inlined)
        precisely so that such a comparison changes one thing.
        """
        return sorted(
            agents,
            key=lambda a: (float(snapshot.get(a, "hunger") or 0.0), a),
        )

    def _donors(self, snapshot, region: str, target: str, context):
        """Rank the region's donors deterministically.

        Returns ``(cell, distance, cost_per_migrant, affordable, pop,
        food)`` tuples, best first:

        1. the largest surplus over the cell's own capacity (the people
           the cell cannot support anyway);
        2. then the shortest distance (a cheaper caravan);
        3. then the id (a total order).

        Cells with no one to spare (``population < 2``) are not donors:
        a resettlement must not empty its source.
        """
        tx, ty = (int(snapshot.get(target, "cell_x")),
                  int(snapshot.get(target, "cell_y")))
        out = []
        for cell in context.entities(CELL_PREFIX):
            if cell == target or not is_active(snapshot, cell):
                continue
            if snapshot.get(cell, "region") != region:
                continue
            population = int(snapshot.get(cell, "population") or 0)
            if population < 2:
                continue
            soil = float(snapshot.get(cell, "soil_fertility") or 0.0)
            capacity = int(round(
                int(snapshot.get(cell, "pop_base") or 0) * (1.0 + soil)
            ))
            surplus = population - capacity
            distance = abs(tx - int(snapshot.get(cell, "cell_x"))) + \
                abs(ty - int(snapshot.get(cell, "cell_y")))
            cost = self.RESETTLE_FOOD_BASE + self.RESETTLE_FOOD_PER_STEP * distance
            food = float(snapshot.get(cell, "food_stock") or 0.0)
            affordable = int(food // cost) if cost > 0 else 0
            out.append((surplus, distance, cell, cost, affordable,
                        population, food))
        out.sort(key=lambda row: (-row[0], row[1], row[2]))
        return [
            (cell, distance, cost, affordable, population, food)
            for surplus, distance, cell, cost, affordable, population, food in out
        ]


__all__ = [
    "ResettlementDirectiveSystem",
    "RESETTLE_DONE",
    "RESETTLE_NO_ROOM",
    "RESETTLE_WILD",
    "RESETTLE_UNSUITABLE",
    "RESETTLE_NO_FOOD",
    "RESETTLE_NO_DONOR",
]
