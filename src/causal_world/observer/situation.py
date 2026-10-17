"""v0.8 — the SITUATION layer: what the world is asking of the player.

The v0.7 loop gave the player the tools (observe, hypothesize, decree,
compare) but not the NEXT QUESTION. A researcher can measure anything; a
steward needs the world to tell them what is going wrong — and to tell
them so from the RECORD, not from a script.

An **alert** is therefore a state-derived fact with provenance:

* it names a scope (a cell of the spatial world, a region of the old
  one) and a kind (famine, thin soil, a birth stall, an ageing wave, an
  exhausted reserve of lives, an abandoned cell, a surplus);
* it carries a severity and the tick it has been true since;
* it cites the transition ids that produced the numbers it is based on,
  so the player can walk the evidence in the journal.

Nothing here is a narrative: the layer reads the committed writes of the
journal (or the live state of a running world), compares them with the
thresholds of the current law, and reports what the numbers say. A world
with no problem produces no alerts — the feed is never padded.

Read-only by construction: the archive projection is a SQL pass over the
committed transitions, the same journal the observer and query layers
already read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The thresholds of the situation layer. They are stated in the units of
#: the world (rations per person, soil points, ticks), not in adjectives.
FAMINE_FOOD_PC = 1.0      #: rations per person: below one, the cell eats
FOOD_EMPTY = 0.5         #: the stores of a cell, in rations per person
THIN_SOIL = 0.35          #: soil points: below this the land is spent
SURPLUS_FOOD_PC = 40.0    #: rations per person: more than this is waste
BIRTH_STALL_TICKS = 40    #: no birth for this long in a living cell
POOL_LOW_SHARE = 0.15     #: free reserve of lives below this share
#: v0.10: the same thresholds the birth law uses, so the LIMIT diagnosis
#: and the refusal of a conception cannot disagree about the world.
BIRTH_FOOD_PC_MIN = 3.0   #: below this the birth law refuses to conceive
#: The things that can stop growth. Stated as the world's own answer
#: ("what binds") instead of the old "capacity or food". The last two
#: exist because a birth stall is not always about land or stores: an
#: empty-of-adults cell cannot conceive, and an exhausted reserve of
#: lives cannot supply a child anywhere.
LIMIT_CAPACITY = "capacity"
LIMIT_FOOD = "food"
LIMIT_SOIL = "soil"
LIMIT_ADULTS = "adults"
LIMIT_POOL = "pool"
LIMIT_NONE = "none"

#: The reproduction age of the birth law (must match
#: ``SpatialBirthSystem.MATURITY``): the observer must not disagree with
#: the law about who can have a child.
BIRTH_MATURITY = 20


@dataclass(frozen=True)
class Alert:
    """One situation of the world, with its evidence."""

    kind: str
    scope: str
    severity: float
    since_tick: int
    message: str
    evidence: tuple = field(default_factory=tuple)
    #: Structured reading behind the alert (v0.10): e.g. the limit that
    #: binds a cell's growth and the numbers it was read from. The client
    #: may show it, but the message already states it in words.
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "scope": self.scope,
            "severity": round(float(self.severity), 4),
            "since_tick": self.since_tick,
            "message": self.message,
            "evidence": [dict(e) for e in self.evidence],
            "detail": dict(self.detail),
        }


# ----------------------------------------------------------------------
# A read-only view of the world's fields, with their provenance
# ----------------------------------------------------------------------
class FieldHistory:
    """The time series of a few fields — the memory of the situation layer.

    The situation layer has to answer "since when?", and the answer must
    be the same whether the world is running (the live path) or recorded
    (the archive path). Both build this structure:

    * the live path appends the current values of the world's fields
      once per tick (the server does it right after the step);
    * the archive path replays the committed writes of the journal.
    """

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], list] = {}

    def add(self, entity: str, field_name: str, tick: int, value) -> None:
        self._data.setdefault((entity, field_name), []).append((tick, value))

    def series(self, entity: str, field_name: str) -> list:
        return list(self._data.get((entity, field_name), ()))

    def last_true(self, entity: str, field_name: str, pred) -> int | None:
        """The last tick at which ``pred(value)`` held.

        ``None`` when the predicate never held — the caller then reports
        the current tick instead of inventing a starting point.
        """
        last = None
        for tick, value in self._data.get((entity, field_name), ()):
            try:
                ok = pred(value)
            except Exception:
                ok = False
            if ok:
                last = tick
        return last

    def value_at(self, entity: str, field_name: str, tick: int):
        """The last value of the field at or before ``tick``."""
        value = None
        for t, v in self._data.get((entity, field_name), ()):
            if t <= tick:
                value = v
            else:
                break
        return value


def history_from_journal(journal, entities: list[str], fields: list[str]) -> FieldHistory:
    """Build the history of a few fields from the committed writes."""
    history = FieldHistory()
    for field_name in fields:
        rows = _query(
            journal,
            "SELECT t.tick AS tick, json_extract(j.value,'$[0]') AS entity, "
            "       json_extract(j.value,'$[3]') AS value "
            "FROM transitions t, json_each(t.payload,'$.writes') j "
            "WHERE t.status='COMMITTED' "
            "AND json_extract(j.value,'$[1]')=? "
            "ORDER BY t.id",
            (field_name,),
        )
        for row in rows:
            if row["entity"] in entities:
                history.add(row["entity"], field_name, int(row["tick"]),
                            row["value"])
    return history


class StateView:
    """``(entity, field) -> (value, tid, tick)`` over a world.

    Two sources, one interface:

    * :meth:`from_journal` — the committed writes of an archive (the
      read-only path; the value is the one the world HAD, never a
      recomputation);
    * :meth:`from_state` — the live state of a running world (the
      interactive path; the value is the current one and the tid is the
      transition that last wrote it).
    """

    def __init__(self, values: dict, ticks: bool = True) -> None:
        self._values = values
        self._ticks = ticks
        self._tick_of_tid = None
        self.history: FieldHistory | None = None

    # -- construction --------------------------------------------------
    @classmethod
    def from_journal(cls, journal) -> "StateView":
        rows = _query(
            journal,
            "SELECT t.id AS tid, t.tick AS tick, "
            "       json_extract(j.value,'$[0]') AS entity, "
            "       json_extract(j.value,'$[1]') AS field, "
            "       json_extract(j.value,'$[3]') AS value "
            "FROM transitions t, json_each(t.payload, '$.writes') j "
            "WHERE t.status='COMMITTED' "
            "ORDER BY t.id",
        )
        values = {}
        for row in rows:
            values[(row["entity"], row["field"])] = (
                row["value"], row["tid"], row["tick"],
            )
        return cls(values, ticks=True)

    @classmethod
    def from_state(cls, state, tick_of=None) -> "StateView":
        """The live state of a running world.

        ``tick_of`` is an optional resolver ``tid -> tick`` (the archive
        can look a transition up by id); without it the alerts carry the
        transition ids but not their ticks.
        """
        values = {}
        for entity in state.entities():
            for name in state.fields_of(entity):
                values[(entity, name)] = (
                    state.get(entity, name),
                    state.get_source(entity, name),
                    None,
                )
        view = cls(values, ticks=False)
        view._tick_of_tid = tick_of
        return view

    # -- reads ---------------------------------------------------------
    def get(self, entity: str, field_name: str, default=None):
        entry = self._values.get((entity, field_name))
        return default if entry is None else entry[0]

    def source(self, entity: str, field_name: str):
        entry = self._values.get((entity, field_name))
        return None if entry is None else entry[1]

    def tick_of(self, entity: str, field_name: str):
        entry = self._values.get((entity, field_name))
        if entry is None:
            return None
        if self._ticks:
            return entry[2]
        if self._tick_of_tid is not None and entry[1] is not None:
            try:
                return self._tick_of_tid(entry[1])
            except Exception:
                return None
        return None

    def entities_with_prefix(self, prefix: str) -> list:
        return sorted({e for e, _ in self._values if e.startswith(prefix)})

    def max_tick(self) -> int:
        ticks = [v[2] for v in self._values.values() if v[2] is not None]
        return max(ticks) if ticks else 0


def _query(journal, sql: str, params: tuple = ()):
    query = getattr(journal, "query", None)
    if callable(query):
        return query(sql, params)
    return []


def project_state(journal) -> dict:
    """The committed state of the world as ``{(entity, field): (value, tid, tick)}``."""
    return StateView.from_journal(journal)._values


def _evidence(view: StateView, entity: str, field_name: str) -> list:
    value = view.get(entity, field_name)
    if value is None:
        return []
    tid = view.source(entity, field_name)
    tick = view.tick_of(entity, field_name)
    return [
        {
            "tid": tid,
            "tick": tick,
            "entity": entity,
            "field": field_name,
            "value": value,
        }
    ]


def _last_food_tick(journal, cell: str) -> int | None:
    """The last tick at which the cell's stores were not empty."""
    rows = _query(
        journal,
        "SELECT t.tick AS tick, json_extract(j.value,'$[3]') AS v "
        "FROM transitions t, json_each(t.payload, '$.writes') j "
        "WHERE t.status='COMMITTED' "
        "AND json_extract(j.value,'$[0]')=? "
        "AND json_extract(j.value,'$[1]')='food_stock' "
        "ORDER BY t.id",
        (cell,),
    )
    last = None
    for row in rows:
        if row["v"] is not None and float(row["v"]) > 0.0:
            last = int(row["tick"])
    return last


def _last_birth_tick(journal) -> dict:
    """The last birth tick per cell (from the birth transitions)."""
    rows = _query(
        journal,
        "SELECT t.tick AS tick, json_extract(j.value,'$[0]') AS entity "
        "FROM transitions t, json_each(t.payload, '$.writes') j "
        "WHERE t.status='COMMITTED' AND t.operation='agent.birth' "
        "AND json_extract(j.value,'$[1]')='cell' "
        "ORDER BY t.id",
    )
    last: dict = {}
    for row in rows:
        last[row["entity"]] = int(row["tick"])
    return last


# ----------------------------------------------------------------------
def _food_pc_at(history: FieldHistory, scope: str, tick: int):
    """The rations per person of a scope at a tick (from the history)."""
    food = history.value_at(scope, "food_stock", tick)
    pop = history.value_at(scope, "population", tick)
    if food is None or pop is None:
        return None
    try:
        return float(food) / max(int(pop), 1)
    except (TypeError, ValueError):
        return None


def _last_food_pc_tick(history: FieldHistory, scope: str, pred):
    """The last tick at which the scope's food per person satisfied pred."""
    last = None
    for tick, _food in history.series(scope, "food_stock"):
        value = _food_pc_at(history, scope, tick)
        if value is not None and pred(value):
            last = tick
    return last


def _is_active(view: "StateView", cell: str) -> bool:
    """A wild parcel is land, not a cell: it has no people and no alerts.

    Earlier spatial worlds have no ``land_active`` field: a parcel
    without it is an ordinary cell.
    """
    value = view.get(cell, "land_active")
    return True if value is None else bool(int(value))


def growth_limit(view: "StateView", scope: str,
                 tick: int | None = None) -> dict:
    """What stops a cell from growing, in the world's own numbers.

    The v0.8 alert said "capacity or food". The player deserves the
    actual answer, computed with the SAME arithmetic the birth law uses:

    * ``capacity`` — the head count has reached the capacity the law
      computes (``round(pop_base x (1+soil))`` — the law ROUNDS, so the
      observer rounds too, or it would call a cell "not full" while the
      law refuses to conceive in it);
    * ``food``     — the stores are below ``BIRTH_FOOD_PC_MIN`` per head;
    * ``soil``     — room and food are there, but the land is spent;
    * ``adults``   — nobody in the cell is old enough to conceive;
    * ``pool``     — the world has no free lives left to supply a child;
    * ``none``     — nothing in the model blocks a birth right now.

    Stated as a reading, not a prediction: it says which of the law's
    own gates is closed, not what will happen next.
    """
    population = int(view.get(scope, "population", 0) or 0)
    soil = float(view.get(scope, "soil_fertility", 0.0) or 0.0)
    food = float(view.get(scope, "food_stock", 0.0) or 0.0)
    pop_base = int(view.get(scope, "pop_base", 0) or 0)
    # the law's own arithmetic (SpatialBirthSystem.compute)
    capacity = int(round(pop_base * (1.0 + soil)))
    food_pc = food / max(population, 1)
    base = {"population": population, "capacity": capacity,
            "food_pc": round(food_pc, 2), "soil": round(soil, 3)}
    if capacity > 0 and population >= capacity:
        return {**base, "limit": LIMIT_CAPACITY}
    if population > 0 and food_pc <= BIRTH_FOOD_PC_MIN:
        return {**base, "limit": LIMIT_FOOD}
    if population > 0 and soil < THIN_SOIL:
        return {**base, "limit": LIMIT_SOIL}
    if tick is not None and population > 0:
        adults = adults_in_cell(view, scope, tick)
        base["adults"] = adults
        if adults == 0:
            return {**base, "limit": LIMIT_ADULTS}
        if free_lives(view) == 0:
            return {**base, "limit": LIMIT_POOL}
    return {**base, "limit": LIMIT_NONE}


def adults_in_cell(view: "StateView", scope: str, tick: int) -> int:
    """Alive agents in the cell older than the reproduction age."""
    count = 0
    for agent in view.entities_with_prefix("agent:"):
        if not view.get(agent, "alive"):
            continue
        if view.get(agent, "cell") != scope:
            continue
        birth_tick = view.get(agent, "birth_tick")
        if birth_tick is None:
            continue
        if tick - int(birth_tick) > BIRTH_MATURITY:
            count += 1
    return count


def free_lives(view: "StateView") -> int:
    """The world's unused reserve of lives (dormant slots with no region)."""
    free = 0
    for entity in view.entities_with_prefix("agent:"):
        if view.get(entity, "region") == "none":
            free += 1
    return free


#: How each limit is said in words.
LIMIT_WORDS = {
    LIMIT_CAPACITY: "ёмкость",
    LIMIT_FOOD: "еда",
    LIMIT_SOIL: "земля",
    LIMIT_ADULTS: "нет взрослых",
    LIMIT_POOL: "резерв жизней",
    LIMIT_NONE: "ничего",
}


def situations(
    journal_or_view,
    *,
    current_tick: int | None = None,
    journal=None,
    history: FieldHistory | None = None,
) -> list:
    """The alerts of the world, most urgent first.

    ``journal_or_view`` is either a journal (read-only path: the
    committed writes are projected) or a
    :class:`StateView` (live path). ``journal`` is optional and only
    used for the history-dependent readings (how long a cell has been
    empty, when its last birth was).

    Works for the spatial world (cells) and for the region worlds: the
    scope is a cell when the world has cells and a region otherwise.
    """
    if isinstance(journal_or_view, StateView):
        view = journal_or_view
    else:
        view = StateView.from_journal(journal_or_view)
        journal = journal_or_view
    if not view._values:
        return []
    tick = current_tick if current_tick is not None else view.max_tick()

    cells = [
        c for c in view.entities_with_prefix("cell:")
        if _is_active(view, c)
    ]
    regions = view.entities_with_prefix("region:")
    scopes = cells or regions

    if history is None:
        history = view.history
    if history is None and journal is not None:
        history = history_from_journal(
            journal, scopes, ["food_stock", "population", "soil_fertility"]
        )
    births = _last_birth_tick(journal) if (journal is not None and cells) else {}

    alerts: list[Alert] = []
    for scope in scopes:
        population = int(view.get(scope, "population", 0) or 0)
        soil = float(view.get(scope, "soil_fertility", 0.0) or 0.0)
        food = float(view.get(scope, "food_stock", 0.0) or 0.0)
        food_pc = food / max(population, 1)
        evidence = (
            _evidence(view, scope, "population")
            + _evidence(view, scope, "food_stock")
            + _evidence(view, scope, "soil_fertility")
        )

        if population == 0:
            since = view.get(scope, "empty_since")
            if since is None and journal is not None:
                since = _last_food_tick(journal, scope)
            alerts.append(
                Alert(
                    kind="abandoned",
                    scope=scope,
                    severity=1.0,
                    since_tick=int(since) if since is not None else tick,
                    message=(
                        f"{scope}: в клетке никого не осталось — земля "
                        f"ждёт новых людей (почва {soil:.2f})"
                    ),
                    evidence=tuple(evidence),
                )
            )
            continue

        if food_pc <= FOOD_EMPTY:
            since = None
            if history is not None:
                last_good = _last_food_pc_tick(
                    history, scope, lambda v: v > FOOD_EMPTY
                )
                since = None if last_good is None else last_good + 1
            if since is None and journal is not None:
                since = _last_food_tick(journal, scope)
            alerts.append(
                Alert(
                    kind="famine",
                    scope=scope,
                    severity=min(1.0, 0.6 + (FOOD_EMPTY - food_pc)),
                    since_tick=since if since is not None else tick,
                    message=(
                        f"{scope}: закрома опустела ({food:.0f} на "
                        f"{population} человек) — грозит голод"
                    ),
                    evidence=tuple(evidence),
                )
            )
        elif food_pc < FAMINE_FOOD_PC:
            since = tick
            if history is not None:
                last_good = _last_food_pc_tick(
                    history, scope, lambda v: v >= FAMINE_FOOD_PC
                )
                since = tick if last_good is None else last_good + 1
            alerts.append(
                Alert(
                    kind="hunger",
                    scope=scope,
                    severity=0.4,
                    since_tick=since,
                    message=(
                        f"{scope}: еды мало ({food_pc:.1f} на человека) — "
                        f"запасы тают"
                    ),
                    evidence=tuple(evidence),
                )
            )
        elif food_pc > SURPLUS_FOOD_PC:
            since = tick
            if history is not None:
                last_good = _last_food_pc_tick(
                    history, scope, lambda v: v <= SURPLUS_FOOD_PC
                )
                since = tick if last_good is None else last_good + 1
            alerts.append(
                Alert(
                    kind="surplus",
                    scope=scope,
                    severity=0.2,
                    since_tick=since,
                    message=(
                        f"{scope}: излишек еды ({food_pc:.0f} на человека) — "
                        f"есть чем поделиться или вложиться в землю"
                    ),
                    evidence=tuple(evidence),
                )
            )

        if soil < THIN_SOIL:
            since = tick
            if history is not None:
                last_good = history.last_true(
                    scope, "soil_fertility", lambda v: float(v) >= THIN_SOIL
                )
                since = tick if last_good is None else last_good + 1
            alerts.append(
                Alert(
                    kind="thin_soil",
                    scope=scope,
                    severity=min(1.0, (THIN_SOIL - soil) / THIN_SOIL + 0.3),
                    since_tick=since,
                    message=(
                        f"{scope}: почва истощена ({soil:.2f}) — урожай "
                        f"падает, нужен компост или залежь"
                    ),
                    evidence=tuple(evidence),
                )
            )

        # The birth stall: the cell keeps its own birth history, so the
        # alert works on the live path as well as on the archive.
        last_birth = view.get(scope, "last_birth_tick")
        if last_birth is None and births:
            last_birth = births.get(scope)
        if last_birth:
            stalled = tick - int(last_birth)
            if stalled > BIRTH_STALL_TICKS:
                limit = growth_limit(view, scope, tick)
                alerts.append(
                    Alert(
                        kind="birth_stall",
                        scope=scope,
                        severity=0.5,
                        since_tick=int(last_birth),
                        message=(
                            f"{scope}: рождений нет уже {stalled} тиков — "
                            f"предел: {LIMIT_WORDS.get(limit['limit'], limit['limit'])}"
                            + (
                                f" ({limit['population']} из "
                                f"{limit['capacity']:.0f})"
                                if limit["limit"] == LIMIT_CAPACITY else ""
                            )
                        ),
                        evidence=tuple(evidence),
                        detail=limit,
                    )
                )

    # --- the reserve of lives (the dormant pool) -------------------------
    free_pool = 0
    total_pool = 0
    for (entity, field_name), (value, _tid, _tick) in view._values.items():
        if not entity.startswith("agent:") or field_name != "region":
            continue
        total_pool += 1
        if value == "none":
            free_pool += 1
    if total_pool and free_pool / total_pool < POOL_LOW_SHARE:
        alerts.append(
            Alert(
                kind="pool_low",
                scope="world",
                severity=0.6,
                since_tick=tick,
                message=(
                    f"резерв жизней иссякает: свободно {free_pool} из "
                    f"{total_pool} — мир полон, новых не будет"
                ),
                evidence=(),
            )
        )

    alerts.sort(key=lambda a: (-a.severity, a.scope))
    return alerts


def to_dicts(alerts) -> list:
    return [a.to_dict() for a in alerts]
