"""v0.5 query-engine demonstration: the six spec questions, via the API.

Strictly read-only on the archives (JournalView mode=ro); the query-index
cache is a derived artifact under runs/. Runs in phases so a single
archive's index can be built, queried, and torn down without holding
several multi-GB caches at once (disk-bounded sandbox):

    python3 experiments/query_demo.py immune     # needs full index (traces)
    python3 experiments/query_demo.py ecology    # compost+fertile, writes-only
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.journal import JournalView  # noqa: E402
from causal_world.query.index import QueryIndex  # noqa: E402
from causal_world.query.query import CausalQuery  # noqa: E402

RUNS = os.path.join(os.path.dirname(__file__), "..", "runs")
IMMUNE = os.path.join(RUNS, "v05_immune.db")
COMPOST = os.path.join(RUNS, "v05_compost.db")
FERTILE = os.path.join(RUNS, "v05_fertile_migration.db")


def hr(title: str) -> None:
    print("\n" + "=" * 72 + f"\n{title}\n" + "=" * 72)


def fmt_t(t) -> str:
    return f"t{t.tick} T{t.id} {t.system}.{t.operation}"


def open_indexed(db_path: str, **build_kw):
    cache = db_path + ".qidx"
    view = JournalView(db_path)
    idx = QueryIndex(view, cache)
    stats = idx.build(**build_kw)
    reads = f"{stats.idx_reads} reads / " if stats.idx_reads else ""
    ent = f"{stats.idx_entity} entity / " if stats.idx_entity else ""
    print(f"[index] {os.path.basename(db_path)}: {stats.transitions} trans "
          f"-> {stats.idx_writes} writes / {reads}{ent}"
          f"built in {stats.build_seconds:.1f}s "
          f"({'incremental' if stats.incremental else 'full'}), "
          f"cache {stats.cache_bytes/1e6:.0f} MB")
    return view, idx


# ---------------------------------------------------------------------
def phase_immune() -> None:
    """Causal closures + close-call draws on the immune world (full index)."""
    view, idx = open_indexed(IMMUNE)
    q = CausalQuery(idx)

    hr("Q1 — why did this agent die? (backward trace, immune world)")
    death = q.operation("agent.death").committed_only().ticks(400, 573).first()
    agent = next(w.entity for w in death.writes if w.field == "alive")
    print(f"death: {fmt_t(death)} of {agent}")
    tr = q.trace(death.id, direction="backward", depth=6)
    print(f"backward trace: {len(tr.nodes)} nodes "
          f"(max depth {max(tr.depths.values())}); "
          f"the death reads shared region state, so the ancestor cone "
          f"reaches back to genesis")
    # show the CLOSEST causes first (depth asc, recency desc)
    close = sorted(tr.nodes, key=lambda t: (tr.depths[t.id], -t.tick))
    for t in close[:12]:
        reads = {r.field: r.value for r in t.reads if r.entity == agent}
        rstr = ", ".join(
            f"{k}={round(v,3) if isinstance(v,float) else v}"
            for k, v in list(reads.items())[:4])
        draws = "; ".join(
            f"{d.purpose} {d.value:.3f}{'<' if d.outcome else '>='}"
            f"{d.threshold:.3f}"
            for d in t.random_draws
            if d.value is not None and d.threshold is not None)
        print(f"  d{tr.depths[t.id]} {fmt_t(t)}"
              + (f"  [{rstr}]" if rstr else "")
              + (f"  DRAW {draws}" if draws else ""))

    hr("Q2 — who read what THIS harvest wrote? (forward closure)")
    harvest = (q.system("AgricultureSystem").operation("agriculture.harvest")
               .committed_only().ticks(300, 300).first())
    def _d(w):
        if isinstance(w.old, (int, float)) and isinstance(w.new, (int, float)):
            return round(w.new - w.old, 4)
        return None
    print(f"source: {fmt_t(harvest)} "
          f"{[(w.entity, w.field, _d(w)) for w in harvest.writes]}")
    for depth in (1, 2, 3):
        t0 = time.time()
        n = q.caused_by(harvest.id, depth=depth).count()
        print(f"  depth {depth}: {n} dependent transitions "
              f"({(time.time()-t0)*1000:.0f} ms)")
    for t in q.caused_by(harvest.id, depth=1).list(limit=4):
        print(f"    e.g. {fmt_t(t)}")

    hr("Q3 — writers of region:4.soil_fertility (immune, t0..9999)")
    n = q.writes_to("region:4", "soil_fertility").committed_only() \
         .ticks(0, 9999).count()
    b = q.budget("region:4", "soil_fertility", 0, 9999)
    print(f"  {n} writes, net {b.net:+.6f}")
    for e in b.inflows + b.outflows:
        print(f"      {e.system}.{e.operation}: {e.total_delta:+.6f} "
              f"({e.count} effective)")

    hr("DRILL-DOWN — delta profiles (immune region:4 soil)")
    for r in q.delta_profile("region:4", "soil_fertility"):
        print(f"    {r.system}.{r.operation}: n={r.writes} "
              f"+{r.positive}/-{r.negative} mean={r.mean_delta:+.9f}")

    hr("Q5 — which draws decided this agent's fate? (close calls)")
    life = q.timeline(agent, limit=100000)
    close = []
    for t in life:
        for d in t.random_draws:
            if (d.value is not None and d.threshold is not None
                    and abs(d.value - d.threshold) < 0.05):
                close.append((t.tick, t.operation, d.purpose, d.value,
                              d.threshold, d.outcome))
    print(f"  {agent}: {len(life)} transitions, {len(close)} close-call "
          f"draws (|value-threshold|<0.05)")
    for tick, op, purpose, v, thr, outcome in close[:8]:
        print(f"    t{tick} {op} {purpose}: {v:.4f} vs {thr:.4f} -> "
              f"{'passed' if outcome else 'failed'}")

    hr("Q6 — counterfactual footprint of one infection")
    infect = (q.system("ImmuneDiseaseSystem").operation("disease.infect")
              .committed_only().ticks(100, 200).first())
    if infect is not None:
        print(f"source: {fmt_t(infect)}")
        for depth in (1, 3, 6):
            t0 = time.time()
            n = q.caused_by(infect.id, depth=depth).count()
            print(f"  depth {depth}: {n} transitions depend on it "
                  f"({(time.time()-t0)*1000:.0f} ms)")

    hr("STREAMING — laziness on a million-transition journal")
    total = q.committed_only().count()
    t0 = time.time()
    stream = q.committed_only().execute()
    first10 = [next(stream) for _ in range(10)]
    print(f"  first 10 of {total} committed in "
          f"{(time.time()-t0)*1000:.0f} ms (pages of 500): "
          f"{[t.id for t in first10]}")

    idx.close()
    view.close()


# ---------------------------------------------------------------------
def phase_ecology() -> None:
    """Write-level queries: compost vs informed-migration (writes-only index)."""
    cv, ci = open_indexed(COMPOST, include_reads=False, include_entity=False)
    q_g = CausalQuery(ci)

    hr("Q3 — writers of region:4.soil_fertility (compost G, t0..3999)")
    n = q_g.writes_to("region:4", "soil_fertility").committed_only() \
           .ticks(0, 3999).count()
    b = q_g.budget("region:4", "soil_fertility", 0, 3999)
    print(f"  {n} writes, net {b.net:+.6f}")
    for e in b.inflows + b.outflows:
        print(f"      {e.system}.{e.operation}: {e.total_delta:+.9f} "
              f"({e.count} effective)")

    hr("DRILL-DOWN — same op name, different law (compost region:4 soil, "
       "equilibrium t2000..3999)")
    for r in q_g.delta_profile("region:4", "soil_fertility", 2000, 3999):
        print(f"    {r.system}.{r.operation}: n={r.writes} "
              f"+{r.positive}/-{r.negative} mean={r.mean_delta:+.9f} "
              f"range [{r.min_delta:+.9f}, {r.max_delta:+.9f}]")

    hr("Q4 — migration entropy: blind compost vs informed migration")
    ent_g = (q_g.operation("agent.migrate").committed_only()
             .entropy(by="write:region", actual_changes_only=True))
    print(f"  compost (blind):    {ent_g.total} moves, "
          f"entropy {ent_g.entropy_bits:.3f} bits, "
          f"{len(ent_g.distribution)} destinations")
    ci.close()
    cv.close()

    if os.path.exists(FERTILE):
        fv, fi = open_indexed(FERTILE, include_reads=False,
                              include_entity=False)
        q_f = CausalQuery(fi)
        ent_f = (q_f.operation("agent.migrate").committed_only()
                 .entropy(by="write:region", actual_changes_only=True))
        top = ent_f.distribution[0] if ent_f.distribution else ("-", 0)
        print(f"  informed migration: {ent_f.total} moves, "
              f"entropy {ent_f.entropy_bits:.3f} bits, "
              f"{len(ent_f.distribution)} destinations, top {top[0]} "
              f"({top[1]/max(ent_f.total,1):.1%})")
        fi.close()
        fv.close()


PHASES = {"immune": phase_immune, "ecology": phase_ecology}


def main(argv) -> int:
    phase = argv[1] if len(argv) > 1 else "immune"
    if phase not in PHASES:
        print(f"usage: query_demo.py [{'|'.join(PHASES)}]")
        return 2
    hr(f"BUILD: {phase} phase")
    PHASES[phase]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
