"""Derived time series, reconstructed from the journal alone.

The v0.1 kernel persists no per-tick snapshots — the journal IS the
source of truth. Every series here is a replay of committed writes in id
order, so it is exact (no sampling error) and deterministic. The
reconstruction is a single streaming pass with O(entities) memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from causal_world.kernel.transition import Transition, TransitionStatus


@dataclass
class TimeSeries:
    """World-level series sampled every ``sample_every`` ticks."""

    sample_every: int = 1
    population: list[tuple[int, int]] = field(default_factory=list)
    # mean soil over inhabited regions (soil > 0.1 and population > 0)
    soil: list[tuple[int, float]] = field(default_factory=list)
    # per-region population and soil at the last sampled tick
    final_region_population: dict[str, int] = field(default_factory=dict)
    final_region_soil: dict[str, float] = field(default_factory=dict)
    total_agents: int = 0
    last_tick: int = 0


def _iter_committed(journal):
    if hasattr(journal, "committed"):
        yield from journal.committed()
    else:
        for t in journal:
            if t.status is TransitionStatus.COMMITTED:
                yield t


def build_series(journal, sample_every: int = 1,
                 total_agents: int | None = None) -> TimeSeries:
    """Replay committed writes and sample world-level series.

    ``total_agents`` defaults to the archive meta when available.
    """
    series = TimeSeries(sample_every=max(1, sample_every))
    if total_agents is None and hasattr(journal, "meta"):
        meta_agents = journal.meta("agents")
        total_agents = int(meta_agents) if meta_agents else None
    series.total_agents = total_agents or 0

    dead: set[str] = set()
    region_pop: dict[str, int] = {}
    region_soil: dict[str, float] = {}
    initial_regions: dict[str, int] = {}
    last_sampled = -1

    def sample(tick: int) -> None:
        nonlocal last_sampled
        if tick == last_sampled:
            return
        if tick % series.sample_every != 0 and tick != series.last_tick:
            pass
        last_sampled = tick
        alive = series.total_agents - len(dead)
        series.population.append((tick, alive))
        inhabited = [
            soil for region, soil in region_soil.items()
            if soil > 0.1 and region_pop.get(region, 0) > 0
        ]
        if inhabited:
            series.soil.append((tick, sum(inhabited) / len(inhabited)))

    for t in _iter_committed(journal):
        for w in t.writes:
            if w.entity.startswith("region:"):
                if w.field == "population":
                    region_pop[w.entity] = int(w.new)
                elif w.field == "soil_fertility":
                    region_soil[w.entity] = float(w.new)
            elif w.entity.startswith("agent:"):
                if w.field == "alive" and w.new is False:
                    dead.add(w.entity)
                elif w.field == "region" and w.old is None:
                    initial_regions[w.entity] = 1
        if t.tick != series.last_tick:
            if series.last_tick >= 0 and (
                    series.last_tick % series.sample_every == 0):
                sample(series.last_tick)
            series.last_tick = t.tick
    if series.last_tick >= 0:
        sample(series.last_tick)

    if series.total_agents == 0:
        series.total_agents = len(initial_regions)
        series.population = [
            (tick, series.total_agents - len(dead))
            for tick, _ in series.population
        ]
    series.final_region_population = dict(region_pop)
    series.final_region_soil = dict(region_soil)
    return series
