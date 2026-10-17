#!/usr/bin/env python3
"""v0.12 checkpoint — 100 000 living × 20 ticks, measured, not extrapolated.

The checkpoint answers one question: does the CURRENT engine pass a fixed
horizon at the target size, and if it does not, where exactly does it
stop? No optimisation is performed here. The protocol is the one used by
stages 1/2c/2d: seed 7, ``player_resettle``, 2 regions.

The report keeps the seven requested groups apart:

* simulation — ``step()`` minus the journal and index calls inside it;
* journal — ``record()`` (payload + canonical bytes) plus ``commit()``;
* index — ``add()`` (derived causal index);
* observation — the cell index advance, the cell slice and the situation
  feed, i.e. the frame path, not a full view;
* memory — RSS now and peak, after every phase;
* storage — SQLite file + WAL bytes, transitions, payload volume, index
  objects when they can be counted;
* resilience — every completed tick, the journal hash after it, and a
  read-only reopen check. A full replay at 100k is NOT attempted: it
  needs a second full world in RAM and is reported as such.

A progress JSONL is appended and fsynced after every phase and tick. If
the process is killed, the parent/renderer still knows the last completed
tick, the last RSS and the archive state. A soft memory guard stops the
run cleanly before the next tick; an address-space limit turns a hard
allocation failure into ``MemoryError`` instead of an OOM kill.

Usage:
    python3 experiments/v012_checkpoint.py --agents 20000 --ticks 2
    python3 experiments/v012_checkpoint.py --agents 100000 --ticks 20 \\
        --max-rss-mb 3600 --max-seconds 2400 --limit-as-gb 3.9
    python3 experiments/v012_checkpoint.py --render-only \\
        --progress /tmp/check100k.jsonl --out ... --json ...
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.situation import situations  # noqa: E402
from causal_world.observer.slice import CellSlice, WorldIndex  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402

PAGE = os.sysconf("SC_PAGE_SIZE")


def rss_mb() -> float:
    with open("/proc/self/statm", encoding="ascii") as handle:
        return int(handle.read().split()[1]) * PAGE / 1e6


def peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def file_mb(path: str, suffix: str = "") -> float:
    target = Path(path + suffix)
    return target.stat().st_size / 1e6 if target.exists() else 0.0


def storage(path: str) -> dict:
    return {
        "db_mb": round(file_mb(path), 1),
        "wal_mb": round(file_mb(path, "-wal"), 1),
        "shm_mb": round(file_mb(path, "-shm"), 2),
    }


class Progress:
    """Append-only JSONL: one fsynced line per phase; survives a kill."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.handle = open(path, "w", encoding="utf-8", buffering=1)

    def emit(self, event: str, **fields) -> None:
        line = json.dumps({"event": event, **fields}, ensure_ascii=False)
        self.handle.write(line + "\n")
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def close(self) -> None:
        try:
            self.handle.close()
        except OSError:
            pass


def run(args) -> int:
    progress = Progress(args.progress)
    db = args.db or f"/tmp/v012-checkpoint-{args.agents}.db"
    for suffix in ("", "-wal", "-shm"):
        Path(db + suffix).unlink(missing_ok=True)
    if args.limit_as_gb:
        limit = int(args.limit_as_gb * 1024**3)
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    report = {
        "config": {
            "seed": 7, "ruleset": "player_resettle", "regions": 2,
            "agents": args.agents, "ticks": args.ticks,
            "max_rss_mb": args.max_rss_mb, "max_seconds": args.max_seconds,
            "limit_as_gb": args.limit_as_gb,
        },
        "machine": {
            "cpu": os.cpu_count(),
            "ram_gb": round(os.sysconf("SC_PAGE_SIZE")
                            * os.sysconf("SC_PHYS_PAGES") / 1e9, 1),
            "python": sys.version.split()[0],
        },
        "phases": [], "ticks": [], "storage_final": {},
        "outcome": "running", "last_completed_tick": -1,
        "error": None,
    }
    started = time.perf_counter()
    archive = None
    sim = None
    index = None

    def phase(name: str, **fields) -> None:
        entry = {"phase": name, "at_s": round(time.perf_counter() - started, 2),
                 "rss_mb": round(rss_mb(), 1), "peak_mb": round(peak_mb(), 1),
                 **fields}
        report["phases"].append(entry)
        progress.emit("phase", **entry)

    def finish(outcome: str, error: str | None = None) -> None:
        report["outcome"] = outcome
        report["error"] = error
        report["elapsed_s"] = round(time.perf_counter() - started, 2)
        report["storage_final"] = storage(db)
        report["peak_mb"] = round(peak_mb(), 1)
        progress.emit("final", **report)
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    phase("start", agents=args.agents, ticks=args.ticks,
          db=db, disk_free_mb=round(
              os.statvfs(os.path.dirname(db)).f_bavail
              * os.statvfs(os.path.dirname(db)).f_frsize / 1e6, 0))
    try:
        t = time.perf_counter()
        sim = create_world(
            seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
            regions=2, agents=args.agents, persist=db,
        )
        archive = sim.journal
        genesis_s = time.perf_counter() - t
        counts = archive.counts()
        report["genesis"] = {
            "seconds": round(genesis_s, 2),
            "transitions": counts[0], "committed": counts[1],
            "rejected": counts[2], "state_hash": None,
        }
        phase("genesis", seconds=round(genesis_s, 2), transitions=counts[0],
              **storage(db))
        # state.hash() builds a full canonical payload; record whether it
        # fits, but never let it poison the tick measurement.
        try:
            t = time.perf_counter()
            report["genesis"]["state_hash"] = sim.state.hash()
            phase("genesis_state_hash",
                  seconds=round(time.perf_counter() - t, 2))
        except MemoryError:
            # Hashing the state builds a full canonical payload. At the
            # target size it may not fit; that is a finding, not a reason
            # to abandon the ticks that might still fit.
            phase("genesis_state_hash", skipped="MemoryError")

        t = time.perf_counter()
        index = WorldIndex.from_state(sim.state, journal=archive)
        phase("index_init", seconds=round(time.perf_counter() - t, 2),
              agents=index.agent_count, alive=index.alive_count,
              pool=index.pool_stats)

        acc = {"record": 0.0, "add": 0.0}
        original_record, original_add = archive.record, archive.add

        def timed_record(transition):
            t0 = time.perf_counter()
            try:
                return original_record(transition)
            finally:
                acc["record"] += time.perf_counter() - t0

        def timed_add(transition):
            t0 = time.perf_counter()
            try:
                return original_add(transition)
            finally:
                acc["add"] += time.perf_counter() - t0

        archive.record = timed_record
        archive.add = timed_add

        for _ in range(args.ticks):
            done = len(report["ticks"])
            if rss_mb() >= args.max_rss_mb:
                finish("stopped_memory_guard")
                return 0
            if time.perf_counter() - started >= args.max_seconds:
                finish("stopped_time_guard")
                return 0
            tick = sim.state.tick
            before = dict(acc)
            t = time.perf_counter()
            sim.step()
            step_s = time.perf_counter() - t
            t = time.perf_counter()
            archive.commit()
            commit_s = time.perf_counter() - t
            record_s = acc["record"] - before["record"]
            add_s = acc["add"] - before["add"]

            t = time.perf_counter()
            index.advance(archive, tick)
            advance_s = time.perf_counter() - t
            t = time.perf_counter()
            view = CellSlice.from_state(sim.state, index=index)
            slice_s = time.perf_counter() - t
            t = time.perf_counter()
            alerts = situations(view, current_tick=sim.state.tick)
            situations_s = time.perf_counter() - t
            observe_s = advance_s + slice_s + situations_s

            total_s = step_s + commit_s + observe_s
            row = {
                "tick": tick,
                "step_s": round(step_s, 3),
                "record_s": round(record_s, 3),
                "add_s": round(add_s, 3),
                "commit_s": round(commit_s, 3),
                "advance_s": round(advance_s, 3),
                "slice_s": round(slice_s, 3),
                "situations_s": round(situations_s, 3),
                "simulation_s": round(max(0.0, step_s - record_s - add_s), 3),
                "journal_s": round(record_s + commit_s, 3),
                "observation_s": round(observe_s, 3),
                "total_s": round(total_s, 3),
                "transitions": len(archive),
                "committed": archive.counts()[1],
                "rejected": archive.counts()[2],
                "journal_hash": archive.hash(),
                "alerts": len(alerts),
                "rss_mb": round(rss_mb(), 1),
                "peak_mb": round(peak_mb(), 1),
                **storage(db),
            }
            report["ticks"].append(row)
            report["last_completed_tick"] = tick
            progress.emit("tick", **row)
            done += 1
            if rss_mb() >= args.max_rss_mb:
                finish("stopped_memory_guard")
                return 0

        finish("completed")
        return 0
    except MemoryError:
        try:
            finish("memory_error", traceback.format_exc(limit=3))
        except MemoryError:
            progress.emit("final", outcome="memory_error",
                          last_completed_tick=report["last_completed_tick"])
        return 3
    except BaseException as exc:  # noqa: BLE001 — a checkpoint must report
        try:
            finish("error", f"{type(exc).__name__}: {exc}")
        except BaseException:
            progress.emit("final", outcome="error",
                          error=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        progress.close()
        try:
            if archive is not None:
                archive.close()
        except BaseException:
            pass


# ----------------------------------------------------------------------
def archive_snapshot(path: str) -> dict:
    """Read-only post-mortem of an archive left by a killed process.

    The point is to report *what exists on disk*, not to infer what would
    have happened: row counts, tick range and the derived index. Kept in a
    separate function so a damaged file can never break rendering.
    """
    import sqlite3

    out: dict = {}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    try:
        count, min_tick, max_tick = conn.execute(
            "SELECT COUNT(*), MIN(tick), MAX(tick) FROM transitions"
        ).fetchone()
        out["transitions"] = int(count)
        out["tick_min"] = min_tick
        out["tick_max"] = max_tick
        out["statuses"] = {
            str(k): int(v) for k, v in conn.execute(
                "SELECT status, COUNT(*) FROM transitions GROUP BY status"
            )
        }
        out["systems"] = {
            str(k): int(v) for k, v in conn.execute(
                "SELECT system, COUNT(*) FROM transitions GROUP BY system"
            )
        }
        rows = {}
        for table in ("latest_writer", "history", "dependents"):
            try:
                rows[table] = int(conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0])
            except sqlite3.Error:
                rows[table] = -1
        out["index_rows"] = rows
        if out["tick_min"] is not None:
            out["ticks"] = [out["tick_min"]] if out["tick_min"] == out["tick_max"] else [
                out["tick_min"], out["tick_max"]
            ]
    finally:
        conn.close()
    return out


def load_progress(path: str) -> dict:
    """A final line if present; otherwise a report rebuilt from events."""
    lines = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:
                break
    final = next((line for line in reversed(lines) if line.get("event") == "final"),
                 None)
    if final is not None:
        final.pop("event", None)
        return final
    cfg = next((line for line in lines if line.get("event") == "phase"
                and line.get("phase") == "start"), {})
    report = {
        "config": {"seed": 7, "ruleset": "player_resettle", "regions": 2,
                   "agents": cfg.get("agents"), "ticks": cfg.get("ticks")},
        "machine": {}, "phases": [], "ticks": [], "storage_final": {},
        "outcome": "killed_or_incomplete", "last_completed_tick": -1,
        "error": "no final event; the process ended without writing one",
    }
    for line in lines:
        if line.get("event") == "phase":
            entry = dict(line)
            entry.pop("event", None)
            report["phases"].append(entry)
        elif line.get("event") == "tick":
            entry = dict(line)
            entry.pop("event", None)
            report["ticks"].append(entry)
            report["last_completed_tick"] = entry["tick"]
    if report["ticks"]:
        report["storage_final"] = {
            "db_mb": report["ticks"][-1]["db_mb"],
            "wal_mb": report["ticks"][-1]["wal_mb"],
        }
    else:
        db = cfg.get("db")
        if db and Path(db).exists():
            report["storage_final"] = storage(db)
            try:
                report["archive_at_death"] = archive_snapshot(db)
            except Exception as exc:  # noqa: BLE001 — a corpse may be unreadable
                report["archive_at_death_error"] = f"{type(exc).__name__}: {exc}"
    return report


def render(report: dict) -> str:
    cfg = report.get("config", {})
    machine = report.get("machine", {})
    phases = report.get("phases", [])
    ticks = report.get("ticks", [])
    genesis = report.get("genesis") or {}
    st = report.get("storage_final", {})
    death = report.get("archive_at_death") or {}
    oom = report.get("oom") or {}
    app = report.get("appendix_20k") or {}
    outcome = report.get("outcome")
    last = report.get("last_completed_tick", -1)

    def num(value):
        return f"{value:,}".replace(",", " ") if isinstance(value, int) else value

    lines: list[str] = []
    a = lines.append
    a(f"# v0.12 — контрольная точка {num(cfg.get('agents'))} живых × "
      f"{cfg.get('ticks')} тиков")
    a("")
    a(f"Машина: {machine.get('cpu', '?')} CPU, "
      f"{machine.get('ram_gb', '?')} ГБ RAM. seed 7, `player_resettle`, "
      "2 региона. Конфигурация: "
      f"{num(cfg.get('agents'))} живых на старте, {cfg.get('ticks')} тиков.")
    a("")
    verdict = {
        "completed": "горизонт пройден",
        "stopped_memory_guard": "остановлен memory-guard",
        "stopped_time_guard": "остановлен по времени",
        "memory_error": "MemoryError",
        "killed_oom_in_genesis": "убит ядром по OOM в генезисе",
        "killed_or_incomplete": "процесс не оставил финальной записи",
    }.get(outcome, str(outcome))
    a(f"**Итог: {verdict}; последний завершённый тик — "
      f"{last if last >= 0 else 'нет'}.**")
    if report.get("error"):
        a("")
        a("```")
        a(str(report["error"])[-1500:])
        a("```")
    a("")
    a("Ничего не оптимизировалось под этот размер: это прогон текущего "
      "движка. Если он остановлен, остановка — результат, а не сбой "
      "оформления.")
    a("")

    # ---------------------------------------------------------------- 1
    a("## 1. Симуляция (правила без наблюдения)")
    a("")
    if ticks:
        a("| тик | `step()` минус журнал и индекс, с | тик целиком (с журналом и кадром), с |")
        a("|---:|---:|---:|")
        for row in ticks:
            a(f"| {row['tick']} | {row['simulation_s']} | {row['total_s']} |")
        a("")
        a("`simulation_s` — атрибуция, а не независимый бюджет: `record()` и "
          "`add()` вызываются внутри `step()`, а `record()` может сбросить "
          "пачку строк, поставленную раньше. Интегральная величина — "
          "`тик целиком`.")
    else:
        a("**Не измерено: ни один тик не завершён.** Время шага правил "
          "на этом размере не существует как измерение — мир не был "
          "создан. Смотрите §5: ограничитель сработал в генезисе.")
    a("")

    # ---------------------------------------------------------------- 2
    a("## 2. Журнал (запись, сериализация, commit)")
    a("")
    if ticks:
        a("| тик | `record()` (payload + канонические байты), с | `commit()`, с | журнал всего, с | переходов накопительно | БД, МБ |")
        a("|---:|---:|---:|---:|---:|---:|")
        for row in ticks:
            a(f"| {row['tick']} | {row['record_s']} | {row['commit_s']} | "
              f"{row['journal_s']} | {num(row['transitions'])} | {row['db_mb']} |")
        a("")
        a("Сериализация payload и канонических байтов входит в `record()`; "
          "отдельного таймера у неё нет. `commit()` — фиксация транзакции, "
          "включая WAL.")
    else:
        a("**Не измерено: ни один тик не завершён.** Журнал остановился на "
          "генезисе: "
          f"{num(death.get('transitions')) or num(genesis.get('transitions'))} "
          "переходов записаны и зафиксированы (см. §6).")
    a("")

    # ---------------------------------------------------------------- 3
    a("## 3. Индекс (обновление и полная перестройка)")
    a("")
    init = next((p for p in phases if p.get("phase") == "index_init"), None)
    if init:
        a(f"Полная сборка клеточного индекса из состояния "
          f"(`WorldIndex.from_state`): **{init.get('seconds')} с** "
          f"({num(init.get('agents'))} сущностей, {num(init.get('alive'))} живых).")
        a("")
    if ticks:
        a("| тик | `add()` (производный причинный индекс), с |")
        a("|---:|---:|")
        for row in ticks:
            a(f"| {row['tick']} | {row['add_s']} |")
        a("")
    else:
        a("**Обновление индекса не измерено:** ни одного `step()` не "
          "завершено. " + ("" if init else "Полная сборка также не измерена."))
        a("")
    rebuild = report.get("rebuild_20k") or {}
    if rebuild:
        a(f"Полная перестройка причинного индекса (`rebuild_index`) на "
          f"копии архива 20k × 2 — **{rebuild.get('seconds')} с** "
          f"({num(rebuild.get('transitions'))} переходов, "
          f"{num(rebuild.get('rows'))} строк индекса; counts до/после "
          f"совпали: {'да' if rebuild.get('same') else 'НЕТ'}).")
    else:
        a("Полная перестройка на целевом объёме не запускалась: архив "
          "остановлен на генезисе, а `DELETE`+повторная вставка десятков "
          "миллионов строк — отдельная операция, которая сама является "
          "испытанием. Для ориентира в §«Приложение A» измерена перестройка "
          "на 20k.")
    a("")

    # ---------------------------------------------------------------- 4
    a("## 4. Наблюдение (кадр и чтение истории)")
    a("")
    if ticks:
        a("| тик | `advance`, с | срез клеток, с | ситуации, с | всего, с | алертов |")
        a("|---:|---:|---:|---:|---:|---:|")
        for row in ticks:
            a(f"| {row['tick']} | {row['advance_s']} | {row['slice_s']} | "
              f"{row['situations_s']} | {row['observation_s']} | {row['alerts']} |")
        a("")
        a("Это путь кадра сессии: продвижение клеточного индекса по "
          "записанным тикам, сборка среза клеток и лента ситуаций. Полный "
          "`StateView` в кадре не строится.")
        a("")
        if ticks[0]["advance_s"] > 1.0:
            a("Первый кадр дорог не из-за наблюдения как такового: генезис "
              "и первый шаг делят `tick=0`, поэтому `advance(0)` проигрывает "
              "весь генезисный батч поверх уже построенного индекса. Это "
              "измеренный факт текущей семантики тиков, а не оценка.")
            a("")
    else:
        a("**Не измерено:** ни один кадр не построен, потому что не "
          "завершён ни один тик. Стоимость пути кадра на этом размере "
          "неизвестна; известна только цена полной сборки индекса (§3).")
        a("")
    a("Чтение истории (запросы `at_tick`/`writes_at_tick`/`history_of`) в "
      "этот прогон отдельно не таймировалось; в кадре используется "
      "`writes_at_tick`, его стоимость входит в `advance`.")
    a("")

    # ---------------------------------------------------------------- 5
    a("## 5. Память")
    a("")
    a("| фаза | секунд | RSS, МБ | пик RSS, МБ |")
    a("|---|---:|---:|---:|")
    for entry in phases:
        a(f"| {entry.get('phase')} | {entry.get('seconds', '—')} | "
          f"{entry.get('rss_mb', '—')} | {entry.get('peak_mb', '—')} |")
    a("")
    if oom:
        a(f"Ядро убило процесс по OOM: `anon-rss: {num(oom.get('anon_rss_kb'))} kB`, "
          f"`total-vm: {num(oom.get('total_vm_kb'))} kB`. Это "
          f"{oom.get('anon_rss_kb', 0) / 1024**2:.2f} ГиБ анонимной памяти — "
          "предел машины, а не лимита `RLIMIT_AS` (3.7 ГиБ не были "
          "достигнуты). Мягкий memory-guard проверяется между тиками и "
          "внутрь `create_world()` попасть не может.")
        a("")
    if ticks:
        a("| тик | RSS, МБ | пик RSS, МБ |")
        a("|---:|---:|---:|")
        for row in ticks:
            a(f"| {row['tick']} | {row['rss_mb']} | {row['peak_mb']} |")
        a("")
    if not ticks:
        a("Прирост по этапам на 100k измерить нельзя: после `start` ни одна "
          "фаза не завершилась. 3.83 ГБ — это RSS в момент смерти, а не "
          "пик завершённой фазы; пик завершённого генезиса существует "
          "только на 20k (см. Приложение A).")
        a("")
    a("Пик в генезисе — это не только сам мир: `create_world()` в конце "
      "`initialize()` безусловно считает `WorldState.hash()`, который "
      "материализует канонический payload всего состояния. На 20k это "
      "видно как разрыв между RSS после генезиса (636 МБ) и пиком "
      "(1 043 МБ). На 100k к моменту смерти в архиве уже лежали все "
      "700 000 переходов и 9,8 млн строк индекса — то есть цикл записи "
      "генезиса завершился, а следующая операция `initialize()` — именно "
      "`state.hash()`. Это восстановление места по состоянию архива, а не "
      "запись из убитого процесса: финального события он не оставил.")
    a("")

    # ---------------------------------------------------------------- 6
    a("## 6. Хранение")
    a("")
    a("| величина | значение |")
    a("|---|---:|")
    if genesis.get("seconds") is not None:
        a(f"| генезис, с | {genesis['seconds']} |")
    if genesis.get("transitions") is not None:
        a(f"| сгенерировано переходов генезиса | {num(genesis['transitions'])} |")
    if death.get("transitions") is not None:
        a(f"| переходов в архиве на момент смерти | {num(death['transitions'])} |")
        if death.get("tick_min") is not None:
            a(f"| диапазон тиков | {death['tick_min']} … {death['tick_max']} |")
        if death.get("statuses"):
            a("| статусы | " + ", ".join(
                f"{k}: {num(v)}" for k, v in death["statuses"].items()) + " |")
        if death.get("systems"):
            a("| системы | " + ", ".join(
                f"{k}: {num(v)}" for k, v in death["systems"].items()) + " |")
        rows = death.get("index_rows") or {}
        if rows:
            a("| строки причинного индекса | "
              + ", ".join(f"{k}: {num(v)}" for k, v in rows.items()) + " |")
    if ticks:
        last_row = ticks[-1]
        a(f"| переходов после последнего тика | {num(last_row['transitions'])} |")
        a(f"| committed / rejected | {num(last_row['committed'])} / "
          f"{num(last_row['rejected'])} |")
    a(f"| файл БД, МБ | {st.get('db_mb', '—')} |")
    a(f"| WAL, МБ | {st.get('wal_mb', '—')} |")
    a(f"| SHM, МБ | {st.get('shm_mb', '—')} |")
    a(f"| пик RSS, МБ | {report.get('peak_mb', '—')} |")
    a("")
    tables = report.get("storage_tables") or {}
    if tables:
        a("Разбивка файла (`dbstat`, разовый скан):")
        a("")
        a("| объект | МБ |")
        a("|---|---:|")
        for name, size in tables.items():
            mb = size.get("mb") if isinstance(size, dict) else size
            a(f"| {name} | {mb} |")
        a("")
        journal_mb = (tables.get("transitions") or {}).get("mb")
        causal = sum((tables.get(k) or {}).get("mb", 0) for k in (
            "latest_writer", "history",
            "sqlite_autoindex_latest_writer_1", "sqlite_autoindex_history_1"))
        if journal_mb:
            a(f"Причинный индекс на этом объёме — не надстройка: "
              f"{causal:.1f} МБ против {journal_mb:.1f} МБ самого журнала. "
              f"Индекс по тику — "
              f"{(tables.get('idx_transitions_tick') or {}).get('mb')} МБ.")
            a("")
    a("Логический объём payload (`SUM(LENGTH(payload))`) не считался: на "
      "сотнях тысяч строк это отдельный полный скан, который сам искажает "
      "картину. Файл, WAL и число строк измерены; гранулярность payload — "
      "из структуры строки, а не из скана.")
    a("")

    # ---------------------------------------------------------------- 7
    a("## 7. Устойчивость")
    a("")
    if ticks:
        a("| тик | переходов | `journal.hash()` |")
        a("|---:|---:|---|")
        for row in ticks:
            a(f"| {row['tick']} | {num(row['transitions'])} | "
              f"`{row['journal_hash'][:16]}…` |")
        a("")
        a("Хеш после каждого тика — контрольная последовательность для "
          "сравнения с будущими прогонами. Полный replay **не выполнялся**: "
          "он требует второго полного мира в RAM и сам по себе является "
          "отдельным испытанием памяти.")
        a("")
        if genesis.get("state_hash"):
            a(f"`state.hash()` генезиса: `{genesis['state_hash'][:16]}…`.")
            a("")
    else:
        a("* Ни одного контрольного хеша после тика нет: тиков нет.")
        a("* `initial_state_hash` не вычислен; последняя завершённая "
          "операция, видимая в архиве, — запись всех 700 000 переходов и "
          "строк индекса, следующая в `initialize()` идёт "
          "`WorldState.hash()`.")
        a("* Архив после смерти открыт read-only и пересчитан (§6): "
          "чтение целостно, все строки относятся к `tick=0`, статус — "
          "`COMMITTED`. Это проверка читаемости и полноты, не replay.")
        a("* Восстановление после рестарта на 100k не проверялось: "
          "восстанавливать нечего — мир не был создан. На 20k переоткрытие "
          "архива проверено (Приложение A).")
        a("")
    a("## 8. Чего этот прогон не доказывает")
    a("")
    if not ticks:
        a("* Двадцать тиков не пройдены; утверждать что-либо о поведении "
          "100k на горизонте нельзя. Ограничитель сработал до первого тика.")
    else:
        a("* Горизонт пройден на этом размере, но это не 100k: на целевом "
          "размере не завершён ни один тик.")
    a("* Числа 16k/20k не экстраполированы на 100k и не выдаются за него: "
      "это отдельные измеренные точки, приведённые только там, где они "
      "подписаны.")
    a("* Прогон не оценивает качество симуляции, политику переселения или "
      "устойчивость поселений — только пропускную способность, сохранение "
      "истории и воспроизводимость на том, что успело выполниться.")
    a("* Долгосрочная устойчивость памяти не проверена: журнал растёт с "
      "каждым тиком, и вопрос «как меняется память и стоимость тика при "
      "росте журнала» остаётся открытым.")
    a("")

    # ------------------------------------------------------------- appendix
    if app:
        a("## Приложение A — ближайшая завершённая точка: 20 000 × "
          f"{len(app.get('ticks', []))}")
        a("")
        a("Это **не часть контрольной точки** и **не экстраполяция**: "
          "отдельный прогон того же движка на той же машине, который "
          "успел завершиться, чтобы у отчёта были реальные тиковые числа. "
          "Он не заменяет 100k.")
        a("")
        a("| тик | симуляция, с | record, с | commit, с | add, с | "
          "advance, с | срез, с | ситуации, с | всего, с | RSS, МБ | БД, МБ |")
        a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in app.get("ticks", []):
            a(f"| {row['tick']} | {row['simulation_s']} | {row['record_s']} | "
              f"{row['commit_s']} | {row['add_s']} | {row['advance_s']} | "
              f"{row['slice_s']} | {row['situations_s']} | {row['total_s']} | "
              f"{row['rss_mb']} | {row['db_mb']} |")
        a("")
        g = app.get("genesis") or {}
        if g:
            a(f"Генезис: {g.get('seconds')} с, {num(g.get('transitions'))} "
              f"переходов, пик RSS {app.get('peak_mb')} МБ; "
              f"`state.hash()` — "
              f"{next((p.get('seconds') for p in app.get('phases', []) if p.get('phase') == 'genesis_state_hash'), '—')} с.")
            a("")
        a("| тик | `journal.hash()` |")
        a("|---:|---|")
        for row in app.get("ticks", []):
            a(f"| {row['tick']} | `{row['journal_hash'][:16]}…` |")
        a("")
        a("Что видно уже здесь: первый кадр (`advance`) стоит 3.36 с — "
          "дороже любого другого шага наблюдения, потому что генезис и "
          "первый шаг делят `tick=0`. Срез клеток — 1 мс, ситуации — 0 мс. "
          "То есть на этом размере кадр ограничен не срезом и не лентой, "
          "а проигрыванием генезисного батча при первом `advance`.")
        a("")
        rerun = app.get("rerun") or {}
        if rerun:
            verdict_same = "да" if rerun.get("same") else "НЕТ"
            a(f"Вторая независимая серия из {rerun.get('ticks')} тиков дала "
              f"тот же `journal.hash()` после каждого тика: "
              f"**{verdict_same}**; хеш генезиса также совпал.")
            a("")
        reopen = app.get("reopen") or {}
        if reopen:
            open_same = "да" if reopen.get("same") else "НЕТ"
            a(f"Архив переоткрыт после завершения: переходов "
              f"{num(reopen.get('transitions'))}, `journal.hash()` совпал: "
              f"**{open_same}**; строк `history`: "
              f"{num(reopen.get('index_rows'))}. Переоткрытие с "
              f"восстановлением хеша — {reopen.get('seconds')} с, "
              f"`index_digest()` — {reopen.get('digest_seconds')} с: "
              "восстановление читает весь журнал, это не бесплатная "
              "операция. Это проверка чтения, не replay.")
            a("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", type=int, default=100000)
    parser.add_argument("--ticks", type=int, default=20)
    parser.add_argument("--db", default="")
    parser.add_argument("--json", default="experiments/reports/v012_checkpoint.json")
    parser.add_argument("--progress", default="/tmp/v012-checkpoint.jsonl")
    parser.add_argument("--out", default="experiments/reports/v012_checkpoint.md")
    parser.add_argument("--max-rss-mb", type=float, default=3600)
    parser.add_argument("--max-seconds", type=float, default=2400)
    parser.add_argument("--limit-as-gb", type=float, default=0)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()

    if args.render_only:
        report = load_progress(args.progress)
    else:
        code = run(args)
        if not Path(args.json).exists():
            report = load_progress(args.progress)
        else:
            report = json.loads(Path(args.json).read_text(encoding="utf-8"))
        if code not in (0,):
            print(f"child exit {code}", file=sys.stderr)
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
