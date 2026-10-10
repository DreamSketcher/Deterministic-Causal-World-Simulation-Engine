"""The full journal: simulation truth.

Every transition — committed AND rejected — is recorded here with no
significance thresholds (spec §33). Observability layers may filter; the
journal never does.
"""

from __future__ import annotations

import hashlib

from causal_world.kernel.canonical import canonical_json
from causal_world.kernel.transition import (
    Transition,
    TransitionStatus,
    transition_record,
)


class Journal:
    def __init__(self) -> None:
        self._transitions: list[Transition] = []
        self._by_id: dict[int, Transition] = {}
        self._hasher = hashlib.sha256()
        self._last_id: int | None = None
        self._committed = 0
        self._rejected = 0
        self._last_committed_id: int | None = None

    def record(self, transition: Transition) -> None:
        if transition.id is None:
            raise ValueError("cannot record a transition without an id")
        if self._last_id is not None and transition.id <= self._last_id:
            raise ValueError(
                f"journal records must be ascending by id "
                f"(got T{transition.id} after T{self._last_id})"
            )
        self._last_id = transition.id
        self._transitions.append(transition)
        self._by_id[transition.id] = transition
        # Canonical journal hash: sha256 over newline-joined canonical
        # records in id order, updated incrementally. The disk-backed
        # SqliteArchive uses the identical definition, so memory and
        # archived runs of the same world hash the same.
        self._hasher.update(
            (canonical_json(transition_record(transition)) + "\n").encode("utf-8")
        )
        if transition.status is TransitionStatus.COMMITTED:
            self._committed += 1
            self._last_committed_id = transition.id
        elif transition.status is TransitionStatus.REJECTED:
            self._rejected += 1

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

    def counts(self) -> tuple[int, int, int]:
        return len(self._transitions), self._committed, self._rejected

    def iter_operations(self, operations):
        """Stream committed transitions of the given operations, id order."""
        ops = set(operations)
        for t in self._transitions:
            if t.status is TransitionStatus.COMMITTED and t.operation in ops:
                yield t

    def last_committed_id(self) -> int | None:
        return self._last_committed_id

    def __iter__(self):
        return iter(self._transitions)

    def __len__(self) -> int:
        return len(self._transitions)

    # ------------------------------------------------------------------
    def hash(self) -> str:
        """SHA-256 over the canonical serialization of ALL transitions."""
        return self._hasher.copy().hexdigest()
