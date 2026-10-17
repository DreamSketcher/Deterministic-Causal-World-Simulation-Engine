#!/usr/bin/env python3
"""v0.12, stage 2c — state, snapshot, index: identity and cost.

The invariants of this stage are behavioural and live in
``tests/test_v012_equivalence.py``:

1. state identity against a golden per-tick record;
2. journal hash and transition-id sequence identity;
3. deterministic replay at every tick, not only at the end;
4. full index rebuild == incremental update through the journal;
5. restart from the saved state and journal, with a continued run that
   matches a world that never stopped.

This script measures the COST side of the same work:

* prefix lookups on a snapshot — the pre-2c scan (14 calls, each over
  all pairs) versus the per-snapshot index;
* the tick before (stage 1 profile) and after the change;
* index maintenance: full rebuild vs one-tick advance;
* restart: replay from the archive, and the rebuild of the index from
  the restored state.

Usage:
    python3 experiments/v012_state.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world import create_world  # noqa: E402
from causal_world.kernel.snapshot import Snapshot  # noqa: E402
from causal_world.observer.slice import WorldIndex  # noqa: E402
from causal_world.server import continuity  # noqa: E402
from causal_world.server.session import Session  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402

#: the prefixes the tick actually asks for (14 calls in the profile)
PREFIXES = (
    "agent:", "region:", "cell:", "agent:", "region:", "agent:",
    "region:", "cell:", "agent:", "region:", "agent:", "ruin:",
    "agent:", "region:",
)


def _world(agents: int):
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents,
    )
    sim.run(3)
    return sim


def _scan(snapshot: Snapshot, prefix: str) -> list[str]:
    """The pre-2c implementation, kept here as the reference."""
    return sorted({entity for entity, _ in snapshot.data
                   if entity.startswith(prefix)})


def prefix_bench(agents: int) -> dict:
    sim = _world(agents)
    snapshot = Snapshot.from_state(sim.state)

    t = time.perf_counter()
    for prefix in PREFIXES:
        _scan(snapshot, prefix)
    scan_s = time.perf_counter() - t

    # warm the per-snapshot index the way a real tick does: the first
    # call pays for the build, the rest are lookups
    t = time.perf_counter()
    snapshot.entities_with_prefix("agent:")
    first_s = time.perf_counter() - t
    t = time.perf_counter()
    for prefix in PREFIXES[1:]:
        snapshot.entities_with_prefix(prefix)
    indexed_s = first_s + (time.perf_counter() - t)

    assert [_scan(snapshot, p) for p in PREFIXES] == \
        [snapshot.entities_with_prefix(p) for p in PREFIXES]
    return {
        "agents": agents,
        "pairs": len(snapshot.data),
        "scan_s": round(scan_s, 4),
        "indexed_s": round(indexed_s, 4),
        "first_call_s": round(first_s, 4),
        "speedup": round(scan_s / indexed_s, 1) if indexed_s else 0,
    }


def index_bench(agents: int, ticks: int = 3) -> dict:
    sim = _world(agents)
    t = time.perf_counter()
    rebuilt = WorldIndex.from_state(sim.state, journal=sim.journal)
    rebuild_s = time.perf_counter() - t

    incremental = WorldIndex.from_state(sim.state, journal=sim.journal)
    advances = []
    for _ in range(ticks):
        sim.step()
        t = time.perf_counter()
        incremental.advance(sim.journal, sim.state.tick - 1)
        advances.append(time.perf_counter() - t)

    fresh = WorldIndex.from_state(sim.state, journal=sim.journal)
    same = all((
        incremental.entities("agent:") == fresh.entities("agent:"),
        incremental.entities("cell:") == fresh.entities("cell:"),
        incremental.entities("region:") == fresh.entities("region:"),
        incremental.alive_count == fresh.alive_count,
        incremental.agent_count == fresh.agent_count,
        incremental.pool_stats == fresh.pool_stats,
        all(incremental.agents_in_cell(c) == fresh.agents_in_cell(c)
            for c in fresh.entities("cell:")),
    ))
    return {
        "agents": agents,
        "rebuild_s": round(rebuild_s, 3),
        "advance_s": round(sum(advances) / len(advances), 4),
        "equal_after_advance": same,
        "rebuilt_cells": len(rebuilt.entities("cell:")),
    }


def restart_bench() -> dict:
    d = tempfile.mkdtemp(prefix="v012-state-")
    session = Session(
        seed=7, ruleset="player_resettle", regions=2, agents=54,
        max_ticks=200, db_dir=d,
    )
    for seq in range(1, 13):
        session.decide(seq, 6)
    live_state = session.sim.state.hash()
    live_journal = session.sim.journal.hash()
    t = time.perf_counter()
    session.close()
    close_s = time.perf_counter() - t

    t = time.perf_counter()
    sim, archive, lives = continuity.replay_head(session.db_path)
    replay_s = time.perf_counter() - t

    t = time.perf_counter()
    index = WorldIndex.from_state(sim.state, journal=archive)
    rebuild_s = time.perf_counter() - t
    out = {
        "state_hash_equal": sim.state.hash() == live_state,
        "journal_hash_equal": archive.hash() == live_journal,
        "close_s": round(close_s, 3),
        "replay_s": round(replay_s, 3),
        "index_rebuild_s": round(rebuild_s, 3),
        "cells": len(index.entities("cell:")),
        "alive": index.alive_count,
        "lives": len(lives),
    }
    archive.close()
    return out


def _load_tick_json(path: str) -> dict[int, float]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for run in data.get("runs", []):
        ticks = [t["step_s"] for t in run["ticks"]]
        out[run["agents"]] = round(sum(ticks) / len(ticks), 3)
    return out


def render(report: dict) -> str:
    lines: list[str] = []
    a = lines.append
    a("# v0.12, шаг 2c — состояние, снимок и индекс: тождество и цена")
    a("")
    a("Инварианты этапа проверяются `tests/test_v012_equivalence.py` "
      f"({report['invariant_tests']} тестов): эталон по каждому тику "
      "(`tests/golden/v012_reference.json`), идентичность журнала и "
      "последовательности id, детерминированный replay, совпадение "
      "полной перестройки индекса с инкрементальной после каждого тика, "
      "рестарт из архива с продолжением, совпадающим с непрерванным "
      "миром.")
    a("")
    a("## 1. Снимок: префиксные чтения")
    a("")
    a("Системы спрашивают сущности по префиксу 14 раз за тик. До правки "
      "каждый вызов сканировал ВСЕ пары (сущность, поле); после — индекс "
      "по префиксам строится один раз на снимок, дальше это O(1).")
    a("")
    a("| живых | пар | 14 сканов, с | 14 чтений по индексу, с | "
      "первый вызов (построение), с | ускорение |")
    a("|---:|---:|---:|---:|---:|---:|")
    for r in report["prefix"]:
        a(f"| {r['agents']} | {r['pairs']} | {r['scan_s']:.3f} | "
          f"{r['indexed_s']:.3f} | {r['first_call_s']:.3f} | "
          f"{r['speedup']:.0f}× |")
    a("")
    a("Совпадение ответов скана и индекса проверяется прямо в замере: "
      "если списки разойдутся, скрипт падает. Это же закреплено тестом.")
    a("")
    a("## 2. Тик до и после")
    a("")
    before = report["tick_before"]
    after = report["tick_after"]
    if before and after:
        a("| живых | тик до 2c, с | тик после 2c, с | изменение |")
        a("|---:|---:|---:|---:|")
        for size in sorted(set(before) & set(after)):
            delta = after[size] / before[size] if before[size] else 0
            a(f"| {size} | {before[size]:.3f} | {after[size]:.3f} | "
              f"{delta:.0%} |")
        a("")
        a("«До» — отчёт шага 2a (`reports/v012_profile.md`), «после» — тот "
          "же протокол (`reports/v012_profile_stage2.md`): те же seed, "
          "ruleset и число тиков.")
    else:
        a("Сравнение недоступно: нет одного из профилей.")
    a("")
    a("Заметьте: снимок **не** стал легче — он по-прежнему копирует "
      "значения и провенанс, потому что контракт «снимок не смотрит в "
      "живое состояние» остаётся. Убран не снимок, а повторяющийся скан "
      "внутри тика.")
    a("")
    a("## 3. Индекс: перестройка против инкремента")
    a("")
    a("| живых | полная перестройка, с | продвижение на тик, с | "
      "совпало после продвижения | клеток |")
    a("|---:|---:|---:|---|---:|")
    for r in report["index"]:
        a(f"| {r['agents']} | {r['rebuild_s']:.3f} | {r['advance_s']:.4f} | "
          f"{'да' if r['equal_after_advance'] else 'НЕТ'} | "
          f"{r['rebuilt_cells']} |")
    a("")
    a("Перестройка — O(пар), продвижение — O(записей тика). Именно поэтому "
      "индекс нельзя терять при рестарте (раздел 4) и нельзя обновлять "
      "по отклонённым предложениям.")
    a("")
    a("## 4. Рестарт: состояние, журнал, индекс")
    a("")
    r = report["restart"]
    a("| величина | значение |")
    a("|---|---:|")
    a(f"| состояние совпало после replay | {'да' if r['state_hash_equal'] else 'НЕТ'} |")
    a(f"| журнал совпал после replay | {'да' if r['journal_hash_equal'] else 'НЕТ'} |")
    a(f"| закрытие сессии, с | {r['close_s']:.3f} |")
    a(f"| replay из архива, с | {r['replay_s']:.3f} |")
    a(f"| перестройка индекса, с | {r['index_rebuild_s']:.3f} |")
    a(f"| клеток / живых после рестарта | {r['cells']} / {r['alive']} |")
    a("")
    a("Продолжение после рестарта проверяется отдельным тестом: четыре "
      "тика, сыгранные восстановленным миром, дают те же хеши, что четыре "
      "тика мира, который не останавливался. Это тот самый случай, "
      "который проект уже пережил при пересоздании песочницы.")
    a("")
    a("## Что это доказывает")
    a("")
    a("* Представление состояния и чтений можно менять, **не меняя "
      "историю**: golden-эталон по каждому тику и `journal.hash()` "
      "остались теми же.")
    a("* Индекс — производное, но проверяемое производное: полная "
      "перестройка и инкрементальное обновление дают одинаковые ответы "
      "после каждого тика, а рестарт восстанавливает его из архива.")
    a("* Детерминизм проверяется по тикам, а не по финалу: ошибка, "
      "которая «возвращается» к концу прогона, будет поймана.")
    a("")
    a("## Границы")
    a("")
    a("* Замеры — 2 CPU / 4.1 ГБ; абсолютные числа зависят от машины.")
    a("* 2c не меняет модель памяти состояния: пары (сущность, поле) "
      "остаются как есть. Профиль показывает, что снимок — 2.6% тика, а "
      "пик памяти определяется числом сущностей и спящим пулом; менять "
      "представление ради 2.6% было бы преждевременным усложнением.")
    a("* 100k по-прежнему не прогонялся; это контрольная точка после 2d.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", default="500,1000,2000,4000")
    parser.add_argument("--before",
                        default="experiments/reports/v012_profile.json")
    parser.add_argument("--after",
                        default="experiments/reports/v012_profile_stage2.json")
    parser.add_argument("--out", default="experiments/reports/v012_state.md")
    parser.add_argument("--json", default="experiments/reports/v012_state.json")
    args = parser.parse_args()
    sizes = [int(x) for x in args.agents.split(",") if x.strip()]

    report = {
        "invariant_tests": 7,
        "prefix": [prefix_bench(size) for size in sizes],
        "index": [index_bench(size) for size in sizes],
        "restart": restart_bench(),
        "tick_before": _load_tick_json(args.before),
        "tick_after": _load_tick_json(args.after),
    }
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
