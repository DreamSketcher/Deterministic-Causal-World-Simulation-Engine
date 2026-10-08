"""The transition primitives.

* StateRead  — a recorded input: value + the transition that produced it.
* StateChange — a recorded write: entity, field, old, new.
* RandomDraw — a recorded addressable random realization.
* Transition — the atomic unit of world change (invariant I3).

A transition is atomic: either ALL of its writes are committed or NONE of
them are. ``old`` of every write must equal the snapshot value the
transition was computed against, otherwise the resolver rejects it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from causal_world.kernel.canonical import canonical_json, canonical_token


class TransitionStatus(Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class StateRead:
    entity: str
    field: str
    value: Any
    source_transition: int | None


@dataclass(frozen=True)
class StateChange:
    entity: str
    field: str
    old: Any
    new: Any


@dataclass(frozen=True)
class RandomDraw:
    purpose: str
    value: float
    threshold: float | None
    outcome: Any
    # Address of the draw (part of the rules of the world, spec §8/§9):
    entity: str = ""
    index: int = 0


@dataclass
class Transition:
    id: int | None
    tick: int
    system: str
    operation: str
    reads: list[StateRead] = field(default_factory=list)
    writes: list[StateChange] = field(default_factory=list)
    random_draws: list[RandomDraw] = field(default_factory=list)
    priority: int = 0
    status: TransitionStatus = TransitionStatus.PROPOSED
    reject_reason: str | None = None


# ----------------------------------------------------------------------
# Canonical serialization helpers (deterministic ordering and hashing)
# ----------------------------------------------------------------------

def proposal_sort_key(t: Transition) -> tuple[str, str, str]:
    """Content-based key used to assign transition ids.

    Ids are assigned from the SORTED set of all proposals of a tick, never
    from the order in which systems happened to run (spec §19, §30). This
    keeps ids — and every tie-break that uses them — independent of the
    system execution order.
    """
    writes = sorted(
        (w.entity, w.field, canonical_token(w.old), canonical_token(w.new))
        for w in t.writes
    )
    reads = sorted(
        (r.entity, r.field, canonical_token(r.value), r.source_transition)
        for r in t.reads
    )
    draws = sorted((d.purpose, d.entity, d.index) for d in t.random_draws)
    return (t.system, t.operation, canonical_json([writes, reads, draws]))


def transition_record(t: Transition) -> list[Any]:
    """Full canonical record of a transition, used for the journal hash."""
    return [
        t.id,
        t.tick,
        t.system,
        t.operation,
        t.priority,
        t.status.value,
        t.reject_reason,
        [
            [r.entity, r.field, canonical_token(r.value), r.source_transition]
            for r in t.reads
        ],
        [
            [w.entity, w.field, canonical_token(w.old), canonical_token(w.new)]
            for w in t.writes
        ],
        [
            [
                d.purpose,
                d.entity,
                d.index,
                canonical_token(d.value),
                canonical_token(d.threshold),
                canonical_token(d.outcome),
            ]
            for d in t.random_draws
        ],
    ]
