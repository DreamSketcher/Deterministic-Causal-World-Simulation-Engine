#!/usr/bin/env python3
"""v0.9 — ONE SITUATION, ALL THE WAY THROUGH THE LOOP.

The v0.8 slice proved that a player CAN change a world. This script is
the v0.9 question: does the game have a full loop that ends with a new
decision, and is every step of it checkable?

The situation: the poor region of the spatial world. Its four cells lose
soil, their stores empty, people die. The chain the script walks is the
player's:

    observe   — the situation layer names the problem, with evidence ids;
    understand— the causal budget of the cell, read from the archive,
                says which transitions drained the store;
    intervene — four amend orders and four irrigation orders, each with
                the explicit answer of the civic layer;
    verify    — the goal layer's verdict, which asks whether the PEOPLE
                and the LAND survived, not only whether the alert went
                away;
    compare   — a second world with the same seed and the same decisions
                but no orders: same divergence tick, measured difference;
    next      — the problem the intervention creates (a full world with
                no room to grow), named by the same situation layer.

Every number below comes from a recorded archive. The report is written
from the journals, not from the run's own commentary, so the chronicle
can be checked line by line with ``query``/``trace``.

Usage:
    python3 experiments/v09_scenario.py --ticks 600 \\
        --out experiments/reports/v09_scenario.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.budget import CausalBudget  # noqa: E402
from causal_world.observer.compare import CausalComparator  # noqa: E402
from causal_world.observer.goal import goals as goal_verdicts  # noqa: E402
from causal_world.observer.goal import summary as goal_summary  # noqa: E402
from causal_world.observer.journal import JournalView  # noqa: E402
from causal_world.observer.situation import (  # noqa: E402
    StateView,
    history_from_journal,
    situations,
)
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
#: The kinds that OPEN the situation: soil depletion alone is a chronic
#: reading; an empty store or an empty cell is an event the player must
#: answer. The scenario starts its clock from the world's first such
#: event, not from a tick chosen by the author.
DETECT_KINDS = ("famine", "hunger", "abandoned")
AMEND_AFTER = (1, 2, 3, 4)     # ticks after detection
WATER_AFTER = (5, 6, 7, 8)


@dataclass
class Run:
    name: str
    ticks: int
    orders: list[dict] = field(default_factory=list)
    detection: list[dict] = field(default_factory=list)
    alive: int = 0
    births: int = 0
    deaths: int = 0
    soil: dict = field(default_factory=dict)
    cells: dict = field(default_factory=dict)
    verdicts: list[dict] = field(default_factory=list)
    goals_summary: dict = field(default_factory=dict)
    detection_tick: int | None = None
    final_situations: list[dict] = field(default_factory=list)
    capacity: float = 0.0


def run_world(name: str, db: str, args, *, with_orders: bool) -> Run:
    Path(db).unlink(missing_ok=True)
    sim = create_world(
        seed=args.seed, ruleset=get_ruleset("player_spatial"), ticks=0,
        regions=args.regions, agents=args.agents, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (args.ticks + 10)))
    channel = DirectiveChannel()
    for system in sim.systems:
        if isinstance(system, DirectiveSystem):
            system.channel = channel

    result = Run(name=name, ticks=args.ticks)
    detect_tick: int | None = None

    for tick in range(args.ticks + 1):
        if tick:
            sim.step()
            # The world speaks first. The scenario's clock starts at the
            # first tick on which the situation layer reports an event
            # that demands an answer; before that there is nothing to
            # decide and the run is just a world living.
            if detect_tick is None and tick < args.ticks - 60:
                view = StateView.from_state(sim.state)
                alerts = situations(view, current_tick=tick - 1)
                hits = [a for a in alerts if a.kind in DETECT_KINDS]
                if hits:
                    detect_tick = tick
                    result.detection = [a.to_dict() for a in alerts]
                    result.detection_tick = detect_tick
                    if with_orders:
                        _enact(channel, detect_tick, result, args)
    sim.journal.commit()
    sim.journal.close()

    with JournalView(db) as view:
        state = StateView.from_journal(view)
        cells = state.entities_with_prefix("cell:")
        history = history_from_journal(
            view, cells, ["food_stock", "population", "soil_fertility"]
        )
        alerts = situations(view)
        result.verdicts = [
            v.to_dict()
            for v in goal_verdicts(
                history, state, alerts, tick=args.ticks, window=args.ticks
            )
        ]
        result.goals_summary = goal_summary(
            goal_verdicts(history, state, alerts, tick=args.ticks,
                          window=args.ticks)
        )
        result.final_situations = [a.to_dict() for a in alerts]
        for cell in cells:
            result.cells[cell] = {
                "population": state.get(cell, "population"),
                "soil": round(float(state.get(cell, "soil_fertility") or 0), 4),
                "food": round(float(state.get(cell, "food_stock") or 0), 2),
                "law": {
                    "labor_diversion": state.get(cell, "labor_diversion"),
                    "water_aid": state.get(cell, "water_aid"),
                },
            }
            result.soil[cell] = result.cells[cell]["soil"]
        result.alive = sum(
            1 for a in state.entities_with_prefix("agent:")
            if _alive(state, a)
        )
        result.births = sum(
            1 for t in view
            if t.tick <= args.ticks and t.operation == "agent.birth"
            and t.status.value == "COMMITTED"
        )
        result.deaths = 0
        for t in view:
            if t.tick > args.ticks:
                continue
            if t.operation != "agent.death" or t.status.value != "COMMITTED":
                continue
            if any(w.field == "alive" and w.new is False for w in t.writes):
                result.deaths += 1
        result.capacity = sum(
            int(state.get(c, "pop_base"))
            * (1.0 + float(state.get(c, "soil_fertility") or 0))
            for c in cells
        )
    return result


def _enact(channel, detect_tick: int, result: Run, args) -> None:
    """Give the orders, and keep the answer the civic layer returned."""
    for offset, cell in zip(AMEND_AFTER, ORDER_CELLS):
        answer = channel.schedule(
            detect_tick + offset,
            Directive(DIRECTIVE_AMEND, cell, args.amend_value),
        )
        result.orders.append(answer.to_dict())
    for offset, cell in zip(WATER_AFTER, ORDER_CELLS):
        answer = channel.schedule(
            detect_tick + offset,
            Directive(DIRECTIVE_WATER, cell, args.water_value),
        )
        result.orders.append(answer.to_dict())


def _alive(view, agent: str) -> bool:
    return bool(view.get(agent, "alive"))


def first_divergence(base_db: str, fork_db: str):
    """The first transition where two archives part ways."""
    with JournalView(base_db) as a, JournalView(fork_db) as b:
        a_rows = [(t.id, t.tick, t.operation,
                   tuple((w.entity, w.field, w.old, w.new) for w in t.writes))
                  for t in a]
        b_rows = [(t.id, t.tick, t.operation,
                   tuple((w.entity, w.field, w.old, w.new) for w in t.writes))
                  for t in b]
    for left, right in zip(a_rows, b_rows):
        if left != right:
            return {"tick": left[1], "tid": left[0], "base": left[2],
                    "fork": right[2]}
    if len(a_rows) != len(b_rows):
        row = a_rows[len(b_rows)] if len(a_rows) > len(b_rows) else None
        return {"tick": row[1] if row else None,
                "tid": row[0] if row else None,
                "base": "extra transitions", "fork": "none"}
    return None


def understand(db: str, scope: str) -> list[dict]:
    """The archive's own explanation of the DETECTED cell's balance."""
    with JournalView(db) as view:
        budget = CausalBudget(view)
        out = []
        for scope, field_name in (
            (scope, "food_stock"),
            (scope, "soil_fertility"),
        ):
            try:
                report = budget.analyze(scope, field_name)
            except Exception as exc:  # a budget that cannot run is reported
                out.append({"scope": scope, "field": field_name,
                            "error": str(exc)})
                continue
            entries = sorted(
                [*report.inflows, *report.outflows],
                key=lambda entry: -abs(entry.total_delta),
            )[:4]
            out.append({
                "scope": scope,
                "field": field_name,
                "net": round(float(report.net), 4),
                "top": [
                    {"operation": f"{e.system}.{e.operation}",
                     "total": round(float(e.total_delta), 4),
                     "count": e.count}
                    for e in entries
                ],
            })
        return out


def compare(base_db: str, fork_db: str) -> dict:
    with JournalView(base_db) as a, JournalView(fork_db) as b:
        comparator = CausalComparator(a, b, "no_orders", "orders")
        diffs = {}
        for cell in ORDER_CELLS:
            for field_name in ("food_stock", "soil_fertility"):
                try:
                    diff = comparator.compare_field(cell, field_name)
                except Exception as exc:
                    diffs[f"{cell}.{field_name}"] = {"error": str(exc)}
                    continue
                diffs[f"{cell}.{field_name}"] = {
                    "net_delta": round(
                        float(diff.budget_deltas.get(field_name, 0.0)), 4
                    ),
                    "loop": diff.causal_loop_diff,
                }
    return diffs


def render(report: dict, args) -> str:
    lines: list[str] = []
    a = lines.append
    base = report["base"]
    orders = report["orders"]

    a("# v0.9 — сквозная ситуация: от обнаружения до нового решения")
    a("")
    a(f"seed {args.seed}, {args.regions} региона, {args.agents} агентов, "
      f"горизонт {args.ticks} тиков, ruleset `player_spatial`.")
    a("")
    a("Это не сценарий-рассказ: все фазы прочитаны из двух архивов, и "
      "каждую строку можно проверить `query`/`trace`.")
    a("")

    detected = orders.get("detection_tick")
    a("## 1. Наблюдение — мир сам называет проблему "
      f"(тик {detected if detected is not None else '—'})")
    a("")
    if orders["detection"]:
        for alert in orders["detection"][:6]:
            tids = ", ".join(f"T{e['tid']}" for e in alert["evidence"][:3])
            a(f"- **{alert['kind']}** `{alert['scope']}`: {alert['message']} "
              f"(острота {alert['severity']:.2f}, с тика "
              f"{alert['since_tick']}; {tids or 'без evidence'})")
    else:
        a("- На этом тике тревог нет — и это тоже ответ мира.")
    a("")

    a("## 2. Понимание — бюджет причин, а не догадка")
    a("")
    for row in report["understanding"]:
        if "error" in row:
            a(f"- `{row['scope']}.{row['field']}`: бюджет недоступен "
              f"({row['error']})")
            continue
        top = "; ".join(
            f"{c['operation']} {c['total']:+.4f}" for c in row["top"]
        )
        a(f"- `{row['scope']}.{row['field']}`: итог {row['net']:+.4f}; "
          f"вклад: {top}")
    a("")

    a("## 3. Вмешательство — приказы с явным ответом")
    a("")
    a("| тик | приказ | цель | сила | ответ |")
    a("|---:|---|---|---:|---|")
    for order in orders["orders"]:
        a(f"| {order.get('tick')} | {order['name']} | {order['target']} | "
          f"{order['param']} | {order['status']}: {order['message']} |")
    a("")
    accepted = sum(1 for o in orders["orders"] if o["status"] == "accepted")
    a(f"Принято {accepted} из {len(orders['orders'])}; ни один приказ не "
      f"потерян молча.")
    a("")

    a("## 4. Проверка — что стало с людьми и землёй")
    a("")
    a("| мир | живых | рождений | смертей | средняя почва | вымерших клеток |")
    a("|---|---:|---:|---:|---:|---:|")
    for run in (base, orders):
        soil = sum(run["soil"].values()) / len(run["soil"])
        extinct = sum(1 for c in run["cells"].values() if c["population"] == 0)
        a(f"| {run['name']} | {run['alive']} | {run['births']} | "
          f"{run['deaths']} | {soil:.3f} | {extinct} |")
    a("")
    s = orders["goals_summary"]
    a(f"Вердикты целей (мир с приказами): всего {s['total']}, "
      f"решено {s.get('resolved', 0)}, решено с ценой "
      f"{s.get('resolved_with_cost', 0)}, катастроф "
      f"{s.get('collapsed', 0)}, переехало {s.get('transferred', 0)}, "
      f"проверяется {s.get('settling', 0)}, идёт {s.get('active', 0)}.")
    a("")
    for v in [v for v in orders["verdicts"] if v["status"] != "active"][:6]:
        a(f"- **{v['status']}** · {v['kind']} `{v['scope']}` "
          f"({v['opened_tick']}–{v['closed_tick']}): люди "
          f"{v['population_open']}→{v['population_close']}, почва "
          f"{v['soil_open']}→{v['soil_close']}. {v['reason']}")
    a("")

    a("## 5. Сравнение — тот же мир, одно отличие")
    a("")
    divergence = report["divergence"]
    if divergence:
        a(f"Архивы расходятся на тике {divergence['tick']} "
          f"(переход T{divergence['tid']}): "
          f"`{divergence['base']}` против `{divergence['fork']}`.")
    else:
        a("Архивы не разошлись — приказы не изменили ни одного перехода. "
          "Это тоже результат, и его нельзя выдавать за успех.")
    a("")
    a("| поле | Δ бюджета база→приказы | структурный контур |")
    a("|---|---:|---|")
    for name, diff in report["comparison"].items():
        if "error" in diff:
            a(f"| {name} | — | ошибка: {diff['error']} |")
            continue
        a(f"| {name} | {diff['net_delta']:+.4f} | {diff['loop']} |")
    a("")

    a("## 6. Новая проблема из результата")
    a("")
    new = [x for x in orders["final_situations"]
           if x["kind"] in ("birth_stall", "surplus", "thin_soil",
                            "abandoned", "famine")]
    if new:
        for alert in new[:6]:
            a(f"- **{alert['kind']}** `{alert['scope']}`: {alert['message']} "
              f"(с тика {alert['since_tick']})")
    else:
        a("- Новых проблем нет — что для игры означает скучный мир.")
    saturation = orders["alive"] / max(orders["capacity"], 1e-9)
    a("")
    a(f"Ёмкость мира: {orders['capacity']:.1f} мест, занято "
      f"{orders['alive']} ({saturation:.0%}). Следующий шаг игрока — не "
      f"«ещё приказ», а решение о ёмкости: новая земля или рост "
      f"`pop_base` (переселение только перераспределит людей между "
      f"полными клетками). Это и есть новая задача, которую создал успех.")
    a("")

    a("## Проверяемость")
    a("")
    a(f"- база: `query --db {base['name']}.db`; приказы: "
      f"`query --db {orders['name']}.db`")
    a("- расхождение: `compare` по тем же архивам даёт тик и transition-id")
    a("- цели: `goals` читает историю полей из журнала, а не из текста "
      "отчёта")
    a("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--regions", type=int, default=2)
    parser.add_argument("--agents", type=int, default=54)
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--amend-value", type=float, default=0.15)
    parser.add_argument("--water-value", type=float, default=1.0)
    parser.add_argument("--tmp", default="/tmp/v09_scenario")
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    Path(args.tmp).mkdir(parents=True, exist_ok=True)
    base_db = str(Path(args.tmp) / "base.db")
    orders_db = str(Path(args.tmp) / "orders.db")

    print("running base (no orders) …", flush=True)
    base = run_world("base", base_db, args, with_orders=False)
    print("running orders …", flush=True)
    orders = run_world("orders", orders_db, args, with_orders=True)

    report = {
        "config": vars(args),
        "base": base.__dict__,
        "orders": orders.__dict__,
        "understanding": understand(
            base_db,
            (base.detection[0]["scope"] if base.detection else "cell:1:0"),
        ),
        "divergence": first_divergence(base_db, orders_db),
        "comparison": compare(base_db, orders_db),
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
