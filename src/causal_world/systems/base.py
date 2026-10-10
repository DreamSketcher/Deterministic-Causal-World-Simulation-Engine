"""System base class and the TransitionBuilder systems must use.

Systems NEVER touch the live WorldState. They receive the tick's immutable
Snapshot, read through it (recording every meaningful input as a
StateRead), draw addressable randomness (recording RandomDraws) and emit
proposed Transitions. Only the engine's commit step mutates state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import (
    RandomDraw,
    StateChange,
    StateRead,
    Transition,
)


class System(ABC):
    """A simulation system. ``name`` must be stable and unique."""

    name: str = "System"
    #: Used as a deterministic conflict tie-break (spec §14).
    priority: int = 0

    @abstractmethod
    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context: "SystemContext"
    ) -> list[Transition]:
        """Return proposed transitions for this tick.

        Must be a pure function of (snapshot, rng, context): no mutation of
        the WorldState, no dependence on call order or hidden mutable state.
        """


class TransitionBuilder:
    """Builds one transition, recording reads/writes/draws as they happen."""

    def __init__(
        self,
        tick: int,
        system: str,
        operation: str,
        snapshot: Snapshot,
        rng: RandomSource,
        priority: int = 0,
    ) -> None:
        self._tick = tick
        self._system = system
        self._operation = operation
        self._snapshot = snapshot
        self._rng = rng
        self._priority = priority
        self._reads: list[StateRead] = []
        self._writes: list[StateChange] = []
        self._draws: list[RandomDraw] = []

    def read(self, entity: str, field_name: str) -> Any:
        """Record a StateRead (value + provenance from the SNAPSHOT)."""
        value = self._snapshot.require(entity, field_name)
        source = self._snapshot.get_source(entity, field_name)
        self._reads.append(
            StateRead(
                entity=entity,
                field=field_name,
                value=value,
                source_transition=source,
            )
        )
        return value

    def write(self, entity: str, field_name: str, new: Any) -> Any:
        """Record a StateChange. ``old`` is taken from the snapshot."""
        old = self._snapshot.get(entity, field_name)
        self._writes.append(
            StateChange(entity=entity, field=field_name, old=old, new=new)
        )
        return new

    def draw(
        self,
        purpose: str,
        entity: str,
        index: int = 0,
        threshold: float | None = None,
    ) -> RandomDraw:
        """Addressable deterministic draw (spec §8).

        With ``threshold`` this models a probability event
        (outcome = roll < threshold); without it the draw is a continuous
        multiplier and outcome is the value itself (spec §10).
        """
        value = self._rng.draw(self._tick, entity, purpose, index)
        if threshold is None:
            outcome: Any = value
        else:
            outcome = value < threshold
        draw = RandomDraw(
            purpose=purpose,
            value=value,
            threshold=threshold,
            outcome=outcome,
            entity=entity,
            index=index,
        )
        self._draws.append(draw)
        return draw

    def build(self) -> Transition:
        return Transition(
            id=None,
            tick=self._tick,
            system=self._system,
            operation=self._operation,
            reads=self._reads,
            writes=self._writes,
            random_draws=self._draws,
            priority=self._priority,
        )


class SystemContext:
    """Per-tick context handed to systems."""

    def __init__(self, system: System, snapshot: Snapshot, rng: RandomSource) -> None:
        self.system = system
        self.snapshot = snapshot
        self.rng = rng

    def builder(self, operation: str, priority: int | None = None) -> TransitionBuilder:
        # Transition priority defaults to 0. The SYSTEM priority is a
        # separate resolver tie-break and must not leak into transitions.
        return TransitionBuilder(
            tick=self.snapshot.tick,
            system=self.system.name,
            operation=operation,
            snapshot=self.snapshot,
            rng=self.rng,
            priority=0 if priority is None else priority,
        )

    def entities(self, prefix: str) -> list[str]:
        return self.snapshot.entities_with_prefix(prefix)


def all_entities(snapshot: Snapshot, prefix: str) -> Iterable[str]:
    return snapshot.entities_with_prefix(prefix)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
