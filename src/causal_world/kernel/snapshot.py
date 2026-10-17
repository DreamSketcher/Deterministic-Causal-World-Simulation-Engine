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
        snapshot = Snapshot(
            tick=state.tick,
            data=MappingProxyType(dict(state.data)),
            provenance=MappingProxyType(dict(state.provenance)),
        )
        # The entity groups are already maintained by the state; copying
        # them is O(entities), not O(pairs). A state that predates the
        # index (or a hand-made one) falls back to a lazy build.
        groups = getattr(state, "_groups", None)
        if groups:
            object.__setattr__(
                snapshot, "_prefix_cache",
                {key: tuple(sorted(values))
                 for key, values in groups.items()},
            )
        return snapshot

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

    # ------------------------------------------------------------------
    # Entity lookups
    # ------------------------------------------------------------------
    # Systems ask for entities by prefix repeatedly within one tick: at
    # 16k living the profile measured 14 calls per tick, and each call
    # scanned all 1.57M (entity, field) pairs — 48% of the tick. The
    # snapshot is already a frozen copy, so the answer can be computed
    # ONCE per snapshot and reused: the mapping is a pure function of
    # `data`, and the returned lists are the same sorted lists a scan
    # would produce (pinned in tests/test_v012_equivalence.py).
    def _prefixes(self) -> dict[str, tuple[str, ...]]:
        cache = self.__dict__.get("_prefix_cache")
        if cache is not None:
            return cache
        grouped: dict[str, set[str]] = {}
        for entity, _field_name in self.data:
            head, sep, _rest = entity.partition(":")
            key = f"{head}:" if sep else entity
            grouped.setdefault(key, set()).add(entity)
        cache = {key: tuple(sorted(values))
                 for key, values in grouped.items()}
        object.__setattr__(self, "_prefix_cache", cache)
        return cache

    def entities(self) -> list[str]:
        cache = self._prefixes()
        return sorted({entity for values in cache.values()
                       for entity in values})

    def entities_with_prefix(self, prefix: str) -> list[str]:
        """Entities whose id starts with ``prefix``.

        A prefix that names a group (``"agent:"``) is answered from the
        per-snapshot index in O(1); an arbitrary prefix falls back to a
        scan, so the contract stays "startswith", not "equals a group".
        """
        if prefix.endswith(":"):
            return list(self._prefixes().get(prefix, ()))
        return sorted({entity for entity, _ in self.data
                       if entity.startswith(prefix)})

    def fields_of(self, entity: str) -> list[str]:
        return sorted(f for (e, f) in self.data if e == entity)
