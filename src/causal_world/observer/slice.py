"""v0.12, stage 2b — the cell slice: a frame reads the map, not the world.

Stage 1 measured the cost of a frame: `StateView.from_state` built every
(entity, field) pair in the world — 1.57M pairs at 16k living agents,
~9.8M at 100k — and the server did it THREE times per frame, still had
to scan the state for every entity prefix, and asked `adults_in_cell`
(itself a scan over all agents) for each cell.

That is the wrong unit of computation for an interactive spatial world.
A frame needs the visible cells, their regions and a handful of
world-level counters. It does not need the other 99% of the pairs.

This module defines that unit:

* :class:`WorldIndex` — the few indexes a frame needs (entities by
  prefix, fields per cell/region, who lives in which cell, the dormant
  pool). Built once, then advanced by the COMMITTED writes of each tick,
  so its cost is O(writes), not O(state).
* :class:`CellSlice` — a read-only view over a set of cells and their
  regions. It IS a :class:`StateView` (same ``get``/``source``/
  ``tick_of``/``entities_with_prefix`` reads, same provenance), so every
  reader that already works on a view works on a slice unchanged.

What the slice deliberately does NOT do:

* it does not carry agents by default — the map draws cells, not
  people; the controlled agent is read directly by the session;
* it does not carry history — that is the archive's job (2e).

What it must never do: invent a value, drop a provenance link, or let a
reader believe the slice is the whole world when it is not. The
``complete`` flag says which one it is; the acceptance tests compare
every slice pair against the full view.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.situation import StateView


class _WriteView(NamedTuple):
    """The three fields ``apply_write`` reads, without a StateChange."""
    entity: str
    field: str
    new: Any


_AGENT = "agent:"
_CELL = "cell:"
_REGION = "region:"


def _prefix(entity: str) -> str:
    head, sep, _rest = entity.partition(":")
    return f"{head}:"


class WorldIndex:
    """The indexes a frame needs, maintained incrementally.

    Built once from the state (one pass over the pairs), then advanced
    by the committed writes of each tick. Every counter here answers a
    question the frame asks; nothing here is a second source of truth:
    a value is only ever read from ``WorldState`` and a provenance only
    from its own map.
    """

    def __init__(self) -> None:
        self._entities: dict[str, dict[str, None]] = {}
        self._fields: dict[str, set[str]] = {}
        self._cell: dict[str, str] = {}
        self._region: dict[str, str] = {}
        self._alive: dict[str, bool] = {}
        self._agents_by_cell: dict[str, set[str]] = {}
        self._alive_count = 0
        self._pool_total = 0
        self._pool_free = 0
        # cursor for an in-memory Journal (a SqliteArchive answers
        # at_tick() directly and needs no cursor)
        self._cursor = 0

    # -- construction --------------------------------------------------
    @classmethod
    def from_state(cls, state, journal=None) -> "WorldIndex":
        index = cls()
        for (entity, field_name), value in state.data.items():
            index._observe(entity, field_name, value)
        index._finish()
        if journal is not None and hasattr(journal, "_transitions"):
            index._cursor = len(journal._transitions)
        return index

    def _observe(self, entity: str, field_name: str, value) -> None:
        self._entities.setdefault(_prefix(entity), {})[entity] = None
        if _prefix(entity) == _AGENT:
            if field_name == "cell":
                self._cell[entity] = value
            elif field_name == "region":
                self._region[entity] = value
            elif field_name == "alive":
                self._alive[entity] = bool(value)
            return
        # cells and regions: remember which fields exist, so a slice can
        # read all of them without scanning the state for the names
        self._fields.setdefault(entity, set()).add(field_name)

    def _finish(self) -> None:
        self._alive_count = sum(1 for a in self._entities.get(_AGENT, {})
                                if self._alive.get(a))
        self._pool_total = sum(1 for a in self._entities.get(_AGENT, {})
                               if a in self._region)
        self._pool_free = sum(1 for a in self._entities.get(_AGENT, {})
                              if self._region.get(a) == "none")
        for agent, cell in self._cell.items():
            if self._alive.get(agent) and cell and cell != "none":
                self._agents_by_cell.setdefault(cell, set()).add(agent)

    # -- reads ---------------------------------------------------------
    def entities(self, prefix: str) -> tuple[str, ...]:
        return tuple(sorted(self._entities.get(prefix, {})))

    def fields_of(self, entity: str) -> tuple[str, ...]:
        return tuple(sorted(self._fields.get(entity, ())))

    def agents_in_cell(self, cell: str) -> tuple[str, ...]:
        return tuple(sorted(self._agents_by_cell.get(cell, ())))

    @property
    def alive_count(self) -> int:
        return self._alive_count

    @property
    def agent_count(self) -> int:
        return len(self._entities.get(_AGENT, ()))

    @property
    def pool_stats(self) -> tuple[int, int]:
        return (self._pool_total, self._pool_free)

    # -- maintenance ---------------------------------------------------
    def advance(self, journal, tick: int) -> None:
        """Apply the COMMITTED writes of ``tick`` — nothing else.

        Rejected proposals never touched the state, so applying their
        writes would make the index disagree with the world. The filter
        is the same one the engine's commit step used.
        """
        writes_at_tick = getattr(journal, "writes_at_tick", None)
        if callable(writes_at_tick):
            # SqliteArchive: the journal already holds the tick index, so
            # ask for the committed writes only. This skips rejected rows
            # and the reads/draws of every transition — the profile named
            # that deserialisation as the frame bottleneck (v0.12/2d).
            for _tid, entity, field_name, new in writes_at_tick(tick):
                self.apply_write(_WriteView(entity, field_name, new))
            return
        at_tick = getattr(journal, "at_tick", None)
        if callable(at_tick):
            transitions = at_tick(tick)
        else:  # in-memory Journal: take the tail since the last tick
            transitions = journal._transitions[self._cursor:]
            self._cursor = len(journal._transitions)
        for transition in transitions:
            if transition.status is not TransitionStatus.COMMITTED:
                continue
            for write in transition.writes:
                self.apply_write(write)

    def apply_write(self, write) -> None:
        entity = write.entity
        field_name = write.field
        prefix = _prefix(entity)
        self._entities.setdefault(prefix, {})[entity] = None
        if prefix != _AGENT:
            self._fields.setdefault(entity, set()).add(field_name)
            return
        if field_name == "cell":
            self._move(entity, write.new)
        elif field_name == "region":
            old = self._region.get(entity)
            self._region[entity] = write.new
            if old == "none" and write.new != "none":
                self._pool_free -= 1
            elif old != "none" and write.new == "none":
                self._pool_free += 1
            elif old is None:
                self._pool_total += 1
                if write.new == "none":
                    self._pool_free += 1
        elif field_name == "alive":
            was = self._alive.get(entity)
            now = bool(write.new)
            self._alive[entity] = now
            if now and not was:
                self._alive_count += 1
                cell = self._cell.get(entity)
                if cell and cell != "none":
                    self._agents_by_cell.setdefault(cell, set()).add(entity)
            elif was and not now:
                self._alive_count -= 1
                cell = self._cell.get(entity)
                if cell and cell != "none":
                    self._agents_by_cell.get(cell, set()).discard(entity)

    def _move(self, agent: str, cell: str | None) -> None:
        old = self._cell.get(agent)
        self._cell[agent] = cell
        if old and old != "none":
            self._agents_by_cell.get(old, set()).discard(agent)
        if self._alive.get(agent) and cell and cell != "none":
            self._agents_by_cell.setdefault(cell, set()).add(agent)


class CellSlice(StateView):
    """A read-only :class:`StateView` over a set of cells and regions.

    The slice holds exactly the pairs of the entities in scope — cells,
    their owner regions — and answers the world-level questions a frame
    asks (alive count, dormant pool, who lives in a cell) from the
    indexes, so its cost depends on the slice and the indexes, not on
    the number of entities in the world.
    """

    is_cell_slice = True

    def __init__(self, values: dict, index: WorldIndex,
                 cells: tuple[str, ...], regions: tuple[str, ...],
                 tick_of=None, complete: bool = True) -> None:
        super().__init__(values, ticks=False)
        self._index = index
        self.cells = tuple(cells)
        self.regions = tuple(regions)
        self.complete = bool(complete)
        self._tick_of_tid = tick_of

    # -- construction --------------------------------------------------
    @classmethod
    def from_state(cls, state, index: WorldIndex | None = None, *,
                   cells=None, tick_of=None) -> "CellSlice":
        """Read the slice of ``cells`` (all cells when ``cells`` is None)."""
        if index is None:
            index = WorldIndex.from_state(state)
        all_cells = index.entities(_CELL)
        all_regions = index.entities(_REGION)

        if cells is None:
            scope_cells = all_cells
            # a region-only world (v0.7) has no cells: the regions ARE
            # the scope; in a spatial world the scope is the cells and
            # only their owner regions
            scope_regions = all_regions if not all_cells else ()
        else:
            known = set(all_cells)
            scope_cells = tuple(c for c in cells if c in known)
            scope_regions = ()

        if scope_cells:
            owners = {state.get(cell, "region") for cell in scope_cells}
            scope_regions = tuple(r for r in all_regions if r in owners)

        values: dict = {}
        for entity in scope_cells + scope_regions:
            for field_name in index.fields_of(entity):
                values[(entity, field_name)] = (
                    state.get(entity, field_name),
                    state.get_source(entity, field_name),
                    None,  # the tick is resolved through the id, as live
                )

        complete = (
            set(scope_cells) == set(all_cells)
            and set(scope_regions) == set(all_regions)
        )
        return cls(values, index, scope_cells, scope_regions,
                   tick_of=tick_of, complete=complete)

    # -- the world-level questions a frame asks ------------------------
    def agents_in_cell(self, cell: str) -> tuple[str, ...]:
        """Alive agents of one cell — from the index, not from a scan."""
        return self._index.agents_in_cell(cell)

    def free_lives(self) -> int:
        """Dormant pool slots with no region (what `free_lives` counts)."""
        return self._index.pool_stats[1]

    def pool_stats(self) -> tuple[int, int]:
        """(agents that have a region field, of which free)."""
        return self._index.pool_stats

    @property
    def alive_agents(self) -> int:
        return self._index.alive_count

    @property
    def total_agents(self) -> int:
        return self._index.agent_count
