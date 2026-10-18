"""Audit of WorldState.hash(): where the peak comes from. Read-only w.r.t. repo."""
import sys, time, json, gc, resource, os
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(REPO, "src"))
from causal_world.simulation.engine import create_world
from causal_world.world.rules import get_ruleset
from causal_world.kernel.canonical import canonical_token, canonical_json, sha256_hex

agents = int(sys.argv[1]); db = sys.argv[2]
def rss_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"): return round(int(line.split()[1]) / 1024, 1)
def hwm_mb(): return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
out = {"agents": agents, "stages": []}
def mark(name, **kw):
    out["stages"].append({"stage": name, "rss_mb": rss_mb(), "hwm_mb": hwm_mb(), **kw})
    print(json.dumps(out["stages"][-1]), flush=True)

if os.path.exists(db):
    os.remove(db)
mark("start")
sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                   regions=2, agents=agents, persist=db)
mark("after_create_world", pairs=len(sim.state.data))
st = sim.state
pairs = len(st.data)
# Stage 1: entries list (what state_payload does first)
t = time.perf_counter()
entries = [[e, f, canonical_token(v)] for (e, f), v in sorted(st.data.items())]
mark("entries_built", seconds=round(time.perf_counter()-t, 2), pairs=pairs)
# Stage 2: JSON string
t = time.perf_counter()
s = canonical_json({"tick": st.tick, "data": entries})
mark("json_str", seconds=round(time.perf_counter()-t, 2), json_chars=len(s))
# Stage 3: bytes copy
t = time.perf_counter()
b = s.encode("utf-8")
mark("bytes_copy", seconds=round(time.perf_counter()-t, 2), bytes=len(b))
del s
h_split = sha256_hex(b)
del b, entries
gc.collect()
mark("after_release_entries_json_bytes")
# Full hash via the public method, for reference
t = time.perf_counter()
h_full = st.hash()
mark("state_hash_full", seconds=round(time.perf_counter()-t, 2), equal=(h_full == h_split), hash=h_full)
sim.journal.commit()
mark("after_commit", db_mb=round(os.path.getsize(db)/1048576,1))
sim.journal.close()
print("RESULT", json.dumps(out), file=sys.stderr)
