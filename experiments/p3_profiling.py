#!/usr/bin/env python3
"""v0.6 P3 — profiling the real cost of a continuing world (user plan of
2026-10-14). Deterministic: fixed seeds, fixed scripts, JSON dump.

M1 one tick        step cost with/without the SQLite archive; rows/tick
M2 journal.hash()  reopened-archive hash: first call, cached call, call
                   after ONE append (the per-decide pattern) at ~30k rows
M3 long journal    5000-tick archive: play cost; full replay from the
                   archive alone, decomposed by stage; tracemalloc peak
M4/M5 life chain   natural game scenario (seed21/4x50) played life by
                   life to the terminal no_heir: per-life takeover time
                   (absolute numbers, one-shot operations), death-card
                   build, RSS at every boundary; extinction reported,
                   never circumvented
M6                 least-squares fit of replay cost a*T+b from measured
                   points; snapshot break-even from measured terms
M7                 semantics guard: fingerprints/hashes recorded in-band;
                   the --optimize run must reproduce them exactly

Run:  python3 experiments/p3_profiling.py [--optimize] [OUTDIR]
Writes: experiments/p3_profile_data_{base|opt}.json
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

from causal_world import create_world
from causal_world.kernel.canonical import canonical_json
from causal_world.observer.biography import build_biography
from causal_world.observer.journal import JournalView
from causal_world.player import (
    DecisionChannel,
    DecisionStreamReader,
    attach_player_channel,
)
from causal_world.server.session import ProtocolError, Session
from causal_world.simulation.archive import SqliteArchive
from causal_world.simulation.journal import transition_record
from causal_world.world.rules import get_ruleset

OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/p3")
OUT.mkdir(parents=True, exist_ok=True)
OPTIMIZE = "--optimize" in sys.argv
LIFE_CAP = 8           # measured points are enough for the fit; runtime must
LIFE_DECIDE_CAP = 150  # stay comparable across the two passes

DATA: dict = {"optimize_variant": OPTIMIZE}


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def script_actions(n, source=99):
    rng = random.Random(source)
    return [
        2 if (r := rng.random()) < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6
        for _ in range(n)
    ]


# ============================================================ M8 variant ==
def install_incremental_hash_variant():
    """Historical: the P3 experiment monkey-patched this in. Since the
    follow-up commit the SOURCE itself is the optimized implementation
    (commit-synced hash chain), so the variant run is a plain passthrough —
    kept so the --optimize invocation stays reproducible on old tags."""
    if hasattr(SqliteArchive, "_reseed_from_disk"):
        print("note: source already implements the incremental chain; "
              "--optimize is a passthrough", flush=True)
        return

    def fast_hash(self):
        if self._total_at_open:
            h = hashlib.sha256()
            for t in self:  # same connection: sees my committed inserts
                h.update(
                    (canonical_json(transition_record(t)) + "\n").encode("utf-8")
                )
            self._hasher = h
            self._total_at_open = 0
            self._hash_cache = None
        return self._hasher.copy().hexdigest()

    SqliteArchive.hash = fast_hash


# ============================================================== M1 + M2 ===
def measure_tick_and_hash(tmp: Path):
    print("M1/M2: tick cost + hash regimes …", flush=True)
    out = {}
    for persist in (True, False):
        tag = "persist" if persist else "memory"
        db = str(tmp / f"m1_{tag}.db") if persist else None
        sim = create_world(seed=21, ruleset=get_ruleset("player_life"), ticks=0,
                           regions=4, agents=50, persist=db)
        durs = []
        for _ in range(300):
            t0 = time.perf_counter()
            sim.step()
            durs.append(time.perf_counter() - t0)
        rows = sim.journal.counts()[0]
        durs.sort()
        out[tag] = {
            "ticks": 300,
            "rows_per_tick": round(rows / 300, 2),
            "step_median_ms": round(durs[150] * 1e3, 3),
            "step_p95_ms": round(durs[284] * 1e3, 3),
            "step_mean_ms": round(sum(durs) / len(durs) * 1e3, 3),
        }
        if persist:
            sim.journal.close()
            out["persist"]["archive_bytes"] = (tmp / "m1_persist.db").stat().st_size
        else:
            t0 = time.perf_counter()
            for _ in range(300):
                sim.journal.hash()
            out["memory"]["incremental_hash_per_call_us"] = round(
                (time.perf_counter() - t0) / 300 * 1e6, 2)
    delta = out["persist"]["step_median_ms"] - out["memory"]["step_median_ms"]
    out["persist"]["sqlite_share_of_step_pct"] = round(
        100 * delta / out["persist"]["step_median_ms"], 1)

    # M2: hash on a REOPENED archive — first call, cached call, and the
    # call after ONE appended record: that last number is what every
    # decide of a takeover-paid life currently costs per frame
    a = SqliteArchive(str(tmp / "m1_persist.db"))
    t0 = time.perf_counter()
    h = a.hash()
    t1 = time.perf_counter()
    h_cached = a.hash()
    t2 = time.perf_counter()
    last = list(a)[-1]
    a.record(dataclasses.replace(last, id=last.id + 1))
    t3 = time.perf_counter()
    h_after = a.hash()
    t4 = time.perf_counter()
    n = a.counts()[0]
    a.close()
    out["hash_reopened"] = {
        "rows": n,
        "first_ms": round((t1 - t0) * 1e3, 1),
        "cached_ms": round((t2 - t1) * 1e3, 4),
        "cached_equal": h == h_cached,
        "append_ms": round((t3 - t2) * 1e3, 3),
        "hash_after_append_ms": round((t4 - t3) * 1e3, 1),
        "changed_after_append": h_after != h,
    }
    DATA["M1_M2"] = out


# ================================================================== M3 =====
def measure_long_journal(tmp: Path):
    """5000 global ticks on a small world (seed5, 2x30): the tail is a
    dead world — that is the game's own truth (no rule is bent), and the
    dead-tail journaling is a cost a long-lived world really pays."""
    print("M3: 5000-tick journal (play + full replay) …", flush=True)
    db = str(tmp / "m3_long.db")
    sim = create_world(seed=5, ruleset=get_ruleset("player_life"), ticks=0,
                       regions=2, agents=30, persist=db)
    extinction_tick = None
    marks = []
    prev_rows = 0
    t0 = time.perf_counter()
    for t in range(5000):
        if extinction_tick is None and not any(
            sim.state.get(a, "alive") for a in sim.state.entities_with_prefix("agent:")
        ):
            extinction_tick = t
        sim.step()
        if t + 1 in (100, 1000, 5000):
            r = sim.journal.counts()[0]
            marks.append({"after_ticks": t + 1, "rows_delta": r - prev_rows})
            prev_rows = r
    play_wall = time.perf_counter() - t0
    state_hash = sim.state.hash()
    jhash = sim.journal.hash()
    counts = sim.journal.counts()
    sim.journal.close()

    t0 = time.perf_counter()
    with JournalView(db) as view:
        meta = view.meta_all()
        stream = DecisionStreamReader.actions_from(view)
        lo, hi = view.tick_range()
    t_view = time.perf_counter() - t0

    head = hi + 1
    t0 = time.perf_counter()
    replay = create_world(seed=int(meta["seed"]), ruleset=get_ruleset("player_life"),
                          ticks=0, regions=int(meta["regions"]),
                          agents=int(meta["agents"]), persist=None)
    attach_player_channel(replay, DecisionChannel(actions=list(stream)))
    t_create = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(head):
        replay.step()
    t_step = time.perf_counter() - t0
    t0 = time.perf_counter()
    replay_hash = replay.journal.hash()
    replay_state = replay.state.hash()
    t_hash = time.perf_counter() - t0

    a = SqliteArchive(db)
    t0 = time.perf_counter()
    ah = a.hash()
    t_archive_hash = time.perf_counter() - t0
    a.close()

    import tracemalloc
    tracemalloc.start()
    r2 = create_world(seed=5, ruleset=get_ruleset("player_life"), ticks=0,
                      regions=2, agents=30, persist=None)
    with JournalView(db) as v3:
        attach_player_channel(r2, DecisionStreamReader.channel_from(v3))
    t0 = time.perf_counter()
    for _ in range(head):
        r2.step()
    t_replay_traced = time.perf_counter() - t0
    peak = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()

    DATA["M3"] = {
        "world": "seed5, 2x30, player_life, 5000 raw ticks",
        "extinction_tick": extinction_tick,
        "play_wall_s": round(play_wall, 2),
        "play_ticks_per_s": round(5000 / play_wall, 1),
        "rows": {"total": counts[0], "committed": counts[1], "rejected": counts[2]},
        "rows_growth": marks,
        "replay_stages_s": {
            "view_read_stream": round(t_view, 3),
            "create_world": round(t_create, 3),
            "steps": round(t_step, 2),
            "replay_memory_hash": round(t_hash, 4),
            "archive_reopen_full_hash": round(t_archive_hash, 3),
            "steps_under_tracemalloc": round(t_replay_traced, 2),
        },
        "identity": {
            "replay_hash_eq_archive": replay_hash == ah,
            "replay_state_eq_live": replay_state == state_hash,
            "archive_hash_eq_live": ah == jhash,
        },
        "tracemalloc_peak_replay_mb": round(peak, 1),
        "head_ticks_replayed": head,
    }


# ============================================================== M4 + M5 ===
def measure_life_chain(tmp: Path):
    print("M4: life chain with per-life takeover timings …", flush=True)
    script = script_actions(4000)
    db = str(tmp / "dyn_p3.db")
    t_all = time.perf_counter()
    s = Session(seed=21, regions=4, agents=50, max_ticks=10_000, db_path=db)
    lives = []
    life_no = 1
    si = 0
    stopped_by = None
    while True:
        seq = 0
        t_play = time.perf_counter()
        while s.state == "awaiting" and seq < LIFE_DECIDE_CAP and si + seq < len(script):
            s.decide(seq + 1, script[si + seq])
            seq += 1
        play_wall = time.perf_counter() - t_play
        if s.state == "awaiting":
            s.close()
        t_bio = time.perf_counter()
        fp = s.bio()["fingerprint"]
        bio_warm = time.perf_counter() - t_bio
        rec = {
            "n": life_no, "agent": s.controlled, "succession": s.succession,
            "end": s.finish_reason, "decisions": seq,
            "from_tick": s._from, "to_tick": s.sim.state.tick,
            "play_wall_s": round(play_wall, 2),
            "bio_after_finalize_s": round(bio_warm, 2),
            "fingerprint16": fp[:16],
            "rss_mb": round(rss_mb(), 1),
        }
        print(f"  life {rec['n']}: {rec['agent']} {rec['succession']} "
              f"t{rec['from_tick']}..{rec['to_tick']} end={rec['end']} "
              f"decisions={rec['decisions']} play={rec['play_wall_s']}s "
              f"bio={rec['bio_after_finalize_s']}s", flush=True)
        life_no += 1
        if life_no > LIFE_CAP or si + seq >= len(script) - 5:
            lives.append(rec)
            break
        si += seq
        t_to = time.perf_counter()
        try:
            nxt = Session.takeover(db, max_ticks=10_000)
        except ProtocolError as e:
            lives.append(rec)
            stopped_by = {"code": e.code, "extra": e.extra}
            break
        rec_next_prep = time.perf_counter() - t_to
        lives.append(rec | {"next_takeover_s": round(rec_next_prep, 2)})
        s = nxt
    wall = time.perf_counter() - t_all
    with JournalView(db) as v:
        lo_hi = v.tick_range()
        cnt = v.counts()
    DATA["M4_M5"] = {
        "scenario": f"seed21, 4x50, chain, cap {LIFE_CAP} lives x {LIFE_DECIDE_CAP} decisions",
        "lives": lives,
        "reached_ticks": lo_hi[1],
        "counts": {"total": cnt[0], "committed": cnt[1], "rejected": cnt[2]},
        "stopped_by": stopped_by,
        "wall_s": round(wall, 1),
        "rss_mb_end": round(rss_mb(), 1),
    }
    DATA["IDENTITY"] = {
        "fingerprints": [l["fingerprint16"] for l in lives],
        "final_archive_rows": cnt[0],
    }


# ================================================================== M6 =====
def fit_and_breakeven():
    lives = DATA["M4_M5"]["lives"]
    pts = [(l["to_tick"], l["next_takeover_s"]) for l in lives if "next_takeover_s" in l]
    m6: dict = {"points_head_ticks_vs_takeover_s": pts}
    if len(pts) >= 2:
        n = len(pts)
        sx = sum(p[0] for p in pts)
        sy = sum(p[1] for p in pts)
        sxx = sum(p[0] * p[0] for p in pts)
        sxy = sum(p[0] * p[1] for p in pts)
        den = n * sxx - sx * sx
        a = (n * sxy - sx * sy) / den
        b = (sy - a * sx) / n
        m6["fit"] = {"a_s_per_head_tick": round(a, 5), "b_s": round(b, 3)}
        m6["takeover_cost_s_at_head_ticks"] = {
            str(T): round(a * T + b, 2) for T in (1000, 2000, 5000, 20_000)
        }
        m6["50_lives_note"] = (
            f"a 50-life chain is INFEASIBLE under current rules (extinction "
            f"after {len(lives)} lives at T={DATA['M4_M5']['reached_ticks']}); "
            "the 50-life replay bill is the EXTRAPOLATED sum of a*T_i+b for "
            "uniform 400-tick lives, not a faked run"
        )
        tot = sum(a * (400 * (i + 1)) + b for i in range(50))
        m6["extrapolated_50_lives_takeover_total_s"] = round(tot, 1)
    m3 = DATA["M3"]["replay_stages_s"]
    play_pt = DATA["M3"]["play_wall_s"] / 5000
    replay_pt = m3["steps"] / 5000
    verification = m3["archive_reopen_full_hash"] + m3["view_read_stream"]
    m6["snapshot_breakeven"] = {
        "play_s_per_tick": round(play_pt, 4),
        "replay_s_per_tick": round(replay_pt, 4),
        "replay_equals_play_pct": round(100 * replay_pt / play_pt, 0),
        "verification_overhead_s_per_takeover_at_5000t": round(verification, 2),
        "note": ("snapshot pays off when replay+verification exceeds the "
                 "re-play it replaces — see table; M8 alone removes most of "
                 "verification at ZERO format change"),
    }
    DATA["M6"] = m6


def main():
    import shutil

    tmp = OUT / ("opt" if OPTIMIZE else "base")
    shutil.rmtree(tmp, ignore_errors=True)  # a run starts from zero, always
    tmp.mkdir(parents=True, exist_ok=True)
    if OPTIMIZE:
        install_incremental_hash_variant()
    t0 = time.perf_counter()
    measure_tick_and_hash(tmp)
    measure_long_journal(tmp)
    measure_life_chain(tmp)
    fit_and_breakeven()
    DATA["wall_total_s"] = round(time.perf_counter() - t0, 1)
    DATA["rss_mb_final"] = round(rss_mb(), 1)
    suffix = "opt" if OPTIMIZE else "base"
    if hasattr(SqliteArchive, "_reseed_from_disk"):
        suffix = "impl"  # source itself is the optimized chain
    out = Path(__file__).parent / f"p3_profile_data_{suffix}.json"
    out.write_text(json.dumps(DATA, indent=1, sort_keys=True))
    print(f"written: {out}", flush=True)


if __name__ == "__main__":
    main()
