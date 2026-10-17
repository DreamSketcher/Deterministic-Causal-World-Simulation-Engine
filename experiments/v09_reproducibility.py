#!/usr/bin/env python3
"""v0.9 — does the intervention survive a change of starting conditions?

The v0.8 slice measured ONE world (seed 7, 54 agents) and compared it
with a run of the same world without orders. That is an experiment; it is
not yet evidence that the effect is a property of the law rather than of
that one draw. This script asks the review's question:

    does the same intervention produce the same SIGN of effect across
    several seeds and several starting populations, and does it ever
    improve one measure while worsening another?

It runs a small, explicit grid (3 seeds x 3 populations x 2 conditions),
with the SAME order protocol in every decreed run — the protocol from the
v0.8 slice: amend 0.15 on the four cells of the poor region over ticks
20-23, irrigation 1.0 over ticks 24-27. One factor, one protocol, no
per-seed tuning: tuning each world until it survives would prove nothing.

The report also measures the CEILING, which the review named as the main
limit of v0.8: a cell cannot grow past ``pop_base * (1 + soil)``, so the
first question about any demographic lever is whether the world is
already at that line. A second probe runs 100 ticks of nursery in every
cell of a saturated world and reports how many births it bought.

Usage:
    python3 experiments/v09_reproducibility.py --ticks 600 \\
        --out experiments/reports/v09_reproducibility.md
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
    DIRECTIVE_AMEND,
    DIRECTIVE_NURSERY,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset  # noqa: E402

#: The v0.8 order protocol, unchanged: four cells of the poor region.
ORDER_CELLS = ("cell:1:0", "cell:1:1", "cell:1:2", "cell:1:3")
AMEND_AT = (20, 21, 22, 23)
WATER_AT = (24, 25, 26, 27)
AMEND_VALUE = 0.15
WATER_VALUE = 1.0


@dataclass
class Run:
    seed: int
    agents: int
    condition: str
    horizon: int
    alive: int = 0
    peak: int = 0
    births: int = 0
    deaths: int = 0
    starvations: int = 0
    extinct_cells: int = 0
    mean_soil: float = 0.0
    mean_food_pc: float = 0.0
    capacity: float = 0.0
    saturation: float = 0.0
    cells_at_capacity: int = 0
    per_cell: dict = field(default_factory=dict)


def _build(seed: int, agents: int):
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_spatial"), ticks=0,
        regions=2, agents=agents,
    )
    channel = DirectiveChannel()
    for system in sim.systems:
        if isinstance(system, DirectiveSystem):
            system.channel = channel
    return sim, channel


def _schedule(channel, condition: str, ticks: int):
    if condition != "decrees":
        return
    for tick, cell in zip(AMEND_AT, ORDER_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, AMEND_VALUE))
    for tick, cell in zip(WATER_AT, ORDER_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, WATER_VALUE))


def _harvest(sim, run: Run, ticks: int) -> None:
    """Count births and deaths from the committed transitions."""
    for transition in sim.journal:
        if transition.status.value != "COMMITTED":
            continue
        if transition.operation == "agent.birth":
            run.births += 1
        elif transition.operation == "agent.death":
            for write in transition.writes:
                if write.field == "alive" and write.new is False:
                    run.deaths += 1
                    break

    st = sim.state
    cells = sorted(st.entities_with_prefix("cell:"))
    populations = []
    soils = []
    food_pcs = []
    capacity_total = 0.0
    at_capacity = 0
    for cell in cells:
        population = int(st.get(cell, "population") or 0)
        soil = float(st.get(cell, "soil_fertility") or 0.0)
        food = float(st.get(cell, "food_stock") or 0.0)
        pop_base = int(st.get(cell, "pop_base") or 0)
        cap = pop_base * (1.0 + soil)
        populations.append(population)
        soils.append(soil)
        food_pcs.append(food / max(population, 1))
        capacity_total += cap
        if population >= cap:
            at_capacity += 1
        run.per_cell[cell] = {
            "population": population,
            "soil": round(soil, 4),
            "food_pc": round(food / max(population, 1), 3),
            "capacity": round(cap, 2),
        }
    alive = sum(
        1 for a in st.entities_with_prefix("agent:") if st.get(a, "alive")
    )
    run.alive = alive
    run.extinct_cells = sum(1 for p in populations if p == 0)
    run.mean_soil = sum(soils) / max(len(soils), 1)
    run.mean_food_pc = sum(food_pcs) / max(len(food_pcs), 1)
    run.capacity = capacity_total
    run.saturation = alive / max(capacity_total, 1e-9)
    run.cells_at_capacity = at_capacity


def run_one(seed: int, agents: int, condition: str, ticks: int) -> Run:
    sim, channel = _build(seed, agents)
    _schedule(channel, condition, ticks)
    result = Run(seed=seed, agents=agents, condition=condition, horizon=ticks)
    for tick in range(ticks + 1):
        if tick:
            sim.step()
        alive = sum(
            1 for a in sim.state.entities_with_prefix("agent:")
            if sim.state.get(a, "alive")
        )
        result.peak = max(result.peak, alive)
    _harvest(sim, result, ticks)
    return result


def capacity_probe(seed: int, agents: int, ticks: int) -> dict:
    """What does the nursery buy in a world that is already full?

    Runs the measured protocol to a saturated horizon, then switches the
    nursery ON in every cell for the last 100 ticks and counts births.
    The control is the same world with the nursery left OFF. Same seed,
    same orders, one difference — the rule the repo runs on.
    """
    out = {}
    for condition in ("probe_off", "probe_on"):
        sim, channel = _build(seed, agents)
        _schedule(channel, "decrees", ticks)
        for tick in range(ticks + 1):
            if tick:
                sim.step()
        capacity = sum(
            int(sim.state.get(c, "pop_base"))
            * (1.0 + float(sim.state.get(c, "soil_fertility")))
            for c in sim.state.entities_with_prefix("cell:")
        )
        alive = sum(
            1 for a in sim.state.entities_with_prefix("agent:")
            if sim.state.get(a, "alive")
        )
        births = 0
        if condition == "probe_on":
            # The nursery is enacted on the FIRST probe tick: the law is
            # read from the snapshot of that tick, so the policy is in
            # force for the whole window (not one tick late).
            for cell in sim.state.entities_with_prefix("cell:"):
                channel.schedule(sim.state.tick,
                                 Directive(DIRECTIVE_NURSERY, cell, 1.0))
        for tick in range(100):
            sim.step()
        for transition in sim.journal:
            # ONLY the probe window: the births of the run that led to the
            # saturated world must not be counted as what the nursery
            # bought after it.
            if (transition.status.value == "COMMITTED"
                    and transition.operation == "agent.birth"
                    and transition.tick >= ticks):
                births += 1
        out[condition] = {
            "alive_at_start": alive,
            "capacity": round(capacity, 2),
            "saturation": round(alive / max(capacity, 1e-9), 3),
            "births_in_100_ticks": births,
        }
    out["births_bought"] = (
        out["probe_on"]["births_in_100_ticks"]
        - out["probe_off"]["births_in_100_ticks"]
    )
    return out


# ----------------------------------------------------------------------
def analyse(runs: list[Run]) -> dict:
    """The sign of the effect, pair by pair, and the trade-offs."""
    by_key = {(r.seed, r.agents, r.condition): r for r in runs}
    pairs = []
    for (seed, agents, condition) in sorted(by_key):
        if condition != "decrees":
            continue
        base = by_key[(seed, agents, "baseline")]
        dec = by_key[(seed, agents, "decrees")]
        deltas = {
            "alive": dec.alive - base.alive,
            "births": dec.births - base.births,
            "deaths": dec.deaths - base.deaths,
            "mean_soil": round(dec.mean_soil - base.mean_soil, 4),
            "extinct_cells": dec.extinct_cells - base.extinct_cells,
        }
        tradeoffs = []
        if deltas["alive"] > 0 and deltas["mean_soil"] < 0:
            tradeoffs.append("живых больше, почвы меньше")
        if deltas["alive"] > 0 and deltas["deaths"] > 0:
            tradeoffs.append("живых больше, смертей больше")
        if deltas["births"] > 0 and deltas["mean_soil"] < 0:
            tradeoffs.append("рождений больше, почвы меньше")
        pairs.append({
            "seed": seed, "agents": agents,
            "baseline": _row(base), "decrees": _row(dec),
            "delta": deltas, "tradeoffs": tradeoffs,
        })

    def sign(key):
        values = [p["delta"][key] for p in pairs]
        return {
            "positive": sum(1 for v in values if v > 0),
            "zero": sum(1 for v in values if v == 0),
            "negative": sum(1 for v in values if v < 0),
            "mean": round(sum(values) / len(values), 4) if values else 0.0,
        }

    return {
        "pairs": pairs,
        "sign": {k: sign(k) for k in
                 ("alive", "births", "deaths", "mean_soil", "extinct_cells")},
        "tradeoff_pairs": sum(1 for p in pairs if p["tradeoffs"]),
        "total_pairs": len(pairs),
    }


def _row(run: Run) -> dict:
    return {
        "alive": run.alive, "births": run.births, "deaths": run.deaths,
        "mean_soil": round(run.mean_soil, 4),
        "extinct_cells": run.extinct_cells,
        "cells_at_capacity": run.cells_at_capacity,
        "saturation": round(run.saturation, 3),
    }


def render(report: dict, args) -> str:
    lines = []
    a = lines.append
    a("# v0.9 — воспроизводимость вмешательства и потолок ёмкости")
    a("")
    a(f"Сетка: seeds {', '.join(map(str, args.seeds))}; "
      f"стартовое население {', '.join(map(str, args.agents))}; "
      f"горизонт {args.ticks} тиков; 2 условия на точку "
      f"(без приказов / один и тот же протокол приказов).")
    a("")
    a("Протокол приказов одинаков во всех мирах: `amend 0.15` на четырёх "
      "клетках бедного региона в тики 20–23 и `water 1.0` в тики 24–27. "
      "Никакой подстройки под seed.")
    a("")
    a("## Таблица")
    a("")
    a("| seed | старт | условие | живых | рождений | смертей | клеток вымерло | средняя почва | ёмкость занята |")
    a("|---:|---:|---|---:|---:|---:|---:|---:|---:|")
    for p in report["analysis"]["pairs"]:
        for cond in ("baseline", "decrees"):
            row = p[cond]
            a(f"| {p['seed']} | {p['agents']} | {cond} | {row['alive']} | "
              f"{row['births']} | {row['deaths']} | {row['extinct_cells']} | "
              f"{row['mean_soil']:.3f} | {row['saturation']:.2f} |")
    a("")
    a("## Знак эффекта")
    a("")
    a("Δ = (с приказами) − (без приказов). Для смертей и вымерших клеток "
      "отрицательное Δ — улучшение; для остальных — ухудшение. Знак "
      "считается по всем 9 точкам сетки.")
    a("")
    a("| показатель | Δ>0 | Δ=0 | Δ<0 | средний Δ |")
    a("|---|---:|---:|---:|---:|")
    for name, s in report["analysis"]["sign"].items():
        a(f"| {name} | {s['positive']} | {s['zero']} | {s['negative']} | "
          f"{s['mean']:+.3f} |")
    a("")
    tradeoffs = [p for p in report["analysis"]["pairs"] if p["tradeoffs"]]
    a(f"## Обмены (улучшили одно — ухудшили другое): "
      f"{len(tradeoffs)} из {report['analysis']['total_pairs']}")
    a("")
    if tradeoffs:
        for p in tradeoffs:
            a(f"- seed {p['seed']}, старт {p['agents']}: "
              f"{'; '.join(p['tradeoffs'])}")
    else:
        a("- Ни в одной точке протокол не улучшил один показатель ценой "
          "другого — но это и не означает, что цена нулевая: смотрите "
          "строгие Δ в таблице.")
    a("")
    a("## Где эффекта нет — и почему это важно")
    a("")
    saturated = [
        p for p in report["analysis"]["pairs"]
        if p["baseline"]["saturation"] >= 0.85
        and p["delta"]["alive"] <= 2
    ]
    if saturated:
        for p in saturated:
            a(f"- seed {p['seed']}, старт {p['agents']}: базовый мир уже "
              f"занимает {p['baseline']['saturation']:.0%} ёмкости "
              f"({p['baseline']['alive']} из "
              f"{p['baseline']['alive'] / max(p['baseline']['saturation'], 1e-9):.0f}) "
              f"и не теряет людей; приказы дают "
              f"Δ живых {p['delta']['alive']:+d}, Δ почвы "
              f"{p['delta']['mean_soil']:+.3f}.")
        a("")
        a("Это не опровержение эффекта, а его граница: протокол спасает "
          "мир, который терял людей. В мире, уже стоящем на потолке "
          "ёмкости, спасать некого — там нужна политика ёмкости, а не "
          "политика выживания. Игра должна показывать эту разницу, иначе "
          "игрок будет применять один и тот же приказ к любой проблеме.")
        a("")
    a("## Потолок ёмкости")
    a("")
    probe = report["capacity_probe"]
    a(f"Мир после протокола (seed {args.probe_seed}, старт "
      f"{args.probe_agents}, {args.ticks} тиков) заполнен на "
      f"{probe['probe_off']['saturation']:.0%} ёмкости "
      f"({probe['probe_off']['alive_at_start']} из "
      f"{probe['probe_off']['capacity']:.0f}).")
    a("")
    a("| 100 тиков | ясли выкл | ясли 1.0 во всех клетках |")
    a("|---|---:|---:|")
    a(f"| рождений | {probe['probe_off']['births_in_100_ticks']} | "
      f"{probe['probe_on']['births_in_100_ticks']} |")
    a("")
    a(f"**Ясли купили {probe['births_bought']:+d} рождений за 100 тиков "
      f"насыщенного мира (из "
      f"{probe['probe_off']['births_in_100_ticks']}).**")
    a("")
    a("Это не сбой политики: закон мира запрещает зачатие, когда "
      "население клетки достигло `pop_base × (1 + soil)`. Пока ёмкость "
      "жёсткая, любой демографический рычаг упирается в неё; менять "
      "нужно не его, а саму ёмкость (переселение освобождает место, но "
      "не создаёт его).")
    a("")
    a("## Что этот прогон НЕ доказывает")
    a("")
    a("- Это сетка из нескольких точек, а не статистика: знак эффекта "
      "проверяется, величина — нет.")
    a("- Протокол приказов один и тот же; другие протоколы (сила, срок, "
      "адресат) не проверялись и не должны считаться эквивалентными.")
    a("- Ёмкость считается по формуле мира и проверяется в насыщенном "
      "мире; переходные режимы (недозаполненные клетки) ею не описаны.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="7,11,23")
    parser.add_argument("--agents", default="36,54,72")
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--probe-seed", type=int, default=7)
    parser.add_argument("--probe-agents", type=int, default=54)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    args.seeds = [int(s) for s in str(args.seeds).split(",")]
    args.agents = [int(a) for a in str(args.agents).split(",")]

    runs: list[Run] = []
    for seed in args.seeds:
        for agents in args.agents:
            for condition in ("baseline", "decrees"):
                run = run_one(seed, agents, condition, args.ticks)
                runs.append(run)
                print(f"seed {seed:>2} agents {agents:>3} {condition:>8}: "
                      f"alive {run.alive:>3}, births {run.births:>3}, "
                      f"deaths {run.deaths:>3}, soil {run.mean_soil:.3f}, "
                      f"sat {run.saturation:.2f}", flush=True)

    probe = capacity_probe(args.probe_seed, args.probe_agents, args.ticks)
    print(f"capacity probe: {probe['probe_off']['births_in_100_ticks']} vs "
          f"{probe['probe_on']['births_in_100_ticks']} births "
          f"({probe['births_bought']:+d})", flush=True)

    report = {
        "config": {
            "seeds": args.seeds,
            "agents": args.agents,
            "ticks": args.ticks,
            "protocol": {
                "amend": {"value": AMEND_VALUE, "ticks": list(AMEND_AT),
                          "cells": list(ORDER_CELLS)},
                "water": {"value": WATER_VALUE, "ticks": list(WATER_AT),
                          "cells": list(ORDER_CELLS)},
            },
        },
        "runs": [r.__dict__ for r in runs],
        "analysis": analyse(runs),
        "capacity_probe": probe,
    }

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(render(report, args), encoding="utf-8")
        print(f"written {args.out}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"written {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
