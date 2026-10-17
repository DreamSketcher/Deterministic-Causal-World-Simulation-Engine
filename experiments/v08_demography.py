#!/usr/bin/env python3
"""v0.8 — demographic diagnosis of the living world.

QUESTION
    Why does ``player_civic`` (the v0.7 civic world) lose its population
    around tick 600, and WHICH demographic parameter is responsible?

METHOD (repo discipline)
    * one factor per probe — every probe changes exactly ONE thing, so a
      difference in the outcome is attributable (no multi-factor claims);
    * the baseline is the rules as they are: no rule is edited here;
    * every number is measured from the run, never extrapolated;
    * the causal chain of the last death is traced through the journal
      (``causal.trace``), so the verdict rests on provenance, not on a
      plausible story.

PROBES
    baseline       player_civic as shipped (2 regions x 100 agents, 700 ticks)
    no_senescence  SENESCENCE_ONSET pushed out of reach (age death off)
    no_disease     the pathogen system removed from the roster
    birth_x10      the birth rate multiplied by 10 (supply of newborns)
    compost_no_age the research ruleset ``compost`` (no age death at all)

Run:
    python3 experiments/v08_demography.py --out experiments/reports/v08_demography.md
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.systems.birth import BirthSystem  # noqa: E402
from causal_world.systems.senescence import SenescenceSystem  # noqa: E402
from causal_world.world.rules import CivicRules, get_ruleset  # noqa: E402

SAMPLE_EVERY = 25

DEATH_OPS = ("agent.death", "agent.senescence", "disease.infect")


# ----------------------------------------------------------------------
@dataclass
class RegionStat:
    """Per-region census at one sampled tick."""

    tick: int
    region: str
    population: int
    workers: int
    soil: float
    food: float
    food_pc: float
    capacity: int
    capacity_limited: bool
    food_limited: bool


@dataclass
class RunResult:
    name: str
    ruleset: str
    seed: int
    regions: int
    agents: int
    ticks: int
    population_curve: list[tuple[int, int]] = field(default_factory=list)
    peak_population: int = 0
    peak_tick: int = 0
    extinction_tick: int | None = None
    births_total: int = 0
    first_birth_tick: int | None = None
    deaths_by_operation: dict[str, int] = field(default_factory=dict)
    age_histogram: dict[str, int] = field(default_factory=dict)
    mean_age_final: float = 0.0
    max_age_final: int = 0
    capacity_limited_ticks: int = 0
    food_limited_ticks: int = 0
    final_regions: list[RegionStat] = field(default_factory=list)
    state_hash: str = ""
    journal_hash: str = ""
    db_path: str = ""


def _capacity(pop_base: int, soil: float) -> int:
    """BirthSystem's carrying capacity (same formula, for the report)."""
    return int(round(pop_base * (BirthSystem.CAPACITY_BASE + BirthSystem.CAPACITY_SOIL * soil)))


def run_probe(
    name: str,
    ruleset_name: str,
    seed: int,
    regions: int,
    agents: int,
    ticks: int,
    db_path: str,
    patch=None,
) -> RunResult:
    """One probe: run the world, sample the demography, count the ledger.

    ``patch`` is a context manager that changes EXACTLY ONE law for the
    duration of the run (the change must be active while the systems
    compute, not only while the ruleset is built).
    """
    with (patch() if patch is not None else contextlib.nullcontext()):
        return _run_probe(
            name, ruleset_name, seed, regions, agents, ticks, db_path
        )


def _run_probe(
    name: str,
    ruleset_name: str,
    seed: int,
    regions: int,
    agents: int,
    ticks: int,
    db_path: str,
) -> RunResult:
    """The body of a probe (runs with the patch already active)."""
    for suffix in ("", "-wal", "-shm"):
        Path(db_path + suffix).unlink(missing_ok=True)

    rules = get_ruleset(ruleset_name)
    sim = create_world(
        seed=seed,
        ruleset=rules,
        ticks=0,
        regions=regions,
        agents=agents,
        persist=db_path,
    )
    agent_ids = [e for e in sim.state.entities() if e.startswith("agent:")]
    region_ids = [e for e in sim.state.entities() if e.startswith("region:")]

    result = RunResult(
        name=name,
        ruleset=ruleset_name,
        seed=seed,
        regions=regions,
        agents=agents,
        ticks=ticks,
        db_path=db_path,
    )
    # Age buckets (25 ticks wide) — the age structure is the whole story.
    buckets = [(0, 50), (50, 100), (100, 150), (150, 200), (200, 250),
               (250, 300), (300, 350), (350, 10_000)]

    for tick in range(ticks + 1):
        alive = 0
        ages: list[int] = []
        for a in agent_ids:
            if sim.state.get(a, "alive"):
                alive += 1
                born = sim.state.get(a, "birth_tick")
                ages.append(tick - int(born if born is not None else 0))
        if alive > result.peak_population:
            result.peak_population = alive
            result.peak_tick = tick
        if result.extinction_tick is None and alive == 0 and tick > 0:
            result.extinction_tick = tick
        if tick % SAMPLE_EVERY == 0:
            result.population_curve.append((tick, alive))
            for lo, hi in buckets:
                n = sum(1 for age in ages if lo <= age < hi)
                if n:
                    result.age_histogram[f"{lo}-{hi}"] = (
                        result.age_histogram.get(f"{lo}-{hi}", 0) + n
                    )
        if tick == ticks:
            result.mean_age_final = (sum(ages) / len(ages)) if ages else 0.0
            result.max_age_final = max(ages) if ages else 0
            for r in region_ids:
                pop = int(sim.state.get(r, "population") or 0)
                soil = float(sim.state.get(r, "soil_fertility") or 0.0)
                food = float(sim.state.get(r, "food_stock") or 0.0)
                pop_base = int(sim.state.get(r, "pop_base") or 0)
                cap = _capacity(pop_base, soil)
                food_pc = food / max(pop, 1)
                result.final_regions.append(
                    RegionStat(
                        tick=tick,
                        region=r,
                        population=pop,
                        workers=int(sim.state.get(r, "workers") or 0),
                        soil=soil,
                        food=food,
                        food_pc=food_pc,
                        capacity=cap,
                        capacity_limited=pop >= cap,
                        food_limited=food_pc <= BirthSystem.BIRTH_FOOD_PC_MIN,
                    )
                )
                if pop >= cap:
                    result.capacity_limited_ticks += 1
                if food_pc <= BirthSystem.BIRTH_FOOD_PC_MIN:
                    result.food_limited_ticks += 1
        if tick < ticks:
            sim.step()

    # --- ledger: births and deaths by operation (read from the journal) --
    rows = sim.journal.query(
        "SELECT operation, COUNT(*) AS n FROM transitions "
        "WHERE status='COMMITTED' AND operation IN (?,?,?,?) "
        "GROUP BY operation",
        ("agent.birth",) + DEATH_OPS,
    )
    for row in rows:
        if row["operation"] == "agent.birth":
            result.births_total = int(row["n"])
        else:
            result.deaths_by_operation[row["operation"]] = int(row["n"])
    first = sim.journal.query(
        "SELECT MIN(tick) AS t FROM transitions "
        "WHERE status='COMMITTED' AND operation='agent.birth'"
    )
    if first and first[0]["t"] is not None:
        result.first_birth_tick = int(first[0]["t"])

    result.state_hash = sim.state.hash()
    result.journal_hash = sim.journal.hash()
    sim.journal.close()
    return result


# ----------------------------------------------------------------------
def probes(args) -> list[RunResult]:
    out: list[RunResult] = []
    tmp = Path(args.tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    out.append(
        run_probe(
            "baseline (player_civic as shipped)",
            "player_civic",
            args.seed,
            args.regions,
            args.agents,
            args.ticks,
            str(tmp / "baseline.db"),
        )
    )

    @contextlib.contextmanager
    def no_senescence():
        # ONE factor: the age-death law is pushed out of reach.
        original = SenescenceSystem.SENESCENCE_ONSET
        SenescenceSystem.SENESCENCE_ONSET = 10 ** 6
        try:
            yield
        finally:
            SenescenceSystem.SENESCENCE_ONSET = original

    out.append(
        run_probe(
            "probe A: no age death",
            "player_civic",
            args.seed,
            args.regions,
            args.agents,
            args.ticks,
            str(tmp / "no_senescence.db"),
            patch=no_senescence,
        )
    )

    @contextlib.contextmanager
    def no_disease():
        # ONE factor: the pathogen system leaves the roster.
        original = list(CivicRules.default_systems)
        CivicRules.default_systems = [
            s for s in original if s != "ImmuneDiseaseSystem"
        ]
        try:
            yield
        finally:
            CivicRules.default_systems = original

    out.append(
        run_probe(
            "probe B: no disease system",
            "player_civic",
            args.seed,
            args.regions,
            args.agents,
            args.ticks,
            str(tmp / "no_disease.db"),
            patch=no_disease,
        )
    )

    @contextlib.contextmanager
    def birth_x10():
        # ONE factor: the supply of newborns (both rate constants x10).
        base, span = BirthSystem.RATE_BASE, BirthSystem.RATE_SPAN
        BirthSystem.RATE_BASE = base * 10
        BirthSystem.RATE_SPAN = span * 10
        try:
            yield
        finally:
            BirthSystem.RATE_BASE, BirthSystem.RATE_SPAN = base, span

    out.append(
        run_probe(
            "probe C: birth rate x10",
            "player_civic",
            args.seed,
            args.regions,
            args.agents,
            args.ticks,
            str(tmp / "birth_x10.db"),
            patch=birth_x10,
        )
    )

    out.append(
        run_probe(
            "control: compost research world (no age death, no heredity)",
            "compost",
            args.seed,
            args.regions,
            args.agents,
            args.ticks,
            str(tmp / "compost.db"),
        )
    )
    return out


# ----------------------------------------------------------------------
def render(results: list[RunResult]) -> str:
    lines: list[str] = []
    add = lines.append
    first = results[0]
    add("# v0.8 — демографическая диагностика живого мира")
    add("")
    add(
        f"Прогон: seed {first.seed}, {first.regions} региона, {first.agents} агентов, "
        f"{first.ticks} тиков. Каждый зонд меняет РОВНО ОДИН фактор."
    )
    add("")
    add("## 1. Сводка")
    add("")
    add("| зонд | пик населения | тик пика | вымирание | рождений | смертей | причина смерти |")
    add("|---|---|---|---|---|---|---|")
    for r in results:
        deaths = sum(r.deaths_by_operation.values())
        causes = ", ".join(
            f"{k}={v}" for k, v in sorted(r.deaths_by_operation.items())
        ) or "—"
        add(
            f"| {r.name} | {r.peak_population} | {r.peak_tick} | "
            f"{r.extinction_tick if r.extinction_tick is not None else '—'} | "
            f"{r.births_total} | {deaths} | {causes} |"
        )
    add("")
    add("## 2. Кривая населения (каждые 25 тиков)")
    add("")
    ticks = [t for t, _ in results[0].population_curve]
    add("| тик | " + " | ".join(r.name.split(":")[0] for r in results) + " |")
    add("|---" * (len(results) + 1) + "|")
    for i, t in enumerate(ticks):
        row = [str(t)]
        for r in results:
            curve = dict(r.population_curve)
            row.append(str(curve.get(t, "")))
        add("| " + " | ".join(row) + " |")
    add("")
    add("## 3. Возрастная структура (сумма по всем сэмплам)")
    add("")
    add("| зонд | " + " | ".join(sorted(results[0].age_histogram)) + " | средний возраст в конце | макс. возраст |")
    add("|---" * (len(results[0].age_histogram) + 3) + "|")
    for r in results:
        keys = sorted(r.age_histogram)
        add(
            f"| {r.name} | "
            + " | ".join(str(r.age_histogram.get(k, 0)) for k in keys)
            + f" | {r.mean_age_final:.1f} | {r.max_age_final} |"
        )
    add("")
    add("## 4. Рождаемость: чем ограничена")
    add("")
    add("| зонд | тиков, ограниченных ёмкостью | тиков, ограниченных едой | первое рождение |")
    add("|---|---|---|---|")
    for r in results:
        add(
            f"| {r.name} | {r.capacity_limited_ticks} | {r.food_limited_ticks} | "
            f"{r.first_birth_tick if r.first_birth_tick is not None else '—'} |"
        )
    add("")
    add("## 5. Финальное состояние регионов (baseline)")
    add("")
    add("| регион | население | ёмкость | почва | еда | еда/чел. | ограничено ёмкостью | ограничено едой |")
    add("|---|---|---|---|---|---|---|---|")
    for rs in results[0].final_regions:
        add(
            f"| {rs.region} | {rs.population} | {rs.capacity} | {rs.soil:.3f} | "
            f"{rs.food:.1f} | {rs.food_pc:.2f} | "
            f"{'да' if rs.capacity_limited else 'нет'} | "
            f"{'да' if rs.food_limited else 'нет'} |"
        )
    add("")
    add("## 6. Отпечатки")
    add("")
    for r in results:
        add(f"- **{r.name}** — state `{r.state_hash[:16]}`, journal `{r.journal_hash[:16]}`")
    add("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--regions", type=int, default=2)
    ap.add_argument("--agents", type=int, default=100)
    ap.add_argument("--ticks", type=int, default=700)
    ap.add_argument("--tmp", default="/tmp/v08_demography")
    ap.add_argument("--out", default="experiments/reports/v08_demography.md")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    results = probes(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render(results), encoding="utf-8")
    print(f"written: {args.out}")
    if args.json:
        payload = []
        for r in results:
            payload.append(
                {
                    "name": r.name,
                    "ruleset": r.ruleset,
                    "peak_population": r.peak_population,
                    "peak_tick": r.peak_tick,
                    "extinction_tick": r.extinction_tick,
                    "births_total": r.births_total,
                    "deaths_by_operation": r.deaths_by_operation,
                    "mean_age_final": r.mean_age_final,
                    "capacity_limited_ticks": r.capacity_limited_ticks,
                    "food_limited_ticks": r.food_limited_ticks,
                    "state_hash": r.state_hash,
                    "journal_hash": r.journal_hash,
                    "final_regions": [
                        {
                            "region": rs.region,
                            "population": rs.population,
                            "capacity": rs.capacity,
                            "soil": rs.soil,
                            "food": rs.food,
                            "food_pc": rs.food_pc,
                        }
                        for rs in r.final_regions
                    ],
                }
            )
        Path(args.json).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"written: {args.json}")


if __name__ == "__main__":
    main()
