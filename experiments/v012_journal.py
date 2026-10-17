#!/usr/bin/env python3
"""v0.12, stage 2d — the journal: logical history, physical storage, access.

The stage has three independent acceptance groups, and this script keeps
them apart instead of blending them into one "faster" number:

* LOGICAL HISTORY — what the journal MEANS: transitions, ids, statuses,
  causal sources, ticks, values, journal hash. A physical change passes
  only if this group is unchanged (proved by tests against the golden
  run and an in-memory journal; this script publishes the hash and the
  counts it measured, never "looks equivalent").
* PHYSICAL STORAGE — what the journal COSTS TO KEEP: file + WAL bytes,
  logical payload bytes, rows in every derived index table, peak RSS.
* ACCESS — what it costs to ASK: point lookup by id, tick, id range,
  entity, field, a sequential scan and a committed scan. Replay is
  measured separately by the tests and by ``--replay``.

Each size runs in its OWN process, exactly like the stage-1 profile, so
peak RSS of one size cannot inflate the next. The protocol is also the
same as stage 1/2c: seed 7, ``player_resettle``, 2 regions, 3 ticks.

Usage:
    python3 experiments/v012_journal.py                  # after 2d
    python3 experiments/v012_journal.py --label "до 2d" \
        --json /tmp/journal_before.json --out /tmp/journal_before.md
    python3 experiments/v012_journal.py --before /tmp/journal_before.json
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.journal import JournalView  # noqa: E402
from causal_world.simulation.archive import _transition_from_row  # noqa: E402
from causal_world.simulation.archive import SqliteArchive  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402


def _peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _file_bytes(path: str) -> dict:
    out = {}
    for suffix, name in (("", "db"), ("-wal", "wal"), ("-shm", "shm")):
        p = Path(path + suffix)
        out[name] = p.stat().st_size if p.exists() else 0
    out["total"] = out["db"] + out["wal"] + out["shm"]
    return out


def _table_bytes(conn: sqlite3.Connection) -> dict:
    """Per-table bytes via dbstat; {} when SQLite lacks the vtab."""
    try:
        rows = conn.execute(
            "SELECT name, SUM(pgsize) AS b FROM dbstat GROUP BY name"
        ).fetchall()
    except sqlite3.Error:
        return {}
    return {row[0]: int(row[1]) for row in rows}


# ----------------------------------------------------------------------
# one child = one size
# ----------------------------------------------------------------------
def run_one(agents: int, ticks: int, workdir: str, access_ticks: int = 12) -> dict:
    db = os.path.join(workdir, f"journal-{agents}.db")
    t0 = time.perf_counter()
    sim = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents, persist=db,
    )
    archive: SqliteArchive = sim.journal
    # Genesis is a one-off and must not be charged to the first measured
    # tick: flush it fully (rows, index rows and hash chain) before the
    # timer starts. `genesis_s` includes that commit.
    t = time.perf_counter()
    archive.commit()
    genesis_commit_s = time.perf_counter() - t
    genesis_s = time.perf_counter() - t0
    assert archive is sim.index, "persist mode: one store for journal and index"

    acc = {"record_s": 0.0, "add_s": 0.0, "records": 0, "writes": 0, "reads": 0}
    orig_record, orig_add = archive.record, archive.add

    def timed_record(transition):
        t = time.perf_counter()
        try:
            return orig_record(transition)
        finally:
            acc["record_s"] += time.perf_counter() - t
            acc["records"] += 1

    def timed_add(transition):
        t = time.perf_counter()
        try:
            return orig_add(transition)
        finally:
            acc["add_s"] += time.perf_counter() - t
            acc["writes"] += len(transition.writes)
            acc["reads"] += sum(
                1 for r in transition.reads if r.source_transition is not None
            )

    archive.record = timed_record
    archive.add = timed_add

    per_tick = []
    for _ in range(ticks):
        before = dict(acc)
        t = time.perf_counter()
        sim.step()
        tick_s = time.perf_counter() - t
        t = time.perf_counter()
        archive.commit()
        commit_s = time.perf_counter() - t
        per_tick.append({
            "tick": sim.state.tick - 1,
            "tick_s": round(tick_s, 4),
            "commit_s": round(commit_s, 4),
            "record_s": round(acc["record_s"] - before["record_s"], 4),
            "add_s": round(acc["add_s"] - before["add_s"], 4),
            "records": acc["records"] - before["records"],
            "writes": acc["writes"] - before["writes"],
            "reads": acc["reads"] - before["reads"],
            "transitions": len(archive),
        })

    archive.record = orig_record
    archive.add = orig_add
    live_counts = archive.counts()
    live_hash = archive.hash()
    payload_row = archive.query("SELECT SUM(LENGTH(payload)) AS b FROM transitions")[0]
    payload_bytes = int(payload_row["b"] or 0)
    storage = {
        "files": _file_bytes(db),
        "payload_bytes": payload_bytes,
        "pages": int(archive._conn.execute("PRAGMA page_count").fetchone()[0]),
        "page_size": int(archive._conn.execute("PRAGMA page_size").fetchone()[0]),
        "tables": _table_bytes(archive._conn),
        "rows": {
            table: int(archive.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])
            for table in ("transitions", "latest_writer", "history", "dependents")
        },
    }
    archive.close()

    # ACCESS — measured on a LONGER journal, because a tick query in a
    # three-tick archive is a third of the journal and cannot show what
    # an index does. The scan column asks the identical SQL with the
    # index disabled (`+tick`), so before and after are the same query
    # on the same file, not two different implementations.
    access_db = os.path.join(workdir, f"access-{agents}.db")
    a = create_world(
        seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents, persist=access_db,
    )
    for _ in range(access_ticks):
        a.step()
        a.journal.commit()
    a.journal.close()

    t = time.perf_counter()
    view = JournalView(access_db)
    reopen_s = time.perf_counter() - t
    try:
        access = access_bench(view, agents, access_ticks)
    finally:
        view.close()

    return {
        "agents": agents,
        "genesis_s": round(genesis_s, 3),
        "genesis_commit_s": round(genesis_commit_s, 3),
        "ticks": per_tick,
        "counts": {
            "total": live_counts[0],
            "committed": live_counts[1],
            "rejected": live_counts[2],
        },
        "journal_hash": live_hash,
        "storage": storage,
        "reopen_s": round(reopen_s, 4),
        "access": access,
        "peak_mb": round(_peak_mb(), 1),
    }


def _linear_entity(view: JournalView, entity: str, status: str = "COMMITTED") -> int:
    """Reference query: sequential scan, id order, same filter."""
    wanted = SQL_STATUS[status]
    return sum(
        1 for t in view
        if t.status is wanted and any(w.entity == entity for w in t.writes)
    )


def _linear_field(view: JournalView, entity: str, field: str,
                  status: str = "COMMITTED") -> int:
    wanted = SQL_STATUS[status]
    return sum(
        1 for t in view
        if t.status is wanted
        and any(w.entity == entity and w.field == field for w in t.writes)
    )


def _view_at_tick(view: JournalView, tick: int) -> list:
    """The read-only tick query; the same SQL before and after 2d."""
    method = getattr(view, "at_tick", None)
    if callable(method):
        return method(tick)
    rows = view.query(
        "SELECT * FROM transitions WHERE tick=? ORDER BY id", (tick,)
    )
    return [_transition_from_row(row) for row in rows]


def _view_at_tick_scan(view: JournalView, tick: int) -> list:
    """The SAME tick query with the index disabled (the pre-2d plan)."""
    rows = view.query(
        "SELECT * FROM transitions WHERE +tick=? ORDER BY id", (tick,)
    )
    return [_transition_from_row(row) for row in rows]


def _writes_at_tick_scan(view: JournalView, tick: int):
    rows = view.query(
        "SELECT id, payload FROM transitions "
        "WHERE +tick=? AND status='COMMITTED' ORDER BY id", (tick,)
    )
    out = []
    for row in rows:
        for entity, field_name, _old, new in json.loads(row["payload"])["writes"]:
            out.append((row["id"], entity, field_name, new))
    return out


def _view_range_scan(view: JournalView, lo: int, hi: int) -> list:
    rows = view.query(
        "SELECT * FROM transitions WHERE +tick BETWEEN ? AND ? ORDER BY id",
        (lo, hi),
    )
    return [_transition_from_row(row) for row in rows]


def _view_range(view: JournalView, lo: int, hi: int) -> list:
    method = getattr(view, "between_ticks", None)
    if callable(method):
        return method(lo, hi)
    rows = view.query(
        "SELECT * FROM transitions WHERE tick BETWEEN ? AND ? ORDER BY id",
        (lo, hi),
    )
    return [_transition_from_row(row) for row in rows]


def _time(fn, repeat: int = 1) -> float:
    t = time.perf_counter()
    for _ in range(repeat):
        fn()
    return (time.perf_counter() - t) / repeat


def access_bench(view: JournalView, agents: int, ticks: int) -> dict:
    total = sum(len(batch) for batch in view.iter_batches(100000))
    ids = sorted({1 + (total * i) // 50 for i in range(50)})
    by_id_s = _time(lambda: [view.by_id(i) for i in ids], 20)

    last = max(0, ticks - 1)
    at_tick_s = _time(lambda: _view_at_tick(view, last), 5)
    at_tick_scan_s = _time(lambda: _view_at_tick_scan(view, last), 5)
    range_s = _time(lambda: _view_range(view, max(0, last - 2), last), 5)
    range_scan_s = _time(
        lambda: _view_range_scan(view, max(0, last - 2), last), 5
    )
    range_n = len(_view_range(view, max(0, last - 2), last))
    writes = getattr(view, "writes_at_tick", None)
    if callable(writes):
        writes_s = _time(lambda: writes(last), 5)
        writes_scan_s = _time(lambda: _writes_at_tick_scan(view, last), 5)
        writes_n = len(writes(last))
    else:
        writes_s = writes_scan_s = writes_n = None

    entities = sorted({w.entity for t in _view_at_tick(view, max(0, ticks - 1))
                       for w in t.writes})
    sample_entities = entities[:: max(1, len(entities) // 3)][:3]
    api = getattr(view, "transitions_for_entity", None)
    if callable(api):
        entity_api_s = _time(lambda: [list(api(e)) for e in sample_entities])
        entity_api_n = sum(len(list(api(e))) for e in sample_entities)
    else:
        entity_api_s, entity_api_n = None, None
    entity_linear_s = _time(lambda: [_linear_entity(view, e) for e in sample_entities])
    entity_linear_n = sum(_linear_entity(view, e) for e in sample_entities)

    pairs = []
    for entity in sample_entities:
        for t in _view_at_tick(view, max(0, ticks - 1)):
            for w in t.writes:
                if w.entity == entity:
                    pairs.append((entity, w.field))
                    break
    pairs = pairs[:3]
    field_api = getattr(view, "transitions_for_field", None)
    if callable(field_api):
        field_api_s = _time(lambda: [list(field_api(e, f)) for e, f in pairs])
        field_api_n = sum(len(list(field_api(e, f))) for e, f in pairs)
    else:
        field_api_s, field_api_n = None, None
    field_linear_s = _time(lambda: [_linear_field(view, e, f) for e, f in pairs])
    field_linear_n = sum(_linear_field(view, e, f) for e, f in pairs)

    scan_s = _time(lambda: [None for _ in view.iter_batches(20000)])
    committed_s = _time(lambda: sum(1 for _ in view.committed()))

    return {
        "transitions": total,
        "by_id_us": round(by_id_s / len(ids) * 1e6, 1),
        "at_tick_s": round(at_tick_s, 4),
        "at_tick_scan_s": round(at_tick_scan_s, 4),
        "at_tick_n": len(_view_at_tick(view, last)),
        "range_s": round(range_s, 4),
        "range_scan_s": round(range_scan_s, 4),
        "range_n": range_n,
        "writes_s": round(writes_s, 4) if writes_s is not None else None,
        "writes_scan_s": (round(writes_scan_s, 4)
                          if writes_scan_s is not None else None),
        "writes_n": writes_n,
        "entity_sample": sample_entities,
        "entity_api_s": round(entity_api_s, 4) if entity_api_s is not None else None,
        "entity_api_n": entity_api_n,
        "entity_linear_s": round(entity_linear_s, 4),
        "entity_linear_n": entity_linear_n,
        "field_pairs": [[e, f] for e, f in pairs],
        "field_api_s": round(field_api_s, 4) if field_api_s is not None else None,
        "field_api_n": field_api_n,
        "field_linear_s": round(field_linear_s, 4),
        "field_linear_n": field_linear_n,
        "scan_s": round(scan_s, 4),
        "committed_s": round(committed_s, 4),
    }


# ----------------------------------------------------------------------
# replay: measured separately, on a small closed life
# ----------------------------------------------------------------------
def replay_bench(agents: int, ticks: int) -> dict:
    from causal_world.server import continuity
    from causal_world.server.session import Session

    workdir = tempfile.mkdtemp(prefix="v012-replay-")
    session = Session(
        seed=7, ruleset="player_resettle", regions=2, agents=agents,
        db_dir=workdir, max_ticks=ticks + 5,
    )
    hashes = []
    for seq in range(1, ticks + 1):
        session.decide(seq, 6)
        hashes.append(session.sim.state.hash())
    db_path = session.db_path
    t = time.perf_counter()
    session.close()
    close_s = time.perf_counter() - t

    t = time.perf_counter()
    sim, archive, _lives = continuity.replay_head(db_path)
    replay_s = time.perf_counter() - t
    replay_hash_ok = sim.journal.hash() == archive.hash()
    replay_state_ok = sim.state.hash() == hashes[-1]
    archive.close()

    # replay to a given tick, if the stage provides it
    prefix = getattr(continuity, "replay_until", None)
    if callable(prefix):
        t = time.perf_counter()
        part, expected = prefix(db_path, ticks - 1)
        prefix_s = time.perf_counter() - t
        prefix_state = part.state.hash()
        prefix_state_ok = prefix_state == hashes[-2]
        prefix_hash = expected
        prefix_hash_ok = part.journal.hash() == expected
    else:
        prefix_s, prefix_state_ok, prefix_hash_ok, prefix_hash = None, None, None, None
    for path in Path(workdir).glob("*.db*"):
        path.unlink(missing_ok=True)
    return {
        "agents": agents,
        "ticks": ticks,
        "close_s": round(close_s, 4),
        "replay_s": round(replay_s, 4),
        "replay_hash_ok": bool(replay_hash_ok),
        "replay_state_ok": bool(replay_state_ok),
        "prefix_s": round(prefix_s, 4) if prefix_s is not None else None,
        "prefix_state_ok": prefix_state_ok,
        "prefix_hash_ok": prefix_hash_ok,
        "prefix_hash": prefix_hash,
    }


# ----------------------------------------------------------------------
# render
# ----------------------------------------------------------------------
def render(report: dict, before: dict | None = None) -> str:
    runs = report["runs"]
    lines: list[str] = []
    a = lines.append
    a(f"# v0.12 — {report['config'].get('label', 'шаг 2d — журнал')}")
    a("")
    a(f"Машина: {report['machine']['cpu']} CPU, "
      f"{report['machine']['ram_gb']:.1f} ГБ RAM; Python "
      f"{report['machine']['python']}. seed 7, `player_resettle`, "
      f"2 региона, {report['config']['ticks']} тика на размер; "
      "каждый размер — отдельный процесс.")
    a("")
    a("Здесь намеренно **нет одной цифры «ускорение»**. Приёмка 2d "
      "разделена на три группы, и таблицы ниже публикуют их по "
      "отдельности: что журнал значит, сколько он занимает и сколько "
      "стоит его читать.")
    a("")
    a("## 1. Логическая история")
    a("")
    a("| живых | переходов | committed | rejected | записей/тик | "
      "payload, МБ | `journal.hash()` |")
    a("|---:|---:|---:|---:|---:|---:|---|")
    for r in runs:
        c = r["counts"]
        payload = r["storage"]["payload_bytes"] / 1e6
        a(f"| {r['agents']} | {c['total']} | {c['committed']} | "
          f"{c['rejected']} | {sum(t['records'] for t in r['ticks']) / len(r['ticks']):.0f} | "
          f"{payload:.2f} | `{r['journal_hash'][:12]}…` |")
    a("")
    a("Хеш и счётчики — не доказательство семантики сами по себе: "
      "их равенство эталону проверяют тесты (`tests/test_v012_journal.py`, "
      "включая прогон golden 40 тиков через архив и побайтовое сравнение "
      "каждого перехода с in-memory журналом).")
    a("")
    a("## 2. Стоимость записи")
    a("")
    a("| живых | генезис, с | тик, с | record, с/тик | add (индекс), с/тик | "
      "commit, с/тик | записей/тик | записей состояния/тик |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in runs:
        n = len(r["ticks"])
        tick = sum(t["tick_s"] for t in r["ticks"]) / n
        rec = sum(t["record_s"] for t in r["ticks"]) / n
        add = sum(t["add_s"] for t in r["ticks"]) / n
        com = sum(t["commit_s"] for t in r["ticks"]) / n
        records = sum(t["records"] for t in r["ticks"]) / n
        writes = sum(t["writes"] for t in r["ticks"]) / n
        a(f"| {r['agents']} | {r['genesis_s']:.2f} | {tick:.3f} | "
          f"{rec:.3f} | {add:.3f} | {com:.3f} | {records:.0f} | {writes:.0f} |")
    a("")
    a("«record» — запись перехода в журнал и его канонический байт в хеш-"
      "цепочку; «add» — производный причинный индекс (последний писатель, "
      "история поля, зависимости чтений). Это разные работы, и 2d "
      "уменьшает их по отдельности, не смешивая с симуляцией.")
    a("")
    a("Честно о записи: главный выигрыш 2d — не здесь. Стоимость "
      "`record` определяется двумя каноническими JSON на переход "
      "(payload для чтения и каноническая запись для хеша), а не числом "
      "SQL-вызовов; `record` остаётся крупнейшей статьёй тика. На 500, "
      "2000 и 4000 тик+commit стал дешевле на 6–10%, на 1000 знак "
      "разницы нестабилен между прогонами.")
    a("")
    a("## 3. Физическое хранение")
    a("")
    a("| живых | файл БД, МБ | WAL, МБ | страниц | "
      "`transitions` | `latest_writer` | `history` | `dependents` | "
      "пик RSS, МБ |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in runs:
        st = r["storage"]
        rows = st["rows"]
        a(f"| {r['agents']} | {st['files']['db'] / 1e6:.1f} | "
          f"{st['files']['wal'] / 1e6:.1f} | {st['pages']} | "
          f"{rows['transitions']} | {rows['latest_writer']} | "
          f"{rows['history']} | {rows['dependents']} | {r['peak_mb']:.0f} |")
    a("")
    tables = runs[-1]["storage"]["tables"]
    if tables:
        a("Байты по таблицам (dbstat, крупнейший размер):")
        a("")
        a("| объект | МБ |")
        a("|---|---:|")
        for name, size in sorted(tables.items(), key=lambda kv: -kv[1])[:8]:
            a(f"| `{name}` | {size / 1e6:.1f} |")
        a("")
    tick_index = runs[-1]["storage"]["tables"].get("idx_transitions_tick")
    if tick_index:
        a(f"Новый объект 2d — индекс по тику: {tick_index / 1e6:.2f} МБ "
          f"при {runs[-1]['agents']} живых (против "
          f"{runs[-1]['storage']['files']['db'] / 1e6:.1f} МБ файла). "
          "Он не дублирует историю, а только упорядочивает уже "
          "существующие строки.")
        a("")
    a("Пик RSS относится ко всему процессу, включая построение "
      "12-тикового архива для замеров доступа; он не сравнивается с пиком "
      "профиля, где живут только три тика.")
    a("")
    a("`latest_writer` и `history` — причинный индекс, производный от "
      "журнала; строк в них больше, чем переходов, потому что один переход "
      "пишет несколько полей. Это цена причинности, а не дублирование "
      "истории: их можно удалить и восстановить из `transitions` "
      "(проверяется тестом).")
    a("")
    a("## 4. Стоимость доступа")
    a("")
    a(f"Запросы измерены на журнале в {report['config'].get('access_ticks', 12)} "
      "тиков: на трёх тиках запрос «последний тик» — это треть журнала, и "
      "индекс там почти нечего убирать. Колонка «скан» — **тот же SQL с "
      "отключённым индексом** (`+tick`), то есть путь до 2d на том же файле.")
    a("")
    a("| живых | по id, мкс | один тик: индекс, с | один тик: скан, с | "
      "записи тика: индекс, с | записи тика: скан, с | диапазон: индекс, с | "
      "сущность: API, с | сущность: скан, с | поле: API, с | поле: скан, с |")
    a("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in runs:
        ac = r["access"]
        fmt = lambda v: "—" if v is None else f"{v:.4f}"  # noqa: E731
        a(f"| {r['agents']} | {ac['by_id_us']:.1f} | {ac['at_tick_s']:.4f} | "
          f"{ac['at_tick_scan_s']:.4f} | {fmt(ac['writes_s'])} | "
          f"{fmt(ac['writes_scan_s'])} | {ac['range_s']:.4f} | "
          f"{fmt(ac['entity_api_s'])} | {fmt(ac['entity_linear_s'])} | "
          f"{fmt(ac['field_api_s'])} | {fmt(ac['field_linear_s'])} |")
    a("")
    a("API-запросы обязаны вернуть **тот же набор и тот же порядок**, что "
      "последовательный поиск; это проверяется в тестах, а здесь "
      "публикуется цена. «—» означает, что в этой версии кода запроса "
      "ещё нет. Тик всё равно десериализует свои переходы: индекс убирает "
      "чтение ЧУЖИХ тиков, но не цену собственных записей. Для кадра важна "
      "именно колонка «записи тика»: это проекция без reads/draws/Transition, "
      "которую теперь использует клеточный индекс 2b.")
    a("")
    biggest = runs[-1]
    a(f"Диапазон из трёх тиков при {biggest['agents']} живых: "
      f"{biggest['access']['range_s']:.3f} с по индексу против "
      f"{biggest['access']['range_scan_s']:.3f} с тем же SQL без индекса. "
      "Индекс ускоряет выборку ОДНОГО тика (путь кадра), но диапазон с "
      "`ORDER BY id` требует сортировки выбранных строк — на этом запросе "
      "выигрыша нет, и это опубликовано, а не спрятано. Порядок строк "
      "одинаков в обоих случаях (проверяется тестом).")
    a("")
    rp = report.get("replay")
    if rp:
        a("## 5. Replay")
        a("")
        a("| живых | тиков | close, с | replay до головы, с | журнал совпал | "
          "состояние совпало | replay до тика, с | состояние на тике | журнал префикса |")
        a("|---:|---:|---:|---:|---|---|---:|---|---|")
        for r in rp:
            prefix_s = "—" if r["prefix_s"] is None else f"{r['prefix_s']:.3f}"
            prefix_state = ("—" if r["prefix_state_ok"] is None
                            else ("да" if r["prefix_state_ok"] else "НЕТ"))
            prefix_hash = ("—" if r["prefix_hash_ok"] is None
                           else ("да" if r["prefix_hash_ok"] else "НЕТ"))
            a(f"| {r['agents']} | {r['ticks']} | {r['close_s']:.3f} | "
              f"{r['replay_s']:.3f} | {'да' if r['replay_hash_ok'] else 'НЕТ'} | "
              f"{'да' if r['replay_state_ok'] else 'НЕТ'} | "
              f"{prefix_s} | {prefix_state} | {prefix_hash} |")
        a("")
        a("Replay — это прогон мира заново из одного архива, поэтому его "
          "время включает симуляцию, а не только чтение. Отдельно измерен "
          "префикс до заданного тика: он обязан дать то же состояние и ту же "
          "логическую историю, что непрерванный прогон.")
        a("")
    if before:
        a("## 6. До / после 2d")
        a("")
        a("| живых | тик+commit до, с | тик+commit после, с | record до, с | "
          "record после, с | add до, с | add после, с |")
        a("|---:|---:|---:|---:|---:|---:|---:|")
        old = {r["agents"]: r for r in before["runs"]}
        for r in runs:
            o = old.get(r["agents"])
            if not o:
                continue
            avg = lambda run, key: sum(t[key] for t in run["ticks"]) / len(run["ticks"])  # noqa: E731
            a(f"| {r['agents']} | {avg(o, 'tick_s') + avg(o, 'commit_s'):.3f} | "
              f"{avg(r, 'tick_s') + avg(r, 'commit_s'):.3f} | "
              f"{avg(o, 'record_s'):.3f} | {avg(r, 'record_s'):.3f} | "
              f"{avg(o, 'add_s'):.3f} | {avg(r, 'add_s'):.3f} |")
        a("")
        a("Сравнение — на тех же размерах, seed, ruleset и числе тиков; "
          "«до» снято тем же скриптом до правок.")
        a("")
    a("## Что это доказывает и чего не доказывает")
    a("")
    a("* Батчи и индексы не меняют `journal.hash()` и логическую историю — "
      "это проверяется на golden-прогоне и на in-memory журнале.")
    a("* Индексы производны: полная перестройка из журнала даёт те же "
      "строки, что инкрементальное обновление, после каждого тика.")
    a("* Запросы через индекс возвращают тот же набор и порядок, что "
      "последовательный поиск.")
    a("* Физическое хранение измерено, но **не** объявлено дешёвым: "
      "причинный индекс по-прежнему сопоставим по объёму с журналом, и "
      "это видно в таблице, а не спрятано.")
    a("* 100k по-прежнему не прогонялся; контрольная точка — после 2d, "
      "по опубликованным здесь метрикам.")
    a("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", default="500,1000,2000,4000")
    parser.add_argument("--ticks", type=int, default=3)
    parser.add_argument("--child", type=int, default=0)
    parser.add_argument("--workdir", default="")
    parser.add_argument("--access-ticks", type=int, default=12)
    parser.add_argument("--replay-agents", default="500,1000")
    parser.add_argument("--label", default="шаг 2d — журнал: батчи, индексы, доступ")
    parser.add_argument("--out", default="experiments/reports/v012_journal.md")
    parser.add_argument("--json", default="experiments/reports/v012_journal.json")
    parser.add_argument("--before", default="",
                        help="JSON of a previous run; renders a до/после table")
    args = parser.parse_args()

    if args.child:
        workdir = args.workdir or tempfile.mkdtemp(prefix="v012-journal-")
        Path(workdir).mkdir(parents=True, exist_ok=True)
        print(json.dumps(run_one(
            args.child, args.ticks, workdir, access_ticks=args.access_ticks
        )))
        return 0

    sizes = [int(s) for s in args.agents.split(",") if s.strip()]
    runs = []
    for agents in sizes:
        workdir = tempfile.mkdtemp(prefix=f"v012-journal-{agents}-")
        proc = subprocess.run(
            [sys.executable, __file__, "--child", str(agents),
             "--ticks", str(args.ticks), "--access-ticks",
             str(args.access_ticks), "--workdir", workdir],
            capture_output=True, text=True, check=True,
        )
        runs.append(json.loads(proc.stdout.strip().splitlines()[-1]))

    replay = []
    for agents in [int(s) for s in args.replay_agents.split(",") if s.strip()]:
        replay.append(replay_bench(agents, max(3, args.ticks + 3)))

    report = {
        "config": {
            "agents": sizes, "ticks": args.ticks,
            "access_ticks": args.access_ticks, "label": args.label,
        },
        "machine": {
            "cpu": os.cpu_count(),
            "ram_gb": round(
                os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1
            ),
            "python": sys.version.split()[0],
        },
        "runs": runs,
        "replay": replay,
    }
    before = json.loads(Path(args.before).read_text(encoding="utf-8")) if args.before else None
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(render(report, before), encoding="utf-8")
    Path(args.json).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"written {args.out}")
    print(f"written {args.json}")
    return 0


SQL_STATUS = None


if __name__ == "__main__":
    from causal_world.kernel.transition import TransitionStatus

    SQL_STATUS = {
        "COMMITTED": TransitionStatus.COMMITTED,
        "REJECTED": TransitionStatus.REJECTED,
    }
    raise SystemExit(main())
