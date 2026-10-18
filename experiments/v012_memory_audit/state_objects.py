"""Python-object accounting of WorldState at N agents (no archive, no hashing)."""
import sys, os, json, gc

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(REPO,"src"))
from causal_world.simulation.engine import create_world
from causal_world.world.rules import get_ruleset
agents=int(sys.argv[1])
def rss():
    for l in open("/proc/self/status"):
        if l.startswith("VmRSS"): return int(l.split()[1])/1024
r0=rss()
sim=create_world(seed=7, ruleset=get_ruleset("player_resettle"), ticks=0, regions=2, agents=agents, persist=None)
gc.collect()
st=sim.state
r1=rss()
data=st.data; prov=st.provenance
n=len(data)
ents=set(); flds=set(); ent_ids=set(); fld_ids=set(); key_ids=set()
tv={}; vbytes=0
import sys as S
ent_obj_bytes=0; fld_obj_bytes=0
for (e,f),v in data.items():
    if id(e) not in ent_ids: ent_ids.add(id(e)); ent_obj_bytes+=S.getsizeof(e)
    if id(f) not in fld_ids: fld_ids.add(id(f)); fld_obj_bytes+=S.getsizeof(f)
    t=type(v).__name__; tv[t]=tv.get(t,0)+1
    if t in("float","str"): vbytes+=S.getsizeof(v)
prov_none=sum(1 for v in prov.values() if v is None)
prov_int_bytes=sum(S.getsizeof(v) for v in prov.values() if v is not None)
out=dict(agents=agents,pairs=n,entities=len(ent_ids),entity_str_objs=len(ent_ids),field_str_objs=len(fld_ids),
  rss_before_mb=round(r0,1), rss_after_create_mb=round(r1,1),
  bytes_per_pair_rss=round((r1-r0)*1048576/n,1),
  data_dict_mb=round(S.getsizeof(data)/1048576,1), provenance_dict_mb=round(S.getsizeof(prov)/1048576,1),
  key_tuples_mb=round(n*S.getsizeof(next(iter(data)))/1048576,1),
  entity_strings_mb=round(ent_obj_bytes/1048576,1), field_strings_mb=round(fld_obj_bytes/1048576,1),
  value_types=tv, value_objs_float_str_mb=round(vbytes/1048576,1),
  prov_none=prov_none, prov_int_objs_mb=round(prov_int_bytes/1048576,1))
print(json.dumps(out, ensure_ascii=False, indent=1))
