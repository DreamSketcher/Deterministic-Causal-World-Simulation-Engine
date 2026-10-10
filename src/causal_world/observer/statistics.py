"""Statistics: aggregate read-only views over journal + index + state.

Computed after the fact; never feeds back into the simulation (I11).
No significance thresholds exist in the journal itself (spec §33/§34) —
filtering is strictly an observer concern and happens only here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.events import EventView, events_from_journal


@dataclass
class RunStatistics:
    ticks: int = 0
    total_transitions: int = 0
    committed: int = 0
    rejected: int = 0
    by_operation: dict[str, int] = field(default_factory=dict)
    events_by_type: dict[str, int] = field(default_factory=dict)
    final_population: int = 0
    final_infected: int = 0
    final_food_stock: float = 0.0
    leaderboard: list[tuple[str, float]] = field(default_factory=list)
    events: list[EventView] = field(default_factory=list)


def compute_statistics(simulation) -> RunStatistics:
    journal = simulation.journal
    state = simulation.state

    stats = RunStatistics(ticks=state.tick, total_transitions=len(journal))
    for t in journal:
        if t.status is TransitionStatus.COMMITTED:
            stats.committed += 1
            stats.by_operation[t.operation] = stats.by_operation.get(t.operation, 0) + 1
        elif t.status is TransitionStatus.REJECTED:
            stats.rejected += 1

    stats.events = events_from_journal(journal)
    for event in stats.events:
        stats.events_by_type[event.type] = stats.events_by_type.get(event.type, 0) + 1

    agents = state.entities_with_prefix("agent:")
    survivors: list[tuple[str, float]] = []
    for agent in agents:
        if state.get(agent, "alive"):
            stats.final_population += 1
            if state.get(agent, "infected"):
                stats.final_infected += 1
            survivors.append((agent, float(state.get(agent, "health"))))
    # Canonical leaderboard order: health desc, then entity id asc (spec §30).
    stats.leaderboard = sorted(survivors, key=lambda item: (-item[1], item[0]))[:5]

    for region in state.entities_with_prefix("region:"):
        stats.final_food_stock += float(state.get(region, "food_stock") or 0.0)

    return stats


def format_statistics(stats: RunStatistics) -> str:
    lines = [
        f"Ticks:            {stats.ticks}",
        f"Transitions:      {stats.total_transitions} "
        f"(committed {stats.committed}, rejected {stats.rejected})",
    ]
    for event_type in sorted(stats.events_by_type):
        lines.append(f"Events[{event_type}]: {stats.events_by_type[event_type]}")
    lines.append(f"Population:       {stats.final_population} "
                 f"(infected {stats.final_infected})")
    lines.append(f"Food stock:       {stats.final_food_stock:.1f}")
    if stats.leaderboard:
        lines.append("Leaderboard (health):")
        for agent, health in stats.leaderboard:
            lines.append(f"  {agent:<10} {health:.1f}")
    return "\n".join(lines)
