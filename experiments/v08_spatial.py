#!/usr/bin/env python3
"""v0.8 — the vertical slice, measured: the spatial world with and without
the player's laws.

The slice has four parts, and this script measures three of them:

1. **the spatial world** — a grid of cells, each with its own soil,
   food, people and law;
2. **a stable horizon** — the population must not die out at tick ~250
   the way the v0.7 world did (measured in ``v08_demography.md``);
3. **one meaningful intervention** — the player tends the cells that are
   losing their balance, and the world survives;
4. **a reproducible experiment** — the same seed, one changed decision.

Usage:
    python3 experiments/v08_spatial.py --ticks 600 \\
        --decree "20:amend:cell:1:0:0.25" --decree "20:water:cell:1:2:1.0" \\
        --out experiments/reports/v08_vertical_slice.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.systems.directive import (  # noqa: E402
    DIRECTIVE_ALL_NAMES,
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset  # noqa: E402

SAMPLE_EVERY = 25
DEATH_OPS = ("agent.death", "agent.senescence", "disease.infect")


@dataclass
class CellSample:
    tick: int
    cell: str
    population: int
    soil: float
    food: float
    food_pc: float
    balance: float


@dataclass
class RunResult:
    name: str
    ticks: int
    curve: list[tuple[int, int]] = field(default_factory=list)
    soil_curve: list[tuple[int, float]] = field(default_factory=list)
    food_curve: list[tuple[int, float]] = field(default_factory=list)
    cells: dict[str, list[CellSample]] = field(default_factory=dict)
    births: int = 0
    deaths: dict[str, int] = field(default_factory=dict)
    peak: int = 0
    peak_tick: int = 0
    extinction_tick: int | None = None
    final_alive: int = 0
    state_hash: str = ""
    journal_hash: str = ""


def _balance(sim, cell: str) -> float:
    """Harvest per capita / consumption per capita (the food balance)."""
    st = sim.state
    region = st.get(cell, "region")
    temperature = float(st.get(region, "temperature"))
    rainfall = float(st.get(region, "rainfall"))
    rain_factor = float(st.get(cell, "rain_factor"))
    soil = float(st.get(cell, "soil_fertility"))
    workers = int(st.get(cell, "workers") or 0)
    diversion = float(st.get(cell, "labor_diversion") or 0.0)
    water = float(st.get(cell, "water_aid") or 0.0)
    temp_f = max(0.0, 1.0 - abs(temperature - 14.0) / 26.0)
    rain_f = min(1.3, max(0.0, (rainfall + water * 0.25) * rain_factor / 0.55))
    harvest = 3.6 * temp_f * rain_f * soil * workers * (1.0 - diversion)
    consumption = 1.1 * max(workers, 1)
    return harvest / consumption


def run(name: str, args, decrees: list[tuple[int, str, float]]) -> RunResult:
    ruleset_name = args.ruleset
    db = str(Path(args.tmp) / f"{name}.db")
    for suffix in ("", "-wal", "-shm"):
        Path(db + suffix).unlink(missing_ok=True)

    sim = create_world(
        seed=args.seed,
        ruleset=get_ruleset(ruleset_name),
        ticks=0,
        regions=args.regions,
        agents=args.agents,
        persist=db,
    )
    channel = DirectiveChannel()
    for system in sim.systems:
        if isinstance(system, DirectiveSystem):
            system.channel = channel
    scheduled = {}
    for tick, target, param in decrees:
        kind = next(
            (k for k, n in DIRECTIVE_ALL_NAMES.items() if n == param[0]), None
        ) if isinstance(param, tuple) else None
        scheduled[tick] = (target, param)

    result = RunResult(name=name, ticks=args.ticks)
    cells = sim.state.entities_with_prefix("cell:")

    for tick in range(args.ticks + 1):
        # enact the decrees scheduled for THIS tick (the law sees them
        # from the next tick on — one coherent snapshot per tick)
        if tick in scheduled:
            target, param = scheduled[tick]
            kind = next(k for k, n in DIRECTIVE_ALL_NAMES.items() if n == param[0])
            channel.schedule(tick, Directive(kind, target, param[1]))

        alive = sum(
            1
            for a in sim.state.entities_with_prefix("agent:")
            if sim.state.get(a, "alive")
        )
        if alive > result.peak:
            result.peak = alive
            result.peak_tick = tick
        if result.extinction_tick is None and alive == 0 and tick > 0:
            result.extinction_tick = tick
        if tick % SAMPLE_EVERY == 0:
            result.curve.append((tick, alive))
            soil = [
                float(sim.state.get(c, "soil_fertility") or 0.0) for c in cells
            ]
            food = [
                float(sim.state.get(c, "food_stock") or 0.0) for c in cells
            ]
            result.soil_curve.append((tick, sum(soil) / len(soil)))
            result.food_curve.append((tick, sum(food) / len(food)))
            for c in cells:
                pop = int(sim.state.get(c, "population") or 0)
                f = float(sim.state.get(c, "food_stock") or 0.0)
                result.cells.setdefault(c, []).append(
                    CellSample(
                        tick=tick,
                        cell=c,
                        population=pop,
                        soil=float(sim.state.get(c, "soil_fertility") or 0.0),
                        food=f,
                        food_pc=f / max(pop, 1),
                        balance=_balance(sim, c),
                    )
                )
        if tick < args.ticks:
            sim.step()

    # A death is a COMMITTED write of alive -> False. Counting the
    # operation names would count infections as deaths, so the ledger is
    # read from the writes.
    births = 0
    deaths: dict[str, int] = {}
    for t in sim.journal:
        if t.status.value != "COMMITTED":
            continue
        if t.operation == "agent.birth":
            births += 1
            continue
        for w in t.writes:
            if w.field == "alive" and w.new is False:
                deaths[t.operation] = deaths.get(t.operation, 0) + 1
    result.births = births
    result.deaths = deaths
    result.final_alive = sum(
        1
        for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    )
    result.state_hash = sim.state.hash()
    result.journal_hash = sim.journal.hash()
    sim.journal.close()
    return result


def render(results: list[RunResult], args) -> str:
    lines: list[str] = []
    add = lines.append
    add("# v0.8 — вертикальный срез: пространственный мир, устойчивый горизонт, одно вмешательство")
    add("")
    add(
        f"Правила: `{args.ruleset}`, seed {args.seed}, {args.regions} региона, "
        f"{args.agents} агентов, {args.ticks} тиков."
    )
    add("")
    add("## 1. Сводка")
    add("")
    add("| прогон | пик | тик пика | живы в конце | вымирание | рождений | смерти |")
    add("|---|---|---|---|---|---|---|")
    for r in results:
        causes = ", ".join(f"{k}={v}" for k, v in sorted(r.deaths.items())) or "—"
        add(
            f"| {r.name} | {r.peak} | {r.peak_tick} | {r.final_alive} | "
            f"{r.extinction_tick if r.extinction_tick is not None else '—'} | "
            f"{r.births} | {causes} |"
        )
    add("")
    add("## 2. Население (каждые 25 тиков)")
    add("")
    ticks = [t for t, _ in results[0].curve]
    add("| тик | " + " | ".join(r.name for r in results) + " |")
    add("|---" * (len(results) + 1) + "|")
    for t in ticks:
        row = [str(t)]
        for r in results:
            row.append(str(dict(r.curve).get(t, "")))
        add("| " + " | ".join(row) + " |")
    add("")
    add("## 3. Почва и еда (средние по клеткам)")
    add("")
    add("| прогон | средняя почва (старт → конец) | средняя еда (старт → конец) |")
    add("|---|---|---|")
    for r in results:
        soil = r.soil_curve
        food = r.food_curve
        add(
            f"| {r.name} | {soil[0][1]:.3f} → {soil[-1][1]:.3f} | "
            f"{food[0][1]:.1f} → {food[-1][1]:.1f} |"
        )
    add("")
    add("## 4. Клетки (последний прогон): баланс еды = урожай/потребление")
    add("")
    last = results[-1]
    add("| клетка | население (старт → конец) | почва | еда/чел. | баланс (старт → конец) |")
    add("|---|---|---|---|---|")
    for cell, samples in last.cells.items():
        first, final = samples[0], samples[-1]
        add(
            f"| {cell} | {first.population} → {final.population} | "
            f"{final.soil:.3f} | {final.food_pc:.1f} | "
            f"{first.balance:.2f} → {final.balance:.2f} |"
        )
    add("")
    add("## 5. Отпечатки")
    add("")
    for r in results:
        add(f"- **{r.name}** — state `{r.state_hash[:16]}`, journal `{r.journal_hash[:16]}`")
    add("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--regions", type=int, default=2)
    ap.add_argument("--agents", type=int, default=54)
    ap.add_argument("--ticks", type=int, default=600)
    ap.add_argument("--ruleset", default="player_spatial")
    ap.add_argument("--tmp", default="/tmp/v08_spatial")
    ap.add_argument("--out", default="experiments/reports/v08_vertical_slice.md")
    ap.add_argument("--json", default="")
    ap.add_argument(
        "--decree",
        action="append",
        default=[],
        help="TICK:KIND:TARGET:PARAM, e.g. 20:amend:cell:1:0:0.25",
    )
    args = ap.parse_args()
    Path(args.tmp).mkdir(parents=True, exist_ok=True)

    decrees = []
    for spec in args.decree:
        # TICK:KIND:TARGET:PARAM — the target itself contains colons
        # ("cell:1:0"), so parse from both ends.
        parts = spec.split(":")
        if len(parts) < 4:
            raise SystemExit(f"bad --decree {spec!r}")
        tick = int(parts[0])
        kind = parts[1]
        param = float(parts[-1])
        target = ":".join(parts[2:-1])
        decrees.append((tick, target, (kind, param)))

    results = [run("без приказов", args, [])]
    if decrees:
        results.append(run("с приказами игрока", args, decrees))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render(results, args), encoding="utf-8")
    print(f"written: {args.out}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(
                [
                    {
                        "name": r.name,
                        "curve": r.curve,
                        "births": r.births,
                        "deaths": r.deaths,
                        "final_alive": r.final_alive,
                        "extinction_tick": r.extinction_tick,
                        "state_hash": r.state_hash,
                        "journal_hash": r.journal_hash,
                    }
                    for r in results
                ],
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"written: {args.json}")


if __name__ == "__main__":
    main()
