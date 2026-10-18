"""Scale check of the observer index and the archive index (v0.12/3).

Two independent comparisons, both at ``AGENTS`` living agents:

A. Observer index, per tick: the incrementally advanced ``WorldIndex`` against
   a ``WorldIndex`` rebuilt from the state of the same tick. The compared
   facts are the ones the test ``test_v012_index_genesis`` compares (entities,
   fields, alive counts, pool stats, agents by cell) and the cell slice built
   from each (values, provenance, complete/total). Equality is checked on
   a SHA-256 over the canonical JSON of the facts, so the output stays small.

B. Archive index: the derived tables (latest_writer, history, dependents)
   maintained incrementally by ``record``/``add`` against the same tables
   rebuilt from ``transitions`` alone (``rebuild_index``) on a backup copy of
   the file. The live file is not modified by the rebuild.

usage: python index_equivalence.py AGENTS TICKS WORKDIR
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time

from causal_world import create_world
from causal_world.observer.slice import CellSlice, WorldIndex
from causal_world.simulation.archive import SqliteArchive
from causal_world.world.rules import get_ruleset


def _digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def index_facts(index: WorldIndex) -> dict:
    cells = index.entities("cell:")
    regions = index.entities("region:")
    return {
        "agents": index.entities("agent:"),
        "cells": cells,
        "regions": regions,
        "fields": {e: index.fields_of(e) for e in cells + regions},
        "alive": index.alive_count,
        "agent_count": index.agent_count,
        "pool": index.pool_stats,
        "agents_by_cell": {c: index.agents_in_cell(c) for c in cells},
    }


def slice_facts(state, index: WorldIndex) -> dict:
    view = CellSlice.from_state(state, index)
    values = dict(view._values)
    return {
        "cells": view.cells,
        "regions": view.regions,
        "complete": view.complete,
        "values": [[e, f, v] for (e, f), v in sorted(values.items())],
        "provenance": [[e, f, state.get_source(e, f)]
                       for (e, f) in sorted(values)],
        "alive": view.alive_agents,
        "total": view.total_agents,
        "pool": view.pool_stats(),
        "by_cell": {c: view.agents_in_cell(c) for c in view.cells},
    }


def main(agents: int, ticks: int, workdir: str) -> dict:
    os.makedirs(workdir, exist_ok=True)
    db = os.path.join(workdir, "eq.db")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(db + suffix):
            os.remove(db + suffix)
    out: dict = {"agents": agents, "ticks": ticks, "per_tick": []}

    t = time.perf_counter()
    sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                       regions=2, agents=agents, persist=db)
    out["genesis_s"] = round(time.perf_counter() - t, 2)
    incremental = WorldIndex.from_state(sim.state, journal=sim.journal)

    for _ in range(ticks):
        t = time.perf_counter()
        sim.step()
        step_s = time.perf_counter() - t
        t = time.perf_counter()
        incremental.advance(sim.journal, sim.state.tick - 1)
        advance_s = time.perf_counter() - t
        t = time.perf_counter()
        rebuilt = WorldIndex.from_state(sim.state, journal=sim.journal)
        rebuild_s = time.perf_counter() - t
        inc_facts = index_facts(incremental)
        reb_facts = index_facts(rebuilt)
        inc_slice = slice_facts(sim.state, incremental)
        reb_slice = slice_facts(sim.state, rebuilt)
        row = {
            "tick": sim.state.tick - 1,
            "facts_digest_incremental": _digest(inc_facts),
            "facts_digest_rebuilt": _digest(reb_facts),
            "facts_equal": inc_facts == reb_facts,
            "slice_digest_incremental": _digest(inc_slice),
            "slice_digest_rebuilt": _digest(reb_slice),
            "slice_equal": inc_slice == reb_slice,
            "step_s": round(step_s, 2),
            "advance_s": round(advance_s, 3),
            "rebuild_s": round(rebuild_s, 2),
            "state_hash": sim.state.hash(),
        }
        out["per_tick"].append(row)
        print(json.dumps(row), flush=True)

    # B. archive: incremental tables vs rebuild from transitions only
    sim.journal.commit()
    live_digest = sim.journal.index_digest()
    live_counts = sim.journal.index_counts()
    copy = os.path.join(workdir, "rebuild_copy.db")
    if os.path.exists(copy):
        os.remove(copy)
    src = sqlite3.connect(db)
    dst = sqlite3.connect(copy)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    archive = SqliteArchive(copy)
    try:
        t = time.perf_counter()
        archive.rebuild_index()
        rebuild_s = time.perf_counter() - t
        out["archive"] = {
            "incremental_digest": live_digest,
            "rebuilt_digest": archive.index_digest(),
            "incremental_counts": live_counts,
            "rebuilt_counts": archive.index_counts(),
            "rebuild_s": round(rebuild_s, 2),
        }
    finally:
        archive.close()
    out["archive"]["equal"] = (
        out["archive"]["incremental_digest"] == out["archive"]["rebuilt_digest"]
        and out["archive"]["incremental_counts"] == out["archive"]["rebuilt_counts"]
    )
    out["all_equal"] = all(r["facts_equal"] and r["slice_equal"]
                           for r in out["per_tick"]) and out["archive"]["equal"]
    sim.journal.close()
    return out


if __name__ == "__main__":
    result = main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
    print("RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
