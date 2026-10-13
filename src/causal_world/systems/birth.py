"""BirthSystem: heredity by activating the dormant pool (v0.6 step 2).

A region may bring a child into the world when it is fed, below its
carrying capacity, and a dormant pool slot is free. The child is a
PRE-ALLOCATED dormant agent (``alive=False``, ``region="none"``, blank
placeholder fields from genesis). This system ACTIVATES it by writes — the
resolver forbids creating fields mid-run (``allow_creation=False`` in
``step()``), so every future field already exists at genesis and birth is a
plain ``old=placeholder -> new=inherited`` write. Determinism: every choice
is an addressable draw, so the same seed yields bit-identical births.

Dormant vs dead (Option D stays rejected — we never recycle a corpse):
a dormant slot is ``alive==False AND region=="none"``; birth sets
``region`` to a real region and death never resets it, so a dead agent is
``alive==False AND region=="region:r"`` and is never re-selected.

Inheritance (design v06-02, O1/O2 + the immune_memory refinement). The
trait that actually gates survival is ``immune_memory`` (it attenuates
infection damage), and metabolism erodes ``immunity`` every tick — so we
inherit ``immune_memory`` itself (Lamarckian, exactly the "survivors
accumulate memory, children inherit it" model). Because survivors pass on
memory, ``avg(immune_memory)`` of newborns RISES with generation depth:
emergent evolution, not a programmed trend. Generation is a state field
(U2), so the drift is one ``avg(immune_memory) GROUP BY generation`` query.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class BirthSystem(System):
    name = "BirthSystem"
    #: After AgentSystem(10)/Disease(20); births write only dormant slots
    #: (which every other system skips), so this never conflicts.
    priority = 30

    # --- heredity (O2) ---
    MAX_HEALTH_BASE = 100.0  # keep in sync with PlayerLifeRules.MAX_HEALTH_BASE
    MEM_HERITABILITY = 0.6  # fraction of parent's immune_memory inherited
    IMMUNITY_FROM_MEMORY = 0.4  # newborn immunity = 0.30 + this * parent memory
    MUT_MEMORY = 0.05  # +/- mutation on immune_memory
    MUT_IMMUNITY = 0.05  # +/- mutation on immunity
    MUT_MAX_HEALTH = 5.0  # +/- mutation on max_health
    MUT_RISK = 0.05  # +/- mutation on risk_tolerance

    # --- birth occasion (O1 / U1) ---
    MATURITY = 20  # a parent must be older than this many ticks (O1)
    BIRTH_FOOD_PC_MIN = 3.0  # per-capita food floor to consider a birth
    FOOD_PC_RICH = 20.0  # per-capita food that saturates the birth rate
    RATE_BASE = 0.01  # birth-rate threshold floor (U1)
    RATE_SPAN = 0.04  # birth-rate threshold span (U1: 0.01..0.05)
    # Carrying capacity (O1): regional, tracks soil. Base is set so a region
    # can grow past its genesis population (migration inflates it) up to ~2x
    # at high fertility, and it FALLS with soil (ecological pressure).
    CAPACITY_BASE = 1.0  # capacity = pop_base * (CAPACITY_BASE + CAPACITY_SOIL*soil)
    CAPACITY_SOIL = 1.0

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        tick = snapshot.tick
        agents = context.entities("agent:")

        # Free dormant slots (canonical sorted order — nuance 2). A dormant
        # slot is alive==False AND region=="none"; dead agents keep their
        # region, so they are never recycled (Option D rejected).
        free_dormant = [
            a
            for a in agents
            if not snapshot.get(a, "alive") and snapshot.get(a, "region") == "none"
        ]
        if not free_dormant:
            return out

        # Mature alive agents grouped by region (O1: parent must be > MATURITY
        # ticks old). Built once per tick; ``agents`` is sorted so each group
        # is in canonical order for the addressable parent draw.
        mature_by_region: dict[str, list[str]] = {}
        for a in agents:
            if snapshot.get(a, "alive") and (
                tick - int(snapshot.get(a, "birth_tick"))
            ) > self.MATURITY:
                mature_by_region.setdefault(snapshot.get(a, "region"), []).append(a)

        claimed: set[str] = set()  # dormant slots taken earlier THIS tick
        for region in context.entities("region:"):
            parents = mature_by_region.get(region)
            if not parents:
                continue
            remaining = [a for a in free_dormant if a not in claimed]
            if not remaining:
                break  # pool exhausted -> carrying capacity reached (O5)

            pop = int(snapshot.get(region, "population"))
            pop_base = int(snapshot.get(region, "pop_base"))
            soil = float(snapshot.get(region, "soil_fertility"))
            food = float(snapshot.get(region, "food_stock"))
            food_pc = food / max(pop, 1)

            # Carrying capacity (O1): regional, tracks soil (ecology). Food
            # gates the RATE (below), not capacity, so food is not double-counted.
            capacity = int(
                round(pop_base * (self.CAPACITY_BASE + self.CAPACITY_SOIL * soil))
            )
            if pop >= capacity or food_pc <= self.BIRTH_FOOD_PC_MIN:
                continue

            # Birth occasion (U1): food-surplus-driven rate in [0.01, 0.05].
            surplus = clamp(
                (food_pc - self.BIRTH_FOOD_PC_MIN) / self.FOOD_PC_RICH, 0.0, 1.0
            )
            rate = self.RATE_BASE + self.RATE_SPAN * surplus
            occ_value = rng.draw(tick, region, "birth.occurrence", 0)
            if not occ_value < rate:
                continue  # a failed roll creates no transition (spec §26)

            b = context.builder("agent.birth")
            b.read(region, "population")
            b.read(region, "pop_base")
            b.read(region, "soil_fertility")
            b.read(region, "food_stock")
            occ = b.draw("birth.occurrence", region, index=0, threshold=rate)
            assert occ.value == occ_value

            # Choose the dormant slot (nuance 2: addressable draw over the
            # SORTED free list — not pool[0], not random.choice).
            sel = b.draw("birth.select", region, index=0)
            child = remaining[int(sel.value * len(remaining)) % len(remaining)]

            # Choose the parent (nuance 3: a random MATURE alive agent of the
            # region for v0.6; trait-weighted selection is a v0.7+ variant).
            par = b.draw("birth.parent", region, index=0)
            parent = parents[int(par.value * len(parents)) % len(parents)]

            p_mem = float(b.read(parent, "immune_memory"))
            p_hp = float(b.read(parent, "max_health"))
            p_risk = float(b.read(parent, "risk_tolerance"))
            p_gen = int(b.read(parent, "generation"))

            # Heredity draws, keyed by the CHILD entity (mutation indices).
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
            # Mean-reverting heritability (quantitative genetics, h^2=0.9):
            # offspring = base + h^2*(parent - base) + mutation. The literal
            # "0.9*parent + m" decays geometrically to 0 (a frail dynasty);
            # the +0.1*base term keeps max_health stable around the baseline.
            hp = clamp(
                0.90 * p_hp
                + 0.10 * self.MAX_HEALTH_BASE
                + (d2.value - 0.5) * 2 * self.MUT_MAX_HEALTH,
                1.0,
                100.0,
            )
            risk = clamp(
                0.70 * p_risk + 0.30 * d3.value + (d4.value - 0.5) * 2 * self.MUT_RISK
            )

            # Activation: every field exists at genesis (placeholders), so
            # these are writes, not creations. ``alive False->True`` is the
            # activation; the rest are the inherited attributes.
            b.read(child, "alive")
            b.write(child, "alive", True)
            b.write(child, "region", region)
            b.write(child, "parent_id", parent)
            b.write(child, "generation", p_gen + 1)
            b.write(child, "birth_tick", tick)
            b.write(child, "immune_memory", mem)
            b.write(child, "immunity", imm)
            b.write(child, "max_health", hp)
            b.write(child, "health", hp)  # born at full health
            b.write(child, "hunger", 0.1)  # newborn
            b.write(child, "risk_tolerance", risk)
            b.write(child, "infected", False)

            claimed.add(child)
            out.append(b.build())
        return out
