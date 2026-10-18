"""SenescenceSystem: age-based death (v0.6 step 2, GAME RULESET ONLY).

The first diagnostic showed compost survivors are effectively immortal
(gen-0 still 115 alive at t1800), so "generation" never advances: gen-0
dominates the parent pool and heredity produces no turnover. Senescence is
the biological standard that creates generational turnover — and the natural
selection pressure v0.7+ will build on. An agent past ``SENESCENCE_ONSET``
faces a per-tick death probability rising linearly to ``MAX_DEATH_PROB`` at
``MAX_LIFESPAN`` ( Decision 1: onset 250, max 350, 0.05/tick ).

Game-ruleset ONLY: research rulesets (default/immune/compost/...) never name
this system, so their equilibrium — and the default world's pinned hashes —
are preserved bit-for-bit (the freeze). The lifespan knobs live here as class
constants (systems cannot read the ruleset); PlayerLifeRules opts in by
naming ``SenescenceSystem`` in ``default_systems``.

Determinism: the death roll is an addressable draw ``agent.senescence`` keyed
by (tick, agent), so the same seed yields bit-identical lifespans.
"""

from __future__ import annotations

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp


class SenescenceSystem(System):
    name = "SenescenceSystem"
    #: System priority 25: above AgentSystem(10), below Birth(30).
    #: Transition priority 1 (ADR v13-1): above the player's action (transition
    #: priority 0), so the controlled agent's death by age cannot be cancelled
    #: by the action it chose on the same tick; below DiseaseSystem's infection
    #: (transition priority 2), which keeps its documented precedence.
    priority = 25
    TRANSITION_PRIORITY = 1

    SENESCENCE_ONSET = 250  # ticks; no age death before this
    MAX_LIFESPAN = 350  # ticks; death probability reaches MAX_DEATH_PROB here
    MAX_DEATH_PROB = 0.05  # per-tick death probability at MAX_LIFESPAN
    DEATH_PROB_CAP = 0.5  # safety clamp for extreme ages

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        out: list[Transition] = []
        tick = snapshot.tick
        span = max(1, self.MAX_LIFESPAN - self.SENESCENCE_ONSET)
        for agent in context.entities("agent:"):
            if not snapshot.get(agent, "alive"):
                continue
            age = tick - int(snapshot.get(agent, "birth_tick"))
            if age <= self.SENESCENCE_ONSET:
                continue
            death_prob = clamp(
                (age - self.SENESCENCE_ONSET) / span * self.MAX_DEATH_PROB,
                0.0,
                self.DEATH_PROB_CAP,
            )
            roll = rng.draw(tick, agent, "agent.senescence", 0)
            if not roll < death_prob:
                continue  # a failed roll creates no transition (spec §26)
            b = context.builder("agent.senescence", priority=self.TRANSITION_PRIORITY)
            b.read(agent, "alive")
            b.read(agent, "birth_tick")
            b.read(agent, "health")
            rec = b.draw("agent.senescence", agent, index=0, threshold=death_prob)
            assert rec.value == roll
            b.write(agent, "alive", False)
            b.write(agent, "health", 0.0)
            out.append(b.build())
        return out
