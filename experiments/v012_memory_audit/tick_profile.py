"""Splits the tick time at scale into generation, serialisation, SQLite write
and commit (v0.12/3). cProfile is run around the steps only, the genesis is not
profiled. cProfile inflates absolute times; the SHARES are what is compared.

usage: python tick_profile.py AGENTS TICKS WORKDIR
"""
from __future__ import annotations

import cProfile
import io
import json
import os
import pstats
import sys
import time

from causal_world import create_world
from causal_world.world.rules import get_ruleset

# (label, substring of "file:function" in pstats keys)
BUCKETS = [
    ("systems_compute (generation of proposals)", "systems/"),
    ("resolver.resolve (validation)", "resolver"),
    ("state commit (_commit)", "engine.py:_commit"),
    ("serialisation (canonical bytes / payload)", "archive.py:_payload_of"),
    ("serialisation (canonical bytes)", "archive.py:_canonical_bytes"),
    ("serialisation (canonical_json)", "canonical.py:canonical_json"),
    ("SQLite executemany (write)", "{method 'executemany'"),
    ("SQLite execute", "{method 'execute'"),
    ("archive._drain (batch build)", "archive.py:_drain"),
    ("archive._flush", "archive.py:_flush"),
    ("archive.commit (WAL fsync etc.)", "archive.py:commit"),
    ("archive.record (total)", "archive.py:record"),
    ("causal index add (total)", "archive.py:add"),
    ("journal.record (total)", "journal.py:record"),
]


def bucket_table(stats: pstats.Stats) -> dict[str, dict[str, float]]:
    """Per bucket: own time (sum over matching functions, no double count)
    and cumulative time (largest matching function, i.e. its outermost call)."""
    own: dict[str, float] = {}
    cum: dict[str, float] = {}
    for (fname, line, func), (cc, nc, tt, ct, callers) in stats.stats.items():
        key = f"{fname}:{func}"
        for label, needle in BUCKETS:
            if needle in key:
                own[label] = own.get(label, 0.0) + tt
                cum[label] = max(cum.get(label, 0.0), ct)
    return {label: {"own_s": round(own.get(label, 0.0), 3),
                    "cum_s": round(cum.get(label, 0.0), 3)}
            for label, _ in BUCKETS if label in own}


def main(agents: int, ticks: int, workdir: str) -> dict:
    os.makedirs(workdir, exist_ok=True)
    db = os.path.join(workdir, "prof.db")
    for s in ("", "-wal", "-shm"):
        if os.path.exists(db + s):
            os.remove(db + s)
    sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                       regions=2, agents=agents, persist=db)
    profiler = cProfile.Profile()
    wall = time.perf_counter()
    profiler.enable()
    for _ in range(ticks):
        sim.step()
    profiler.disable()
    wall = time.perf_counter() - wall
    stats = pstats.Stats(profiler, stream=io.StringIO())
    buf = io.StringIO()
    pstats.Stats(profiler, stream=buf).sort_stats("cumulative").print_stats(60)
    sim.journal.close()
    return {
        "agents": agents, "ticks": ticks, "wall_s_under_profiler": round(wall, 2),
        "total_tottime_s": round(sum(v[2] for v in stats.stats.values()), 2),
        "buckets_tottime_s": bucket_table(stats),
        "top_cumulative": buf.getvalue()[:12000],
    }


if __name__ == "__main__":
    print("RESULT " + json.dumps(main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]),
                                 ensure_ascii=False), flush=True)
