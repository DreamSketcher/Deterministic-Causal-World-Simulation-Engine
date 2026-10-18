"""Localises the tick-0 RSS step: RSS around Snapshot.from_state (v0.12).

usage: snapshot_copy_probe.py AGENTS DB_PATH
Builds the world as the checkpoint does, then measures RSS before the first
snapshot copy, after it, after releasing it, and after a second copy (does the
heap get reused?). Each number is VmRSS in MB.
"""
import gc, json, os, sys, time
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(REPO, "src"))
from causal_world.kernel.snapshot import Snapshot
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
sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                   regions=2, agents=agents, persist=db)
sim.journal.commit()
gc.collect()
out = {"agents": agents, "pairs": len(sim.state.data), "steps": []}
def mark(name):
    out["steps"].append([name, rss()]); print(name, rss(), flush=True)
mark("after_genesis")
t = time.perf_counter(); snap = Snapshot.from_state(sim.state); out["copy1_s"] = round(time.perf_counter() - t, 2)
mark("copy1_held")
del snap; gc.collect()
mark("copy1_released")
snap = Snapshot.from_state(sim.state)
mark("copy2_held")
del snap; gc.collect()
mark("copy2_released")
print("RESULT", json.dumps(out))
sim.journal.close()
