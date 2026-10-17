#!/usr/bin/env python3
"""v0.10 — the effect does not live in one regime.

The v0.9 grid showed the same order protocol helping a degrading world
and doing nothing in a saturated one. That is an important boundary, but
it was found POST HOC: the grid was not built to contain regimes, so the
"0 trade-offs" claim described the corner of the parameter space where
the mechanism happens to work.

This experiment does what the review asked: it MEASURES the regime of
every baseline world before comparing anything, then reports the effect
inside each regime:

    degradation  the baseline is losing people over the measured window;
    saturation   the baseline holds, but its cells are at the capacity
                 line (the birth law refuses to grow);
    equilibrium  the baseline holds with room to spare.

Regime is read from the BASELINE only (the world with no orders): a
world is not classified by the intervention it receives. The protocol
is then applied to the paired world with the same seed and density, and
the effect is reported per regime.

The measurement also separates the two kinds of improvement the review
named: births and deaths are the same population seen twice, so the
report gives the strict per-run deltas plus the deaths that were
STARVATION deaths (hunger at the last living tick above the starvation
threshold), not just "fewer deaths".

Usage:
    python3 experiments/v010_regimes.py --ticks 600 \\
        --out experiments/reports/v010_regimes.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.player import DecisionChannel, attach_player_channel  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.systems.directive import (  # noqa: E402
    DIRECTIVE_AMEND,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset  # noqa: E402

ORDER_CELLS = ("cell:1:0", "cell:1:1", "cell:1:2", "cell:1:3")
AMEND_AT = (20, 21, 22, 23)
WATER_AT = (24, 25, 26, 27)
AMEND_VALUE = 0.15
WATER_VALUE = 1.0

#: When the regime is read (before the world has settled into its end
#: state) and the window over which it is measured.
REGIME_AT = 300
REGIME_FROM = 120
#: starvation threshold of the spatial world (its agent law)
STARVATION = 0.75


@dataclass
class Run:
    seed: int
    agents: int
    condition: str
    alive: int = 0
    alive_early: int = 0
    births: int = 0
    deaths: int = 0
    starvation_deaths: int = 0
    extinct_cells: int = 0
    mean_soil: float = 0.0
    capacity: float = 0.0
    saturation: float = 0.0
    regime: str = ""
    cells_at_capacity: int = 0


def run_one(seed: int, agents: int, condition: str, ticks: int) -> Run:
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_spatial"), ticks=0,
        regions=2, agents=agents,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (ticks + 10)))
    channel = DirectiveChannel()
    for system in sim.systems:
        if isinstance(system, DirectiveSystem):
            system.channel = channel
    if condition == "decrees":
        for tick, cell in zip(AMEND_AT, ORDER_CELLS):
            channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, AMEND_VALUE))
        for tick, cell in zip(WATER_AT, ORDER_CELLS):
            channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, WATER_VALUE))

    result = Run(seed=seed, agents=agents, condition=condition)
    hunger: dict[str, float] = {}
    for tick in range(ticks + 1):
        if tick:
            before = {
                a: bool(sim.state.get(a, "alive"))
                for a in sim.state.entities_with_prefix("agent:")
            }
            sim.step()
            for agent, was_alive in before.items():
                if was_alive and not sim.state.get(agent, "alive"):
                    if hunger.get(agent, 0.0) >= STARVATION:
                        result.starvation_deaths += 1
        if tick == REGIME_FROM or tick == REGIME_AT:
            alive = sum(
                1 for a in sim.state.entities_with_prefix("agent:")
                if sim.state.get(a, "alive")
            )
            if tick == REGIME_FROM:
                result.alive_early = alive
        for agent in sim.state.entities_with_prefix("agent:"):
            if sim.state.get(agent, "alive"):
                hunger[agent] = float(sim.state.get(agent, "hunger") or 0.0)

    st = sim.state
    cells = sorted(st.entities_with_prefix("cell:"))
    result.alive = sum(
        1 for a in st.entities_with_prefix("agent:") if st.get(a, "alive")
    )
    result.capacity = sum(
        int(st.get(c, "pop_base")) * (1.0 + float(st.get(c, "soil_fertility")))
        for c in cells
    )
    result.saturation = result.alive / max(result.capacity, 1e-9)
    result.cells_at_capacity = sum(
        1 for c in cells
        if int(st.get(c, "population")) >= int(st.get(c, "pop_base"))
        * (1.0 + float(st.get(c, "soil_fertility")))
    )
    result.mean_soil = sum(
        float(st.get(c, "soil_fertility")) for c in cells
    ) / max(len(cells), 1)
    result.extinct_cells = sum(
        1 for c in cells if int(st.get(c, "population")) == 0
    )
    for transition in sim.journal:
        if transition.status.value != "COMMITTED":
            continue
        if transition.operation == "agent.birth":
            result.births += 1
        elif any(
            w.entity.startswith("agent:") and w.field == "alive"
            and w.new is False
            for w in transition.writes
        ):
            # Every way a life ends (hunger, disease, senescence).
            result.deaths += 1

    if result.alive <= 0.85 * max(result.alive_early, 1):
        result.regime = "degradation"
    elif result.saturation >= 0.85:
        # The baseline ends at the capacity line: the birth law has
        # little room left, so a lever that only lifts births cannot do
        # much here. This is the regime's OUTCOME, not a prediction.
        result.regime = "saturation"
    else:
        result.regime = "equilibrium"
    return result


def analyse(runs: list[Run]) -> dict:
    by_key = {(r.seed, r.agents, r.condition): r for r in runs}
    pairs = []
    for (seed, agents, condition) in sorted(by_key):
        if condition != "decrees":
            continue
        base = by_key[(seed, agents, "baseline")]
        dec = by_key[(seed, agents, "decrees")]
        pairs.append({
            "seed": seed, "agents": agents,
            "regime": base.regime,
            "base": _row(base), "dec": _row(dec),
            "delta": {
                "alive": dec.alive - base.alive,
                "births": dec.births - base.births,
                "deaths": dec.deaths - base.deaths,
                "starvation_deaths":
                    dec.starvation_deaths - base.starvation_deaths,
                "mean_soil": round(dec.mean_soil - base.mean_soil, 4),
                "extinct_cells": dec.extinct_cells - base.extinct_cells,
            },
        })
    regimes = {}
    for pair in pairs:
        bucket = regimes.setdefault(pair["regime"], [])
        bucket.append(pair)
    summary = {}
    for regime, group in sorted(regimes.items()):
        keys = ("alive", "births", "deaths", "starvation_deaths",
                "mean_soil", "extinct_cells")
        summary[regime] = {
            "n": len(group),
            "delta": {
                key: {
                    "positive": sum(1 for p in group if p["delta"][key] > 0),
                    "zero": sum(1 for p in group if p["delta"][key] == 0),
                    "negative": sum(1 for p in group if p["delta"][key] < 0),
                    "mean": round(sum(p["delta"][key] for p in group)
                                  / len(group), 4),
                }
                for key in keys
            },
        }
    return {"pairs": pairs, "by_regime": summary}


def _row(run: Run) -> dict:
    return {
        "alive": run.alive, "births": run.births, "deaths": run.deaths,
        "starvation_deaths": run.starvation_deaths,
        "mean_soil": round(run.mean_soil, 4),
        "extinct_cells": run.extinct_cells,
        "capacity": round(run.capacity, 1),
        "saturation": round(run.saturation, 3),
        "cells_at_capacity": run.cells_at_capacity,
        "regime": run.regime,
    }


def _points(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "точка"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "точки"
    return "точек"


def render(report: dict, args) -> str:
    lines = []
    a = lines.append
    a("# v0.10 — эффект по режимам мира, а не по удачной точке")
    a("")
    a(f"Сетка: seeds {', '.join(map(str, args.seeds))}; старт "
      f"{', '.join(map(str, args.agents))}; горизонт {args.ticks}. "
      f"Режим читается по ИТОГУ базового мира (без приказов) на "
      f"горизонте {args.ticks}: падение ≥ 15 % — degradation, итоговое "
      f"насыщение ≥ 85 % — saturation, иначе equilibrium; при одних и "
      f"тех же seed/численности второй мир получает один и тот же "
      f"протокол.")
    a("")
    a("| seed | старт | режим | живых база→приказы | рождений | смертей | "
      "из них голодных | почва | занято ёмкости |")
    a("|---:|---:|---|---|---:|---:|---:|---:|---:|")
    for p in report["analysis"]["pairs"]:
        b, d = p["base"], p["dec"]
        a(f"| {p['seed']} | {p['agents']} | {p['regime']} | "
          f"{b['alive']} → {d['alive']} | {b['births']} → {d['births']} | "
          f"{b['deaths']} → {d['deaths']} | "
          f"{b['starvation_deaths']} → {d['starvation_deaths']} | "
          f"{b['mean_soil']:.3f} → {d['mean_soil']:.3f} | "
          f"{b['saturation']:.0%} → {d['saturation']:.0%} |")
    a("")
    a("## По режимам")
    a("")
    a("Δ = (с приказами) − (без приказов). Для смертей и вымерших клеток "
      "отрицательное Δ — улучшение.")
    a("")
    a("| режим | точек | показатель | Δ>0 | Δ=0 | Δ<0 | средний Δ |")
    a("|---|---:|---|---:|---:|---:|---:|")
    for regime, block in report["analysis"]["by_regime"].items():
        for key, counts in block["delta"].items():
            a(f"| {regime} | {block['n']} | {key} | {counts['positive']} | "
              f"{counts['zero']} | {counts['negative']} | "
              f"{counts['mean']:+.3f} |")
    a("")
    a("\* «Голодная смерть» — прокси: смерть агента, у которого на "
      "последнем живом тике голод был выше порога мира (0.75). Ядро не "
      "хранит причину смерти в переходе, поэтому это атрибуция по "
      "состоянию, а не доказанная причина; отчёт называет её прокси.")
    a("")
    a("## Что это меняет в выводе v0.9")
    a("")
    summary = report["analysis"]["by_regime"]
    for regime, block in summary.items():
        alive = block["delta"]["alive"]["mean"]
        births = block["delta"]["births"]["mean"]
        a(f"- **{regime}** ({block['n']} {_points(block['n'])}): "
          f"средний Δ живых {alive:+.1f}, рождений {births:+.1f}.")
    a("")
    a("| режим | точек | средний Δ живых | средний Δ рождений |")
    a("|---|---:|---:|---:|")
    for regime, block in summary.items():
        a(f"| {regime} | {block['n']} | "
          f"{block['delta']['alive']['mean']:+.1f} | "
          f"{block['delta']['births']['mean']:+.1f} |")
    a("")
    saturation = summary.get("saturation")
    if saturation and saturation["delta"]["alive"]["mean"] < 5:
        a("В v0.9 «0 обменов из 9» звучало как свойство закона. Здесь "
          "видно, что это свойство КОРЗИНЫ точек: в режиме насыщения "
          "протокол почти ничего не меняет (средний Δ живых "
          f"{saturation['delta']['alive']['mean']:+.1f}), и «нет обменов» "
          "там означает не «всё хорошо», а «воздействия почти нет».")
    a("")
    a("Отсюда правило для интерфейса: приказ должен показывать не только "
      "эффект, но и режим мира, в котором он применён. Один и тот же "
      "рычаг — это лечение в деградации и трата в насыщении.")
    a("")
    a("## Честные ограничения")
    a("")
    a("- Режим — это ИТОГ базового мира на горизонте (падение ≥ 15 % → "
      "degradation; итоговое насыщение ≥ 85 % → saturation; иначе "
      "equilibrium), а не прогноз и не свойство seed. Смена порога "
      "перегруппирует точки, и таблица выше даёт для этого все числа.")
    a("- Сетка остаётся сеткой (несколько точек), а не статистикой.")
    a("- Голодная смерть — прокси по голоду на последнем живом тике, "
      "а не причина из перехода: смерть от инфекции при голоде тоже "
      "попадёт в счётчик.")
    a("- Протокол всё ещё один; меняются seed, старт и режим, но не сила "
      "приказа.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="7,11,23,31")
    parser.add_argument("--agents", default="36,54,72")
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    args.seeds = [int(x) for x in str(args.seeds).split(",")]
    args.agents = [int(x) for x in str(args.agents).split(",")]

    runs = []
    for seed in args.seeds:
        for agents in args.agents:
            for condition in ("baseline", "decrees"):
                run = run_one(seed, agents, condition, args.ticks)
                runs.append(run)
                print(f"seed {seed:>2} agents {agents:>3} {condition:>8}: "
                      f"alive {run.alive:>3} births {run.births:>3} "
                      f"deaths {run.deaths:>3} "
                      f"starv {run.starvation_deaths:>3} "
                      f"soil {run.mean_soil:.3f} sat {run.saturation:.2f} "
                      f"[{run.regime}]", flush=True)

    report = {
        "config": vars(args),
        "runs": [r.__dict__ for r in runs],
        "analysis": analyse(runs),
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
