"""v0.8 — the SPATIAL living world: cells, a stable demography, cell laws.

Why this module exists
----------------------
The v0.7 civic world (``player_civic``) is a world of REGIONS: one soil
number, one food stock, one population per region. It also has a measured
demographic defect, documented in ``experiments/reports/v08_demography.md``:

    1. the birth supply is a per-REGION event (Bernoulli 0.01..0.05 per
       tick), so a region of 50 people produces ONE child per 20-100 ticks
       while a senescence wave removes dozens per tick — the roster can
       never replace its dead;
    2. the compost law returns nutrients PROPORTIONAL TO POPULATION while
       the degradation is CONSTANT, so every death lowers the soil, which
       lowers the harvest, which starves the survivors: a death spiral
       that ends the world at ~tick 250 (measured, not estimated);
    3. the disease wave kills ~45 % of the population in the first 75
       ticks, before any world memory can build.

v0.8 fixes the MODEL (not the story):

* **Soil law — per worker, not per region.** Degradation and the
  nutrient return both scale with the labour applied to the field, so the
  equilibrium soil is a property of the LABOUR REGIME, not of the head
  count. A population decline no longer drags the soil down with it, and
  the player's ``amend`` lever (labour to compost) moves the equilibrium
  measurably. Food and harvest scale with the workers of the cell, so the
  per-capita balance is stable.
* **Birth law — per adult.** Conception is a per-adult probability
  (addressable draw), gated by the cell's food and its carrying
  capacity. The supply of newborns now scales with the number of
  reproductive adults, which is what a demography needs to replace its
  dead.
* **Nursery — a model policy, not a mortality compensation.** The
  ``nursery`` parameter of a cell raises the conception rate and the
  newborn's health. It does NOT touch the death rate: it changes the
  model's reproduction and child health, nothing else.
* **Cells — the spatial layer.** A region owns a GRID of cells; each cell
  has its own soil, food, people and law. Cells differ in rainfall
  (genesis draw), so the map is heterogeneous and the player's choices
  are spatial. Food is LOCAL: a cell's people eat that cell's stores, and
  migration moves people to a better neighbouring cell.

Everything is composed as rules over the frozen kernel. The research
worlds and the v0.6/v0.7 game worlds never name these systems, so their
genesis and journals stay bit-identical (the freeze).

One writer per field (the repo's discipline):

* ``SpatialAgricultureSystem`` writes ``soil_fertility``/``food_stock``
  of a cell (and the region aggregate);
* ``SpatialAgentSystem`` writes ``population``/``workers`` of a cell and
  of a region;
* ``SpatialBirthSystem`` writes the newborn's fields and activates a
  dormant slot;
* ``SpatialDirectiveSystem`` writes the LAW parameters of a cell
  (``labor_diversion``/``water_aid``/``rest_until``/``nursery``); the
  laws above only READ them.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp
from causal_world.systems.fertility import CompostAgricultureSystem
from causal_world.systems.player import PlayerAgentSystem
from causal_world.systems.directive import (
    AMEND_CAP,
    DIRECTIVE_ALL_NAMES,
    DIRECTIVE_AMEND,
    DIRECTIVE_REST,
    DIRECTIVE_WATER,
    REST_MAX,
    WATER_CAP,
    DirectiveSystem,
)

#: v0.8 directive table (the v0.7 three plus the nursery).
SPATIAL_DIRECTIVE_NAMES = dict(DIRECTIVE_ALL_NAMES)

#: Entity prefix of a spatial cell.
CELL_PREFIX = "cell:"


def is_active(snapshot, cell: str) -> bool:
    """Is this parcel part of the working world?

    A v0.10 capacity world pre-creates WILD parcels (``land_active = 0``):
    they are land, not cells — the ecology, the census, births,
    migration and the situation feed must ignore them until a claim
    activates them. Every earlier spatial world has no such field, and
    a parcel without it is an ordinary cell.
    """
    try:
        value = snapshot.get(cell, "land_active")
    except Exception:
        return True
    if value is None:
        return True
    return bool(int(value))


# ----------------------------------------------------------------------
# 1. The spatial law of a cell
# ----------------------------------------------------------------------
class SpatialAgricultureSystem(CompostAgricultureSystem):
    """Per-cell ecology: climate x soil x labour -> food, labour -> soil.

    The soil law of v0.8 (the fix for the measured death spiral):

        degradation = DEGRADATION_PER_WORKER x workers x (1 + salinity)
        compost     = workers x COMPOST_PER_WORKER x (1 - soil)
                     + diverted_workers x AMEND_PER_WORKER x (1 - soil)

    Both terms scale with the LABOUR, so the equilibrium soil

        soil* = 1 - DEGRADATION_PER_WORKER / effective_compost_per_worker

    does NOT depend on the head count: fewer people eat less, but the
    land keeps its balance. Before (v0.3.3-G compost) the nutrient return
    was proportional to the POPULATION while the degradation was flat,
    so every death lowered the soil and started a spiral.

    At the baseline numbers the equilibrium is soil 0.5, and diverting a
    quarter of the labour to ACTIVE composting lifts it to ~0.67 at the
    price of a quarter of the harvest. That is the trade the player is
    asked to make, and it is measured, not asserted.
    """

    name = "SpatialAgricultureSystem"
    priority = 0

    #: The climate response of v0.8. The v0.1 law (16 °C optimum, a span
    #: of 14) makes a cold region a cliff: the harvest per worker falls
    #: below the consumption and no lever can lift it back. v0.8 uses a
    #: gentler curve, so a cell's food balance is a MANAGEABLE quantity
    #: (0.9-1.1 in a typical cell) that the player's levers can cross.
    OPTIMAL_TEMPERATURE = 14.0
    TEMPERATURE_SPAN = 26.0
    RAIN_REFERENCE = 0.55
    RAIN_CAP = 1.3

    #: Per-worker nutrient return and per-worker degradation. The
    #: equilibrium soil is 1 - DEGRADATION/COMPOST = 0.47, i.e. a cell
    #: that nobody tends drifts to a thin but stable soil. The pair is
    #: scaled so the soil RELAXES in ~40 ticks: a decree must be visible
    #: on the map within a human lifetime of the world.
    COMPOST_PER_WORKER = 0.0034
    DEGRADATION_PER_WORKER = 0.0018
    #: Active composting: what a diverted worker adds on top of the
    #: ambient waste stream. At a sixth of the labour diverted the
    #: equilibrium soil rises from 0.47 to ~0.65, which lifts the food
    #: balance by ~18 % — the price is that share of the harvest, paid
    #: NOW, for a soil that pays off over the next ~60 ticks.
    AMEND_PER_WORKER = 0.012
    #: Irrigation: effective rainfall up, the soil mined a little faster
    #: (salinity). Food now, soil later.
    WATER_RAIN_BONUS = 0.25
    WATER_SALT_FACTOR = 0.15
    #: Fallow recovery (absolute, per tick).
    REST_RECOVERY = 0.003

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        cells = [
            c for c in context.entities(CELL_PREFIX)
            if is_active(snapshot, c)
        ]
        for cell in cells:
            b = context.builder("agriculture.harvest")
            region = b.read(cell, "region")
            temperature = b.read(region, "temperature")
            rainfall = b.read(region, "rainfall")
            rain_factor = b.read(cell, "rain_factor")
            soil = b.read(cell, "soil_fertility")
            workers = b.read(cell, "workers")
            population = b.read(cell, "population")
            food = b.read(cell, "food_stock")
            # --- the enacted law of this cell -------------------------
            diversion = float(b.read(cell, "labor_diversion"))
            water = float(b.read(cell, "water_aid"))
            rest_until = int(b.read(cell, "rest_until"))

            resting = snapshot.tick < rest_until
            spoilage = self.SPOILAGE_RATE * food
            consumption = self.CONSUMPTION_PER_CAPITA * population

            if resting:
                # Fallow: nothing is grown (no crop draw — an unplanted
                # field has no crop to vary), the field heals, the stores
                # are eaten.
                new_food = max(0.0, food - spoilage - consumption)
                new_soil = clamp(soil + self.REST_RECOVERY, 0.05, 1.0)
            else:
                variance_draw = b.draw("agriculture.crop_variance", cell)
                crop_variance = 0.75 + 0.5 * variance_draw.value

                temp_factor = max(
                    0.0,
                    1.0
                    - abs(temperature - self.OPTIMAL_TEMPERATURE)
                    / self.TEMPERATURE_SPAN,
                )
                effective_rain = (rainfall + water * self.WATER_RAIN_BONUS) * rain_factor
                rain_factor_eff = clamp(
                    effective_rain / self.RAIN_REFERENCE, 0.0, self.RAIN_CAP
                )
                field_workers = workers * (1.0 - diversion)
                harvest = (
                    self.BASE_YIELD
                    * temp_factor
                    * rain_factor_eff
                    * soil
                    * field_workers
                    * crop_variance
                )
                new_food = max(0.0, food + harvest - spoilage - consumption)
                compost = workers * self.COMPOST_PER_WORKER * (1.0 - soil)
                compost += (
                    workers * diversion * self.AMEND_PER_WORKER * (1.0 - soil)
                )
                degradation = self.DEGRADATION_PER_WORKER * workers * (
                    1.0 + water * self.WATER_SALT_FACTOR
                )
                new_soil = clamp(soil - degradation + compost, 0.05, 1.0)

            b.write(cell, "food_stock", new_food)
            b.write(cell, "soil_fertility", new_soil)
            out.append(b.build())

        out.extend(self._aggregate(context, cells))
        return out

    def _aggregate(self, context, cells: list[str]) -> list[Transition]:
        """Region-level view of the cells (sum of food, mean of soil).

        The observer layer, the ruin system and the region rows of the
        protocol read region fields, so the spatial world keeps those
        fields as DERIVED values — written here, read everywhere else.
        """
        out: list[Transition] = []
        by_region: dict[str, list[str]] = {}
        for cell in cells:
            region = context.snapshot.get(cell, "region")
            by_region.setdefault(region, []).append(cell)
        for region in context.entities("region:"):
            members = by_region.get(region, [])
            if not members:
                continue
            b = context.builder("agriculture.aggregate")
            total_food = 0.0
            total_soil = 0.0
            for cell in members:
                total_food += float(b.read(cell, "food_stock"))
                total_soil += float(b.read(cell, "soil_fertility"))
            b.write(region, "food_stock", total_food)
            b.write(region, "soil_fertility", total_soil / len(members))
            out.append(b.build())
        return out


# ----------------------------------------------------------------------
# 2. The spatial people
# ----------------------------------------------------------------------
class SpatialAgentSystem(System):
    """Census, metabolism, health and MIGRATION on a cell grid.

    Differences from the v0.6 ``AgentSystem`` (everything else is the
    same law, so the two worlds stay comparable):

    * the census counts per CELL and aggregates to the region;
    * metabolism reads the CELL's stores (food is local);
    * migration moves to a NEIGHBOURING CELL, chosen by the best food
      per capita among the neighbours (informed migration — the same
      idea as ``FertileMigrationAgentSystem``, one level down).
    """

    name = "SpatialAgentSystem"
    priority = 10

    HUNGER_RATE = 0.07
    INTAKE_RELIEF = 0.1
    STARVATION_THRESHOLD = 0.75
    MIGRATION_THRESHOLD = 0.55

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        agents = context.entities("agent:")
        out.extend(self._census(context, agents))
        for agent in agents:
            if not snapshot.get(agent, "alive"):
                continue
            metabolism = self._metabolism(context, agent)
            if metabolism is not None:
                out.append(metabolism)
            health = self._health(context, agent)
            if health is not None:
                out.append(health)
            migration = self._migration(context, agent)
            if migration is not None:
                out.append(migration)
        return out

    # ------------------------------------------------------------------
    def _census(self, context, agents: list[str]) -> list[Transition]:
        out: list[Transition] = []
        snapshot = context.snapshot
        active = [
            c for c in context.entities(CELL_PREFIX)
            if is_active(snapshot, c)
        ]
        members: dict[str, list[str]] = {cell: [] for cell in active}
        for agent in agents:
            cell = snapshot.get(agent, "cell")
            if cell in members:
                members[cell].append(agent)

        for cell in active:
            b = context.builder("agents.census", priority=1)
            alive_count = 0
            for agent in members[cell]:
                b.read(agent, "cell")
                if b.read(agent, "alive"):
                    alive_count += 1
            b.write(cell, "population", alive_count)
            b.write(cell, "workers", alive_count)
            # WHEN the cell was emptied: the fact that lets the world
            # say "this land has been empty since tick N" without
            # recomputing anything.
            empty_since = int(b.read(cell, "empty_since") or 0)
            if alive_count == 0:
                b.write(cell, "empty_since", empty_since or snapshot.tick)
            else:
                b.write(cell, "empty_since", 0)
            out.append(b.build())

        # Region aggregate: the sum over the region's cells.
        by_region: dict[str, list[str]] = {}
        for cell in active:
            by_region.setdefault(snapshot.get(cell, "region"), []).append(cell)
        for region in context.entities("region:"):
            b = context.builder("agents.aggregate", priority=1)
            total = 0
            for cell in by_region.get(region, []):
                total += int(b.read(cell, "population"))
            b.write(region, "population", total)
            b.write(region, "workers", total)
            out.append(b.build())
        return out

    # ------------------------------------------------------------------
    def _metabolism(self, context, agent: str) -> Transition | None:
        b = context.builder("agent.metabolism")
        cell = b.read(agent, "cell")
        hunger = b.read(agent, "hunger")
        immunity = b.read(agent, "immunity")
        food = b.read(cell, "food_stock")
        population = b.read(cell, "population")

        food_per_capita = food / max(population, 1)
        eaten = min(1.0, food_per_capita)
        new_hunger = clamp(hunger + self.HUNGER_RATE - self.INTAKE_RELIEF * eaten)
        new_immunity = clamp(immunity + 0.002 - 0.005 * immunity - 0.01 * new_hunger)

        b.write(agent, "hunger", new_hunger)
        b.write(agent, "immunity", new_immunity)
        return b.build()

    def _health(self, context, agent: str) -> Transition | None:
        snapshot = context.snapshot
        infected = bool(snapshot.get(agent, "infected"))
        hunger = float(snapshot.get(agent, "hunger"))

        delta = 0.0
        if infected:
            delta -= 2.5
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

    @staticmethod
    def _is_lethal(snapshot: Snapshot, agent: str, delta: float) -> bool:
        health = float(snapshot.get(agent, "health"))
        return clamp(health + delta, 0.0, 100.0) <= 0.0

    # ------------------------------------------------------------------
    def _migration(self, context, agent: str) -> Transition | None:
        """Move to a better neighbouring cell (informed, deterministic).

        The move is gated exactly as in v0.6: a hungry agent
        (``hunger >= MIGRATION_THRESHOLD``) rolls ``agent.decision``
        against its risk tolerance. The DESTINATION is the neighbour
        with the best food per capita — and only if that neighbour is
        better than the cell the agent is in, so the population sorts
        itself into the fertile cells without churning.
        """
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
        cell = b.read(agent, "cell")
        roll = b.draw("agent.decision", agent, threshold=risk * 0.5)
        assert roll.value == roll_value

        here = self._score(b, cell)
        best, best_score = None, here
        for neighbour in self._neighbours(cell, context):
            score = self._score(b, neighbour)
            if score > best_score:
                best, best_score = neighbour, score
        if best is None:
            return None  # nowhere better to go
        b.write(agent, "cell", best)
        return b.build()

    def _score(self, b, cell: str) -> float:
        food = b.read(cell, "food_stock")
        population = b.read(cell, "population")
        return food / max(population, 1)

    def _neighbours(self, cell: str, context) -> list[str]:
        """The four orthogonal neighbours of a cell (same region)."""
        snapshot = context.snapshot
        if cell not in context.entities(CELL_PREFIX):
            return []
        x = int(snapshot.get(cell, "cell_x"))
        y = int(snapshot.get(cell, "cell_y"))
        region = snapshot.get(cell, "region")
        by_xy: dict[tuple[int, int], str] = {}
        for other in context.entities(CELL_PREFIX):
            if not is_active(snapshot, other):
                continue  # wild land is not walkable
            if snapshot.get(other, "region") != region:
                continue
            by_xy[(int(snapshot.get(other, "cell_x")),
                   int(snapshot.get(other, "cell_y")))] = other
        out = []
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            neighbour = by_xy.get((x + dx, y + dy))
            if neighbour is not None:
                out.append(neighbour)
        return out


# ----------------------------------------------------------------------
# 3. The spatial demography
# ----------------------------------------------------------------------
class SpatialBirthSystem(System):
    """Per-ADULT reproduction (the fix for the v0.7 birth collapse).

    The v0.6 law drew ONE Bernoulli event per region per tick
    (probability 0.01..0.05): a region of 50 people produced one child
    per 20-100 ticks, which no death wave can be replaced from. v0.8
    draws a conception per reproductive adult per tick:

        p = CONCEPT_PER_ADULT
            x food factor        (no conception in a famine)
            x (1 + nursery bonus)  (the policy of the cell)

    so the supply of newborns scales with the number of adults. A
    conception that succeeds activates a dormant slot (the pool is the
    world's reserve of lives) and the child joins the parent's cell.

    The herdity law is the v0.6 one, unchanged (mean-reverting
    ``max_health``, inherited immune memory, addressable mutation) —
    only the OCCASION of a birth changed.
    """

    name = "SpatialBirthSystem"
    priority = 30

    # --- conception ---
    CONCEPT_PER_ADULT = 0.02
    BIRTH_FOOD_PC_MIN = 3.0
    FOOD_PC_RICH = 20.0
    #: Carrying capacity of a cell: its genesis head count, scaled by the
    #: fertility of its soil.
    CAPACITY_BASE = 1.0
    CAPACITY_SOIL = 1.0
    #: A parent must be older than this many ticks.
    MATURITY = 20
    #: The nursery policy: conception rate and child health.
    NURSERY_CONCEPT_BONUS = 1.0
    NURSERY_HEALTH_BONUS = 10.0

    # --- heredity (v0.6 law, unchanged) ---
    MAX_HEALTH_BASE = 100.0
    MEM_HERITABILITY = 0.6
    IMMUNITY_FROM_MEMORY = 0.4
    MUT_MEMORY = 0.05
    MUT_IMMUNITY = 0.05
    MUT_MAX_HEALTH = 5.0
    MUT_RISK = 0.05

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        tick = snapshot.tick
        agents = context.entities("agent:")

        free_dormant = [
            a
            for a in agents
            if not snapshot.get(a, "alive") and snapshot.get(a, "region") == "none"
        ]
        if not free_dormant:
            return out

        mature_by_cell: dict[str, list[str]] = {}
        for a in agents:
            if snapshot.get(a, "alive") and (
                tick - int(snapshot.get(a, "birth_tick"))
            ) > self.MATURITY:
                mature_by_cell.setdefault(snapshot.get(a, "cell"), []).append(a)

        claimed: set[str] = set()
        for cell in context.entities(CELL_PREFIX):
            if not is_active(snapshot, cell):
                continue
            parents = mature_by_cell.get(cell)
            if not parents:
                continue
            remaining = [a for a in free_dormant if a not in claimed]
            if not remaining:
                break  # the reserve of lives is exhausted

            population = int(snapshot.get(cell, "population"))
            pop_base = int(snapshot.get(cell, "pop_base"))
            soil = float(snapshot.get(cell, "soil_fertility"))
            food = float(snapshot.get(cell, "food_stock"))
            nursery = float(snapshot.get(cell, "nursery"))
            births_total = int(snapshot.get(cell, "births_total") or 0)
            food_pc = food / max(population, 1)

            capacity = int(
                round(pop_base * (self.CAPACITY_BASE + self.CAPACITY_SOIL * soil))
            )
            if population >= capacity or food_pc <= self.BIRTH_FOOD_PC_MIN:
                continue

            # Food surplus: 0 in a famine, 1 in a well-fed cell.
            surplus = clamp(
                (food_pc - self.BIRTH_FOOD_PC_MIN) / self.FOOD_PC_RICH, 0.0, 1.0
            )
            p = self.CONCEPT_PER_ADULT * (0.25 + 0.75 * surplus)
            p *= 1.0 + self.NURSERY_CONCEPT_BONUS * nursery

            for parent in parents:
                if len(remaining) == 0:
                    break
                if population >= capacity:
                    break
                # One transition PER CHILD: a builder that carried two
                # children would write the same field twice and be
                # rejected as a duplicate write.
                b = context.builder("agent.birth")
                b.read(cell, "population")
                b.read(cell, "soil_fertility")
                b.read(cell, "food_stock")
                b.read(cell, "nursery")
                b.read(cell, "births_total")
                conception = b.draw("birth.conceive", parent, index=0, threshold=p)
                if not conception.outcome:
                    continue

                sel = b.draw("birth.select", cell, index=0)
                child = remaining[int(sel.value * len(remaining)) % len(remaining)]
                remaining.remove(child)
                claimed.add(child)

                b.read(child, "alive")
                b.write(child, "alive", True)
                b.write(child, "region", b.read(parent, "region"))
                b.write(child, "cell", cell)
                b.write(child, "parent_id", parent)
                b.write(child, "generation", int(b.read(parent, "generation")) + 1)
                b.write(child, "birth_tick", tick)

                p_mem = float(b.read(parent, "immune_memory"))
                p_hp = float(b.read(parent, "max_health"))
                p_risk = float(b.read(parent, "risk_tolerance"))

                d0 = b.draw("birth.mutation", child, index=0)
                d1 = b.draw("birth.mutation", child, index=1)
                d2 = b.draw("birth.mutation", child, index=2)
                d3 = b.draw("birth.mutation", child, index=3)
                d4 = b.draw("birth.mutation", child, index=4)

                mem = clamp(
                    p_mem * self.MEM_HERITABILITY + (d0.value - 0.5) * 2 * self.MUT_MEMORY
                )
                imm = clamp(
                    0.30
                    + self.IMMUNITY_FROM_MEMORY * p_mem
                    + (d1.value - 0.5) * 2 * self.MUT_IMMUNITY
                )
                hp = clamp(
                    0.90 * p_hp
                    + 0.10 * self.MAX_HEALTH_BASE
                    + (d2.value - 0.5) * 2 * self.MUT_MAX_HEALTH,
                    1.0,
                    100.0,
                )
                hp = clamp(
                    hp + self.NURSERY_HEALTH_BONUS * nursery, 1.0, 100.0
                )
                risk = clamp(
                    0.70 * p_risk + 0.30 * d3.value + (d4.value - 0.5) * 2 * self.MUT_RISK
                )

                b.write(child, "immune_memory", mem)
                b.write(child, "immunity", imm)
                b.write(child, "max_health", hp)
                b.write(child, "health", hp)
                b.write(child, "hunger", 0.1)
                b.write(child, "risk_tolerance", risk)
                b.write(child, "infected", False)
                # The cell keeps its own birth history: the situation
                # layer reads it to see that a cell has stopped
                # producing children (and why, from the same record).
                births_total += 1
                b.write(cell, "births_total", births_total)
                b.write(cell, "last_birth_tick", tick)
                population += 1
                out.append(b.build())
        return out


# ----------------------------------------------------------------------
# 4. The player's own avatar in a spatial world
# ----------------------------------------------------------------------
class SpatialPlayerAgentSystem(PlayerAgentSystem):
    """The v0.6 personal card, taught to live in a cell.

    The v0.6 ``PlayerAgentSystem`` moves the avatar between REGIONS. In
    the spatial world an agent belongs to a CELL, so a region hop must
    carry the cell with it — otherwise the avatar would be counted in
    the cell it left and in the region it reached. The avatar lands in
    the first cell of the target region (canonical order): the player
    chooses the LAWS of the map, not the avatar's address.
    """

    name = "SpatialPlayerAgentSystem"

    def _act_1(self, snapshot: Snapshot, context, b, agent: str, tick: int) -> None:
        regions = sorted(
            context.entities("region:"), key=lambda e: int(e.split(":")[1])
        )
        current = b.read(agent, "region")
        if current in regions and len(regions) > 1:
            nxt = regions[(regions.index(current) + 1) % len(regions)]
        else:
            nxt = current  # nowhere to go (single-region world): stay
        b.write(agent, "region", nxt)
        cells = [
            c
            for c in context.entities(CELL_PREFIX)
            if snapshot.get(c, "region") == nxt and is_active(snapshot, c)
        ]
        if cells:
            b.write(agent, "cell", cells[0])


# ----------------------------------------------------------------------
# 5. The civic law of a cell
# ----------------------------------------------------------------------
class SpatialDirectiveSystem(DirectiveSystem):
    """The v0.7 directive system, retargeted at CELLS, plus the nursery.

    A decree names a cell, not a region: the map is the object of the
    game, and the law of a cell is what the player writes. The three
    v0.7 levers keep their meaning (amend / water / rest) and the
    fourth (``nursery``) is the demographic policy of v0.8.
    """

    name = "SpatialDirectiveSystem"
    KIND_NAMES = SPATIAL_DIRECTIVE_NAMES
    TARGET_PREFIX = CELL_PREFIX

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        if self.channel is None:
            return []
        directive = self.channel.at(snapshot.tick)
        if directive is None:
            return []
        target = directive.region
        if directive.kind not in self.KIND_NAMES:
            return []
        if not target.startswith(self.TARGET_PREFIX):
            return []
        if target not in context.entities(self.TARGET_PREFIX):
            return []  # a target that does not exist is simply not enacted

        b = context.builder(self.OPERATION)
        b.draw("player.directive", target, index=0, value=float(directive.kind))

        if directive.kind == DIRECTIVE_AMEND:
            old = float(b.read(target, "labor_diversion"))
            new = clamp(old + float(directive.param), 0.0, AMEND_CAP)
            b.write(target, "labor_diversion", new)
        elif directive.kind == DIRECTIVE_WATER:
            old = float(b.read(target, "water_aid"))
            new = clamp(old + float(directive.param), 0.0, WATER_CAP)
            b.write(target, "water_aid", new)
        elif directive.kind == DIRECTIVE_REST:
            old = int(b.read(target, "rest_until"))
            if directive.param <= 0:
                b.write(target, "rest_until", 0)
            else:
                length = max(1, min(int(directive.param), REST_MAX))
                b.write(target, "rest_until", max(old, snapshot.tick + length))
        else:  # DIRECTIVE_NURSERY
            old = float(b.read(target, "nursery"))
            new = clamp(old + float(directive.param), 0.0, self.NURSERY_CAP)
            b.write(target, "nursery", new)
        return [b.build()]

    #: Cap on the nursery share of a cell's households.
    NURSERY_CAP = 1.0
