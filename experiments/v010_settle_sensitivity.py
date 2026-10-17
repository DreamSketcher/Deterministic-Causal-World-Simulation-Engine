#!/usr/bin/env python3
"""v0.10 — how much does a goal verdict depend on the watch window?

v0.9 chose ``SETTLE_TICKS = 20`` and said why: a famine that ends today
can still kill this week. The review answered, correctly, that 20 is a
parameter of the algorithm, not a proven horizon of stability, and asked
for a sensitivity check before any adaptive window is designed.

This experiment takes ONE recorded world (the spatial world with the
v0.8 order protocol), reconstructs its goals from the archive and
re-evaluates every goal at three windows: 20, 50 and 100 ticks. It then
reports:

* how many goals change their verdict;
* which DIRECTION they change (a wider window can only delay a verdict —
  unless the extra time reveals deaths, which can turn "resolved" into
  "resolved_with_cost" or "collapsed");
* the per-goal table, so a claim about a horizon can be checked by eye.

The point is not to pick a "correct" window. It is to make the
dependence measurable, so the interface can say "this verdict is stable
across the tested horizons" or "this one is not" instead of implying a
certainty the model does not have.

Usage:
    python3 experiments/v010_settle_sensitivity.py --ticks 600 \\
        --out experiments/reports/v010_settle_sensitivity.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.goal import evaluate, episodes  # noqa: E402
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
WINDOWS = (20, 50, 100)


def run_world(db: str, ticks: int, seed: int) -> None:
    Path(db).unlink(missing_ok=True)
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_spatial"), ticks=0,
        regions=2, agents=54, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (ticks + 10)))
    channel = DirectiveChannel()
    for system in sim.systems:
        if isinstance(system, DirectiveSystem):
            system.channel = channel
    for tick, cell in zip((20, 21, 22, 23), ORDER_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, 0.15))
    for tick, cell in zip((24, 25, 26, 27), ORDER_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, 1.0))
    sim.run(ticks)
    sim.journal.commit()
    sim.journal.close()


def evaluate_all(db: str, window: int) -> list[dict]:
    with JournalView(db) as view:
        state = StateView.from_journal(view)
        cells = [
            c for c in state.entities_with_prefix("cell:")
            if state.get(c, "land_active") is None
            or int(state.get(c, "land_active"))
        ]
        history = history_from_journal(
            view, cells,
            ["food_stock", "population", "soil_fertility", "births_total"],
        )
        alerts = situations(view)
        tick = state.max_tick()
        out = []
        for scope in cells:
            for kind in ("feed", "restore_soil", "resettle", "renew"):
                for goal in episodes(history, scope, kind, last_tick=tick):
                    verdict = evaluate(
                        goal, history, state, alerts, tick=tick,
                        settle_ticks=window,
                    )
                    out.append(verdict.to_dict())
        return out


def compare(results: dict[int, list[dict]]) -> dict:
    """How the verdict of the SAME goal changes with the window."""
    index = {}
    for window, verdicts in results.items():
        for verdict in verdicts:
            key = (verdict["kind"], verdict["scope"], verdict["opened_tick"])
            index.setdefault(key, {})[window] = verdict["status"]

    rows = []
    for key, by_window in sorted(index.items()):
        statuses = [by_window.get(w, "—") for w in WINDOWS]
        rows.append({
            "kind": key[0], "scope": key[1], "opened_tick": key[2],
            "statuses": statuses,
            "stable": len(set(statuses)) == 1,
        })

    counts = {window: {} for window in WINDOWS}
    for window, verdicts in results.items():
        for verdict in verdicts:
            counts[window][verdict["status"]] = (
                counts[window].get(verdict["status"], 0) + 1
            )
    changed = [row for row in rows if not row["stable"]]
    return {
        "rows": rows,
        "counts": counts,
        "changed": changed,
        "total": len(rows),
    }


def render(report: dict, args) -> str:
    lines = []
    a = lines.append
    c = report["analysis"]
    a("# v0.10 — чувствительность вердикта к окну наблюдения")
    a("")
    a(f"Один записанный мир: seed {args.seed}, 54 агента, "
      f"{args.ticks} тиков, протокол v0.8 (`amend 0.15` тики 20–23, "
      f"`water 1.0` тики 24–27). Окна: "
      f"{', '.join(map(str, WINDOWS))} тиков.")
    a("")
    a("## Сколько целей меняют вердикт")
    a("")
    a(f"Всего целей, восстановленных из архива: {c['total']}. "
      f"Меняют вердикт хотя бы в одном окне: {len(c['changed'])}.")
    a("")
    a("| окно | вердикты |")
    a("|---:|---|")
    for window in WINDOWS:
        counts = ", ".join(
            f"{status}: {n}" for status, n in sorted(c["counts"][window].items())
        )
        a(f"| {window} | {counts} |")
    a("")
    a("## Цели, зависящие от окна")
    a("")
    if c["changed"]:
        a("| цель | открыта | " + " | ".join(f"окно {w}" for w in WINDOWS) + " |")
        a("|---|---:|" + "---|" * len(WINDOWS))
        for row in c["changed"]:
            a(f"| {row['kind']} `{row['scope']}` | {row['opened_tick']} | "
              + " | ".join(row["statuses"]) + " |")
    else:
        a("Ни одна цель не изменила вердикт: на этом мире выбор окна не "
          "влиял.")
    a("")
    a("## Как читать это")
    a("")
    a("- Более широкое окно может только ЗАДЕРЖАТЬ вердикт (`settling`), "
      "но задержка иногда полезна: за 100 тиков успевают проявиться "
      "смерти, и `resolved` превращается в `resolved_with_cost` или "
      "`collapsed`.")
    a("- Если вердикт меняется, интерфейс не должен показывать его как "
      "установленный факт без окна: рядом с вердиктом обязано стоять, "
      "на каком горизонте он получен.")
    a("- Это НЕ доказательство, что 20 (или 100) — правильный горизонт. "
      "Это измерение зависимости; выбор горизонта остаётся решением "
      "игрока или сценария.")
    a("")
    a("## Ограничения")
    a("")
    a("- Один мир, один протокол: чувствительность к окну может быть "
      "иной в других режимах, и это следующий вопрос, а не текущий ответ.")
    a("- Цели, открытые у самого конца записи, физически не могут "
      "набрать большое окно — для них `settling` ожидаем.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--tmp", default="/tmp/v010_settle")
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()

    Path(args.tmp).mkdir(parents=True, exist_ok=True)
    db = str(Path(args.tmp) / "world.db")
    print("running the world …", flush=True)
    run_world(db, args.ticks, args.seed)

    results = {}
    for window in WINDOWS:
        results[window] = evaluate_all(db, window)
        print(f"window {window:>3}: {len(results[window])} goals", flush=True)

    report = {
        "config": vars(args),
        "windows": list(WINDOWS),
        "analysis": compare(results),
        "verdicts": {str(w): v for w, v in results.items()},
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
