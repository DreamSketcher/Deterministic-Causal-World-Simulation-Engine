"""Player input channel + journal replay (v0.6 step 3, 3c).

Fully synchronous by design (Q2): the harness feeds the channel, ``step()``
drains exactly one decision per live tick. The prototype transport is
``queue.Queue`` (single thread); step 5's sim-server puts the same class
behind a WebSocket reader — nothing in the engine changes.

Determinism contract: the world is reproducible given (seed, decision
stream). The stream is recorded INTO the journal itself — every live tick
of the controlled agent commits a ``player.act`` transition whose
``player.decision`` draw carries the raw action value (including rejected
out-of-range attempts, including idle). That is what makes
``DecisionStreamReader`` lossless: replay = read the draws back out and
feed them to a fresh world under the same seed -> bit-identical journal.

Blocking mode is for the live server (recv until the client acts, then
fall back to idle after a timeout so the simulation can never deadlock);
non-blocking is for tests and offline runs (empty queue -> idle default).
"""

from __future__ import annotations

import queue
from typing import Iterable

from causal_world.systems.player import PlayerAgentSystem


class DecisionChannel:
    """One action per tick, FIFO. ``deliver`` is the server/test side,
    ``next_action`` is the system side (the "blocking recv")."""

    def __init__(
        self,
        actions: Iterable[int] | None = None,
        block: bool = False,
        timeout: float = 30.0,
        default_action: int = 6,
    ) -> None:
        self._q: queue.Queue[int] = queue.Queue()
        for a in actions or ():
            self._q.put(int(a))
        self.block = block
        self.timeout = timeout
        self.default_action = int(default_action)

    def deliver(self, action_index: int) -> None:
        self._q.put(int(action_index))

    def next_action(self) -> int:
        try:
            if self.block:
                return self._q.get(timeout=self.timeout)
            return self._q.get_nowait()
        except queue.Empty:
            return self.default_action  # nobody acted this tick: idle

    @property
    def pending(self) -> int:
        return self._q.qsize()


class DecisionStreamReader:
    """Rebuild a decision stream from a journal (replay input).

    Reads the committed transitions in order; every ``player.act``
    contributes its recorded ``player.decision`` draw value. Dead ticks
    produced no transition in the live run and produce none here either, so
    the system's one-consume-per-live-tick discipline stays aligned.
    """

    @staticmethod
    def actions_from(journal, controlled: str = "agent:0") -> list[int]:
        out: list[int] = []
        for t in journal.all():
            if t.operation != "player.act":
                continue
            # the player system writes only the controlled agent, so the
            # draws on this transition are its decisions (index 0 first)
            if t.random_draws:
                out.append(int(t.random_draws[0].value))
        return out

    @classmethod
    def channel_from(
        cls, journal, controlled: str = "agent:0"
    ) -> DecisionChannel:
        """A preloaded non-blocking channel that replays exactly the live
        stream (then idles forever, matching a run of the same length)."""
        return cls(actions=cls.actions_from(journal, controlled))


def attach_player_channel(
    sim, channel: DecisionChannel, controlled: str = "agent:0"
) -> DecisionChannel:
    """Wire a channel into a create_world-built game.

    The engine's registry instantiates systems no-arg (kernel/step discipline
    — no constructor plumbing through step()), so configuration happens on
    the live instances here. Raises if the world's roster has no
    PlayerAgentSystem (a research world cannot be "attached" — that is the
    ruleset boundary doing its job).
    """
    found = False
    for system in sim.systems:
        if isinstance(system, PlayerAgentSystem):
            system.channel = channel
            system.controlled = controlled
            found = True
    if not found:
        raise ValueError(
            "this world does not run PlayerAgentSystem — attach() only works "
            "on the game ruleset (player_life)"
        )
    return channel
