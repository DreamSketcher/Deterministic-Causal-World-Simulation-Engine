"""Archive integrity after a run (v0.12): reopen, hash, counts, index.

usage: archive_integrity.py DB_PATH EXPECTED_JOURNAL_HASH

Read-only checks, no replay (replay builds a second full world and is a
separate step):

* SQLite ``PRAGMA quick_check``;
* the archive reopens with ``SqliteArchive`` and reports the same journal hash
  and counts as the run's last tick;
* the derived index has its counts and digest (read-only; a rebuild would
  write the file, so it is not part of this check).
Times and the RSS before and after each step are recorded.
"""
import json, os, sqlite3, sys, time
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(REPO, "src"))
from causal_world.simulation.archive import SqliteArchive


def rss_mb():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS"):
            return round(int(line.split()[1]) / 1024, 1)


db, expected = sys.argv[1], sys.argv[2]
out = {"db": db, "steps": []}


def step(name, fn):
    t = time.perf_counter()
    value = fn()
    plain = value if isinstance(value, (int, float, str, list, dict, type(None))) else "ok"
    out["steps"].append({"step": name, "seconds": round(time.perf_counter() - t, 2),
                         "rss_mb": rss_mb(), "value": plain})
    print(json.dumps(out["steps"][-1], ensure_ascii=False), flush=True)
    return value


def quick_check():
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [r[0] for r in c.execute("PRAGMA quick_check")][:5]
    finally:
        c.close()


def dbstat():
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.execute("PRAGMA temp_store=FILE")
    try:
        return {n: round(s / 1048576, 1) for n, s in c.execute(
            "SELECT name, SUM(pgsize) FROM dbstat GROUP BY name ORDER BY SUM(pgsize) DESC")}
    finally:
        c.close()


step("quick_check", quick_check)
out["dbstat_mb"] = step("dbstat", dbstat)
archive = step("reopen", lambda: SqliteArchive(db))
try:
    hash_ = step("journal_hash", archive.hash)
    counts = step("counts", archive.counts)
    out["journal_hash_matches_run"] = hash_.startswith(expected)
    out["journal_hash"] = hash_
    out["counts_total_committed_rejected"] = list(counts)
    out["index_counts"] = list(step("index_counts", archive.index_counts))
    out["index_digest"] = step("index_digest", archive.index_digest)
finally:
    archive.close()
print("RESULT", json.dumps(out, ensure_ascii=False))
