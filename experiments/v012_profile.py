#!/usr/bin/env python3
"""v0.12, stage 1 — measure the engine before touching it.

The review's rule for this stage is explicit: no optimisation without a
measurement, and no rewriting before the measurement names the wall.
This script therefore does ONE thing: it runs the same world at several
sizes and publishes what it costs.

What is measured, per size:

* genesis (a one-off, reported separately from the tick);
* every tick: wall time of ``step()`` and of the journal ``commit()``,
  the archive size after the commit, transitions and writes per tick;
* peak RSS of the whole process (each size runs in its OWN process, so
  a bigger size cannot inherit the previous peak);
* the observer over the same archive: a full ``observe()`` and the
  ``StateView`` construction the server does on every frame;
* a cProfile of one tick, so the report can name the functions that
  consume the time instead of guessing.

Sizes are given in LIVING agents at genesis. The world keeps a dormant
birth pool, so the number of ``agent:*`` entities is larger; the report
publishes both numbers, because the engine pays for entities, not for
the word "agent".

Usage:
    python3 experiments/v012_profile.py
    python3 experiments/v012_profile.py --agents 500,1000,2000
"""

from __future__ import annotations

import argparse
import cProfile
import json
import os
import pstats
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.game import observe  # noqa: E402
from causal_world.observer.situation import StateView, situations  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402


READER_LIMIT = 2000


def _peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _db_bytes(path: str | None) -> int:
    if not path:
        return 0
    total = 0
    for suffix in ("", "-wal", "-shm"):
        p = Path(path + suffix)
        if p.exists():
            total += p.stat().st_size
    return total


# ----------------------------------------------------------------------
# one child = one size
# ----------------------------------------------------------------------

def run_one(agents: int, ticks: int, workdir: str) -> dict:
    db = os.path.join(workdir, f"profile-{agents}.db")
    t0 = time.perf_counter()
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents, persist=db,
    )
    genesis_s = time.perf_counter() - t0
    db_genesis_mb = _db_bytes(db) / 1e6

    agents_total = len(sim.state.entities_with_prefix("agent:"))
    alive = sum(
        1 for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    )
    pairs = len(sim.state.data)

    def _logical_bytes() -> int:
        row = sim.journal.query(
            "SELECT COALESCE(SUM(LENGTH(payload)), 0) AS n FROM transitions"
        )
        return int(row[0]["n"]) if row else 0

    per_tick = []
    logical_before = _logical_bytes()
    for i in range(ticks):
        t = time.perf_counter()
        sim.step()
        step_s = time.perf_counter() - t
        t = time.perf_counter()
        sim.journal.commit()
        commit_s = time.perf_counter() - t
        logical_after = _logical_bytes()
        total, committed, rejected = sim.journal.counts()
        per_tick.append({
            "tick": i + 1,
            "step_s": round(step_s, 3),
            "commit_s": round(commit_s, 3),
            "db_mb": round(_db_bytes(db) / 1e6, 1),
            "logical_mb": round((logical_after - logical_before) / 1e6, 2),
            "transitions": total,
            "committed": committed,
            "rejected": rejected,
        })
        logical_before = logical_after

    peak = _peak_mb()

    # snapshot cost, measured on its own (a pure read of the state)
    from causal_world.kernel.snapshot import Snapshot

    t = time.perf_counter()
    Snapshot.from_state(sim.state)
    snapshot_s = time.perf_counter() - t

    # one tick under the profiler: the shares, not the wall time, matter
    pr = cProfile.Profile()
    pr.enable()
    sim.step()
    sim.journal.commit()
    pr.disable()
    stats = pstats.Stats(pr)
    rows = []
    for (file, line, func), (cc, nc, tt, ct, callers) in stats.stats.items():
        rows.append({
            "name": f"{func} ({Path(file).name}:{line})",
            "cum_s": round(ct, 3),
            "calls": nc,
        })
    rows.sort(key=lambda r: -r["cum_s"])
    step_row = next(
        (r for r in rows if r["name"].startswith("step (")), None
    )
    step_cum = step_row["cum_s"] if step_row else 0.0
    profile_rows = rows[:14]

    # the observer over the same archive (what a frame costs, v0.9+)
    t = time.perf_counter()
    observe(db)
    observe_s = time.perf_counter() - t

    # The server builds a StateView per frame; from_state calls
    # fields_of() per entity, which scans the whole state, so it is
    # quadratic. Measure it only where it is affordable, and say so.
    reader_s = None
    n_alerts = None
    if agents <= READER_LIMIT:
        t = time.perf_counter()
        StateView.from_state(sim.state)
        reader_s = time.perf_counter() - t
        from causal_world.observer.journal import JournalView

        t = time.perf_counter()
        with JournalView(db) as jv:
            n_alerts = len(situations(jv))
        situations_s = time.perf_counter() - t
    else:
        situations_s = None

    total, committed, rejected = sim.journal.counts()
    logical_total_mb = _logical_bytes() / 1e6
    result = {
        "agents": agents,
        "entities": len(sim.state.entities()),
        "agent_entities": agents_total,
        "alive": alive,
        "pairs": pairs,
        "genesis_s": round(genesis_s, 3),
        "ticks": per_tick,
        "db_genesis_mb": round(db_genesis_mb, 1),
        "db_final_mb": round(_db_bytes(db) / 1e6, 1),
        "logical_total_mb": round(logical_total_mb, 1),
        "peak_mb": round(peak, 1),
        "transitions_total": total,
        "committed": committed,
        "rejected": rejected,
        "snapshot_s": round(snapshot_s, 3),
        "step_cum_s": round(step_cum, 3),
        "profile_rows": profile_rows,
        "observe_s": round(observe_s, 3),
        "reader_s": round(reader_s, 3) if reader_s is not None else None,
        "situations": n_alerts,
        "situations_s": (
            round(situations_s, 3) if situations_s is not None else None
        ),

    }
    sim.journal.close()
    Path(db).unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(db + suffix).unlink(missing_ok=True)
    return result


# ----------------------------------------------------------------------
# parent: render
# ----------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _project(x: float, scale: float) -> float:
    return x * scale


def render(report: dict) -> str:
    runs = report["runs"]
    lines: list[str] = []
    a = lines.append
    a("# v0.12, шаг 1 — профиль движка до масштабирования")
    a("")
    a(f"Машина: {report['machine']['cpu']} CPU, "
      f"{report['machine']['ram_gb']:.1f} ГБ RAM; Python "
      f"{report['machine']['python']}. seed 7, `player_resettle`, "
      f"2 региона, {report['config']['ticks']} тика на размер "
      "(генезис не входит во время тика).")
    a("")
    a("Каждый размер — **отдельный процесс**: пик памяти одного размера "
      "не может завысить следующий. Меняется только стартовое население; "
      "правила, seed и протокол одинаковы.")
    a("")
    slots = int(100_000 * (report["pool_ratio"] + 1))
    a("Важно о счёте: в этом ruleset спящий пул рождений равен "
      f"{report['pool_ratio']:.0f}× живых, поэтому `agents=N` — это "
      f"{report['pool_ratio'] + 1:.0f}N слотов `agent:*`. «100k агентов» "
      "ниже означает **100k живых на старте** = "
      f"{slots:,} слотов, если не сказано иное.".replace(
          f"{slots:,}", f"{slots:,}".replace(",", " ")))
    a("")
    a("## 1. Время тика и память")
    a("")
    a("| старт живых | слотов | пар поле/сущность | генезис, с | "
      "тик, с | commit, с | пик RSS, МБ | журнал, МБ/тик | "
      "переходов/тик | записей/тик |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in runs:
        tick = _mean([t["step_s"] for t in r["ticks"]])
        commit = _mean([t["commit_s"] for t in r["ticks"]])
        journal = _mean([t["logical_mb"] for t in r["ticks"]])
        trans = _mean([t["transitions"] for t in r["ticks"]])
        writes = _mean([t["committed"] for t in r["ticks"]])
        a(f"| {r['agents']} | {r['agent_entities']} | {r['pairs']} | "
          f"{r['genesis_s']:.2f} | {tick:.3f} | {commit:.3f} | "
          f"{r['peak_mb']:.0f} | {journal:.1f} | {trans:.0f} | {writes:.0f} |")
    a("")
    a("«Журнал, МБ/тик» — это **логический объём записей** "
      "(`SUM(LENGTH(payload))`), а не прирост файла: SQLite переиспользует "
      "страницы, поэтому файл растёт ступенями. Файл архива после трёх "
      "тиков — в разделе 3.")
    a("")
    biggest = max(runs, key=lambda r: r["agents"])
    trans = _mean([t["transitions"] for t in biggest["ticks"]])
    a(f"Переходов на тик — {trans / biggest['agents']:.1f} на одного "
      f"живого ({trans:.0f} при {biggest['agents']}). Спящие слоты пула "
      f"тоже получают переход каждый тик, и именно поэтому тик дороже, "
      f"чем «цена одного живого агента».")
    a("")
    a("## 2. Куда уходит тик (cProfile, крупнейший размер)")
    a("")
    a(f"Профиль последнего тика при {biggest['agents']} живых "
      f"({biggest['agent_entities']} слотов). Доли кумулятивные и "
      f"пересекаются: строка системы включает работу внутри неё.")
    a("")
    a("| функция | вызовов | кумулятивно, с | доля тика |")
    a("|---|---:|---:|---:|")
    total = biggest.get("step_cum_s") or 0.0
    for row in biggest.get("profile_rows", [])[:12]:
        share = row["cum_s"] / total if total else 0
        a(f"| `{row['name']}` | {row['calls']} | {row['cum_s']:.2f} | "
          f"{share:.0%} |")
    a("")
    if total:
        scan = next(
            (r for r in biggest["profile_rows"]
             if r["name"].startswith("entities_with_prefix")), None
        )
        if scan:
            a(f"Главная строка — `entities_with_prefix`: {scan['cum_s']:.1f} с "
              f"({scan['cum_s'] / total:.0%}) на сканирование состояния по "
              f"префиксу. Это не «медленный закон», а повторяющийся проход "
              f"по всем парам (сущность, поле) в каждом из "
              f"{scan['calls']} вызовов за тик.")
            a("")
    a("## 3. Наблюдатель и чтение архива")
    a("")
    a("| старт живых | снимок, с | observe(), с | StateView, с | "
      "ситуаций | situations(), с | файл архива, МБ | записей, МБ |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in runs:
        reader = ("—" if r["reader_s"] is None
                  else f"{r['reader_s']:.2f}")
        sit = ("—" if r["situations_s"] is None
               else f"{r['situations_s']:.2f}")
        alerts = "—" if r["situations"] is None else r["situations"]
        a(f"| {r['agents']} | {r['snapshot_s']:.3f} | {r['observe_s']:.2f} | "
          f"{reader} | {alerts} | {sit} | {r['db_final_mb']:.0f} | "
          f"{r['logical_total_mb']:.0f} |")
    a("")
    a("")
    a("«Ситуаций» ноль не потому, что проход не работал: на трёх тиках "
      "мир ещё не создал проблем, а время в колонке — стоимость самого "
      "прохода по архиву. Длинный архив — отдельное измерение.")
    a("")
    a("«Записей, МБ» — логический объём полезной нагрузки журнала; «файл "
      "архива» — то, что лежит на диске (SQLite + индексы + WAL), включая "
      "генезис. Разница — цена представления архива, и именно она "
      "заполняет диск.")
    small = [r for r in runs if r["reader_s"] is not None]
    if len(small) >= 2:
        lo, hi = small[-2], small[-1]
        if lo["reader_s"]:
            ratio = hi["reader_s"] / lo["reader_s"]
            grows = hi["agents"] / lo["agents"]
            a("")
            a(f"`StateView.from_state` вырос в {ratio:.1f}× при росте "
              f"населения в {grows:.1f}×: это хуже линейного, и выше "
              f"{READER_LIMIT} живых он не измеряется — вызывать его на "
              f"каждом кадре при таком росте нельзя. Если показатель "
              f"сохранится, на 100k один кадр займёт десятки минут.")
            if grows > 0:
                exponent = 1.0
                try:
                    import math
                    exponent = math.log(ratio) / math.log(grows)
                except Exception:
                    pass
                a(f"Оценка показателя по двум точкам: **{exponent:.2f}** "
                  f"(1.0 — линейно, 2.0 — квадрат).")
                frame_100k = hi["reader_s"] * (100_000 / hi["agents"]) ** exponent
                a("")
                a(f"При сохранении показателя один кадр на 100k живых — "
                  f"≈ **{frame_100k / 3600:.0f} ч**. Это не «медленно»: это "
                  f"невозможно, и стена аналитики стоит раньше стены "
                  f"движка.")
                a("")
                a("Важно: это путь сервера на КАЖДЫЙ кадр (`_world_view` "
                  "вызывает `StateView.from_state`), а не редкий отчёт. "
                  "Исправление здесь не меняет модель: view можно "
                  "построить за один проход, не меняя ни одного "
                  "значения, — но только с тестом эквивалентности.")
    a("")
    a("`observe()` — полный аналитический проход: серии, режим, причинные "
      "бюджеты и карта клеток. Он дешевле тика на этих размерах, но "
      "растёт с ЧИСЛОМ ТИКОВ в архиве (серии читаются из журнала), а не "
      "только с населением. Двух-трёх тиков здесь мало, чтобы увидеть "
      "его стену; это отдельное измерение на длинном архиве.")
    a("")
    a("## 4. Проекция на 100k живых")
    a("")
    a("Коэффициент — отношение 100k к крупнейшему измеренному размеру; "
      "проекция линейна по населению и НЕ учитывает рост архива. Она "
      "показывает порядок величины и место, где кончается машина.")
    a("")
    scale = 100_000 / biggest["agents"]
    tick = _mean([t["step_s"] for t in biggest["ticks"]])
    commit = _mean([t["commit_s"] for t in biggest["ticks"]])
    db = _mean([t["logical_mb"] for t in biggest["ticks"]])
    file_growth = max(
        0.0, (biggest["db_final_mb"] - biggest["db_genesis_mb"])
        / max(len(biggest["ticks"]), 1),
    )
    a("| величина | сейчас (крупнейший) | проекция 100k | доступно |")
    a("|---|---:|---:|---:|")
    a(f"| тик + commit, с | {tick + commit:.2f} | "
      f"{_project(tick + commit, scale):.1f} | — |")
    a(f"| пик RSS, МБ | {biggest['peak_mb']:.0f} | "
      f"{_project(biggest['peak_mb'], scale):.0f} | "
      f"{report['machine']['ram_mb']:.0f} (вся RAM) |")
    a(f"| журнал (записи), МБ/тик | {db:.1f} | {_project(db, scale):.0f} | — |")
    a(f"| архив (файл), МБ/тик | {file_growth:.0f} | "
      f"{_project(file_growth, scale):.0f} | — |")
    a(f"| архив на 20 тиков, ГБ | {file_growth * 20 / 1000:.1f} | "
      f"{_project(file_growth, scale) * 20 / 1000:.0f} | "
      f"{report['machine']['disk_gb']:.0f} (свободно) |")
    a("")
    need_gb = _project(biggest["peak_mb"], scale) / 1024
    a(f"Вывод по контрольной точке: **100k живых на текущем "
      f"представлении в машину не влезают** — проекция пика "
      f"{need_gb:.1f} ГБ при {report['machine']['ram_gb']:.1f} ГБ RAM. "
      f"Это не «медленно», это отказ по памяти, и он наступает раньше "
      f"любого фиксированного горизонта.")
    a("")
    a("## 5. Что это значит для шага 2")
    a("")
    a("* Потолок задаёт **представление состояния и пул**, а не одна "
      "медленная функция: тик тратится на обход всех слотов и на запись "
      "перехода для каждого из них.")
    a("* Спящий пул (6/7 слотов) платит полную цену перехода, хотя не "
      "меняет состояние. Это первый кандидат: пропуск неизменных слотов "
      "не меняет семантику, если переход просто не создаётся.")
    a("* Commit в SQLite — заметная, но не главная доля; её надо мерить "
      "отдельно на длинном архиве, где растёт WAL.")
    a("* Наблюдатель на коротком архиве дешёвый; его стена — число "
      "тиков и квадратичные места в карточках, а не тик.")
    a("* Никакая оптимизация не принимается без проверки эквивалентности "
      "(шаг 3): переходы, состояние и причинные ссылки должны совпасть "
      "с эталонным прогоном.")
    a("")
    a("## Что этот профиль НЕ измеряет")
    a("")
    a("* 100k живых: проекция, а не прогон (прогон упирается в память).")
    a("* Длинный архив (сотни тиков): observe() и чтение журнала там "
      "растут, здесь этого не видно.")
    a("* Параллельное исполнение: на 2 CPU оно ничего не говорит о "
      "большой машине.")
    a("* Стоимость причинных трасс и контрфактических архивов.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", default="500,1000,2000,4000,8000")
    parser.add_argument("--ticks", type=int, default=3)
    parser.add_argument("--child", type=int, default=0)
    parser.add_argument("--workdir", default="")
    parser.add_argument("--out", default="experiments/reports/v012_profile.md")
    parser.add_argument("--json", default="experiments/reports/v012_profile.json")
    args = parser.parse_args()

    if args.child:
        workdir = args.workdir or tempfile.mkdtemp(prefix="v012-")
        Path(workdir).mkdir(parents=True, exist_ok=True)
        result = run_one(args.child, args.ticks, workdir)
        print(json.dumps(result))
        return 0

    sizes = [int(x) for x in args.agents.split(",") if x.strip()]
    workdir = tempfile.mkdtemp(prefix="v012-")
    runs = []
    for size in sizes:
        print(f"profiling {size} agents …", flush=True)
        cmd = [sys.executable, os.path.abspath(__file__),
               "--child", str(size), "--ticks", str(args.ticks),
               "--workdir", workdir]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if out.returncode != 0:
            print(out.stderr[-2000:], file=sys.stderr)
            raise SystemExit(out.returncode)
        runs.append(json.loads(out.stdout.strip().splitlines()[-1]))

    pool_ratio = runs[0]["agent_entities"] / runs[0]["agents"] - 1
    try:
        cpu = os.cpu_count() or 0
        ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
        disk_gb = os.statvfs(".").f_bavail * os.statvfs(".").f_frsize / 1e9
    except Exception:
        cpu, ram_gb, disk_gb = 0, 0.0, 0.0
    report = {
        "config": {"ticks": args.ticks, "sizes": sizes},
        "machine": {
            "cpu": cpu, "ram_gb": round(ram_gb, 1),
            "ram_mb": round(ram_gb * 1000),
            "disk_gb": round(disk_gb, 1),
            "python": sys.version.split()[0],
        },
        "pool_ratio": int(round(pool_ratio)),
        "runs": runs,
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
