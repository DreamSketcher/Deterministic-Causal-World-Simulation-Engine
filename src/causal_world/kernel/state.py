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
    # Derived index: entities grouped by their id prefix ("agent:",
    # "cell:", ...). It is a CACHE of what `data` already says — a new
    # entity is added when its first pair is written — and it is never
    # part of equality or hashing. v0.12/2c: a snapshot used to rebuild
    # this by scanning every pair (1.57M at 16k living); now it copies
    # the groups, which are O(entities).
    _groups: dict[str, set[str]] = field(
        default_factory=dict, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if self.data and not self._groups:
            for entity, _field_name in self.data:
                self._remember(entity)

    def _remember(self, entity: str) -> None:
        head, sep, _rest = entity.partition(":")
        key = f"{head}:" if sep else entity
        self._groups.setdefault(key, set()).add(entity)

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
        return sorted({entity for group in self._groups.values()
                       for entity in group})

    def entities_with_prefix(self, prefix: str) -> list[str]:
        """Entities whose id starts with ``prefix``.

        A group prefix (``"agent:"``) is answered from the derived index;
        an arbitrary prefix falls back to a scan over the entities, never
        over the pairs.
        """
        if prefix.endswith(":"):
            return sorted(self._groups.get(prefix, ()))
        return sorted({entity for group in self._groups.values()
                       for entity in group if entity.startswith(prefix)})

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
        if key not in self.data:
            self._remember(entity)
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
