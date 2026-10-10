"""WorldState: the single mutable source of truth.

``data`` maps ``(entity, field) -> value``.
``provenance`` maps ``(entity, field) -> transition_id | None``.

Invariant I1: WorldState changes only through committed transitions.
This is enforced mechanically: the state is *sealed*; only the commit step
of the simulation engine may open the seal (see ``WorldState.unsealed``).
Any other call to :meth:`WorldState.set` raises :class:`SealedStateError`.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from causal_world.kernel.canonical import sha256_hex, state_payload
from causal_world.kernel.errors import SealedStateError


@dataclass
class WorldState:
    tick: int = 0
    data: dict[tuple[str, str], Any] = field(default_factory=dict)
    provenance: dict[tuple[str, str], int | None] = field(default_factory=dict)

    # Invariant I1 guard. Not part of the logical state.
    _sealed: bool = field(default=True, repr=False, compare=False)

    # ------------------------------------------------------------------
    # Read API (safe everywhere)
    # ------------------------------------------------------------------
    def has(self, entity: str, field_name: str) -> bool:
        return (entity, field_name) in self.data

    def get(self, entity: str, field_name: str) -> Any:
        return self.data.get((entity, field_name))

    def get_source(self, entity: str, field_name: str) -> int | None:
        return self.provenance.get((entity, field_name))

    def entities(self) -> list[str]:
        return sorted({entity for entity, _ in self.data})

    def entities_with_prefix(self, prefix: str) -> list[str]:
        return sorted({entity for entity, _ in self.data if entity.startswith(prefix)})

    def fields_of(self, entity: str) -> list[str]:
        return sorted(f for (e, f) in self.data if e == entity)

    # ------------------------------------------------------------------
    # Write API (only valid while the commit step holds the seal open)
    # ------------------------------------------------------------------
    def set(self, entity: str, field_name: str, value: Any, transition_id: int) -> None:
        if self._sealed:
            raise SealedStateError(
                "WorldState can only be modified through committed transitions "
                "(invariant I1). Direct state.set() is forbidden."
            )
        key = (entity, field_name)
        self.data[key] = value
        # Provenance is updated simultaneously with the value (spec §16).
        self.provenance[key] = transition_id

    @contextmanager
    def unsealed(self) -> Iterator["WorldState"]:
        """Temporarily allow writes. Used exclusively by the commit step."""
        previous = self._sealed
        self._sealed = False
        try:
            yield self
        finally:
            self._sealed = previous

    # ------------------------------------------------------------------
    # Canonical hashing
    # ------------------------------------------------------------------
    def hash(self) -> str:
        """SHA-256 over canonical (tick, entities, fields, values)."""
        return sha256_hex(state_payload(self.tick, self.data))
