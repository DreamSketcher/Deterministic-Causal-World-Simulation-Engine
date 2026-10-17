"""v0.9 — SITUATIONS AS GOALS, with an honest completion test.

The v0.8 situation layer tells the player what is wrong. It does not tell
them when a problem is *solved* — and the naive answer ("the alert went
away") is a trap the whole design of this module exists to avoid:

    A famine disappears when everybody starves to death.

Formally the threshold is no longer violated; strategically the player
has lost the cell. So the completion of a goal is decided by three
things, never by the signal alone:

1. **the signal** — is the original problem still present?
2. **the affected system** — what happened to the people and the land
   the goal was about (population and soil at opening vs at closing)?
3. **related problems** — did the problem move to a neighbour, or was
   it replaced by another critical situation that did not exist when the
   goal was opened?

The verdicts are therefore explicit and few:

* ``active``              — the signal is still there;
* ``resolved``            — the signal is gone and the system is intact;
* ``resolved_with_cost``  — the signal is gone, but the system paid for
  it (a fifth to a half of the people, or soil still under the line);
* ``collapsed``           — the signal is gone because the system is
  gone (the cell emptied, or half its people died);
* ``transferred``         — the signal left this scope but appeared in a
  neighbouring one after the goal was opened, and the goal's own system
  did not pay for it.

Nothing here is a narrative or an inference about causes: every number
is read from the recorded fields, and the evidence is the transition ids
the situation layer already cites. The module works on a
:class:`~causal_world.observer.situation.FieldHistory` (live or archived
alike), so the same code answers the same question in the game and in
the lab.

The thresholds are stated in world units and are deliberately boring:
they are a *contract*, not a drama engine. A player who wants a stricter
definition of success can read them here and argue with them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from causal_world.observer.situation import (
    BIRTH_STALL_TICKS,
    FOOD_EMPTY,
    THIN_SOIL,
    Alert,
    FieldHistory,
    StateView,
)

#: A problem counts as closed only after this many consecutive ticks
#: without the signal: one good tick is noise, not a solution.
RECOVERY_TICKS = 5

#: Losing this share of the opening population is a collapse, whatever
#: the signal says. (Half the people is not "a cost", it is a disaster.)
COLLAPSE_POP_SHARE = 0.5
#: Below this share the goal was met, but at a visible price.
COST_POP_SHARE = 0.8
#: How long after the signal disappears the system is still watched.
#: A famine that ends today can still kill this week: a verdict taken at
#: the closing tick would call a doomed cell "resolved". Twenty ticks is
#: long enough to see starvation deaths and soil relapse, short enough to
#: stay inside one player's attention span.
SETTLE_TICKS = 20

#: How recent a closed goal must still be shown in the live feed.
RECENT_WINDOW = 120

#: Which signals open which goal.
GOAL_OF_SIGNAL = {
    "famine": "feed",
    "hunger": "feed",
    "thin_soil": "restore_soil",
    "abandoned": "resettle",
    "birth_stall": "renew",
}
#: Episodes the history can reconstruct on its own (the birth stall is a
#: property of the cell's OWN counter ``births_total``, so it can).
HISTORY_GOALS = ("feed", "restore_soil", "resettle", "renew")
#: Which signals are "the same problem" when it moves to a neighbour.
SIGNAL_FAMILY = {
    "feed": {"famine", "hunger"},
    "restore_soil": {"thin_soil"},
    "resettle": {"abandoned"},
    "renew": {"birth_stall"},
}
#: Signals that are an outcome of the same system, not a coincidence.
CRITICAL = {"famine", "hunger", "thin_soil", "abandoned"}


@dataclass(frozen=True)
class Goal:
    """One episode of a problem in one scope."""

    kind: str                 # feed | restore_soil | resettle | renew
    scope: str
    signal: str               # the alert kind that opened it
    opened_tick: int
    closed_tick: int | None = None

    @property
    def duration(self) -> int | None:
        return None if self.closed_tick is None else self.closed_tick - self.opened_tick

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "scope": self.scope,
            "signal": self.signal,
            "opened_tick": self.opened_tick,
            "closed_tick": self.closed_tick,
            "duration": self.duration,
        }


@dataclass
class Verdict:
    """The honest completion answer for one goal."""

    goal: Goal
    status: str               # active | settling | resolved |
                              # resolved_with_cost | collapsed | transferred
    reason: str
    population_open: int = 0
    population_close: int = 0
    soil_open: float = 0.0
    soil_close: float = 0.0
    related: tuple[str, ...] = ()
    evidence: tuple = field(default_factory=tuple)
    births_open: int = 0
    births_close: int = 0
    #: ``established`` — the verdict is a rule over recorded numbers;
    #: ``hypothesis`` — the verdict is a plausible reading that the
    #: records do NOT prove (``transferred``: proximity and time order
    #: are not causality). The client must not draw them alike.
    confidence: str = "established"

    @property
    def solved(self) -> bool:
        return self.status in ("resolved", "resolved_with_cost")

    def to_dict(self) -> dict:
        return {
            **self.goal.to_dict(),
            "status": self.status,
            "solved": self.solved,
            "reason": self.reason,
            "population_open": self.population_open,
            "population_close": self.population_close,
            "soil_open": round(float(self.soil_open), 4),
            "soil_close": round(float(self.soil_close), 4),
            "births_open": self.births_open,
            "births_close": self.births_close,
            "related": list(self.related),
            "evidence": [dict(e) for e in self.evidence],
            "confidence": self.confidence,
        }


# ----------------------------------------------------------------------
# Reading episodes from the world's own series
# ----------------------------------------------------------------------
def _bad_signal(kind: str, population: int, food_pc: float, soil: float) -> bool:
    if kind == "feed":
        # An empty cell cannot starve: "no people" is the abandoned
        # goal, and a famine episode there would be noise.
        return population > 0 and food_pc <= FOOD_EMPTY
    if kind == "restore_soil":
        return soil < THIN_SOIL
    if kind == "resettle":
        return population == 0
    return False  # "renew" is read from births_total (see _renew_episodes)


def episodes(
    history: FieldHistory,
    scope: str,
    kind: str,
    *,
    last_tick: int | None = None,
) -> list[Goal]:
    """The episodes of a problem in one scope, from the field history.

    An episode opens on the first tick the signal holds and closes after
    ``RECOVERY_TICKS`` consecutive ticks without it. The ticks come from
    the scope's own series — the same fields the situation layer reads,
    so the two layers cannot disagree about what the world said.

    The ``renew`` goal is read from the cell's ``births_total`` counter:
    a stall opens when no child has been born for ``BIRTH_STALL_TICKS``
    and closes on the tick the counter moves. No separate bookkeeping,
    and the archive and the live world see the same episodes.
    """
    if kind == "renew":
        return _renew_episodes(history, scope, last_tick)
    signal = "famine" if kind == "feed" else (
        "thin_soil" if kind == "restore_soil" else "abandoned"
    )
    ticks = sorted(
        {t for t, _ in history.series(scope, "population")}
        | {t for t, _ in history.series(scope, "food_stock")}
        | {t for t, _ in history.series(scope, "soil_fertility")}
    )
    if not ticks:
        return []
    if last_tick is not None:
        ticks = [t for t in ticks if t <= last_tick]

    out: list[Goal] = []
    opened: int | None = None
    calm = 0
    for tick in ticks:
        population = int(history.value_at(scope, "population", tick) or 0)
        food = float(history.value_at(scope, "food_stock", tick) or 0.0)
        soil = float(history.value_at(scope, "soil_fertility", tick) or 0.0)
        food_pc = food / max(population, 1)
        bad = _bad_signal(kind, population, food_pc, soil)
        if opened is None:
            if bad:
                opened = tick
                calm = 0
        elif bad:
            calm = 0
        else:
            calm += 1
            if calm >= RECOVERY_TICKS:
                out.append(Goal(kind, scope, signal, opened, tick - calm + 1))
                opened = None
                calm = 0
    if opened is not None:
        out.append(Goal(kind, scope, signal, opened, None))
    return out


def _renew_episodes(
    history: FieldHistory, scope: str, last_tick: int | None
) -> list[Goal]:
    """Birth stalls, read from the cell's own ``births_total`` counter."""
    births = history.series(scope, "births_total")
    ticks = sorted({t for t, _ in births}
                   | {t for t, _ in history.series(scope, "population")})
    if last_tick is not None:
        ticks = [t for t in ticks if t <= last_tick]
    out: list[Goal] = []
    opened: int | None = None
    last_change: int | None = None
    last_value = None
    for tick in ticks:
        value = history.value_at(scope, "births_total", tick)
        if value != last_value:
            # a birth (or the first reading) resets the clock
            if opened is not None:
                out.append(Goal("renew", scope, "birth_stall", opened, tick))
                opened = None
            last_change = tick
            last_value = value
        if opened is None:
            population = int(history.value_at(scope, "population", tick) or 0)
            if (
                population > 0
                and last_change is not None
                and tick - last_change > BIRTH_STALL_TICKS
            ):
                opened = last_change
    if opened is not None:
        out.append(Goal("renew", scope, "birth_stall", opened, None))
    return out


# ----------------------------------------------------------------------
# Deciding whether a goal was actually solved
# ----------------------------------------------------------------------
def _active(view: StateView, cell: str) -> bool:
    """A wild parcel (``land_active = 0``) is land, not a goal scope."""
    value = view.get(cell, "land_active")
    return True if value is None else bool(int(value))


def _neighbours(scope: str, view: StateView) -> list[str]:
    """The orthogonal neighbours of a cell (empty for region worlds).

    The coordinates come from the cell's OWN fields (``cell_x``/``cell_y``
    inside its region), never from the entity id: ``cell:1:0`` is "region
    1, cell 0", not a point on a plane, and reading it as coordinates is
    exactly the kind of plausible-looking mistake this repo refuses.
    """
    if not scope.startswith("cell:"):
        return []
    region = view.get(scope, "region")
    x = view.get(scope, "cell_x")
    y = view.get(scope, "cell_y")
    if region is None or x is None or y is None:
        return []
    out = []
    for other in view.entities_with_prefix("cell:"):
        if not _active(view, other):
            continue
        if view.get(other, "region") != region:
            continue
        ox, oy = view.get(other, "cell_x"), view.get(other, "cell_y")
        if ox is None or oy is None:
            continue
        if abs(int(ox) - int(x)) + abs(int(oy) - int(y)) == 1:
            out.append(other)
    return sorted(out)


def _share(now: int, opening: int) -> float:
    return 1.0 if opening <= 0 else now / opening


def evaluate(
    goal: Goal,
    history: FieldHistory,
    view: StateView,
    alerts: list[Alert],
    *,
    tick: int,
    neighbours: list[str] | None = None,
    settle_ticks: int | None = None,
) -> Verdict:
    """The verdict for one goal.

    ``alerts`` are the CURRENT alerts (as of ``tick``), so the caller
    does not have to reconstruct the feed at the closing tick.
    ``settle_ticks`` overrides the default watch window: the v0.10
    sensitivity experiment changes it to ask how much the verdict
    depends on the chosen horizon.
    """
    window = SETTLE_TICKS if settle_ticks is None else int(settle_ticks)
    closed = goal.closed_tick
    # The system is watched for the whole window after the signal goes
    # away (SETTLE_TICKS by default; the parameter exists so the choice
    # can be MEASURED, not asserted).
    at = tick if closed is None else min(tick, closed + window)
    pop_open = int(history.value_at(goal.scope, "population", goal.opened_tick) or 0)
    pop_close = int(history.value_at(goal.scope, "population", at) or 0)
    pop_at_close = (
        pop_close if closed is None
        else int(history.value_at(goal.scope, "population", closed) or 0)
    )
    soil_open = float(
        history.value_at(goal.scope, "soil_fertility", goal.opened_tick) or 0.0
    )
    soil_close = float(history.value_at(goal.scope, "soil_fertility", at) or 0.0)
    births_open = int(history.value_at(goal.scope, "births_total",
                                       goal.opened_tick) or 0)
    births_close = int(history.value_at(goal.scope, "births_total", at) or 0)

    here = [a for a in alerts if a.scope == goal.scope]
    family = SIGNAL_FAMILY[goal.kind]
    related: list[str] = []
    transferred_to: list[str] = []
    if neighbours is None:
        neighbours = _neighbours(goal.scope, view)
    for other in neighbours:
        for a in alerts:
            if a.scope != other or a.kind not in family:
                continue
            if a.since_tick <= goal.opened_tick:
                continue  # it was already there when the goal opened
            transferred_to.append(other)
            related.append(f"{a.kind}@{other}")

    evidence = _evidence_for(goal, history, view, at)

    # 1. The signal is still there.
    if goal.closed_tick is None:
        if not any(a.kind in family for a in here):
            # The alert disappeared but the history says the episode is
            # still open (e.g. an alert outage). Never claim a win from a
            # missing reading: stay active.
            return Verdict(goal, "active",
                           f"сигнал {goal.signal} ещё в истории, но текущей "
                           f"тревоги нет — считать решённым нельзя",
                           pop_open, pop_close, soil_open, soil_close,
                           tuple(related), tuple(evidence))
        return Verdict(goal, "active", _active_reason(goal, here),
                       pop_open, pop_close, soil_open, soil_close,
                       tuple(related), tuple(evidence))

    # 2. The signal is gone. If the people were already gone at that
    #    moment, the verdict is immediate; otherwise watch the system.
    if pop_at_close == 0:
        return Verdict(
            goal, "collapsed",
            f"{goal.signal} ушёл, но в {goal.scope} уже не было людей: "
            f"это не решение, а потеря клетки",
            pop_open, pop_close, soil_open, soil_close,
            tuple(related), tuple(evidence),
        )
    if closed + window > tick:
        return Verdict(
            goal, "settling",
            f"{goal.signal} ушёл на тике {closed}; последствия ещё "
            f"наблюдаются ({tick - closed} из {window} тиков) — "
            f"объявлять победу рано",
            pop_open, pop_close, soil_open, soil_close,
            tuple(related), tuple(evidence),
        )

    # 3. The signal is gone and the settling window has passed.
    if goal.kind in ("feed", "restore_soil", "resettle", "renew"):
        if pop_close == 0:
            return Verdict(
                goal, "collapsed",
                f"{goal.signal} ушёл, потому что в {goal.scope} не осталось "
                f"людей: это не решение, а потеря клетки",
                pop_open, pop_close, soil_open, soil_close,
                tuple(related), tuple(evidence),
            )
        if pop_open > 0 and pop_close / pop_open <= COLLAPSE_POP_SHARE:
            return Verdict(
                goal, "collapsed",
                f"{goal.signal} ушёл, но населения осталось "
                f"{pop_close} из {pop_open} — цена больше половины людей",
                pop_open, pop_close, soil_open, soil_close,
                tuple(related), tuple(evidence),
            )

    if goal.kind == "renew":
        # A birth stall ends when a child is born. That is the fact; the
        # question is whether the cell can now GROW.
        if births_close <= births_open:
            return Verdict(
                goal, "active",
                f"рождений в {goal.scope} так и нет "
                f"({births_open} за эпизод) — предел не снят",
                pop_open, pop_close, soil_open, soil_close,
                tuple(related), tuple(evidence),
            )
        if pop_close <= pop_open:
            return Verdict(
                goal, "resolved_with_cost",
                f"рождения возобновились ({births_open} → {births_close}), "
                f"но население не выросло ({pop_open} → {pop_close}): "
                f"смертность съела прирост",
                pop_open, pop_close, soil_open, soil_close,
                tuple(related), tuple(evidence),
                births_open=births_open, births_close=births_close,
            )

    # "Transferred" is a statement about a PROBLEM MOVING between places.
    # A birth stall is not a place-bound problem, and it has its own
    # verdict above; it must never fall through to this reading.
    if (
        goal.kind in ("feed", "restore_soil", "resettle")
        and transferred_to
        and pop_open > 0
        and pop_close / pop_open >= COST_POP_SHARE
    ):
        return Verdict(
            goal, "transferred",
            f"ПРЕДПОЛОЖЕНИЕ (не доказано): {goal.signal} ушёл из "
            f"{goal.scope}, но появился рядом: "
            f"{', '.join(sorted(set(transferred_to)))} — проблема могла "
            f"переехать, а могла возникнуть сама; близость и время не "
            f"доказывают перенос причины",
            pop_open, pop_close, soil_open, soil_close,
            tuple(related), tuple(evidence),
            confidence="hypothesis",
        )

    if goal.kind == "restore_soil" and soil_close < THIN_SOIL:
        # The episode closed because the soil crossed the line; if the
        # recorded value is still under it, do not claim a recovery.
        return Verdict(
            goal, "resolved_with_cost",
            f"эпизод закрыт, но почва {soil_close:.2f} всё ещё ниже порога "
            f"{THIN_SOIL:.2f}",
            pop_open, pop_close, soil_open, soil_close,
            tuple(related), tuple(evidence),
        )

    if pop_open > 0 and pop_close / pop_open < COST_POP_SHARE:
        return Verdict(
            goal, "resolved_with_cost",
            f"{goal.signal} ушёл, но населения осталось "
            f"{pop_close} из {pop_open} — цель достигнута ценой людей",
            pop_open, pop_close, soil_open, soil_close,
            tuple(related), tuple(evidence),
        )

    return Verdict(
        goal, "resolved",
        f"{goal.signal} ушёл, население {pop_open} → {pop_close}, "
        f"почва {soil_open:.2f} → {soil_close:.2f}: система цела",
        pop_open, pop_close, soil_open, soil_close,
        tuple(related), tuple(evidence),
        births_open=births_open, births_close=births_close,
    )


def _active_reason(goal: Goal, here: list[Alert]) -> str:
    worst = max(here, key=lambda a: a.severity)
    return (f"{worst.kind} в {goal.scope} продолжается "
            f"(с тика {worst.since_tick}, острота {worst.severity:.2f})")


def _evidence_for(goal: Goal, history: FieldHistory, view: StateView, at: int):
    out = []
    for field_name in ("population", "food_stock", "soil_fertility"):
        sid = view.source(goal.scope, field_name)
        if sid is not None:
            out.append({
                "tid": sid,
                "tick": view.tick_of(goal.scope, field_name),
                "entity": goal.scope,
                "field": field_name,
                "value": view.get(goal.scope, field_name),
            })
    return out


# ----------------------------------------------------------------------
# The public feed
# ----------------------------------------------------------------------
def goals(
    history: FieldHistory,
    view: StateView,
    alerts: list[Alert],
    *,
    tick: int,
    window: int = RECENT_WINDOW,
    scopes: list[str] | None = None,
) -> list[Verdict]:
    """All goal verdicts worth showing: open ones and recently closed ones.

    Scope order is the world's order (cells, then regions), so two runs
    with the same seed produce the same feed in the same order.
    """
    if scopes is None:
        cells = [
            c for c in view.entities_with_prefix("cell:")
            if _active(view, c)
        ]
        scopes = cells or view.entities_with_prefix("region:")
    verdicts: list[Verdict] = []
    for scope in scopes:
        for kind in HISTORY_GOALS:
            for goal in episodes(history, scope, kind, last_tick=tick):
                closed = goal.closed_tick
                if closed is not None and closed < tick - window:
                    continue
                if closed is None and not any(
                    a.scope == scope for a in alerts
                ):
                    # An episode the alerts already stopped reporting and
                    # the history has not closed yet: do not invent a
                    # goal from a stale series.
                    continue
                verdicts.append(
                    evaluate(goal, history, view, alerts, tick=tick)
                )
    # Open goals first, then the most recent; stable within a tick.
    verdicts.sort(key=lambda v: (v.goal.closed_tick is not None,
                                 -v.goal.opened_tick, v.goal.scope))
    return verdicts


def summary(verdicts: list[Verdict]) -> dict:
    """Counts for a chronicle: never a single 'solved' number."""
    out = {"active": 0, "settling": 0, "resolved": 0,
           "resolved_with_cost": 0, "collapsed": 0, "transferred": 0}
    for v in verdicts:
        out[v.status] = out.get(v.status, 0) + 1
    out["total"] = len(verdicts)
    return out
