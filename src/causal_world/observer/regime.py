"""L2 — RegimeClassifier: collapse / equilibrium / oscillation / decline.

Classifies a recorded run from DERIVED series only — the classifier has
no access to ruleset names or law formulas. It sees what an external
scientist would see: population over time, soil over time, and the
causal breakdown of deaths.

Decision tree (in this order):

1. COLLAPSE — the population reaches zero;
2. EQUILIBRIUM — population is stable in the final 20 % of the run
   (coefficient of variation < 5 %);
3. OSCILLATION — a periodic component survives detrending
   (autocorrelation peak > 0.3 at a lag > 20);
4. SLOW_DECLINE — anything else (falling or noisy, still alive).

One deviation from the v0.4 proposal: the proposal's autocorrelation ran
on the raw series, which makes every monotonic decline look periodic
(a trend correlates with itself at every lag). The series is detrended
first and monotonic runs are excluded, so OSCILLATION means an actual
repeating component.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from causal_world.observer.deaths import DeathClassifier
from causal_world.observer.series import TimeSeries, build_series


class RegimeType(Enum):
    COLLAPSE = "collapse"
    EQUILIBRIUM = "equilibrium"
    OSCILLATION = "oscillation"
    SLOW_DECLINE = "slow_decline"


@dataclass(frozen=True)
class RegimeReport:
    type: RegimeType
    extinction_tick: int | None
    equilibrium_population: float | None
    oscillation_period: int | None
    dominant_death_cause: str
    death_causes: tuple[tuple[str, float], ...]
    soil_trajectory: str  # monotonic_decline / convergent / recovering
    confidence: float


class RegimeClassifier:
    """Classifies a run's regime from its journal."""

    def __init__(self, journal, series: TimeSeries | None = None,
                 sample_every: int = 1, total_agents: int | None = None,
                 death_trace_depth: int = 40, max_classified_deaths: int = 0):
        self._journal = journal
        self._series = series or build_series(
            journal, sample_every=sample_every, total_agents=total_agents)
        self._depth = death_trace_depth
        self._max_deaths = max_classified_deaths

    @property
    def series(self) -> TimeSeries:
        return self._series

    # ------------------------------------------------------------------
    def classify(self) -> RegimeReport:
        pop = self._series.population
        causes = self._death_cause_breakdown()
        dominant = causes[0][0] if causes else "none"
        soil_trend = self._soil_trend(self._series.soil)

        if pop and pop[-1][1] == 0:
            return RegimeReport(
                type=RegimeType.COLLAPSE,
                extinction_tick=self._extinction_tick(),
                equilibrium_population=None,
                oscillation_period=None,
                dominant_death_cause=dominant,
                death_causes=causes,
                soil_trajectory=soil_trend,
                confidence=0.95,
            )

        values = [p for _, p in pop]
        if values:
            late = values[-max(1, len(values) // 5):]
            mean_pop = sum(late) / len(late)
            variance = sum((p - mean_pop) ** 2 for p in late) / len(late)
            cv = (variance ** 0.5) / max(mean_pop, 1)
            if cv < 0.05:
                return RegimeReport(
                    type=RegimeType.EQUILIBRIUM,
                    extinction_tick=None,
                    equilibrium_population=mean_pop,
                    oscillation_period=None,
                    dominant_death_cause=dominant,
                    death_causes=causes,
                    soil_trajectory=soil_trend,
                    confidence=0.90,
                )

        period = self._detect_period(pop)
        if period is not None:
            return RegimeReport(
                type=RegimeType.OSCILLATION,
                extinction_tick=None,
                equilibrium_population=None,
                oscillation_period=period,
                dominant_death_cause=dominant,
                death_causes=causes,
                soil_trajectory=soil_trend,
                confidence=0.75,
            )

        return RegimeReport(
            type=RegimeType.SLOW_DECLINE,
            extinction_tick=None,
            equilibrium_population=None,
            oscillation_period=None,
            dominant_death_cause=dominant,
            death_causes=causes,
            soil_trajectory=soil_trend,
            confidence=0.60,
        )

    # ------------------------------------------------------------------
    def _extinction_tick(self) -> int | None:
        """Tick of the last death = first tick with zero population."""
        query = getattr(self._journal, "query", None)
        if callable(query):
            rows = query(
                "SELECT MAX(tick) AS t FROM transitions "
                "WHERE operation='agent.death' AND status='COMMITTED'"
            )
            if rows and rows[0]["t"] is not None:
                return int(rows[0]["t"])
            return None
        last = None
        for t in self._journal:
            if t.operation == "agent.death":
                last = t.tick
        return last

    def _death_cause_breakdown(self) -> tuple[tuple[str, float], ...]:
        deaths: list[tuple[str, int]] = []
        query = getattr(self._journal, "query", None)
        if callable(query):
            rows = query(
                "SELECT id FROM transitions WHERE operation='agent.death' "
                "AND status='COMMITTED' ORDER BY id"
            )
            for row in rows:
                agent = self._death_agent(row["id"])
                if agent:
                    deaths.append((agent, int(row["id"])))
        else:
            from causal_world.kernel.transition import TransitionStatus

            for t in self._journal:
                if (t.status is TransitionStatus.COMMITTED
                        and t.operation == "agent.death"):
                    for w in t.writes:
                        if w.entity.startswith("agent:") and w.field == "alive":
                            deaths.append((w.entity, t.id))
                            break
        if self._max_deaths and len(deaths) > self._max_deaths:
            step = len(deaths) / self._max_deaths
            deaths = [deaths[int(i * step)] for i in range(self._max_deaths)]

        classifier = DeathClassifier(self._journal)
        counts: dict[str, int] = {}
        for agent, tid in deaths:
            cause = classifier.classify(agent, tid, depth=self._depth)
            counts[cause] = counts.get(cause, 0) + 1
        total = sum(counts.values()) or 1
        return tuple(sorted(
            ((k, v / total) for k, v in counts.items()),
            key=lambda kv: (-kv[1], kv[0]),
        ))

    def _death_agent(self, tid: int) -> str | None:
        query = getattr(self._journal, "query", None)
        if callable(query):
            import json

            rows = query("SELECT payload FROM transitions WHERE id=?", (tid,))
            if not rows:
                return None
            payload = json.loads(rows[0]["payload"])
            for w in payload["writes"]:
                if w[0].startswith("agent:") and w[1] == "alive":
                    return w[0]
            return None
        t = self._journal.by_id(tid)
        for w in t.writes:
            if w.entity.startswith("agent:") and w.field == "alive":
                return w.entity
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _soil_trend(series: list[tuple[int, float]]) -> str:
        if len(series) < 10:
            return "unknown"
        third = max(1, len(series) // 3)
        early = sum(s for _, s in series[:third]) / third
        late = sum(s for _, s in series[-third:]) / third
        diff = late - early
        if abs(diff) < 0.02:
            return "convergent"
        if diff < 0:
            return "monotonic_decline"
        return "recovering"

    @staticmethod
    def _detrend(values: list[float]) -> list[float]:
        n = len(values)
        if n < 3:
            return list(values)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(values) / n
        denom = sum((x - mean_x) ** 2 for x in xs) or 1.0
        slope = sum((x - mean_x) * (y - mean_y)
                    for x, y in zip(xs, values)) / denom
        intercept = mean_y - slope * mean_x
        return [y - (slope * x + intercept) for x, y in zip(xs, values)]

    def _detect_period(self, series: list[tuple[int, int]]) -> int | None:
        """Autocorrelation peak of the DETRENDED population series."""
        if len(series) < 100:
            return None
        values = [float(p) for _, p in series]
        diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        positive = sum(1 for d in diffs if d > 0)
        ratio = positive / max(1, len(diffs))
        if ratio < 0.15 or ratio > 0.85:
            return None  # monotone-ish: a trend, not an oscillation
        detrended = self._detrend(values)
        mean = sum(detrended) / len(detrended)
        var = sum((v - mean) ** 2 for v in detrended)
        if var == 0:
            return None
        best_lag = None
        best_corr = 0.0
        max_lag = max(21, len(detrended) // 3)
        for lag in range(20, max_lag):
            corr = sum(
                (detrended[i] - mean) * (detrended[i + lag] - mean)
                for i in range(len(detrended) - lag)
            ) / var
            if corr > best_corr:
                best_corr = corr
                best_lag = lag
        return best_lag if best_corr > 0.3 else None
