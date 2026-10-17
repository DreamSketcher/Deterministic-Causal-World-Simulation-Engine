"""v0.7 — the RESEARCHER layer: what is a fact, what is a proven link,
and what is only the player's hypothesis.

The concept the game is built on demands three distinct epistemic
levels in the interface, and the repository's own invariant I11 ("the
observer may derive anything from the journal but must never modify it")
is what makes them separable:

1. **OBSERVED FACT** — a committed transition. It happened; the journal
   says so. No inference, no interpretation: ``transition.id`` is the
   reference the UI must show.
2. **CONFIRMED CAUSAL LINK** — a read-dependency between two committed
   transitions that the engine actually recorded. The causal index
   (``idx_reads``) stores exactly these edges, and
   :meth:`CausalQuery.caused` / :meth:`CausalQuery.caused_by` walk them.
   A link is confirmed iff such an edge EXISTS in the record — the
   player never gets to assert one.
3. **PLAYER HYPOTHESIS** — a claim the player makes that the engine has
   NOT confirmed. It is kept as a first-class object with a status, and
   the engine can TEST it against the record (see
   :func:`test_hypothesis`).

The difference matters mechanically: a hypothesis that is silently
upgraded to a "fact" is a lie, and a fact that is silently downgraded to
a "hypothesis" is useless. This module keeps them apart and makes the
distinction machine-checkable.

Deliberately NOT here: any smoothing, any probability of "maybe", any
narrative. The only outputs are: transition ids, edges that exist, and
verdicts derived from those.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from causal_world.observer.journal import JournalView
from causal_world.query.index import QueryIndex
from causal_world.query.query import CausalQuery


class LinkStatus(Enum):
    """The three epistemic levels, as the engine sees them."""

    OBSERVED = "observed"      # a committed transition
    CONFIRMED = "confirmed"    # a recorded read-dependency
    HYPOTHESIS = "hypothesis"  # the player's claim, not yet settled


class Verdict(Enum):
    """The outcome of testing a hypothesis against the record."""

    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Fact:
    """An observed fact: one committed transition, by id."""

    transition_id: int
    tick: int
    system: str
    operation: str
    status: str

    @property
    def level(self) -> LinkStatus:
        return LinkStatus.OBSERVED

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "transition_id": self.transition_id,
            "tick": self.tick,
            "system": self.system,
            "operation": self.operation,
            "status": self.status,
        }


@dataclass(frozen=True)
class ConfirmedLink:
    """A causal link that the record actually contains.

    ``source_id`` wrote something that ``reader_id`` read — the edge the
    causal index stores. ``depth`` is the distance in the read graph.
    """

    source_id: int
    reader_id: int
    depth: int
    entity: str = ""
    field: str = ""

    @property
    def level(self) -> LinkStatus:
        return LinkStatus.CONFIRMED

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "source_id": self.source_id,
            "reader_id": self.reader_id,
            "depth": self.depth,
            "entity": self.entity,
            "field": self.field,
        }


@dataclass(frozen=True)
class Hypothesis:
    """A claim the player makes about the world.

    The claim is deliberately narrow and machine-testable: "transition
    A caused transition B", or "system S.operation O caused the change
    of entity E's field F".
    """

    text: str
    source_id: int | None = None
    reader_id: int | None = None
    system: str | None = None
    operation: str | None = None
    entity: str | None = None
    field: str | None = None
    tick_start: int = 0
    tick_end: int = 2**62

    @property
    def level(self) -> LinkStatus:
        return LinkStatus.HYPOTHESIS

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "text": self.text,
            "source_id": self.source_id,
            "reader_id": self.reader_id,
            "system": self.system,
            "operation": self.operation,
            "entity": self.entity,
            "field": self.field,
        }


@dataclass
class HypothesisReport:
    """The verdict on a hypothesis, with the evidence that produced it."""

    hypothesis: Hypothesis
    verdict: Verdict
    reason: str
    supporting: list = field(default_factory=list)   # transition ids
    contradicting: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "verdict": self.verdict.value,
            "reason": self.reason,
            "supporting": list(self.supporting),
            "contradicting": list(self.contradicting),
        }


def facts_of(view: JournalView, *, system: str | None = None,
             operation: str | None = None, entity: str | None = None,
             field: str | None = None, tick_start: int = 0,
             tick_end: int = 2**62) -> list[Fact]:
    """Every committed transition matching the filters — the observed facts.

    Read straight from the journal, id order. A transition that was
    REJECTED is not a fact: it never changed the world.
    """
    out: list[Fact] = []
    for t in view:
        if t.status.value != "COMMITTED":
            continue
        if t.tick < tick_start or t.tick > tick_end:
            continue
        if system is not None and t.system != system:
            continue
        if operation is not None and t.operation != operation:
            continue
        if entity is not None and not any(w.entity == entity for w in t.writes):
            continue
        if field is not None and not any(w.field == field for w in t.writes):
            continue
        if t.id is None:
            continue
        out.append(Fact(t.id, t.tick, t.system, t.operation, t.status.value))
    return out


def confirmed_links(index: QueryIndex, source_id: int, *,
                    depth: int = 3) -> list[ConfirmedLink]:
    """The read-dependencies that actually exist from one transition.

    This is the ONLY way the game may claim "A caused B": the edges come
    from ``idx_reads``, which the engine wrote when it recorded the
    provenance of each read. A player hypothesis that names a link which
    is not in this set is simply wrong, and the UI must show it as such.
    """
    q = CausalQuery(index)
    rows = index.sql(
        "SELECT source_tid, reader_tid, entity, field FROM idx_reads "
        "WHERE source_tid = ?", (source_id,)
    ).fetchall()
    out = [
        ConfirmedLink(int(r["source_tid"]), int(r["reader_tid"]), 1,
                      str(r["entity"]), str(r["field"]))
        for r in rows
    ]
    if depth > 1:
        seen = {link.reader_id for link in out}
        frontier = list(seen)
        for level in range(2, depth + 1):
            if not frontier:
                break
            marks = ",".join("?" for _ in frontier)
            rows = index.sql(
                f"SELECT source_tid, reader_tid, entity, field FROM idx_reads "
                f"WHERE source_tid IN ({marks})", tuple(frontier)
            ).fetchall()
            nxt = []
            for r in rows:
                rid = int(r["reader_tid"])
                if rid in seen:
                    continue
                seen.add(rid)
                nxt.append(rid)
                out.append(ConfirmedLink(int(r["source_tid"]), rid, level,
                                         str(r["entity"]), str(r["field"])))
            frontier = nxt
    out.sort(key=lambda link: (link.depth, link.reader_id))
    return out


def test_hypothesis(index: QueryIndex, hypothesis: Hypothesis) -> HypothesisReport:
    """Test the player's hypothesis against the recorded world.

    Two shapes of claim, both machine-checkable:

    * **Link claim** (``source_id`` -> ``reader_id``): confirmed iff the
      record contains a read-dependency path from the source to the
      reader; refuted iff both transitions exist but no such path does;
      unresolved iff one of them does not exist at all.
    * **Attribution claim** (``system``/``operation`` caused the change
      of ``entity``/``field``): confirmed iff transitions of exactly that
      system/operation wrote that field in the window; refuted iff the
      field was written in the window but NEVER by that system; unresolved
      iff the field was not written at all.

    The verdict never guesses: "unresolved" is a legitimate and frequent
    answer, and it is the honest one when the record does not settle the
    question.
    """
    if hypothesis.source_id is not None and hypothesis.reader_id is not None:
        return _test_link(index, hypothesis)
    if hypothesis.system and hypothesis.entity and hypothesis.field:
        return _test_attribution(index, hypothesis)
    return HypothesisReport(
        hypothesis=hypothesis,
        verdict=Verdict.UNRESOLVED,
        reason="the hypothesis names no testable relation",
    )


def _test_link(index: QueryIndex, hypothesis: Hypothesis) -> HypothesisReport:
    q = CausalQuery(index)
    src = index.hydrate([hypothesis.source_id])
    dst = index.hydrate([hypothesis.reader_id])
    if not src or not dst:
        return HypothesisReport(
            hypothesis, Verdict.UNRESOLVED,
            "one of the transitions does not exist in the record",
        )
    links = confirmed_links(index, hypothesis.source_id, depth=6)
    readers = {link.reader_id for link in links}
    if hypothesis.reader_id in readers:
        depth = min(link.depth for link in links
                    if link.reader_id == hypothesis.reader_id)
        return HypothesisReport(
            hypothesis, Verdict.CONFIRMED,
            f"the record contains a read-dependency from T{hypothesis.source_id} "
            f"to T{hypothesis.reader_id} (depth {depth})",
            supporting=[hypothesis.source_id, hypothesis.reader_id],
        )
    return HypothesisReport(
        hypothesis, Verdict.REFUTED,
        f"no read-dependency from T{hypothesis.source_id} to "
        f"T{hypothesis.reader_id} exists in the record",
        supporting=[hypothesis.source_id],
        contradicting=[hypothesis.reader_id],
    )


def _test_attribution(index: QueryIndex, hypothesis: Hypothesis) -> HypothesisReport:
    rows = index.sql(
        "SELECT t.id, t.tick FROM idx_writes w "
        "JOIN arch.transitions t ON t.id = w.tid "
        "WHERE w.entity = ? AND w.field = ? AND t.status = 'COMMITTED' "
        "AND t.tick BETWEEN ? AND ? ORDER BY t.tick, t.id",
        (hypothesis.entity, hypothesis.field,
         hypothesis.tick_start, hypothesis.tick_end),
    ).fetchall()
    if not rows:
        return HypothesisReport(
            hypothesis, Verdict.UNRESOLVED,
            f"{hypothesis.entity}.{hypothesis.field} was not written in the "
            f"window, so nothing can be attributed",
        )
    supporting = []
    for r in rows:
        t = index.hydrate([int(r["id"])])
        if not t:
            continue
        tr = t[0]
        if tr.system == hypothesis.system and tr.operation == hypothesis.operation:
            supporting.append(int(r["id"]))
    if supporting:
        return HypothesisReport(
            hypothesis, Verdict.CONFIRMED,
            f"{len(supporting)} committed transition(s) of "
            f"{hypothesis.system}.{hypothesis.operation} wrote "
            f"{hypothesis.entity}.{hypothesis.field} in the window",
            supporting=supporting,
        )
    others = [int(r["id"]) for r in rows]
    return HypothesisReport(
        hypothesis, Verdict.REFUTED,
        f"{hypothesis.entity}.{hypothesis.field} was written in the window, "
        f"but never by {hypothesis.system}.{hypothesis.operation}",
        contradicting=others,
    )
