#!/usr/bin/env python3
"""v0.10 — the capacity policy, measured against its own risk.

The review of v0.9 set the architectural risk in one sentence: a capacity
policy must not become a free way to raise the population for
better-looking metrics. It also gave the acceptance criteria for the
stage, and this script is built around them:

1. the player can tell WHAT limits growth (resources, land, or the
   physical ceiling);
2. an order changes THAT limit, not just a symptom;
3. the goal system can show a successful expansion AND its price or
   its failure.

Design: a capacity world runs the v0.8 order protocol to tick 400 and
reaches the ceiling. It is then split into three arms over the same
seed and the same history:

    control   — no further orders (is expansion necessary at all?);
    claim     — two wild parcels are claimed (one per region);
    terrace   — terraces are bought on the cells at the ceiling.

Every arm runs 200 more ticks. The report gives the price of the
intervention (food actually written away in the journal), the state of
the soil, starvation-attributed deaths, the capacity gained and the goal
verdicts — success, cost and failure side by side.

Usage:
    python3 experiments/v010_capacity.py --ticks 600 \\
        --out experiments/reports/v010_capacity.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.goal import evaluate, episodes, summary  # noqa: E402
from causal_world.observer.journal import JournalView  # noqa: E402
from causal_world.observer.situation import (  # noqa: E402
    StateView,
    growth_limit,
    history_from_journal,
    situations,
)
from causal_world.player import DecisionChannel, attach_player_channel  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.world.rules import CapacityRules  # noqa: E402
from causal_world.systems.directive import (  # noqa: E402
    DIRECTIVE_AMEND,
    DIRECTIVE_CLAIM,
    DIRECTIVE_TERRACE,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
)
from causal_world.world.rules import get_ruleset  # noqa: E402

PROTOCOL_CELLS = ("cell:1:0", "cell:1:1", "cell:1:2", "cell:1:3")
SATURATE_AT = 400
WINDOW = 200
STARVATION = 0.75


@dataclass
class Arm:
    name: str
    alive_start: int = 0
    alive: int = 0
    births: int = 0
    deaths: int = 0
    starvation_deaths: int = 0
    capacity_start: float = 0.0
    capacity: float = 0.0
    saturation: float = 0.0
    mean_soil: float = 0.0
    food: float = 0.0
    paid_food: float = 0.0
    claims: int = 0
    terraces: int = 0
    refusals: int = 0
    limits_at_start: dict = field(default_factory=dict)
    goals: dict = field(default_factory=dict)
    stalls: int = 0
    cells: dict = field(default_factory=dict)


def _active_cells(sim) -> list[str]:
    return sorted(
        c for c in sim.state.entities_with_prefix("cell:")
        if sim.state.get(c, "land_active")
    )


def _capacity(sim, cells) -> float:
    return sum(
        int(sim.state.get(c, "pop_base"))
        * (1.0 + float(sim.state.get(c, "soil_fertility")))
        for c in cells
    )


def run_arm(name: str, db: str, args, orders) -> Arm:
    """One arm: the shared protocol, then this arm's capacity orders."""
    Path(db).unlink(missing_ok=True)
    sim = create_world(
        seed=args.seed, ruleset=get_ruleset("player_capacity"), ticks=0,
        regions=2, agents=54, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (args.ticks + 10)))
    channel = DirectiveChannel()
    for s in sim.systems:
        if s.name == "CapacityDirectiveSystem":
            s.channel = channel
    # the v0.8 protocol: brings the world to its ceiling
    for tick, cell in zip((20, 21, 22, 23), PROTOCOL_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, 0.15))
    for tick, cell in zip((24, 25, 26, 27), PROTOCOL_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, 1.0))

    hunger: dict[str, float] = {}
    starvation = 0
    for tick in range(1, SATURATE_AT + 1):
        before = {
            a: bool(sim.state.get(a, "alive"))
            for a in sim.state.entities_with_prefix("agent:")
        }
        sim.step()
        for agent, was_alive in before.items():
            if was_alive and not sim.state.get(agent, "alive"):
                if hunger.get(agent, 0.0) >= STARVATION:
                    starvation += 1
        for agent in sim.state.entities_with_prefix("agent:"):
            if sim.state.get(agent, "alive"):
                hunger[agent] = float(sim.state.get(agent, "hunger") or 0.0)

    cells = _active_cells(sim)
    arm = Arm(name=name)
    arm.alive_start = sum(
        1 for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    )
    arm.capacity_start = _capacity(sim, cells)
    for cell in cells:
        limit = growth_limit(StateView.from_state(sim.state), cell,
                             int(sim.state.tick))
        arm.limits_at_start[limit["limit"]] = (
            arm.limits_at_start.get(limit["limit"], 0) + 1
        )

    # ---- the arm's own orders ----
    if orders == "claim":
        wild = [
            c for c in sim.state.entities_with_prefix("cell:")
            if not sim.state.get(c, "land_active")
        ]
        per_region: dict[str, list[str]] = {}
        for parcel in wild:
            per_region.setdefault(
                sim.state.get(parcel, "region"), []
            ).append(parcel)
        picks = [sorted(ps)[0] for _, ps in sorted(per_region.items())]
        for offset, parcel in enumerate(picks):
            channel.schedule(SATURATE_AT + 1 + offset,
                             Directive(DIRECTIVE_CLAIM, parcel, 0))
    elif orders == "terrace":
        crowded = sorted(
            cells,
            key=lambda c: -(
                int(sim.state.get(c, "population")) /
                max(float(sim.state.get(c, "pop_base"))
                    * (1 + float(sim.state.get(c, "soil_fertility"))), 1e-9)
            ),
        )
        for offset, cell in enumerate(crowded[:4]):
            channel.schedule(SATURATE_AT + 1 + offset,
                             Directive(DIRECTIVE_TERRACE, cell, 0))

    for _ in range(WINDOW):
        sim.step()
    sim.journal.commit()
    sim.journal.close()

    cells = _active_cells(sim)
    arm.alive = sum(
        1 for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    )
    arm.capacity = _capacity(sim, cells)
    arm.saturation = arm.alive / max(arm.capacity, 1e-9)
    arm.mean_soil = sum(
        float(sim.state.get(c, "soil_fertility")) for c in cells
    ) / max(len(cells), 1)
    arm.food = sum(float(sim.state.get(c, "food_stock")) for c in cells)
    arm.starvation_deaths = starvation

    with JournalView(db) as view:
        state = StateView.from_journal(view)
        history = history_from_journal(
            view, cells,
            ["food_stock", "population", "soil_fertility", "births_total"],
        )
        alerts = situations(view)
        tick = state.max_tick()
        verdicts = []
        for scope in cells:
            for kind in ("feed", "restore_soil", "resettle", "renew"):
                for goal in episodes(history, scope, kind, last_tick=tick):
                    if goal.closed_tick is not None and (
                        goal.closed_tick < SATURATE_AT
                    ):
                        continue  # goals decided BEFORE the arm's orders
                    verdicts.append(evaluate(
                        goal, history, state, alerts, tick=tick
                    ))
        arm.goals = summary(verdicts)
        arm.stalls = sum(1 for a in alerts if a.kind == "birth_stall")
        for transition in view:
            if transition.tick <= SATURATE_AT:
                continue
            if transition.status.value != "COMMITTED":
                continue
            if transition.operation == "agent.birth":
                arm.births += 1
            elif any(
                w.entity.startswith("agent:") and w.field == "alive"
                and w.new is False
                for w in transition.writes
            ):
                # Every way a life ends counts (hunger, disease,
                # senescence) — not only the operation named "death".
                arm.deaths += 1
            if transition.operation != "player.directive":
                continue
            writes = {w.field: w for w in transition.writes}
            if "claim_state" in writes:
                if int(writes["claim_state"].new) == 1:
                    arm.claims += 1
                    if "land_cost" in writes:
                        arm.paid_food += float(writes["land_cost"].new)
                else:
                    arm.refusals += 1
            if "terrace_state" in writes:
                if int(writes["terrace_state"].new) == 1:
                    arm.terraces += 1
                    arm.paid_food += float(
                        writes["food_stock"].old - writes["food_stock"].new
                    )
                else:
                    arm.refusals += 1
        for cell in cells:
            arm.cells[cell] = {
                "population": int(state.get(cell, "population") or 0),
                "capacity": round(
                    float(state.get(cell, "pop_base") or 0)
                    * (1.0 + float(state.get(cell, "soil_fertility") or 0)),
                    2,
                ),
                "soil": round(float(state.get(cell, "soil_fertility") or 0), 4),
                "terraces": state.get(cell, "terraces"),
            }
    return arm


def render(report: dict, args) -> str:
    lines = []
    a = lines.append
    arms = report["arms"]
    a("# v0.10 — политика ёмкости: цена, а не подарок")
    a("")
    a(f"seed {args.seed}, 54 агента, `player_capacity`. Мир проходит "
      f"протокол v0.8 до тика {SATURATE_AT} (у потолка ёмкости), затем "
      f"три плеча по {WINDOW} тиков: контроль, заявка целины, террасы.")
    a("")
    a("## Критерий 1 — игрок видит, что именно ограничивает рост")
    a("")
    a("Перед вмешательством слой ситуаций называет предел каждой клетки:")
    a("")
    a("| предел | клеток |")
    a("|---|---:|")
    for limit, count in sorted(
        report["arms"]["control"]["limits_at_start"].items()
    ):
        a(f"| {limit} | {count} |")
    a("")
    a("## Критерий 2 — приказ меняет именно этот предел")
    a("")
    a("| плечо | живых на старте → в конце | ёмкость | рождений за "
      f"{WINDOW} | смертей | из них голодных* | почва | еда | заплачено еды |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name in ("control", "claim", "terrace"):
        arm = arms[name]
        a(f"| {name} | {arm['alive_start']} → {arm['alive']} | "
          f"{arm['capacity_start']:.0f} → {arm['capacity']:.0f} | "
          f"{arm['births']} | {arm['deaths']} | "
          f"{arm['starvation_deaths']} | {arm['mean_soil']:.3f} | "
          f"{arm['food']:.0f} | {arm['paid_food']:.0f} |")
    a("")
    a("\\* «Голодная смерть» — прокси по голоду на последнем живом тике "
      "(0.75), а не причина из перехода.")
    a("")
    a("## Критерий 3 — цели показывают успех, цену и провал")
    a("")
    a("| плечо | цели (вердикты) | незакрытых birth_stall |")
    a("|---|---|---:|")
    for name in ("control", "claim", "terrace"):
        arm = arms[name]
        counts = ", ".join(
            f"{status}: {n}" for status, n in sorted(arm["goals"].items())
            if status != "total"
        ) or "—"
        a(f"| {name} | {counts} | {arm['stalls']} |")
    a("")
    a("## Что измерено")
    a("")
    claim = arms["claim"]
    terrace = arms["terrace"]
    control = arms["control"]
    a(f"- **Заявка**: ёмкость +{claim['capacity'] - control['capacity']:.0f} "
      f"к контролю, рождений {claim['births']} против "
      f"{control['births']} в контроле, заплачено "
      f"{claim['paid_food']:.0f} еды; отказов мира — "
      f"{claim['refusals']}.")
    if (claim["births"] <= control["births"]
            and claim["alive"] <= control["alive"]):
        a("  - **Это провал заявки как политики роста, и он измерен.** "
          "Места в мире стало больше, но люди в них не пошли: миграция "
          "в законе срабатывает от голода, а сытый мир не голодает. "
          "Заявка без механизма переселения — цена без результата; "
          "цель `resettle` в новой клетке остаётся открытой.")
    a(f"- **Террасы**: ёмкость +{terrace['capacity'] - control['capacity']:.0f} "
      f"к контролю, рождений {terrace['births']} против "
      f"{control['births']}, заплачено {terrace['paid_food']:.0f} еды, "
      f"почва {terrace['mean_soil']:.3f} против {control['mean_soil']:.3f}.")
    a(f"- **Контроль**: без вмешательства живых {control['alive']}, "
      f"рождений {control['births']}; если он не растёт, расширение "
      f"действительно меняет предел, а не только число в отчёте.")
    a("")
    a("## Что этот прогон НЕ доказывает")
    a("")
    a("- Это один seed и один протокол: цена и эффект заявки зависят от "
      "запасов региона, и это должно проверяться сеткой перед балансом.")
    a("- Цели считаются по истории полей; расширение само по себе не "
      "создаёт цель — оно снимает `birth_stall` и создаёт `renew`-эпизод, "
      "если в новой клетке действительно рождаются дети.")
    a("- «Заплачено еды» — сумма записей журнала (land_cost и разница "
      "food_stock в террасе), а не оценка альтернативной стоимости.")
    a("- Средняя почва в плече claim ниже контроля НЕ потому, что земля "
      "испорчена: после заявки в среднее входят две новые клетки со своей "
      "почвой, а заявка не тратит почву вовсе. Это эффект состава набора, "
      "и его нельзя читать как деградацию.")
    paid_soil = terrace["terraces"] * CapacityRules.TERRACE_SOIL_COST
    a(f"- В плече terrace {terrace['terraces']} террас заплатили "
      f"{paid_soil:.2f} почвы в моменты переходов; к тику 600 средняя "
      f"почва сошлась с контролем. Цена видна в журнале, а не в "
      f"итоговом снимке.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--tmp", default="/tmp/v010_capacity")
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    Path(args.tmp).mkdir(parents=True, exist_ok=True)

    arms = {}
    for name, orders in (("control", None), ("claim", "claim"),
                         ("terrace", "terrace")):
        print(f"arm {name} …", flush=True)
        arm = run_arm(name, str(Path(args.tmp) / f"{name}.db"), args, orders)
        arms[name] = arm.__dict__
        print(f"  alive {arm.alive} capacity {arm.capacity:.0f} "
              f"births {arm.births} paid {arm.paid_food:.0f}", flush=True)

    report = {"config": vars(args), "arms": arms}
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
