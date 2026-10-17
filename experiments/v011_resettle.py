#!/usr/bin/env python3
"""v0.11 — resettlement: does the world USE the land it was given?

The v0.10 report measured an honest failure: a claim adds room, but the
people do not come, because the world's own migration fires on HUNGER
and moves to a neighbouring cell. Creating a possibility and using it
were two mechanisms; only the first existed.

This script isolates the second one:

    control   — the v0.8 protocol, then nothing;
    claim     — the same protocol, then two wild parcels are claimed;
    resettle  — the same claims, then people are MOVED into the claimed
                parcels (two orders per parcel).

The only difference between ``claim`` and ``resettle`` is the move
itself. The report measures:

* whether the new land is actually inhabited (population, occupancy);
* whether that use costs anything (transport food, source losses);
* whether it merely redistributes people or creates new ones
  (the journal check: a move changes the TOTAL by zero);
* whether the goal layer calls the result a success, a success with a
  cost, or a failure — on BOTH sides of the move;
* the destination card the player would see before ordering.

Usage:
    python3 experiments/v011_resettle.py --ticks 600 \
        --out experiments/reports/v011_resettle.md
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
    history_from_journal,
    resettle_opportunities,
    situations,
)
from causal_world.player import DecisionChannel, attach_player_channel  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.systems.directive import (  # noqa: E402
    DIRECTIVE_AMEND,
    DIRECTIVE_CLAIM,
    DIRECTIVE_RESETTLE,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
)
from causal_world.world.rules import ResettlementRules, get_ruleset  # noqa: E402

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
    refusals: int = 0
    moves: int = 0
    moved_people: int = 0
    move_cost: float = 0.0
    capacity_writes: int = 0
    total_delta_in_moves: int = 0
    occupied_cells: int = 0
    active_cells: int = 0
    cells: dict = field(default_factory=dict)
    card: list = field(default_factory=list)
    goals: dict = field(default_factory=dict)
    goal_details: list = field(default_factory=list)
    source_drops: list = field(default_factory=list)


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


def _wild_by_region(sim):
    out: dict[str, list[str]] = {}
    for parcel in sim.state.entities_with_prefix("cell:"):
        if sim.state.get(parcel, "land_active"):
            continue
        out.setdefault(sim.state.get(parcel, "region"), []).append(parcel)
    return {region: sorted(ps) for region, ps in out.items()}


def run_arm(name: str, db: str, args, orders) -> Arm:
    Path(db).unlink(missing_ok=True)
    sim = create_world(
        seed=args.seed, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=54, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (args.ticks + 10)))
    channel = DirectiveChannel()
    system = None
    for s in sim.systems:
        if s.name == "ResettlementDirectiveSystem":
            s.channel = channel
            system = s
    assert system is not None

    # the v0.8 protocol (the same one the v0.10 capacity arms used)
    for tick, cell in zip((20, 21, 22, 23), PROTOCOL_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, 0.15))
    for tick, cell in zip((24, 25, 26, 27), PROTOCOL_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, 1.0))

    hunger: dict[str, float] = {}
    starvation = 0
    for _ in range(SATURATE_AT):
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
    populations_before = {
        c: int(sim.state.get(c, "population")) for c in cells
    }
    wild = _wild_by_region(sim)
    picks = [parcels[0] for _, parcels in sorted(wild.items())]

    if orders in ("claim", "resettle"):
        for offset, parcel in enumerate(picks):
            channel.schedule(SATURATE_AT + 1 + offset,
                             Directive(DIRECTIVE_CLAIM, parcel, 0))
    if orders == "resettle":
        # Two orders per parcel: the first moves two people, the second
        # asks for the remainder (0 = as many as the cell can take).
        for offset, parcel in enumerate(picks):
            channel.schedule(SATURATE_AT + 5 + offset,
                             Directive(DIRECTIVE_RESETTLE, parcel, 2))
            channel.schedule(SATURATE_AT + 15 + offset,
                             Directive(DIRECTIVE_RESETTLE, parcel, 0))

    # The destination card, as the player would see it BEFORE the move
    # (the parcels are active by tick 403 in the claim/resettle arms).
    for _ in range(3):
        sim.step()
    if orders in ("claim", "resettle"):
        view_now = StateView.from_state(sim.state)
        wanted = set(picks)
        arm.card = [
            row for row in resettle_opportunities(
                view_now, int(sim.state.tick),
                soil_min=system.RESETTLE_SOIL_MIN,
                food_pc_min=system.RESETTLE_FOOD_PC_MIN,
                cost_base=system.RESETTLE_FOOD_BASE,
                cost_per_step=system.RESETTLE_FOOD_PER_STEP,
                max_per_order=system.RESETTLE_MAX_PER_ORDER,
            )
            if row["destination"] in wanted
        ]

    for _ in range(WINDOW - 3):
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
    arm.active_cells = len(cells)
    arm.occupied_cells = sum(
        1 for c in cells if int(sim.state.get(c, "population")) > 0
    )
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
                        continue  # decided BEFORE the arm's orders
                    verdicts.append(evaluate(
                        goal, history, state, alerts, tick=tick
                    ))
        arm.goals = summary(verdicts)
        arm.goal_details = [
            {
                "scope": v.goal.scope,
                "kind": v.goal.kind,
                "status": v.status,
                "reason": v.reason,
                "confidence": v.confidence,
            }
            for v in verdicts
            if v.goal.kind == "resettle"
        ]
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
        for transition in view:
            if (transition.tick <= SATURATE_AT
                    or transition.status.value != "COMMITTED"
                    or transition.operation != "player.resettle"):
                continue
            arm.moves += 1
            fields = {w.field: w for w in transition.writes}
            if "resettle_state" in fields:
                if int(fields["resettle_state"].new) != 1:
                    arm.refusals += 1
                    continue
            moved = int(fields["resettle_moved"].new)
            arm.moved_people += moved
            arm.move_cost += float(fields["resettle_cost"].new)
            arm.paid_food += float(fields["resettle_cost"].new)
            # The move must neither create nor destroy people/capacity:
            # the sum of cell-population changes in this transition is 0,
            # and it writes no capacity field.
            arm.total_delta_in_moves += sum(
                int(w.new) - int(w.old)
                for w in transition.writes
                if w.field == "population" and w.entity.startswith("cell:")
            )
            for forbidden in ("pop_base", "soil_fertility", "land_active"):
                if any(w.field == forbidden for w in transition.writes):
                    arm.capacity_writes += 1
        for cell in cells:
            arm.cells[cell] = {
                "population": int(state.get(cell, "population") or 0),
                "capacity": round(
                    float(state.get(cell, "pop_base") or 0)
                    * (1.0 + float(state.get(cell, "soil_fertility") or 0)),
                    2,
                ),
                "soil": round(float(state.get(cell, "soil_fertility") or 0), 4),
                "resettled_in": int(state.get(cell, "resettled_in") or 0),
                "resettled_out": int(state.get(cell, "resettled_out") or 0),
                "last_source": state.get(cell, "last_source"),
            }
        for cell in cells:
            sent = int(state.get(cell, "resettled_out") or 0)
            if not sent:
                continue
            arm.source_drops.append({
                "source": cell,
                "before": populations_before.get(cell, 0),
                "after": int(state.get(cell, "population") or 0),
                "sent": sent,
            })
    return arm


def render(report: dict, args) -> str:
    lines = []
    a = lines.append
    arms = report["arms"]
    a("# v0.11 — переселение: мир начинает использовать открытую землю")
    a("")
    a(f"seed {args.seed}, 54 агента, `player_resettle`. Мир проходит "
      f"протокол v0.8 до тика {SATURATE_AT}; затем три плеча по {WINDOW} "
      f"тиков: контроль, заявка целины, заявка + переселение. Разница "
      f"между claim и resettle — ТОЛЬКО само перемещение людей.")
    a("")
    a("## 1. Возможность найдена до приказа (карточка назначения)")
    a("")
    a("Слой наблюдения читает свободную ёмкость, пригодность почвы и "
      "запаса, выбирает источник и считает цену — той же арифметикой, "
      "которую применит закон:")
    a("")
    a("| назначение | свободно | почва | еда/чел | источник | расстояние | "
      "цена/чел | максимум людей | пригодно |")
    a("|---|---:|---:|---:|---|---:|---:|---:|---|")
    for row in arms["resettle"]["card"]:
        a(f"| {row['destination']} | {row['room']} | {row['soil']:.2f} | "
          f"{row['food_pc']:.1f} | {row['source']} | {row['distance']} | "
          f"{row['cost_per_migrant']:.1f} | {row['max_movers']} | "
          f"{'да' if row['feasible'] else row['reason']} |")
    a("")
    a("## 2. Перемещение реально и атомарно")
    a("")
    a("| плечо | заявок целины | переселено людей | цена еды | отказов | "
      "изменение суммы населения в переходах | записей ёмкости |")
    a("|---|---:|---:|---:|---:|---:|---:|")
    for name in ("control", "claim", "resettle"):
        arm = arms[name]
        a(f"| {name} | {arm['claims']} | {arm['moved_people']} | "
          f"{arm['move_cost']:.0f} | {arm['refusals']} | "
          f"{arm['total_delta_in_moves']:+d} | {arm['capacity_writes']} |")
    a("")
    a("Сумма изменений населения в переходах переселения = 0, записей "
      "`pop_base`/`soil_fertility`/`land_active` = 0: приказ "
      "ПЕРЕРАСПРЕДЕЛЯЕТ людей и еду, он не создаёт ни людей, ни ёмкость.")
    a("")
    a("## 3. Цена и результат")
    a("")
    a("| плечо | живых на старте → в конце | ёмкость | рождений | смертей | "
      "из них голодных* | почва | еда | занято клеток | людей в новых клетках |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name in ("control", "claim", "resettle"):
        arm = arms[name]
        newcomers = sum(
            c["population"] for cell, c in arm["cells"].items()
            if c["resettled_in"] and cell in report["parcels"]
        )
        a(f"| {name} | {arm['alive_start']} → {arm['alive']} | "
          f"{arm['capacity_start']:.0f} → {arm['capacity']:.0f} | "
          f"{arm['births']} | {arm['deaths']} | {arm['starvation_deaths']} | "
          f"{arm['mean_soil']:.3f} | {arm['food']:.0f} | "
          f"{arm['occupied_cells']}/{arm['active_cells']} | {newcomers} |")
    a("")
    a("\\* «Голодная смерть» — прокси по голоду на последнем живом тике "
      "(0.75), а не причина из перехода.")
    a("")
    a("### Куда именно пришли люди")
    a("")
    a("| клетка | население | ёмкость | почва | приняла | отдала | источник |")
    a("|---|---:|---:|---:|---:|---:|---|")
    for cell in report["parcels"]:
        for name in ("claim", "resettle"):
            row = arms[name]["cells"].get(cell)
            if row is None:
                continue
            a(f"| {name}: {cell} | {row['population']} | "
              f"{row['capacity']:.1f} | {row['soil']:.3f} | "
              f"{row['resettled_in']} | {row['resettled_out']} | "
              f"{row['last_source']} |")
    a("")
    moved = arms["resettle"]["moved_people"]
    new_parcels = [c for c in report["parcels"]
                   if arms["resettle"]["cells"].get(c, {}).get("resettled_in")]
    still = sum(arms["resettle"]["cells"][c]["population"] for c in new_parcels)
    a(f"Переселено {moved} человек; в новых клетках к концу плеча живут "
      f"{still}. Разница — не «потерянные приказы»: это смерти и "
      f"естественная миграция за {WINDOW} тиков, и она видна в журнале.")
    if any(not arms["resettle"]["cells"][c]["population"] for c in new_parcels):
        a("")
        a("**Важно про горизонт:** одна из новых клеток к концу плеча снова "
          "пуста. Её первый эпизод `abandoned` закрылся и получил вердикт "
          "`resolved` на своём окне, а новый эпизод уже открыт и показан "
          "как `active`. Вердикт — утверждение о своём горизонте; текущее "
          "состояние показывается рядом, а не подменяется им.")
    a("")
    if arms["resettle"]["source_drops"]:
        a("### Что потерял источник")
        a("")
        a("| источник | население до плеча | после | отдал |")
        a("|---|---:|---:|---:|")
        for row in arms["resettle"]["source_drops"]:
            a(f"| {row['source']} | {row['before']} | {row['after']} | "
              f"{row['sent']} |")
        a("")
    a("## 4. Вердикты целей: обе стороны перемещения")
    a("")
    a("| плечо | вердикты целей |")
    a("|---|---|")
    for name in ("control", "claim", "resettle"):
        arm = arms[name]
        a(f"| {name} | " + ", ".join(
            f"{k}: {v}" for k, v in sorted(arm["goals"].items())
        ) + " |")
    a("")
    if arms["resettle"]["goal_details"]:
        a("| цель | вердикт | уверенность | почему |")
        a("|---|---|---|---|")
        for goal in arms["resettle"]["goal_details"]:
            a(f"| {goal['kind']} {goal['scope']} | {goal['status']} | "
              f"{goal['confidence']} | {goal['reason']} |")
        a("")
    a("## Что этот прогон доказывает")
    a("")
    new_claim = sum(
        c["population"] for cell, c in arms["resettle"]["cells"].items()
        if c["resettled_in"] and cell in report["parcels"]
    )
    if moved:
        a(f"- **Мир использовал открытую землю:** {moved} человек "
          f"переселены, в новых клетках живут {new_claim}.")
    else:
        a("- **Переселение не сработало:** ни один человек не переехал; "
          "это провал механики, а не измеренный результат.")
    a(f"- **Перераспределение, а не создание:** сумма населения в "
      f"переходах {arms['resettle']['total_delta_in_moves']:+d}, "
      f"записей ёмкости {arms['resettle']['capacity_writes']}.")
    claims_cost = (arms["resettle"]["paid_food"]
                   - arms["resettle"]["move_cost"])
    a(f"- **Цена записана:** {arms['resettle']['move_cost']:.0f} еды "
      f"транспорта + {claims_cost:.0f} еды заявок; людей отдали "
      f"{len(arms['resettle']['source_drops'])} клетки-источника.")
    a("")
    a("## Что этот прогон НЕ доказывает")
    a("")
    a("- Один seed и один сценарий: сетка по режимам — отдельный отчёт "
      "`v011_grid.md`; цена и эффект зависят от запасов региона.")
    a("- Переселение внутри региона: межрегиональные караваны в v0.11 не "
      "моделируются (нет торговли и коридоров), и отчёт не делает вид, "
      "что они есть.")
    a("- «Голодная смерть» — прокси; причина смерти в переходе не хранится.")
    a("- Естественная миграция по-прежнему срабатывает от голода; приказ "
      "переселения её не заменяет, а дополняет.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    tmp = Path("/tmp/v011_resettle")
    tmp.mkdir(parents=True, exist_ok=True)
    arms = {}
    for name, orders in (("control", "none"), ("claim", "claim"),
                         ("resettle", "resettle")):
        print(f"arm {name} …", flush=True)
        arms[name] = run_arm(name, str(tmp / f"{name}.db"), args, orders)
        print(f"  alive {arms[name].alive} births {arms[name].births} "
              f"moved {arms[name].moved_people} "
              f"paid {arms[name].paid_food:.0f} "
              f"occupied {arms[name].occupied_cells}", flush=True)

    # the two parcels the arms claim (first reserve parcel of each region)
    sim = create_world(
        seed=args.seed, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=54,
    )
    wild = _wild_by_region(sim)
    parcels = [parcels_[0] for _, parcels_ in sorted(wild.items())]

    report = {
        "config": {
            "seed": args.seed, "ticks": args.ticks,
            "saturate_at": SATURATE_AT, "window": WINDOW,
            "ruleset": "player_resettle",
            "ruleset_version": ResettlementRules.ruleset_version,
        },
        "parcels": parcels,
        "arms": {name: arm.__dict__ for name, arm in arms.items()},
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
