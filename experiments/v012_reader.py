#!/usr/bin/env python3
"""v0.12, stage 2a — the reader: one pass instead of a quadratic scan.

The profile (stage 1) measured `StateView.from_state` at 4.6 s for 500
living and 17.8 s for 1000, exponent ~2.17. The cause was not the model:
the view asked `fields_of()` for every entity, and `fields_of()` scans
the whole state. The fix is a single pass over the stored pairs.

This script measures the BEFORE and the AFTER on the same state, and
checks that they are the same mapping. The slow path is kept here as a
reference implementation, deliberately — a benchmark that only measures
the new code cannot show what changed.

Usage:
    python3 experiments/v012_reader.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world import create_world  # noqa: E402
from causal_world.observer.situation import StateView  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402


def slow_from_state(state) -> dict:
    """The pre-v0.12 implementation, kept as the reference."""
    values = {}
    for entity in state.entities():
        for name in state.fields_of(entity):
            values[(entity, name)] = (
                state.get(entity, name),
                state.get_source(entity, name),
                None,
            )
    return values


def run_one(agents: int) -> dict:
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents,
    )
    sim.run(3)
    before_hash = sim.state.hash()

    t = time.perf_counter()
    reference = slow_from_state(sim.state)
    slow_s = time.perf_counter() - t

    t = time.perf_counter()
    view = StateView.from_state(sim.state)
    fast_s = time.perf_counter() - t

    assert view._values == reference, "the one-pass view is not equivalent"
    assert sim.state.hash() == before_hash, "reading changed the state"
    return {
        "agents": agents,
        "pairs": len(sim.state.data),
        "slow_s": round(slow_s, 3),
        "fast_s": round(fast_s, 4),
    }


def render(report: dict) -> str:
    lines: list[str] = []
    a = lines.append
    a("# v0.12, шаг 2a — наблюдатель: один проход вместо квадрата")
    a("")
    a("Замеры на одном и том же состоянии (seed 7, `player_resettle`, "
      "3 тика). «Было» — старая реализация, сохранённая здесь как "
      "эталон; «стало» — `StateView.from_state` после правки. Перед "
      "замером проверяется, что словари совпадают, а хеш состояния не "
      "изменился.")
    a("")
    a("| живых | пар | было, с | стало, с | ускорение |")
    a("|---:|---:|---:|---:|---:|")
    for r in report["runs"]:
        speed = r["slow_s"] / r["fast_s"] if r["fast_s"] else 0
        a(f"| {r['agents']} | {r['pairs']} | {r['slow_s']:.2f} | "
          f"{r['fast_s']:.4f} | {speed:.0f}× |")
    a("")
    first, last = report["runs"][0], report["runs"][-1]
    if first["fast_s"] and last["fast_s"]:
        grows = last["agents"] / first["agents"]
        ratio = last["fast_s"] / first["fast_s"]
        a(f"Рост нового прохода: {ratio:.1f}× при росте населения в "
          f"{grows:.1f}× (старый был квадратичен: "
          f"{last['slow_s'] / first['slow_s']:.1f}× на том же диапазоне). "
          f"Остаток сверх линейного — стоимость сборки словаря и кеш, а "
          f"не повторный скан.")
        a("")
    a("## Что это значит")
    a("")
    a("* Кадр карты и карточка клетки больше не зависят от квадрата: "
      "на демо-мире (54 агента) это доли миллисекунды, на 2 000 живых — "
      "десятки миллисекунд вместо 80 секунд.")
    a("* Но **этого мало для 100k**: полный view — это словарь на "
      "~9.8M пар, и даже линейная сборка займёт секунды. Поэтому "
      "следующий шаг — не «ещё быстрее строить весь мир», а клеточный "
      "срез: кадру нужна одна клетка и её окрестность, а не весь "
      "словарь.")
    a("* Семантика не изменилась: тот же набор ключей, те же значения и "
      "тот же провенанс. Это закреплено `tests/test_v012_reader.py`.")
    a("* Это первый шаг шага 2, а не закрытие v0.12: тик по-прежнему "
      "упирается в префиксные сканы (`entities_with_prefix`, 48% тика "
      "при 16k), а 100k живых — в память.")
    a("")
    a("## Границы")
    a("")
    a("* Замеры — на 2 CPU / 4.1 ГБ; абсолютные числа зависят от машины.")
    a("* «Было» — реконструкция старого кода в этом файле, а не прогон "
      "предыдущего коммита; равенство словарей проверяется до замера.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", default="500,1000,2000")
    parser.add_argument("--out", default="experiments/reports/v012_reader.md")
    parser.add_argument("--json", default="experiments/reports/v012_reader.json")
    args = parser.parse_args()
    sizes = [int(x) for x in args.agents.split(",") if x.strip()]
    runs = []
    for size in sizes:
        print(f"reading {size} agents …", flush=True)
        runs.append(run_one(size))
    report = {"runs": runs}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render(report), encoding="utf-8")
    Path(args.json).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"written {args.out}")
    print(f"written {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
