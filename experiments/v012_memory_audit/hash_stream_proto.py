"""Prototype (v0.12 memory audit): streamed canonical hash vs WorldState.hash().

Not wired into the kernel. Checks byte-equal digests and Python-allocation peak
via tracemalloc. Run: python experiments/v012_memory_audit/hash_stream_proto.py N
"""
import sys, os, json, hashlib, time
from json.encoder import encode_basestring_ascii as enc
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from causal_world.kernel.canonical import canonical_token
import tracemalloc
def measure(fn):
    tracemalloc.start()
    t = time.perf_counter()
    v = fn()
    dt = time.perf_counter() - t
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return v, round(peak/1048576, 1), round(dt, 2)

from causal_world.simulation.engine import create_world
from causal_world.world.rules import get_ruleset

def hash_streamed2(tick, data, chunk=8192):
    h = hashlib.sha256()
    h.update(b'{"data":[')
    buf = []
    first = True
    for key in sorted(data):
        e, f = key
        tok = canonical_token(data[key])
        buf.append(('' if first else ',') + '["' + enc(e)[1:-1] + '","' + enc(f)[1:-1] + '","' + enc(tok)[1:-1] + '"]')
        first = False
        if len(buf) >= chunk:
            h.update("".join(buf).encode("ascii")); buf.clear()
    if buf:
        h.update("".join(buf).encode("ascii"))
    h.update(('],"tick":' + json.dumps(tick) + "}").encode("ascii"))
    return h.hexdigest()

if __name__ == "__main__":
    agents = int(sys.argv[1])
    sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0,
                       regions=2, agents=agents, persist=None)
    st = sim.state
    h_old, peak_old, t_old = measure(st.hash)
    h_new, peak_new, t_new = measure(lambda: hash_streamed2(st.tick, st.data))
    print(json.dumps(dict(agents=agents, pairs=len(st.data), equal=h_old == h_new,
        old_peak_mb=peak_old, old_s=t_old, new_peak_mb=peak_new, new_s=t_new)))
