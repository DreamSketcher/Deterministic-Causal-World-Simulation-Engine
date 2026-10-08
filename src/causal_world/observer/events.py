"""EventView: narrative interpretations DERIVED from primitive writes.

The kernel knows nothing about "infection" or "death" (invariant I15).
This module is one possible observer-side interpretation of committed
StateChanges; a different ruleset could interpret the same primitives
differently (spec §22, §23).

Events are never an input to the simulation. They exist only after the
fact, reconstructed from the journal.
"""

from __future__ import annotations

from dataclasses import dataclass

from causal_world.kernel.transition import Transition, TransitionStatus


@dataclass(frozen=True)
class EventView:
    tick: int
    transition_id: int
    entity: str
    type: str
    detail: str


def events_from_transition(transition: Transition) -> list[EventView]:
    if transition.status is not TransitionStatus.COMMITTED:
        return []
    if transition.id is None:
        return []
    events: list[EventView] = []
    for w in sorted(transition.writes, key=lambda w: (w.entity, w.field)):
        if w.field == "alive" and w.old is True and w.new is False:
            events.append(
                EventView(
                    transition.tick, transition.id, w.entity, "death",
                    f"committed by T{transition.id} ({transition.system})",
                )
            )
        elif w.field == "infected" and w.old is False and w.new is True:
            events.append(
                EventView(
                    transition.tick, transition.id, w.entity, "infection",
                    f"committed by T{transition.id} ({transition.system})",
                )
            )
        elif w.field == "infected" and w.old is True and w.new is False:
            events.append(
                EventView(
                    transition.tick, transition.id, w.entity, "recovery",
                    f"committed by T{transition.id} ({transition.system})",
                )
            )
        elif (
            w.field == "region"
            and w.entity.startswith("agent:")
            and w.old is not None  # old=None is genesis creation, not movement
            and w.old != w.new
        ):
            events.append(
                EventView(
                    transition.tick, transition.id, w.entity, "migration",
                    f"{w.old} → {w.new}",
                )
            )
    return events


def events_from_journal(journal) -> list[EventView]:
    events: list[EventView] = []
    ordered = sorted(journal.all(), key=lambda t: (t.id is None, t.id or 0))
    for transition in ordered:
        events.extend(events_from_transition(transition))
    return events
