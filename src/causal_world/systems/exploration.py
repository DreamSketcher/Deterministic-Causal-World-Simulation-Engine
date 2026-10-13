"""ExplorationSystem: agents discover ruins for a food bonus (v0.6 step 2).

An alive agent whose region holds an ACTIVE, non-empty ruin may explore it
(an addressable ``agent.explore`` draw gated by ``risk_tolerance`` — the
curious take more chances). Exploring relieves hunger from the ruin's reserve
and draws the reserve down. The bonus lands in the agent's causal trace: the
``agent.explore`` transition READS the ruin and WRITES the agent's hunger, so
a biography query shows "you found a granary your ancestors left; it fed you."

Conflict discipline (priority 40, the highest of the v0.6 systems):

* Each explorer gets their OWN ``agent.explore`` transition writing THEIR
  ``hunger`` — distinct agents, so explorers never conflict with each other.
  It does overlap AgentSystem's metabolism (which also writes hunger); the
  higher system priority means the exploration bonus wins and that agent's
  metabolism is withdrawn for the tick (they ate from the ruin, not foraged).
* The ruin's ``resource_food`` is drawn down by ONE aggregated ``ruin.deplete``
  transition per ruin (``-10`` per explorer), never per explorer — so multiple
  same-tick explorers cannot conflict on the single reserve field. RuinSystem
  writes ``resource_food`` only on activation (inactive slot), which this
  system never targets, so the two never collide either.

v0.6 bonus is FOOD only; ``resource_knowledge`` stays 0 until epochs (v0.6.1)
give knowledge a use (O3). The player's explore is a ``player.decision`` action
(U3), wired to the decision card in step 3 — same transition shape.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class ExplorationSystem(System):
    name = "ExplorationSystem"
    #: Highest of the v0.6 systems: the food bonus must survive its overlap
    #: with metabolism (hunger) rather than be withdrawn.
    priority = 40

    EXPLORE_BASE = 0.02  # base exploration probability
    EXPLORE_RISK = 0.10  # scaled by risk_tolerance
    EXPLORE_MAX = 0.15  # cap
    BONUS_FRACTION = 0.2  # hunger relief = 0.2 * ruin reserve (O3)
    DEPLETION_PER_EXPLORER = 10.0  # reserve drawn down per explorer (O3)

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        tick = snapshot.tick

        # Active, non-empty ruins keyed by their region.
        ruin_by_region: dict[str, str] = {}
        for ruin in context.entities("ruin:"):
            if bool(snapshot.get(ruin, "active")) and float(
                snapshot.get(ruin, "resource_food")
            ) > 0.0:
                ruin_by_region[snapshot.get(ruin, "region")] = ruin
        if not ruin_by_region:
            return out

        # Per-agent exploration decision (risk-gated), aggregated per ruin so
        # the reserve is drawn down once. ``agents`` is sorted, so each ruin's
        # explorer list is in canonical order.
        explorers: dict[str, list[tuple[str, float, float]]] = {}
        for agent in context.entities("agent:"):
            if not snapshot.get(agent, "alive"):
                continue
            ruin = ruin_by_region.get(snapshot.get(agent, "region"))
            if ruin is None:
                continue
            risk = float(snapshot.get(agent, "risk_tolerance"))
            p = clamp(self.EXPLORE_BASE + self.EXPLORE_RISK * risk, 0.0, self.EXPLORE_MAX)
            roll = rng.draw(tick, agent, "agent.explore", 0)
            if roll < p:
                explorers.setdefault(ruin, []).append((agent, p, roll))

        for ruin in sorted(explorers):
            members = explorers[ruin]
            reserve = float(snapshot.get(ruin, "resource_food"))
            bonus = self.BONUS_FRACTION * reserve
            # One bonus transition per explorer (agent-specific causal trace).
            for agent, p, roll in members:
                b = context.builder("agent.explore")
                b.read(ruin, "active")
                b.read(ruin, "resource_food")
                b.read(agent, "region")
                b.read(agent, "risk_tolerance")
                hunger = b.read(agent, "hunger")
                rec = b.draw("agent.explore", agent, index=0, threshold=p)
                assert rec.value == roll
                b.write(agent, "hunger", clamp(hunger - bonus, 0.0, 1.0))
                out.append(b.build())
            # One aggregated draw-down for the ruin (single resource_food write).
            taken = min(reserve, self.DEPLETION_PER_EXPLORER * len(members))
            d = context.builder("ruin.deplete")
            d.read(ruin, "active")
            d.read(ruin, "resource_food")
            d.write(ruin, "resource_food", reserve - taken)
            out.append(d.build())
        return out
