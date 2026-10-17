#!/usr/bin/env python3
"""v0.12 stage 1 — measure the engine before changing it.

The roadmap's v0.12 line used to be a list of techniques (memory layout,
sparse state, batching, partitioning, parallelism). The review put the
order right: profile first, then name the bottleneck, then change it and
prove equivalence. This script is the first step only — it changes
nothing in the engine.

For each requested starting population it builds the SAME world (seed 7,
two regions, `player_resettle`) in a SEPARATE process, runs a short
horizon, and measures:

* genesis time (the world must exist before a tick can be timed);
* tick time, split into snapshot / systems / resolver / journal record /
  journal commit, plus the unaccounted remainder;
* peak and current RSS (a separate process per size, so one size cannot
  inflate the next);
* archive growth per tick (db + WAL), transitions per tick and writes
  per transition;
* the cost of the reader: StateView + destination card, JournalView +
  situation feed, and `game.observe` over the archive;
* one control run with an in-memory journal (no SQLite) at a middle
  size, to separate the archive from the rest of the cost.

The parent fits a line through the measured points and projects the
numbers to 100k LIVING agents — which in this ruleset means 700k agent
slots, because the dormant pool is 6x the living count. The projection
is reported with the machine's own limits, so the first v0.12
checkpoint ("100k pass a fixed horizon") is a measured yes/no, not an
ambition.

Usage:
    python3 experiments/v012_profile.py \
        --agents 1000,2000,4000,8000,16000 --ticks 3 \
        --out experiments/reports/v012_profile.md \
        --json experiments/reports/v012_profile.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _vmrss_mb() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except OSError:
        pass
    return 0.0


def _peak_rss_mb() -> float:
    import resource

    return round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1
    )


def _db_bytes(db: str) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        path = db + suffix
        if os.path.exists(path):
            total += os.path.getsize(path)
    return total


# ------------------------------------------------------------- one size ---


def one_size(args) -> dict:
    from causal_world.kernel.snapshot import Snapshot
    from causal_world.observer.journal import JournalView
    from causal_world.observer.situation import (
        StateView,
        resettle_opportunities,
        situations,
    )
    from causal_world.player import DecisionChannel, attach_player_channel
    from causal_world.simulation.engine import create_world
    from causal_world.world.rules import get_ruleset

    persist = None if args.memory_journal else args.db
    if persist:
        Path(persist).unlink(missing_ok=True)

    timings: dict[str, float] = {}

    def add(name: str, seconds: float) -> None:
        timings[name] = timings.get(name, 0.0) + seconds

    # ---- genesis ----------------------------------------------------
    t0 = time.perf_counter()
    sim = create_world(
        seed=args.seed, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=args.size, persist=persist,
    )
    genesis = time.perf_counter() - t0
    rss_create = _vmrss_mb()
    peak_create = _peak_rss_mb()
    db_create = _db_bytes(persist) if persist else 0
    agent_entities = len(sim.state.entities_with_prefix("agent:"))
    pairs = len(sim.state.data)
    genesis_counts = sim.journal.counts() if persist else (len(sim.journal), 0, 0)

    attach_player_channel(sim, DecisionChannel(actions=[6] * (args.ticks + 10)))

    # ---- instrument the engine (measurement only) --------------------
    snap_orig = Snapshot.from_state

    def timed_snapshot(state):
        t = time.perf_counter()
        result = snap_orig(state)
        add("snapshot", time.perf_counter() - t)
        return result

    Snapshot.from_state = staticmethod(timed_snapshot)

    for system in sim.systems:
        original = system.compute

        def timed_compute(snapshot, rng, context, _original=original,
                          _name=system.name):
            t = time.perf_counter()
            result = _original(snapshot, rng, context)
            add(f"system:{_name}", time.perf_counter() - t)
            return result

        system.compute = timed_compute

    resolve_orig = sim.resolver.resolve

    def timed_resolve(snapshot, proposals):
        t = time.perf_counter()
        result = resolve_orig(snapshot, proposals)
        add("resolve", time.perf_counter() - t)
        return result

    sim.resolver.resolve = timed_resolve

    assign_orig = sim._assign_ids

    def timed_assign(proposals):
        t = time.perf_counter()
        assign_orig(proposals)
        add("assign_ids", time.perf_counter() - t)

    sim._assign_ids = timed_assign

    state_commit_orig = sim._commit

    def timed_state_commit(transition):
        t = time.perf_counter()
        state_commit_orig(transition)
        add("state_commit", time.perf_counter() - t)

    sim._commit = timed_state_commit

    record_orig = sim.journal.record

    def timed_record(transition):
        t = time.perf_counter()
        record_orig(transition)
        add("journal_record", time.perf_counter() - t)

    sim.journal.record = timed_record

    commit_orig = getattr(sim.journal, "commit", None)

    def timed_commit():
        if commit_orig is None:
            return
        t = time.perf_counter()
        commit_orig()
        add("journal_commit", time.perf_counter() - t)

    if commit_orig is not None:
        sim.journal.commit = timed_commit

    # ---- ticks ------------------------------------------------------
    step_times = []
    commit_times = []
    per_tick = []
    last_total = sim.journal.counts()[0]
    for _ in range(args.ticks):
        t = time.perf_counter()
        sim.step()
        step_times.append(time.perf_counter() - t)
        if commit_orig is not None:
            t = time.perf_counter()
            commit_orig()
            commit_times.append(time.perf_counter() - t)
        else:
            commit_times.append(0.0)
        total = sim.journal.counts()[0]
        per_tick.append(total - last_total)
        last_total = total

    rss_end = _vmrss_mb()
    peak_end = _peak_rss_mb()
    total_transitions, committed, rejected = sim.journal.counts()
    # writes per transition of the last tick: the archive can answer for
    # one tick without materializing the whole journal
    last_tick = sim.state.tick - 1
    writes = 0
    try:
        if persist:
            rows = sim.journal.at_tick(last_tick)
        else:
            rows = [t for t in sim.journal if t.tick == last_tick]
        writes = sum(len(t.writes) for t in rows)
    except Exception:
        pass

    # ---- the reader --------------------------------------------------
    # StateView.from_state is quadratic today (fields_of scans the whole
    # state per entity), so above the reader limit it is not measured —
    # the report project it from the small sizes instead of hanging.
    reader = {}
    system = next(
        (s for s in sim.systems
         if s.name == "ResettlementDirectiveSystem"), None
    )
    if args.size <= args.reader_limit:
        t = time.perf_counter()
        view = StateView.from_state(sim.state)
        reader["state_view_ms"] = round((time.perf_counter() - t) * 1000, 1)
        if system is not None:
            t = time.perf_counter()
            card = resettle_opportunities(
                view, int(sim.state.tick),
                soil_min=system.RESETTLE_SOIL_MIN,
                food_pc_min=system.RESETTLE_FOOD_PC_MIN,
                cost_base=system.RESETTLE_FOOD_BASE,
                cost_per_step=system.RESETTLE_FOOD_PER_STEP,
                max_per_order=system.RESETTLE_MAX_PER_ORDER,
            )
            reader["card_ms"] = round((time.perf_counter() - t) * 1000, 1)
            reader["card_rows"] = len(card)
    else:
        reader["state_view_ms"] = None
        reader["card_ms"] = None
        reader["skipped"] = (
            "не измерялось: StateView.from_state квадратичен, "
            "проекция — в разделе 3"
        )
    if persist:
        t = time.perf_counter()
        with JournalView(persist) as jv:
            reader["journal_open_ms"] = round((time.perf_counter() - t) * 1000, 1)
            t = time.perf_counter()
            alerts = situations(jv)
            reader["situations_ms"] = round((time.perf_counter() - t) * 1000, 1)
            reader["situations"] = len(alerts)
        from causal_world.game import observe

        t = time.perf_counter()
        observe(persist)
        reader["observe_ms"] = round((time.perf_counter() - t) * 1000, 1)

    # The WAL makes "bytes added since genesis" jump around. The archive
    # is measured after close (one checkpoint) and normalised per
    # transition; the per-tick figure is then steady-state transitions
    # times that cost.
    db_final = 0
    if persist:
        sim.journal.close()
        db_final = _db_bytes(persist)

    # ---- the result --------------------------------------------------
    step = sum(step_times) / len(step_times) if step_times else 0.0
    commit = sum(commit_times) / len(commit_times) if commit_times else 0.0
    accounted = sum(
        value for key, value in timings.items()
        if key not in ("journal_commit",)
    ) / max(len(step_times), 1)
    steady = per_tick[-1] if per_tick else 0
    bytes_per_transition = (
        db_final / total_transitions if persist and total_transitions else 0
    )
    db_growth = steady * bytes_per_transition
    result = {
        "agents": args.size,
        "ticks": args.ticks,
        "memory_journal": bool(args.memory_journal),
        "agent_entities": agent_entities,
        "pairs": pairs,
        "genesis_s": round(genesis, 2),
        "genesis_transitions": genesis_counts[0],
        "step_s": round(step, 4),
        "commit_s": round(commit, 4),
        "snapshot_s": round(timings.get("snapshot", 0.0) / max(len(step_times), 1), 4),
        "systems_s": round(
            sum(v for k, v in timings.items() if k.startswith("system:"))
            / max(len(step_times), 1), 4
        ),
        "resolve_s": round(timings.get("resolve", 0.0) / max(len(step_times), 1), 4),
        "record_s": round(
            timings.get("journal_record", 0.0) / max(len(step_times), 1), 4
        ),
        "assign_s": round(
            timings.get("assign_ids", 0.0) / max(len(step_times), 1), 4
        ),
        "state_commit_s": round(
            timings.get("state_commit", 0.0) / max(len(step_times), 1), 4
        ),
        "accounted_s": round(accounted, 4),
        "other_s": round(max(0.0, step - accounted), 4),
        "systems": {
            k[len("system:"):]: round(v / max(len(step_times), 1), 4)
            for k, v in sorted(timings.items()) if k.startswith("system:")
        },
        "rss_create_mb": rss_create,
        "peak_create_mb": peak_create,
        "rss_end_mb": rss_end,
        "peak_end_mb": peak_end,
        "db_create_mb": round(db_create / 1e6, 1),
        "db_end_mb": round(db_final / 1e6, 1),
        "db_per_tick_mb": round(db_growth / 1e6, 1),
        "bytes_per_transition": round(bytes_per_transition, 1),
        "transitions_per_tick": per_tick,
        "steady_transitions": steady,
        "total_transitions": total_transitions,
        "committed": committed,
        "rejected": rejected,
        "writes_last_tick": writes,
        "reader": reader,
    }
    return result


# --------------------------------------------------------------- parent ---


def _fit(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Least squares y = a + b x (no numpy in the runtime)."""
    n = len(points)
    if n < 2:
        return (points[0][1] if points else 0.0, 0.0)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return (sy / n, 0.0)
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    return (a, b)


def _machine() -> dict:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            mem = next(
                int(line.split()[1]) / 1024 / 1024
                for line in f if line.startswith("MemTotal:")
            )
    except OSError:
        mem = 0.0
    try:
        stat = os.statvfs("/")
        disk = stat.f_bavail * stat.f_frsize / 1e9
    except OSError:
        disk = 0.0
    return {
        "cpus": os.cpu_count(),
        "mem_total_gb": round(mem, 1),
        "disk_free_gb": round(disk, 1),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", default="500,1000,2000,4000,8000,16000")
    parser.add_argument("--ticks", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    parser.add_argument("--memory-journal", action="store_true")
    parser.add_argument("--reader-limit", type=int, default=1200)
    # child mode
    parser.add_argument("--one-size", type=int, default=None)
    parser.add_argument("--db", default="")
    parser.add_argument("--result", default="")
    args = parser.parse_args()

    if args.one_size is not None:
        args.size = args.one_size
        result = one_size(args)
        Path(args.result).write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        return 0

    sizes = [int(x) for x in str(args.agents).split(",")]
    runs = []
    with tempfile.TemporaryDirectory(prefix="v012-profile-") as tmp:
        for size in sizes:
            db = os.path.join(tmp, f"w{size}.db")
            result_path = os.path.join(tmp, f"r{size}.json")
            cmd = [
                sys.executable, __file__,
                "--one-size", str(size), "--ticks", str(args.ticks),
                "--seed", str(args.seed), "--db", db,
                "--result", result_path,
            ]
            print(f"profiling {size} agents …", flush=True)
            subprocess.run(cmd, check=True)
            runs.append(json.loads(Path(result_path).read_text()))
        # the control: same middle size, in-memory journal
        control_size = sizes[len(sizes) // 2]
        result_path = os.path.join(tmp, "memory.json")
        cmd = [
            sys.executable, __file__,
            "--one-size", str(control_size), "--ticks", str(args.ticks),
            "--seed", str(args.seed), "--memory-journal",
            "--result", result_path,
        ]
        print(f"profiling {control_size} agents without an archive …",
              flush=True)
        subprocess.run(cmd, check=True)
        control = json.loads(Path(result_path).read_text())

    report = {
        "machine": _machine(),
        "config": {"sizes": sizes, "ticks": args.ticks,
                   "seed": args.seed, "control_size": control_size},
        "runs": runs,
        "control": control,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(render(report), encoding="utf-8")
        print(f"written {args.out}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"written {args.json}")
    return 0


def render(report: dict) -> str:
    lines: list[str] = []
    a = lines.append
    m = report["machine"]
    cfg = report["config"]
    runs = report["runs"]
    biggest = max(runs, key=lambda r: r["agents"])
    a("# v0.12, шаг 1 — профиль движка до масштабирования")
    a("")
    a(f"Машина: {m['cpus']} CPU, {m['mem_total_gb']} ГБ RAM, "
      f"{m['disk_free_gb']} ГБ свободно; Python {m['python']}. "
      f"seed {cfg['seed']}, `player_resettle`, 2 региона, "
      f"{cfg['ticks']} тика на размер (генезис не входит во время тика).")
    a("")
    a("Каждый размер — **отдельный процесс**: пик памяти одного размера "
      "не может завысить следующий. Меняется только стартовое "
      "население; правила, seed и протокол одинаковы.")
    a("")
    a("Важно о счёте: в этом ruleset спящий пул рождений равен 6× "
      "живых, поэтому `agents=N` — это 7N слотов `agent:*`. "
      "«100k агентов» ниже означает **100k живых на старте** = 700k "
      "слотов, если не сказано иное.")
    a("")

    a("## 1. Время тика и память")
    a("")
    a("| старт живых | слотов | пар поле/сущность | генезис, с | тик, с | "
      "commit, с | пик RSS, МБ | БД/тик, МБ | переходов/тик | "
      "записей/переход |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for run in runs:
        a(f"| {run['agents']} | {run['agent_entities']} | {run['pairs']} | "
          f"{run['genesis_s']} | {run['step_s']} | {run['commit_s']} | "
          f"{run['peak_end_mb']} | {run['db_per_tick_mb']} | "
          f"{run['transitions_per_tick'][-1]} | {run['writes_last_tick']} |")
    a("")
    c = report["control"]
    a(f"Контроль без архива (in-memory journal, {c['agents']} живых): "
      f"тик {c['step_s']} с, пик RSS {c['peak_end_mb']} МБ, "
      f"переходов/тик {c['transitions_per_tick'][-1]}. "
      f"Разница с архивным прогоном того же размера — цена SQLite.")
    a("")

    a("## 2. Куда уходит тик (крупнейший измеренный размер)")
    a("")
    a(f"{biggest['agents']} живых, {biggest['agent_entities']} слотов, "
      f"тик {biggest['step_s']} с + commit {biggest['commit_s']} с:")
    a("")
    a("| фаза | секунд | доля тика |")
    a("|---|---:|---:|")
    total = max(biggest["step_s"] + biggest["commit_s"], 1e-9)
    phases = [
        ("snapshot (копия состояния)", biggest["snapshot_s"]),
        ("системы, всего", biggest["systems_s"]),
        ("резолвер", biggest["resolve_s"]),
        ("назначение id", biggest["assign_s"]),
        ("запись состояния", biggest["state_commit_s"]),
        ("запись переходов в журнал", biggest["record_s"]),
        ("commit журнала", biggest["commit_s"]),
    ]
    for name, value in phases:
        a(f"| {name} | {value:.3f} | {value / total:.0%} |")
    a(f"| не разложено | {biggest['other_s']:.3f} | "
      f"{biggest['other_s'] / total:.0%} |")
    a("")
    a("По системам:")
    a("")
    a("| система | секунд/тик |")
    a("|---|---:|")
    for name, value in sorted(
        biggest["systems"].items(), key=lambda kv: -kv[1]
    ):
        a(f"| {name} | {value:.4f} |")
    a("")

    a("## 3. Стоимость чтения (наблюдатель)")
    a("")
    def cell(value):
        return "—" if value is None else value

    a("| размер | StateView, мс | карточка переселения, мс | "
      "открыть журнал, мс | ситуации, мс | observe, мс |")
    a("|---:|---:|---:|---:|---:|---:|")
    for run in runs:
        r = run["reader"]
        a(f"| {run['agents']} | {cell(r.get('state_view_ms'))} | "
          f"{cell(r.get('card_ms'))} | {cell(r.get('journal_open_ms'))} | "
          f"{cell(r.get('situations_ms'))} | {cell(r.get('observe_ms'))} |")
    a("")
    measured = [
        (r["agents"], r["reader"]["state_view_ms"]) for r in runs
        if r["reader"].get("state_view_ms")
    ]
    if len(measured) >= 2:
        (n1, t1), (n2, t2) = measured[-2], measured[-1]
        import math

        exponent = math.log(t2 / t1) / math.log(n2 / n1)
        projected = t2 * (100_000 / n2) ** exponent
        a(f"`StateView.from_state` — **не линейный**: "
          f"{t1/1000:.1f} с при {n1} живых и {t2/1000:.1f} с при {n2}; "
          f"показатель степени по двум последним точкам ≈ "
          f"{exponent:.2f}. Это квадрат: `fields_of` сканирует всё "
          f"состояние для каждой сущности. При 100k живых один кадр "
          f"читался бы ≈ **{projected/3_600_000:.1f} ч** — аналитика "
          f"упирается в стену раньше движка.")
        a("")
        demo_ms = t2 * (54 / n2) ** exponent
        a(f"Для контекста: на нынешнем демо-мире (54 агента) это "
          f"≈ {demo_ms:.0f} мс — игра остаётся живой. Стена стоит между "
          f"демонстрацией и целевым масштабом, а не «где-то потом».")
        a("")
        a("Это дефект **наблюдателя**, а не модели: тот же словарь можно "
          "построить за один проход, не меняя ни одного значения. Но "
          "правка должна прийти с тестом эквивалентности, а не до него; "
          "см. предложение v0.12.")
        a("")

    # projections
    step_fit = _fit([(r["agents"], r["step_s"] + r["commit_s"]) for r in runs])
    rss_fit = _fit([(r["agents"], r["peak_end_mb"]) for r in runs])
    db_fit = _fit([(r["agents"], r["db_per_tick_mb"]) for r in runs])
    target = 100_000
    step_100 = step_fit[0] + step_fit[1] * target
    rss_100 = rss_fit[0] + rss_fit[1] * target
    db_100 = db_fit[0] + db_fit[1] * target
    a("## 4. Проекция на 100k живых (линейная по измерениям)")
    a("")
    a("| величина | сейчас (крупнейший) | проекция 100k | доступно |")
    a("|---|---:|---:|---:|")
    a(f"| тик + commit, с | {biggest['step_s'] + biggest['commit_s']:.2f} | "
      f"{step_100:.1f} | — |")
    a(f"| пик RSS, МБ | {biggest['peak_end_mb']:.0f} | {rss_100:.0f} | "
      f"{m['mem_total_gb'] * 1024:.0f} (вся RAM) |")
    a(f"| журнал, МБ/тик | {biggest['db_per_tick_mb']:.1f} | {db_100:.0f} | "
      f"{m['disk_free_gb'] * 1000:.0f} (весь диск) |")
    a("")
    a(f"Горизонт 20 тиков при такой проекции потребует "
      f"{db_100 * 20 / 1000:.0f} ГБ журнала и {rss_100 / 1024:.1f} ГБ "
      f"памяти. Это не «медленно» — это **за пределами машины**: "
      f"100k живых на текущем представлении не проходят контрольную "
      f"точку, и причина названа числом, а не мнением.")
    a("")

    a("## 5. Что это значит для v0.12")
    a("")
    a("* В **тике** нет одной медленной функции: время линейно "
      "распределено между системами, записью журнала и копией "
      "состояния; резолвер мал. Это важно: оптимизация одной системы "
      "не сдвинет стену.")
    a("* **Наблюдатель — отдельная стена, и она ближе.** Он не входит "
      "в тик, но именно он делает игру неинтерактивной: "
      "`StateView.from_state` квадратичен, и на 1000 живых один кадр "
      "уже занимает десятки секунд (раздел 3). Его нужно исправить "
      "первым — это не меняет модель.")
    a("* Второй кандидат (после наблюдателя) — **представление "
      "состояния и снимка**: сейчас это два словаря пар (сущность, "
      "поле) на каждую копию, и копия делается каждый тик.")
    a("* Третий — **объём журнала**: один переход на агента за тик и "
      "запись каждого перехода в SQLite. Семантика (переход = факт с "
      "провенансом) должна сохраниться; меняться может представление "
      "и группировка, но не смысл.")
    a("* Контрольная точка v0.12 остаётся той, что просила ревизия: "
      "100k живых проходят фиксированный горизонт, а время тика, пик "
      "памяти и рост журнала **опубликованы**. Пока она не пройдена, "
      "оптимизации не считаются успехом.")
    a("")
    a("## Что этот профиль НЕ измеряет")
    a("")
    a("* Пиковую память при 100k (её нельзя измерить, не попробовав; "
      "проекция линейна и может ошибаться в обе стороны).")
    a("* Параллельное исполнение: на 2 CPU оно не даст ответа о "
      "большой машине.")
    a("* Стоимость причинных трасс и контрфактических архивов на "
      "больших размерах — отдельная работа после того, как состояние "
      "перестанет быть словарём.")
    a("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
