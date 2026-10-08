"""The full journal: simulation truth.

Every transition — committed AND rejected — is recorded here with no
significance thresholds (spec §33). Observability layers may filter; the
journal never does.
"""

from __future__ import annotations

from causal_world.kernel.canonical import canonical_json, sha256_hex
from causal_world.kernel.transition import (
    Transition,
    TransitionStatus,
    transition_record,
)


class Journal:
    def __init__(self) -> None:
        self._transitions: list[Transition] = []
        self._by_id: dict[int, Transition] = {}

    def record(self, transition: Transition) -> None:
        self._transitions.append(transition)
        if transition.id is not None:
            self._by_id[transition.id] = transition

    # ------------------------------------------------------------------
    def all(self) -> list[Transition]:
        return list(self._transitions)

    def by_id(self, transition_id: int) -> Transition:
        if transition_id not in self._by_id:
            raise KeyError(f"no transition T{transition_id} in journal")
        return self._by_id[transition_id]

    def has(self, transition_id: int) -> bool:
        return transition_id in self._by_id

    def committed(self) -> list[Transition]:
        return [t for t in self._transitions if t.status is TransitionStatus.COMMITTED]

    def rejected(self) -> list[Transition]:
        return [t for t in self._transitions if t.status is TransitionStatus.REJECTED]

    def at_tick(self, tick: int) -> list[Transition]:
        return [t for t in self._transitions if t.tick == tick]

    def __iter__(self):
        return iter(self._transitions)

    def __len__(self) -> int:
        return len(self._transitions)

    # ------------------------------------------------------------------
    def hash(self) -> str:
        """SHA-256 over the canonical serialization of ALL transitions."""
        ordered = sorted(
            self._transitions, key=lambda t: (t.id is None, t.id if t.id is not None else 0)
        )
        payload = canonical_json([transition_record(t) for t in ordered]).encode("utf-8")
        return sha256_hex(payload)
