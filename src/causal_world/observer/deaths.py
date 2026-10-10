"""Death-cause classification by backward causal reachability.

Ported from ``experiments/survival.py`` (v0.2+) into the observer layer,
where it belongs: it is a read-only interpretation of the journal. The
algorithm is unchanged so every past report remains reproducible:

* disease-reach:   some ``disease.infect`` transition is an ancestor
  reached through the deceased's OWN fields;
* starvation-reach: some ancestor transition reads this agent's
  ``hunger >= STARVATION_THRESHOLD``.

Restricting the walk to the agent's own chain keeps each label narrow
and unambiguous. The causal graph is acyclic, so the depth-bounded DFS
is exact.
"""

from __future__ import annotations

STARVATION_THRESHOLD = 0.75


class DeathClassifier:
    """Backward-DAG reachability over a deceased agent's own chain.

    Works over anything with ``by_id(tid)`` returning kernel transitions
    (a ``JournalView`` or an in-memory causal index). When the journal
    also exposes a read-only SQL ``query()`` (recorded archives), read
    summaries are cached from payload JSON, which is much faster than
    reconstructing full Transition objects for deep walks.
    """

    def __init__(self, journal) -> None:
        self._journal = journal
        self._node_cache: dict[int, list] = {}

    def _reads_of(self, tid: int) -> list[tuple[str, str, object, int | None]]:
        cached = self._node_cache.get(tid)
        if cached is not None:
            return cached
        summary: list[tuple[str, str, object, int | None]]
        query = getattr(self._journal, "query", None)
        if callable(query):
            import json

            rows = query("SELECT payload FROM transitions WHERE id=?", (tid,))
            if rows:
                payload = json.loads(rows[0]["payload"])
                summary = [(r[0], r[1], r[2], r[3]) for r in payload["reads"]]
            else:
                summary = []
        else:
            summary = [
                (r.entity, r.field, r.value, r.source_transition)
                for r in self._journal.by_id(tid).reads
            ]
        self._node_cache[tid] = summary
        return summary

    def _operation_of(self, tid: int) -> str:
        query = getattr(self._journal, "query", None)
        if callable(query):
            rows = query("SELECT operation FROM transitions WHERE id=?", (tid,))
            return rows[0]["operation"] if rows else ""
        return self._journal.by_id(tid).operation

    def classify(self, agent: str, death_tid: int, depth: int = 40) -> str:
        acute = self._operation_of(death_tid) == "disease.infect"

        disease = acute
        starvation = False
        stack: list[tuple[int, int]] = [(death_tid, 0)]
        seen = {death_tid}
        while stack and not (disease and starvation):
            current_id, d = stack.pop()
            if not disease and self._operation_of(current_id) == "disease.infect":
                disease = True
            for entity, r_field, value, source in self._reads_of(current_id):
                if entity != agent:
                    continue  # follow only the deceased's own chain
                if (
                    r_field == "hunger"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and value >= STARVATION_THRESHOLD
                ):
                    starvation = True
                if (
                    source is not None
                    and d < depth
                    and source not in seen
                ):
                    seen.add(source)
                    stack.append((source, d + 1))
        if acute:
            return "acute_infection"
        if disease and starvation:
            return "disease+starvation"
        if disease:
            return "disease"
        if starvation:
            return "starvation"
        return "other"

