"""Localises the tick-0 RSS step, phase by phase (v0.12).

usage: tick0_rss_probe.py AGENTS DB_PATH
Mirrors the checkpoint harness order: create_world -> WorldIndex.from_state ->
tick 0 (step, commit, advance, slice, situations) -> tick 1 (same). VmRSS in MB
after each phase.
"""
import gc, json, os, sys, time
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(REPO, "src"))
from causal_world.observer.situation import situations
from causal_world.observer.slice import CellSlice, WorldIndex
from causal_world.simulation.engine import create_world
from causal_world.world.rules import get_ruleset

def rss():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return round(int(line.split()[1]) / 1024, 1)

agents, db = int(sys.argv[1]), sys.argv[2]
for p in (db, db + "-wal", db + "-shm"):
    if os.path.exists(p):
        os.remove(p)
rows = []
def mark(name, seconds=None):
    rows.append({"phase": name, "rss_mb": rss(), "seconds": seconds})
    print(json.dumps(rows[-1]), flush=True)

sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                   regions=2, agents=agents, persist=db)
mark("genesis")
archive = sim.journal
t = time.perf_counter(); archive.commit(); mark("genesis_commit", round(time.perf_counter() - t, 2))
t = time.perf_counter(); index = WorldIndex.from_state(sim.state, journal=archive)
mark("index_init", round(time.perf_counter() - t, 2))

for _ in range(2):
    tick = sim.state.tick
    t = time.perf_counter(); sim.step(); mark(f"t{tick}_step", round(time.perf_counter() - t, 2))
    t = time.perf_counter(); archive.commit(); mark(f"t{tick}_commit", round(time.perf_counter() - t, 2))
    t = time.perf_counter(); index.advance(archive, tick); mark(f"t{tick}_advance", round(time.perf_counter() - t, 2))
    t = time.perf_counter(); view = CellSlice.from_state(sim.state, index=index); mark(f"t{tick}_slice", round(time.perf_counter() - t, 2))
    t = time.perf_counter(); situations(view, current_tick=sim.state.tick); mark(f"t{tick}_situations", round(time.perf_counter() - t, 2))
    gc.collect(); mark(f"t{tick}_after_gc")
print("RESULT", json.dumps(rows))
sim.journal.close()
