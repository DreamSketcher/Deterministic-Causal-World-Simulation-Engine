"""Physical-representation variants of the causal index. Same logical rows; built from a read-only source."""
import sqlite3, time, json, os, sys
src = sys.argv[1]
WORK = os.environ.get("AUDIT_WORK", "/tmp")
s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
LW = s.execute("SELECT entity, field, tid FROM latest_writer").fetchall()
HI = s.execute("SELECT entity, field, tid FROM history").fetchall()
base = dict(s.execute("SELECT name, SUM(pgsize)/1048576.0 FROM dbstat GROUP BY name").fetchall())
def fresh(path):
    for p in (path, path+"-wal", path+"-shm", path+"-journal"):
        if os.path.exists(p): os.remove(p)
    return sqlite3.connect(path)
def finish(c, path, name, t0, extra):
    c.commit(); c.execute("VACUUM"); c.close()
    return dict(name=name, build_s=round(time.perf_counter()-t0,2), file_mb=round(os.path.getsize(path)/1048576,2), **extra)

out = {"baseline_index_mb": {k: round(base[k],2) for k in base if k in ("latest_writer","history","sqlite_autoindex_latest_writer_1","sqlite_autoindex_history_1")},
       "rows": [len(LW), len(HI)], "variants": []}
# V1: identical columns, WITHOUT ROWID (removes the duplicate copy of each row).
p = os.path.join(WORK, "var_V1.db"); t0=time.perf_counter(); c = fresh(p)
c.execute("CREATE TABLE latest_writer(entity TEXT NOT NULL, field TEXT NOT NULL, tid INTEGER NOT NULL, PRIMARY KEY(entity,field)) WITHOUT ROWID")
c.execute("CREATE TABLE history(entity TEXT NOT NULL, field TEXT NOT NULL, tid INTEGER NOT NULL, PRIMARY KEY(entity,field,tid)) WITHOUT ROWID")
c.executemany("INSERT INTO latest_writer VALUES (?,?,?)", LW); c.executemany("INSERT INTO history VALUES (?,?,?)", HI)
out["variants"].append(finish(c, p, "V1_without_rowid", t0, {}))
# V3: interned entity/field ids + WITHOUT ROWID.
p = os.path.join(WORK, "var_V3.db"); t0=time.perf_counter(); c = fresh(p)
ents = sorted({e for e,_,_ in LW}); flds = sorted({f for _,f,_ in LW})
eid = {e:i+1 for i,e in enumerate(ents)}; fid = {f:i+1 for i,f in enumerate(flds)}
c.execute("CREATE TABLE ent(eid INTEGER PRIMARY KEY, name TEXT NOT NULL)"); c.executemany("INSERT INTO ent VALUES (?,?)", [(eid[e],e) for e in ents])
c.execute("CREATE TABLE fld(fid INTEGER PRIMARY KEY, name TEXT NOT NULL)"); c.executemany("INSERT INTO fld VALUES (?,?)", [(fid[f],f) for f in flds])
c.execute("CREATE TABLE latest_writer(eid INTEGER NOT NULL, fid INTEGER NOT NULL, tid INTEGER NOT NULL, PRIMARY KEY(eid,fid)) WITHOUT ROWID")
c.execute("CREATE TABLE history(eid INTEGER NOT NULL, fid INTEGER NOT NULL, tid INTEGER NOT NULL, PRIMARY KEY(eid,fid,tid)) WITHOUT ROWID")
c.executemany("INSERT INTO latest_writer VALUES (?,?,?)", [(eid[e],fid[f],t) for e,f,t in LW])
c.executemany("INSERT INTO history VALUES (?,?,?)", [(eid[e],fid[f],t) for e,f,t in HI])
out["variants"].append(finish(c, p, "V3_interned_ids_without_rowid", t0, {"entities": len(ents), "fields": len(flds)}))
print(json.dumps(out, ensure_ascii=False, indent=1))
