"""L1 — CausalBudget: who put how much into each variable, and took out.

Decomposes every recorded change of ``(entity, field)`` by its source
(``system.operation``), splitting inflows (positive deltas) from outflows
(negative ones). The journal is the only input; the world is never
touched (invariant I11).

Design notes / deviations from the v0.4 proposal:

* Only COMMITTED transitions count. The frozen kernel persists exactly
  two final statuses, COMMITTED and REJECTED; VALIDATED is a transient
  state that never reaches the archive, and rejected transitions never
  changed state (spec §17), so including them would double-count.
* Non-numeric writes (``region``, ``alive``, ``infected``, ...) have no
  delta and are excluded from budgets; they are still events (see
  ``observer.events``).
* The scan is indexed once per budget object; ``analyze`` /
  ``full_budget`` are then lookups, so asking many questions of one
  journal costs one pass.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Iterator

from causal_world.kernel.transition import Transition, TransitionStatus

_INF_TICK = 2**62


@dataclass(frozen=True)
class BudgetEntry:
    system: str
    operation: str
    total_delta: float
    count: int
    mean_delta: float


@dataclass(frozen=True)
class CausalBudgetReport:
    entity: str
    field: str
    tick_range: tuple[int, int]
    inflows: tuple[BudgetEntry, ...]  # positive deltas, |total| desc
    outflows: tuple[BudgetEntry, ...]  # negative deltas, |total| desc
    net: float

    def dominant_inflow(self) -> str | None:
        return self.inflows[0].operation if self.inflows else None

    def dominant_outflow(self) -> str | None:
        return self.outflows[0].operation if self.outflows else None


# ----------------------------------------------------------------------
# scanning
# ----------------------------------------------------------------------

class _Buckets:
    """(entity, field) -> (system, operation) -> [in_d, in_n, out_d, out_n]."""

    def __init__(self) -> None:
        self.data: dict[tuple[str, str], dict[tuple[str, str], list[float]]] = (
            defaultdict(lambda: defaultdict(lambda: [0.0, 0, 0.0, 0]))
        )

    def add(self, entity: str, field: str, system: str, operation: str,
            delta: float) -> None:
        b = self.data[(entity, field)][(system, operation)]
        if delta > 0:
            b[0] += delta
            b[1] += 1
        elif delta < 0:
            b[2] += delta
            b[3] += 1


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _scan_python(journal: Iterable[Transition], tick_start: int,
                 tick_end: int) -> _Buckets:
    buckets = _Buckets()
    for t in journal:
        if t.status is not TransitionStatus.COMMITTED:
            continue
        if t.tick < tick_start or t.tick > tick_end:
            continue
        for w in t.writes:
            if not (_is_number(w.old) and _is_number(w.new)):
                continue
            buckets.add(w.entity, w.field, t.system, t.operation,
                        w.new - w.old)
    return buckets


_SQL_SCAN = """
SELECT json_extract(w.value, '$[0]') AS entity,
       json_extract(w.value, '$[1]') AS field,
       t.system AS system,
       t.operation AS operation,
       SUM(CASE WHEN json_extract(w.value, '$[3]')
                 - json_extract(w.value, '$[2]') > 0
            THEN json_extract(w.value, '$[3]')
                 - json_extract(w.value, '$[2]') ELSE 0 END) AS in_delta,
       SUM(CASE WHEN json_extract(w.value, '$[3]')
                 - json_extract(w.value, '$[2]') > 0
            THEN 1 ELSE 0 END) AS in_count,
       SUM(CASE WHEN json_extract(w.value, '$[3]')
                 - json_extract(w.value, '$[2]') < 0
            THEN json_extract(w.value, '$[3]')
                 - json_extract(w.value, '$[2]') ELSE 0 END) AS out_delta,
       SUM(CASE WHEN json_extract(w.value, '$[3]')
                 - json_extract(w.value, '$[2]') < 0
            THEN 1 ELSE 0 END) AS out_count
FROM transitions t, json_each(t.payload, '$.writes') w
WHERE t.status = 'COMMITTED'
  AND t.tick BETWEEN ? AND ?
  AND json_type(w.value, '$[2]') IN ('integer', 'real')
  AND json_type(w.value, '$[3]') IN ('integer', 'real')
GROUP BY 1, 2, 3, 4
"""


def _scan_sql(view, tick_start: int, tick_end: int) -> _Buckets:
    buckets = _Buckets()
    rows = view.query(
        _SQL_SCAN,
        (int(tick_start), int(min(tick_end, _INF_TICK))),
    )
    for row in rows:
        key = (row["system"], row["operation"])
        field_buckets = buckets.data[(row["entity"], row["field"])]
        b = field_buckets[key]
        b[0] = float(row["in_delta"] or 0.0)
        b[1] = int(row["in_count"] or 0)
        b[2] = float(row["out_delta"] or 0.0)
        b[3] = int(row["out_count"] or 0)
    return buckets


# ----------------------------------------------------------------------
# the layer
# ----------------------------------------------------------------------

class CausalBudget:
    """Budget decomposition of all committed changes of (entity, field).

    ``journal`` is anything iterable over kernel ``Transition`` objects
    (an in-memory journal, a list) OR a ``JournalView`` over a recorded
    archive — the latter uses a single SQL aggregation pass, which keeps
    multi-million-transition archives queryable.
    """

    def __init__(self, journal) -> None:
        self._journal = journal
        self._buckets: _Buckets | None = None
        self._range: tuple[int, int] | None = None

    # -- index ---------------------------------------------------------
    def _ensure_index(self) -> None:
        if self._buckets is not None:
            return
        from causal_world.observer.journal import JournalView

        if isinstance(self._journal, JournalView):
            self._buckets = _scan_sql(self._journal, 0, _INF_TICK)
            self._range = self._journal.tick_range()
        else:
            self._buckets = _scan_python(self._journal, 0, _INF_TICK)
            ticks = [t.tick for t in self._touched()]
            self._range = (min(ticks), max(ticks)) if ticks else (0, 0)

    def _touched(self) -> Iterator[Transition]:
        journal = self._journal
        if hasattr(journal, "committed"):
            yield from journal.committed()
        else:
            for t in journal:
                if t.status is TransitionStatus.COMMITTED:
                    yield t

    def covered_ticks(self) -> tuple[int, int]:
        self._ensure_index()
        assert self._range is not None
        return self._range

    def fields_of(self, entity: str) -> list[str]:
        self._ensure_index()
        assert self._buckets is not None
        return sorted(f for (e, f) in self._buckets.data if e == entity)

    # -- reports ---------------------------------------------------------
    def analyze(self, entity: str, field: str, tick_start: int = 0,
                tick_end: float = math.inf) -> CausalBudgetReport:
        """Budget of one (entity, field) inside a tick window.

        With a window narrower than the indexed range the exact per-tick
        deltas are re-derived from the journal (a second filtered pass);
        full-range queries are pure lookups.
        """
        self._ensure_index()
        lo, hi = self._range or (0, 0)
        full_range = tick_start <= lo and tick_end >= hi
        if full_range:
            assert self._buckets is not None
            buckets = self._buckets
        else:
            end = int(tick_end) if not math.isinf(tick_end) else _INF_TICK
            from causal_world.observer.journal import JournalView

            if isinstance(self._journal, JournalView):
                buckets = _scan_sql(self._journal, int(tick_start), end)
            else:
                buckets = _scan_python(self._journal, int(tick_start), end)

        inflows: list[BudgetEntry] = []
        outflows: list[BudgetEntry] = []
        for (system, op), (in_d, in_n, out_d, out_n) in sorted(
                buckets.data.get((entity, field), {}).items()):
            if in_n:
                inflows.append(BudgetEntry(system, op, in_d, in_n,
                                           in_d / in_n))
            if out_n:
                outflows.append(BudgetEntry(system, op, out_d, out_n,
                                            out_d / out_n))
        inflows.sort(key=lambda e: abs(e.total_delta), reverse=True)
        outflows.sort(key=lambda e: abs(e.total_delta), reverse=True)
        net = sum(e.total_delta for e in inflows) + sum(
            e.total_delta for e in outflows)
        window = (int(tick_start),
                  int(tick_end) if not math.isinf(tick_end) else _INF_TICK)
        return CausalBudgetReport(
            entity=entity, field=field, tick_range=window,
            inflows=tuple(inflows), outflows=tuple(outflows), net=net)

    def full_budget(self, entity: str, tick_start: int = 0,
                    tick_end: float = math.inf
                    ) -> dict[str, CausalBudgetReport]:
        """Budgets of every numeric field of one entity."""
        return {
            field: self.analyze(entity, field, tick_start, tick_end)
            for field in self.fields_of(entity)
        }
