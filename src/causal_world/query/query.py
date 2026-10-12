"""CausalQuery: composable, streaming queries over the QueryIndex.

Every filter method returns a NEW CausalQuery (immutable builder);
``execute()`` is a lazy iterator that hydrates kernel ``Transition``
objects page by page — a 16 GB archive never lands in memory, and
``itertools.islice`` gives early termination for free.

Naming follows the v0.5 spec exactly, with unambiguous aliases:

* ``caused_by(tid, depth)`` — transitions that READ what ``tid`` wrote
  (downstream dependents; alias ``dependents_of``);
* ``caused(tid, depth)``    — transitions whose writes were READ by
  ``tid`` (upstream ancestors; alias ``ancestors_of``).

Aggregations (``budget``, ``entropy``, ``delta_profile``, ``count``)
run entirely inside SQLite over the indexes — milliseconds after the
one-time build.
"""

from __future__ import annotations

import copy
import itertools
import math
from dataclasses import dataclass, field as dc_field

from causal_world.observer.budget import (
    BudgetEntry,
    CausalBudgetReport,
)

_PAGE = 500


# ----------------------------------------------------------------------
# results
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class EntropyResult:
    by: str
    distribution: tuple[tuple[object, int], ...]  # value -> count, desc
    entropy_bits: float
    total: int


@dataclass(frozen=True)
class DeltaProfileRow:
    system: str
    operation: str
    writes: int
    positive: int
    negative: int
    zero_or_nonnumeric: int
    total_delta: float
    mean_delta: float | None
    min_delta: float | None
    max_delta: float | None


@dataclass
class TraceResult:
    nodes: list = dc_field(default_factory=list)        # causal order
    depths: dict[int, int] = dc_field(default_factory=dict)
    truncated: bool = False


# ----------------------------------------------------------------------
# the builder
# ----------------------------------------------------------------------

class CausalQuery:
    """Immutable query builder over a QueryIndex."""

    def __init__(self, index) -> None:
        self.index = index
        self._filters: tuple = ()
        self._causal: tuple = ()  # (direction, tid, depth)

    # -- filters ---------------------------------------------------------
    def _clone(self, filters=None, causal=None) -> "CausalQuery":
        new = copy.copy(self)
        new._filters = self._filters + (filters or ())
        new._causal = self._causal + (causal or ())
        return new

    def system(self, name: str) -> "CausalQuery":
        return self._clone(filters=(("system", name),))

    def operation(self, name: str) -> "CausalQuery":
        return self._clone(filters=(("operation", name),))

    def entity(self, entity_id: str) -> "CausalQuery":
        """Transitions touching the entity as writer OR reader."""
        return self._clone(filters=(("entity", entity_id),))

    def entity_prefix(self, prefix: str) -> "CausalQuery":
        return self._clone(filters=(("entity_prefix", prefix),))

    def field(self, field_name: str) -> "CausalQuery":
        """Transitions WRITING the field (any entity)."""
        return self._clone(filters=(("field", field_name),))

    def writes_to(self, entity_id: str, field_name: str) -> "CausalQuery":
        """Transitions writing (entity, field) — the drill-down unit."""
        return self._clone(filters=(("writes_to", (entity_id, field_name)),))

    def ticks(self, start: int, end: int) -> "CausalQuery":
        return self._clone(filters=(("tick_range", (start, end)),))

    def committed_only(self) -> "CausalQuery":
        return self._clone(filters=(("status", "COMMITTED"),))

    def status(self, value: str) -> "CausalQuery":
        return self._clone(filters=(("status", value.upper()),))

    # -- causal closures ---------------------------------------------------
    def caused_by(self, transition_id: int, depth: int = 1) -> "CausalQuery":
        """Downstream: transitions that read what ``transition_id`` wrote."""
        return self._clone(causal=(("forward", transition_id, depth),))

    def dependents_of(self, transition_id: int, depth: int = 1) -> "CausalQuery":
        return self.caused_by(transition_id, depth)

    def caused(self, transition_id: int, depth: int = 1) -> "CausalQuery":
        """Upstream: transitions whose writes were read by this one."""
        return self._clone(causal=(("backward", transition_id, depth),))

    def ancestors_of(self, transition_id: int, depth: int = 1) -> "CausalQuery":
        return self.caused(transition_id, depth)

    # ------------------------------------------------------------------
    # SQL compilation
    # ------------------------------------------------------------------
    def _compile(self) -> tuple[str, list]:
        filter_params: list = []
        causal_params: list = []
        where = ["1=1"]
        ctes: list[str] = []
        closure_sets: list[str] = []

        for key, value in self._filters:
            if key == "system":
                where.append("t.system = ?")
                filter_params.append(value)
            elif key == "operation":
                where.append("t.operation = ?")
                filter_params.append(value)
            elif key == "status":
                where.append("t.status = ?")
                filter_params.append(value)
            elif key == "tick_range":
                where.append("t.tick BETWEEN ? AND ?")
                filter_params.extend(value)
            elif key == "entity":
                where.append(
                    "EXISTS (SELECT 1 FROM idx_entity e "
                    "WHERE e.tid = t.id AND e.entity = ?)")
                filter_params.append(value)
            elif key == "entity_prefix":
                where.append(
                    "EXISTS (SELECT 1 FROM idx_entity e "
                    "WHERE e.tid = t.id AND e.entity LIKE ? || '%')")
                filter_params.append(value)
            elif key == "field":
                where.append(
                    "EXISTS (SELECT 1 FROM idx_writes w "
                    "WHERE w.tid = t.id AND w.field = ?)")
                filter_params.append(value)
            elif key == "writes_to":
                entity_id, field_name = value
                where.append(
                    "EXISTS (SELECT 1 FROM idx_writes w "
                    "WHERE w.tid = t.id AND w.entity = ? AND w.field = ?)")
                filter_params.extend([entity_id, field_name])

        for i, (direction, tid, depth) in enumerate(self._causal):
            name = f"closure{i}"
            if direction == "forward":
                step = ("SELECT r.reader_tid, c.d + 1 FROM idx_reads r "
                        f"JOIN {name} c ON r.source_tid = c.x WHERE c.d < ?")
            else:
                step = ("SELECT r.source_tid, c.d + 1 FROM idx_reads r "
                        f"JOIN {name} c ON r.reader_tid = c.x WHERE c.d < ?")
            # CTE text order: anchor param (tid) then recursive param (depth)
            ctes.append(
                f"{name}(x, d) AS (SELECT ?, 0 UNION {step})")
            causal_params.extend([tid, depth])
            closure_sets.append(f"t.id IN (SELECT x FROM {name} WHERE d > 0)")

        where.extend(closure_sets)
        # CTEs are prepended to the SQL text, so their params come first.
        params = causal_params + filter_params
        # t.id is the archive PRIMARY KEY (unique per row) and every filter
        # is EXISTS/IN (non-fan-out), so no DISTINCT is needed. Omitting it
        # lets SQLite flatten the keyset wrapper and push ORDER BY tid
        # LIMIT down onto the PK scan — first page in milliseconds instead
        # of materializing the whole id set.
        sql = "SELECT t.id AS tid FROM arch.transitions t WHERE " + \
              " AND ".join(where)
        if ctes:
            sql = "WITH RECURSIVE " + ", ".join(ctes) + " " + sql
        return sql, params

    # ------------------------------------------------------------------
    # execution (lazy)
    # ------------------------------------------------------------------
    def _tid_pages(self):
        """Keyset-paginated tid stream in id order."""
        base_sql, params = self._compile()
        cursor_id = 0
        while True:
            sql = (f"SELECT tid FROM ({base_sql}) "
                   f"WHERE tid > ? ORDER BY tid LIMIT {_PAGE}")
            rows = self.index.sql(sql, tuple(params) + (cursor_id,)).fetchall()
            if not rows:
                return
            for r in rows:
                yield r["tid"]
            cursor_id = rows[-1]["tid"]

    def execute(self):
        """Lazy iterator of kernel Transitions, id order."""
        for page in self._pages():
            for t in page:
                yield t

    def _pages(self):
        batch: list[int] = []
        for tid in self._tid_pages():
            batch.append(tid)
            if len(batch) >= _PAGE:
                yield self.index.hydrate(batch)
                batch = []
        if batch:
            yield self.index.hydrate(batch)

    def tids(self):
        """Lazy iterator of matching transition ids (no hydration)."""
        return self._tid_pages()

    def first(self):
        return next(self.execute(), None)

    def list(self, limit: int = 1000) -> list:
        return list(itertools.islice(self.execute(), limit))

    def count(self) -> int:
        base_sql, params = self._compile()
        row = self.index.sql(
            f"SELECT COUNT(*) AS n FROM ({base_sql})", tuple(params)
        ).fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------
    # aggregation: budget (parity with observer L1, but from the index)
    # ------------------------------------------------------------------
    def budget(self, entity: str, field_name: str,
               tick_start: int = 0,
               tick_end: int = 2**62) -> CausalBudgetReport:
        rows = self.index.sql(
            """
            SELECT t.system AS system, t.operation AS operation,
                   SUM(CASE WHEN w.delta > 0 THEN w.delta ELSE 0 END) AS in_d,
                   SUM(CASE WHEN w.delta > 0 THEN 1 ELSE 0 END)       AS in_n,
                   SUM(CASE WHEN w.delta < 0 THEN w.delta ELSE 0 END) AS out_d,
                   SUM(CASE WHEN w.delta < 0 THEN 1 ELSE 0 END)       AS out_n
            FROM idx_writes w
            JOIN arch.transitions t ON t.id = w.tid
            WHERE w.entity = ? AND w.field = ? AND w.delta IS NOT NULL
              AND t.status = 'COMMITTED' AND t.tick BETWEEN ? AND ?
            GROUP BY 1, 2
            """, (entity, field_name, tick_start, tick_end)).fetchall()
        inflows, outflows = [], []
        for r in rows:
            if r["in_n"]:
                inflows.append(BudgetEntry(
                    r["system"], r["operation"], float(r["in_d"]),
                    int(r["in_n"]), float(r["in_d"]) / int(r["in_n"])))
            if r["out_n"]:
                outflows.append(BudgetEntry(
                    r["system"], r["operation"], float(r["out_d"]),
                    int(r["out_n"]), float(r["out_d"]) / int(r["out_n"])))
        inflows.sort(key=lambda e: abs(e.total_delta), reverse=True)
        outflows.sort(key=lambda e: abs(e.total_delta), reverse=True)
        net = (sum(e.total_delta for e in inflows)
               + sum(e.total_delta for e in outflows))
        return CausalBudgetReport(
            entity=entity, field=field_name,
            tick_range=(tick_start, tick_end),
            inflows=tuple(inflows), outflows=tuple(outflows), net=net)

    # ------------------------------------------------------------------
    # aggregation: write-level drill-down (the v0.4 signal, generalized)
    # ------------------------------------------------------------------
    def delta_profile(self, entity: str | None = None,
                      field_name: str | None = None,
                      tick_start: int = 0,
                      tick_end: int = 2**62) -> list[DeltaProfileRow]:
        """Per-(system, operation) delta statistics of matching writes.

        This is how the engine tells `harvest` in CompostAgricultureSystem
        from `harvest` in AgricultureSystem: by the ACTUAL deltas, not by
        names.
        """
        where = ["w.delta IS NOT NULL", "t.status = 'COMMITTED'",
                 "t.tick BETWEEN ? AND ?"]
        params: list = [tick_start, tick_end]
        if entity is not None:
            where.append("w.entity = ?")
            params.append(entity)
        if field_name is not None:
            where.append("w.field = ?")
            params.append(field_name)
        rows = self.index.sql(
            f"""
            SELECT t.system AS system, t.operation AS operation,
                   COUNT(*) AS n,
                   SUM(CASE WHEN w.delta > 0 THEN 1 ELSE 0 END) AS pos,
                   SUM(CASE WHEN w.delta < 0 THEN 1 ELSE 0 END) AS neg,
                   SUM(CASE WHEN w.delta = 0 THEN 1 ELSE 0 END) AS zero,
                   SUM(w.delta) AS total, AVG(w.delta) AS mean,
                   MIN(w.delta) AS mn, MAX(w.delta) AS mx
            FROM idx_writes w
            JOIN arch.transitions t ON t.id = w.tid
            WHERE {' AND '.join(where)}
            GROUP BY 1, 2 ORDER BY ABS(SUM(w.delta)) DESC
            """, tuple(params)).fetchall()
        out = []
        for r in rows:
            nonnum = int(r["n"]) - int(r["pos"]) - int(r["neg"]) - int(r["zero"])
            out.append(DeltaProfileRow(
                system=r["system"], operation=r["operation"],
                writes=int(r["n"]), positive=int(r["pos"]),
                negative=int(r["neg"]),
                zero_or_nonnumeric=int(r["zero"]) + nonnum,
                total_delta=float(r["total"] or 0.0),
                mean_delta=float(r["mean"]) if r["mean"] is not None else None,
                min_delta=float(r["mn"]) if r["mn"] is not None else None,
                max_delta=float(r["mx"]) if r["mx"] is not None else None))
        return out

    # ------------------------------------------------------------------
    # aggregation: entropy
    # ------------------------------------------------------------------
    def entropy(self, by: str = "system",
                actual_changes_only: bool = False) -> EntropyResult:
        """Shannon entropy (bits) of a distribution over matching rows.

        ``by``: "system" | "operation" | "write:<field>" (distribution of
        written values; with ``actual_changes_only`` only rows where
        old is not NULL and old != new count — migration semantics).
        """
        base_sql, params = self._compile()
        if by.startswith("write:"):
            fld = by.split(":", 1)[1]
            change = (" AND w.old IS NOT NULL AND w.new IS NOT NULL "
                      " AND w.old != w.new") if actual_changes_only else ""
            rows = self.index.sql(
                f"""
                SELECT w.new AS k, COUNT(*) AS n
                FROM idx_writes w
                WHERE w.field = ?{change}
                  AND w.tid IN ({base_sql})
                GROUP BY 1 ORDER BY n DESC, k
                """, (fld, *params)).fetchall()
        elif by in ("system", "operation"):
            rows = self.index.sql(
                f"""
                SELECT t.{by} AS k, COUNT(*) AS n
                FROM arch.transitions t
                WHERE t.id IN ({base_sql})
                GROUP BY 1 ORDER BY n DESC, k
                """, tuple(params)).fetchall()
        else:
            raise ValueError(f"unknown entropy grouping: {by!r}")
        dist = tuple((r["k"], int(r["n"])) for r in rows)
        total = sum(n for _, n in dist)
        entropy = 0.0
        if total:
            for _, n in dist:
                p = n / total
                entropy -= p * math.log2(p)
        return EntropyResult(by=by, distribution=dist,
                             entropy_bits=entropy, total=total)

    # ------------------------------------------------------------------
    # traces
    # ------------------------------------------------------------------
    def trace(self, transition_id: int, direction: str = "backward",
              depth: int = 20, max_nodes: int = 50_000) -> TraceResult:
        """Level-by-level BFS trace through idx_reads.

        ``backward``: causes first (what led to this); ``forward``:
        consequences (what depends on this). Forward traces can explode
        in densely coupled worlds — ``max_nodes`` truncates and sets
        ``result.truncated``.
        """
        if direction not in ("backward", "forward"):
            raise ValueError("direction must be 'backward' or 'forward'")
        depths = {transition_id: 0}
        frontier = [transition_id]
        truncated = False
        for level in range(1, depth + 1):
            if not frontier:
                break
            marks = ",".join("?" for _ in frontier)
            if direction == "backward":
                col_from, col_to = "reader_tid", "source_tid"
            else:
                col_from, col_to = "source_tid", "reader_tid"
            rows = self.index.sql(
                f"SELECT DISTINCT {col_to} AS nxt FROM idx_reads "
                f"WHERE {col_from} IN ({marks})", tuple(frontier)).fetchall()
            nxt = [r["nxt"] for r in rows if r["nxt"] not in depths]
            if len(depths) + len(nxt) > max_nodes:
                nxt = nxt[:max(0, max_nodes - len(depths))]
                truncated = True
            for tid in nxt:
                depths[tid] = level
            frontier = nxt
            if truncated:
                break
        order = sorted(depths, key=lambda tid: (
            -depths[tid] if direction == "backward" else depths[tid], tid))
        nodes = self.index.hydrate(order)
        by_id = {t.id: t for t in nodes}
        return TraceResult(
            nodes=[by_id[tid] for tid in order if tid in by_id],
            depths=depths, truncated=truncated)

    # ------------------------------------------------------------------
    # entity timeline
    # ------------------------------------------------------------------
    def timeline(self, entity_id: str, limit: int = 1000) -> list:
        """Everything that ever touched one entity, in tick order."""
        rows = self.index.sql(
            "SELECT tid FROM idx_entity WHERE entity = ? "
            "ORDER BY tick, tid LIMIT ?", (entity_id, limit)).fetchall()
        return self.index.hydrate([r["tid"] for r in rows])
