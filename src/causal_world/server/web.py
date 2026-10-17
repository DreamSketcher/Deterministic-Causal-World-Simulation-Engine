"""v0.7 — the web surface: the living map and the analytical mode.

One process, one port:

* ``/`` and friends — the static client (the map + the analytical mode).
* ``/ws`` — the v0.6 WebSocket session protocol, unchanged.
* ``/analyze`` — a READ-ONLY analysis of the CURRENT world's archive.

The analysis endpoint is the second half of the concept: the map shows
WHAT the world is, the analytical mode shows WHY. It answers with three
kinds of thing, and the client renders them with different badges:

* **observed fact** — a committed transition (by id);
* **confirmed link** — a read-dependency that exists in the record;
* **hypothesis** — the player's own claim, kept separate from both.

Every number comes from the archive; the endpoint never computes a
narrative and never writes to the world. The LLM, when it arrives
(v0.7 of the roadmap), slots in HERE — as a rewriter of these facts,
never as their source.
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from causal_world.observer.budget import CausalBudget
from causal_world.observer.hypothesis import confirmed_links, facts_of
from causal_world.observer.journal import JournalView
from causal_world.observer.series import build_series
from causal_world.observer.goal import goals as goal_verdicts
from causal_world.observer.situation import StateView, history_from_journal, situations
from causal_world.query.index import QueryIndex

#: The static client, shipped inside the package.
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


def static_response(path: str) -> tuple[int, str, bytes]:
    """Serve one file of the static client.

    Returns (status, content-type, body). Unknown paths fall back to
    ``index.html`` so the client can own its own routes.
    """
    if path in ("", "/"):
        target = WEB_ROOT / "index.html"
    else:
        target = WEB_ROOT / path.lstrip("/")
        if not target.is_file() or WEB_ROOT not in target.resolve().parents:
            target = WEB_ROOT / "index.html"
    if not target.is_file():
        return 404, "text/plain; charset=utf-8", b"not found"
    ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript",):
        ctype += "; charset=utf-8"
    return 200, ctype, target.read_bytes()


def analyze(db_path: str, entity: str, field: str,
            *, cache_path: str | None = None) -> dict:
    """Analyse one (entity, field) of a recorded world.

    Read-only: the archive is opened ``mode=ro`` and the query index is
    a derived cache. The three epistemic levels are returned separately
    so the client cannot blur them.
    """
    if not Path(db_path).exists():
        return {"error": "no archive at " + db_path}
    cache = cache_path or (db_path + ".qidx")
    with JournalView(db_path) as view, QueryIndex(view, cache) as idx:
        idx.build()
        budget = CausalBudget(view).analyze(entity, field)

        writers = facts_of(view, field=field, entity=entity)
        links = []
        for fact in writers[:40]:
            for link in confirmed_links(idx, fact.transition_id, depth=1):
                links.append({
                    "source_id": link.source_id,
                    "reader_id": link.reader_id,
                    "depth": link.depth,
                    "entity": link.entity,
                    "field": link.field,
                })
        # keep only the links whose SOURCE wrote the queried field
        writer_ids = {f.transition_id for f in writers}
        links = [l for l in links if l["source_id"] in writer_ids]
        links.sort(key=lambda l: (l["depth"], l["source_id"], l["reader_id"]))

        series = build_series(view, total_agents=_agent_total(view))
        soil_series = [
            (tick, value) for tick, value in series.soil
        ]
        # The series of the ANALYSED entity itself: the soil of a cell,
        # not the average of the regions (v0.8).
        entity_series = _entity_series(view, entity, field)
        # The world speaks about itself (v0.8): the situation feed is
        # computed from the same archive, with the same evidence.
        alerts = situations(view)
        # The GOALS (v0.9): the same archive answers not only what is
        # wrong, but whether the problems were actually solved — the
        # verdict takes the people and the land into account.
        state = StateView.from_journal(view)
        cells = [
            c for c in state.entities_with_prefix("cell:")
            if (state.get(c, "land_active") is None
                or int(state.get(c, "land_active")))
        ]
        regions = state.entities_with_prefix("region:")
        history = history_from_journal(
            view, cells or regions,
            ["food_stock", "population", "soil_fertility", "births_total"],
        )
        verdicts = goal_verdicts(
            history, state, alerts, tick=state.max_tick(),
            window=state.max_tick(),
        )

        return {
            "entity": entity,
            "field": field,
            "budget": {
                "net": budget.net,
                "inflows": [
                    {"system": e.system, "operation": e.operation,
                     "total_delta": e.total_delta, "count": e.count}
                    for e in budget.inflows
                ],
                "outflows": [
                    {"system": e.system, "operation": e.operation,
                     "total_delta": e.total_delta, "count": e.count}
                    for e in budget.outflows
                ],
            },
            "facts": [
                {"level": "observed", "transition_id": f.transition_id,
                 "tick": f.tick, "system": f.system, "operation": f.operation}
                for f in writers[:40]
            ],
            "links": links[:60],
            "hypotheses": [],
            "situations": [a.to_dict() for a in alerts],
            "goals": [v.to_dict() for v in verdicts],
            "series": entity_series or soil_series[-60:],
            "world_soil": soil_series[-60:],
            "population": series.population[-60:],
        }


def _entity_series(view: JournalView, entity: str, field: str,
                    limit: int = 60) -> list:
    """The curve of one field of one entity, read from the record."""
    rows = view.query(
        "SELECT t.tick AS tick, json_extract(j.value,'$[3]') AS value "
        "FROM transitions t, json_each(t.payload,'$.writes') j "
        "WHERE t.status='COMMITTED' "
        "AND json_extract(j.value,'$[0]')=? "
        "AND json_extract(j.value,'$[1]')=? "
        "ORDER BY t.id",
        (entity, field),
    )
    if not rows:
        return []
    step = max(1, len(rows) // limit)
    picked = rows[::step][-limit:]
    out = []
    for row in picked:
        try:
            out.append((int(row["tick"]), round(float(row["value"]), 6)))
        except (TypeError, ValueError):
            continue
    return out


def _agent_total(view: JournalView) -> int:
    rows = view.query(
        "SELECT COUNT(DISTINCT json_extract(value, '$[0]')) AS n "
        "FROM transitions, json_each(transitions.payload, '$.writes') "
        "WHERE json_extract(value, '$[0]') LIKE 'agent:%'"
    )
    return int(rows[0]["n"]) if rows else 0


def make_analyze_handler(db_path_getter):
    """Build the ``/analyze`` handler for a WSGI-ish server.

    ``db_path_getter`` returns the archive of the world to analyse —
    the server passes the LIVE session's archive, so the analytical mode
    and the map talk about the SAME world.
    """

    def handle(query: dict) -> tuple[int, str, bytes]:
        entity = query.get("entity", ["region:0"])[0]
        field = query.get("field", ["soil_fertility"])[0]
        db_path = db_path_getter()
        if not db_path:
            return 404, "application/json", json.dumps(
                {"error": "no live world"}
            ).encode()
        payload = analyze(db_path, entity, field)
        return (200, "application/json",
                json.dumps(payload, default=str).encode("utf-8"))

    return handle
