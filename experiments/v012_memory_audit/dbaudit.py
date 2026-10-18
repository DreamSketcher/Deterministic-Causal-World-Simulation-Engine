import sqlite3, sys, json
db = sys.argv[1]
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
c.execute("PRAGMA temp_store=FILE")
out = {}
out["dbstat"] = {n: round(s/1048576, 2) for n, s in c.execute(
    "SELECT name, SUM(pgsize) FROM dbstat GROUP BY name ORDER BY SUM(pgsize) DESC")}
for t in ["transitions","latest_writer","history","dependents"]:
    out[f"rows_{t}"] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
out["latest_entities"] = c.execute("SELECT COUNT(DISTINCT entity) FROM latest_writer").fetchone()[0]
out["latest_fields"] = c.execute("SELECT COUNT(DISTINCT field) FROM latest_writer").fetchone()[0]
out["avg_len_entity_field"] = c.execute("SELECT AVG(LENGTH(entity)), AVG(LENGTH(field)) FROM latest_writer").fetchone()
out["avg_payload_bytes"] = c.execute("SELECT AVG(LENGTH(payload)) FROM transitions").fetchone()[0]
print(json.dumps(out, ensure_ascii=False, indent=1))
