"""Observability adapter: strictly read-only access to a simulation.

Invariant I11: observability cannot modify simulation state. This adapter
holds no write capability — the WorldState is sealed, and everything here
goes through the journal / causal index / frozen snapshots.

An LLM narrative layer would plug in HERE, as an observer adapter over
``biography()`` / ``events()`` / traces. It is never a dependency of the
kernel or the simulation (spec §47).
"""

from __future__ import annotations

from causal_world.causal.trace import TraceNode, format_trace, trace_back
from causal_world.kernel.transition import Transition, TransitionStatus
from causal_world.observer.events import EventView, events_from_journal
from causal_world.observer.statistics import RunStatistics, compute_statistics


class Observability:
    """Read-only window over a finished or running simulation."""

    def __init__(self, simulation) -> None:
        self._simulation = simulation  # only ever read from

    # ------------------------------------------------------------------
    def events(self) -> list[EventView]:
        return events_from_journal(self._simulation.journal)

    def biography(self, entity: str) -> list[EventView]:
        return [e for e in self.events() if e.entity == entity]

    def rejected_actions(self, entity: str | None = None) -> list[Transition]:
        """Rejected transitions (spec §17) — recorded, state untouched.

        ``entity`` filters to transitions whose writes target that entity.
        """
        rejected = [
            t
            for t in self._simulation.journal
            if t.status is TransitionStatus.REJECTED
        ]
        if entity is not None:
            rejected = [
                t
                for t in rejected
                if any(w.entity == entity for w in t.writes)
            ]
        return sorted(rejected, key=lambda t: (t.id is None, t.id or 0))

    def trace(self, transition_id: int, depth: int = 8) -> TraceNode:
        return trace_back(self._simulation.index, transition_id, depth)

    def render_trace(self, transition_id: int, depth: int = 8) -> str:
        return format_trace(self.trace(transition_id, depth), depth)

    def statistics(self) -> RunStatistics:
        return compute_statistics(self._simulation)

    def state_hash(self) -> str:
        return self._simulation.state.hash()
