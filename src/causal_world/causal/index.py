"""CausalIndex: transition history + provenance + reverse dependencies.

The core causal relation (spec §20):

    Transition A writes X, transition B reads X (as visible in B's
    snapshot)  =>  A -> B.

Edges are reconstructed purely from recorded reads — no manual
``causes=[...]`` lists exist anywhere (spec §13/I13).
"""

from __future__ import annotations

from collections import defaultdict

from causal_world.kernel.transition import Transition, TransitionStatus


class CausalIndex:
    def __init__(self) -> None:
        self.transitions: dict[int, Transition] = {}
        # (entity, field) -> latest committed transition id
        self.latest_writer: dict[tuple[str, str], int] = {}
        # (entity, field) -> committed transition ids, in commit order
        self.history: dict[tuple[str, str], list[int]] = defaultdict(list)
        # source transition id -> transitions that read values it wrote
        self.dependents: dict[int, set[int]] = defaultdict(set)

    # ------------------------------------------------------------------
    def add(self, t: Transition) -> None:
        if t.id is None:
            raise ValueError("cannot index a transition without an id")
        self.transitions[t.id] = t
        if t.status is not TransitionStatus.COMMITTED:
            # Rejected transitions are kept for lookup but never wrote
            # state, so they cannot be provenance sources (spec §17).
            return
        for w in t.writes:
            key = (w.entity, w.field)
            self.latest_writer[key] = t.id
            self.history[key].append(t.id)
        for r in t.reads:
            if r.source_transition is not None:
                self.dependents[r.source_transition].add(t.id)

    # ------------------------------------------------------------------
    def has(self, transition_id: int) -> bool:
        return transition_id in self.transitions

    def get(self, transition_id: int) -> Transition:
        if transition_id not in self.transitions:
            raise KeyError(f"no transition T{transition_id} in causal index")
        return self.transitions[transition_id]

    def writer_of(self, entity: str, field_name: str) -> int | None:
        return self.latest_writer.get((entity, field_name))

    def history_of(self, entity: str, field_name: str) -> list[int]:
        return list(self.history.get((entity, field_name), []))

    def dependents_of(self, transition_id: int) -> list[int]:
        return sorted(self.dependents.get(transition_id, set()))
