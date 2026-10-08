"""Snapshot: the immutable per-tick view every system computes from.

Invariant I4: all systems of one tick receive the same Snapshot.
Invariant I5: the Snapshot carries both data and provenance, as an
independent frozen view — it never reaches back into the live WorldState.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from causal_world.kernel.errors import MissingFieldError
from causal_world.kernel.state import WorldState


@dataclass(frozen=True)
class Snapshot:
    tick: int
    data: Mapping[tuple[str, str], Any]
    provenance: Mapping[tuple[str, str], int | None]

    @staticmethod
    def from_state(state: WorldState) -> "Snapshot":
        """Deep-copy the WorldState containers into a frozen view.

        Values are scalars (bool/int/float/str — enforced by the ruleset
        schema), so copying the containers yields full logical isolation:
        later commits to the WorldState can never mutate a Snapshot.
        """
        return Snapshot(
            tick=state.tick,
            data=MappingProxyType(dict(state.data)),
            provenance=MappingProxyType(dict(state.provenance)),
        )

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------
    def has(self, entity: str, field_name: str) -> bool:
        return (entity, field_name) in self.data

    def get(self, entity: str, field_name: str) -> Any:
        """Value or None when absent. Prefer require()/read via builders."""
        return self.data.get((entity, field_name))

    def require(self, entity: str, field_name: str) -> Any:
        if (entity, field_name) not in self.data:
            raise MissingFieldError(f"snapshot has no field {entity}.{field_name}")
        return self.data[(entity, field_name)]

    def get_source(self, entity: str, field_name: str) -> int | None:
        """Transition id that produced the value visible in THIS snapshot."""
        return self.provenance.get((entity, field_name))

    def entities(self) -> list[str]:
        return sorted({entity for entity, _ in self.data})

    def entities_with_prefix(self, prefix: str) -> list[str]:
        return sorted({entity for entity, _ in self.data if entity.startswith(prefix)})

    def fields_of(self, entity: str) -> list[str]:
        return sorted(f for (e, f) in self.data if e == entity)
