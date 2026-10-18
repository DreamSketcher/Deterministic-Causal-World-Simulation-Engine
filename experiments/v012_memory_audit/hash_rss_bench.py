"""RSS and time of state hashing, one variant per process (v0.12).

usage: hash_rss_bench.py AGENTS {legacy|streamed} DB_PATH

Builds the world exactly as the checkpoint does (persisted archive), then
hashes the state once. Peak RSS during the hash is sampled from
/proc/self/status every 2 ms, because VmHWM cannot separate phases.
``legacy`` is the verbatim pre-change algorithm (kept as reference).
"""
import hashlib, json, os, sys, threading, time
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(REPO, "src"))
from causal_world.kernel.canonical import canonical_json, canonical_token, hash_state
from causal_world.simulation.engine import create_world
from causal_world.world.rules import get_ruleset

def legacy_state_hash(tick, data):
    entries = [[e, f, canonical_token(v)] for (e, f), v in sorted(data.items())]
    return hashlib.sha256(canonical_json({"tick": tick, "data": entries}).encode("utf-8")).hexdigest()

def rss_kb():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return int(line.split()[1])
def hwm_kb():
    for line in open("/proc/self/status"):
        if line.startswith("VmHWM"):
            return int(line.split()[1])

agents, mode, db = int(sys.argv[1]), sys.argv[2], sys.argv[3]
for p in (db, db + "-wal", db + "-shm"):
    if os.path.exists(p):
        os.remove(p)
base = rss_kb()
t0 = time.perf_counter()
sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                   regions=2, agents=agents, persist=db)
build_s = time.perf_counter() - t0
after_build = rss_kb()
hwm_build = hwm_kb()
state = sim.state
pairs = len(state.data)

peak = [rss_kb()]
stop = threading.Event()
def sampler():
    while not stop.is_set():
        peak[0] = max(peak[0], rss_kb())
        time.sleep(0.002)
th = threading.Thread(target=sampler, daemon=True)
th.start()
t = time.perf_counter()
digest = (hash_state(state.tick, state.data) if mode == "streamed"
          else legacy_state_hash(state.tick, state.data))
hash_s = time.perf_counter() - t
stop.set(); th.join()
after_hash = rss_kb()
sim.journal.commit()
sim.journal.close()
out = dict(agents=agents, mode=mode, pairs=pairs,
           build_s=round(build_s, 2), rss_base_mb=round(base / 1024, 1),
           rss_after_build_mb=round(after_build / 1024, 1),
           hwm_after_build_mb=round(hwm_build / 1024, 1),
           hash_s=round(hash_s, 2), hash_rss_peak_mb=round(peak[0] / 1024, 1),
           hash_rss_delta_mb=round((peak[0] - after_build) / 1024, 1),
           rss_after_hash_mb=round(after_hash / 1024, 1),
           db_mb=round(os.path.getsize(db) / 1048576, 1), digest=digest)
print(json.dumps(out))
