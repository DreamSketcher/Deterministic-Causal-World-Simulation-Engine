"""PlayerAgentSystem: one agent of the world is driven by external input.

v0.6 step 3 (3a/3b). Every tick the controlled agent's action comes from the
attached ``DecisionChannel`` — never from the seed. The action is recorded as
a ``player.decision`` draw with ``value=action_index`` (the step-1 contract:
«a dice roll cannot veto an explicit choice» — the dice never decide *what*
was attempted), and the action's OUTCOME stays ordinary rng in the systems
that resolve it (disease rolls, crop variance). The effect is one committed
``player.act`` transition per live tick: the resolver then lets priority 45
win over AgentSystem(10)/Senescence(25) for THIS agent's fields — the NPC
metabolism/migration/mortality transitions for the controlled agent are
withdrawn for the tick ("player overrides autonomy"), while every other
agent's rolls continue untouched (addressable draws cannot shift).

The action card (U3 — one action_index = one purpose = one biography node):

    0 work     hunger −0.30, health −5        (the census already counts the
                                               player as a worker for the
                                               region's harvest)
    1 migrate  region := next region (cyclic, sorted by index)
    2 explore  immediate ruin find: hunger relief + ruin draw-down ON THIS
               transition (reads the ruin entity for provenance; a declared
               explore is certainty, not a roll — Q1; nothing to find is a
               recorded, inert "no" from the world, never a veto)
    3 heal     health +10 (capped at max_health), immunity +0.05
    4 trade    hunger −0.05, health −1         (placeholder: a metal economy
                                               does not exist in v0.6 —
                                               see report deviation notes)
    5 rest     health +5, hunger +0.05
    6 no-op    hunger +0.01                    (idling still burns food)

Out-of-range values are REJECTED, not crashed: the attempt is still recorded
(draw value kept verbatim, ``last_action = −1``) so replay stays aligned, but
no effect fires. If the controlled agent is dead the system is fully inert
and consumes nothing from the channel (the replay stream skips dead ticks on
both sides by construction).

``last_action`` is written every live tick — including idle (6) and rejected
(−1) — precisely so ``DecisionStreamReader`` can rebuild the FULL per-tick
stream from the journal: no silently-dropped decisions, bit-identical replay.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp

#: The action card, canonical (3b). Kept module-level: tests and the client
#: layer import the mapping, they never redefine it.
ACTION_WORK = 0
ACTION_MIGRATE = 1
ACTION_EXPLORE = 2
ACTION_HEAL = 3
ACTION_TRADE = 4
ACTION_REST = 5
ACTION_IDLE = 6
ACTION_NAMES = {
    ACTION_WORK: "work",
    ACTION_MIGRATE: "migrate",
    ACTION_EXPLORE: "explore",
    ACTION_HEAL: "heal",
    ACTION_TRADE: "trade",
    ACTION_REST: "rest",
    ACTION_IDLE: "no-op",
}
N_ACTIONS = 7  # valid indices are [0, N_ACTIONS)


class PlayerAgentSystem(System):
    name = "PlayerAgentSystem"
    #: Above every world-law system (AgentSystem 10, Senescence 25, Birth 30,
    #: Ruin 31, Exploration 40): a player decision wins same-field ties, and
    #: the loser transitions are withdrawn for the controlled agent only.
    priority = 45

    #: effect magnitudes — prototype economy numbers, not physics
    WORK_HUNGER_RELIEF = 0.30
    WORK_HEALTH_COST = 5.0
    EXPLORE_BONUS = 0.2  # hunger relief = 0.2 * ruin reserve (as in step 2)
    EXPLORE_TAKE = 10.0  # reserve drawn down (as ExplorationSystem does)
    HEAL_HEALTH = 10.0
    HEAL_IMMUNITY = 0.05
    TRADE_FOOD = 0.05  # hunger relief: "sold some labor for bread"
    TRADE_HEALTH_COST = 1.0
    REST_HEALTH = 5.0
    REST_HUNGER = 0.05
    IDLE_HUNGER = 0.01

    def __init__(self, channel=None, controlled: str = "agent:0") -> None:
        # The engine registry instantiates no-arg (world stays inert until a
        # harness attaches a channel); tests construct with the channel
        # directly. ``attach_player_channel`` in causal_world.player wires
        # both for create_world-built games.
        self.channel = channel
        self.controlled = controlled

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        if self.channel is None:
            return []  # nobody is playing: the world runs its NPC laws
        agent = self.controlled
        if not snapshot.get(agent, "alive"):
            return []  # dead agents decide nothing (and consume no stream)
        tick = snapshot.tick

        action = int(self.channel.next_action())  # the blocking recv (3c)
        b = context.builder("player.act")
        b.read(agent, "alive")
        b.read(agent, "last_action")
        # Q1: the recorded decision is the player's value verbatim — never an
        # rng roll. threshold=None keeps outcome == value (step-1 convention).
        b.draw("player.decision", agent, index=0, value=float(action))

        if not 0 <= action < N_ACTIONS:
            # Reject (test 3d-8): the attempt stays in the journal for replay
            # alignment, but no effect fires and nothing else is read/written.
            b.write(agent, "last_action", -1)
            return [b.build()]

        b.write(agent, "last_action", action)
        getattr(self, f"_act_{action}")(snapshot, context, b, agent, tick)
        return [b.build()]

    # ---------------------------------------------------------------- effects
    def _act_0(self, snapshot, context, b, agent, tick) -> None:  # work
        hunger = float(b.read(agent, "hunger"))
        health = float(b.read(agent, "health"))
        b.write(agent, "hunger", clamp(hunger - self.WORK_HUNGER_RELIEF))
        b.write(
            agent, "health", clamp(health - self.WORK_HEALTH_COST, 0.0, 1e18)
        )

    def _act_1(self, snapshot, context, b, agent, tick) -> None:  # migrate
        regions = sorted(
            context.entities("region:"), key=lambda e: int(e.split(":")[1])
        )
        current = b.read(agent, "region")
        if current in regions and len(regions) > 1:
            nxt = regions[(regions.index(current) + 1) % len(regions)]
        else:
            nxt = current  # nowhere to go (single-region world): stay
        b.write(agent, "region", nxt)

    def _act_2(self, snapshot, context, b, agent, tick) -> None:  # explore
        # Immediate execution (U3): the choice IS the causal node — bonus and
        # draw-down are written on THIS transition, reading the ruin entity
        # for provenance (an AUTOPSY can point at it). No rng roll gates it:
        # a declared explore is certainty (Q1). If there is nothing to find,
        # the world says "no" — the choice is still recorded (last_action),
        # but no effect fires. Same-tick NPC ruin foraging aggregates into
        # ruin.deplete and LOSES the single reserve field to priority 45:
        # one granary keeps one feeding queue per tick (the rejection is
        # itself journaled, so the NPCs' attempt remains in the causal trace).
        b.read(agent, "region")
        home = snapshot.get(agent, "region")
        found = None
        for ruin in context.entities("ruin:"):
            if (
                snapshot.get(ruin, "active")
                and snapshot.get(ruin, "region") == home
                and float(snapshot.get(ruin, "resource_food")) > 0.0
            ):
                found = ruin
                break
        hunger = float(b.read(agent, "hunger"))
        if found is None:
            return
        reserve = float(b.read(found, "resource_food"))
        b.write(agent, "hunger", clamp(hunger - self.EXPLORE_BONUS * reserve))
        b.write(found, "resource_food", reserve - min(reserve, self.EXPLORE_TAKE))

    def _act_3(self, snapshot, context, b, agent, tick) -> None:  # heal
        health = float(b.read(agent, "health"))
        max_hp = float(b.read(agent, "max_health"))
        immunity = float(b.read(agent, "immunity"))
        b.write(agent, "health", clamp(health + self.HEAL_HEALTH, 0.0, max_hp))
        b.write(agent, "immunity", clamp(immunity + self.HEAL_IMMUNITY))

    def _act_4(self, snapshot, context, b, agent, tick) -> None:  # trade
        # Placeholder until v0.6.1 gives the world a ``metal`` field: trading
        # labor for food. Small numbers, no region write (avoids competing
        # with AgricultureSystem's food_stock transition).
        hunger = float(b.read(agent, "hunger"))
        health = float(b.read(agent, "health"))
        b.write(agent, "hunger", clamp(hunger - self.TRADE_FOOD))
        b.write(agent, "health", clamp(health - self.TRADE_HEALTH_COST, 0.0, 1e18))

    def _act_5(self, snapshot, context, b, agent, tick) -> None:  # rest
        health = float(b.read(agent, "health"))
        max_hp = float(b.read(agent, "max_health"))
        hunger = float(b.read(agent, "hunger"))
        b.write(agent, "health", clamp(health + self.REST_HEALTH, 0.0, max_hp))
        b.write(agent, "hunger", clamp(hunger + self.REST_HUNGER))

    def _act_6(self, snapshot, context, b, agent, tick) -> None:  # no-op
        hunger = float(b.read(agent, "hunger"))
        b.write(agent, "hunger", clamp(hunger + self.IDLE_HUNGER))
