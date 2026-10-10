"""v0.4 observer demonstration: L1-L4 over recorded archives.

Runs the full observer stack over the seed-7 archives (immune 0.3.0,
compost 0.3.3g, fertile_migration 0.3.3i) and prints the answers to the
five questions of the v0.4 spec. Strictly read-only (JournalView is
opened with mode=ro).

    python3 experiments/observer_demo.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.observer.budget import CausalBudget  # noqa: E402
from causal_world.observer.compare import (  # noqa: E402
    CausalComparator,
    migration_stats,
)
from causal_world.observer.compress import NarrativeCompressor  # noqa: E402
from causal_world.observer.journal import JournalView  # noqa: E402
from causal_world.observer.regime import RegimeClassifier  # noqa: E402
from causal_world.observer.series import build_series  # noqa: E402

RUNS = os.path.join(os.path.dirname(__file__), "..", "runs")
IMMUNE = os.path.join(RUNS, "v04_immune.db")
COMPOST = os.path.join(RUNS, "v04_compost.db")
FERTILE = os.path.join(RUNS, "v04_fertile_migration.db")


def hr(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show_budget(view, entity, field, t0=0, t1=float("inf"), label=""):
    budget = CausalBudget(view)
    r = budget.analyze(entity, field, t0, t1)
    if label:
        print(label)
    print(f"  budget {entity}.{field} [t{r.tick_range[0]}..{r.tick_range[1]}]")
    for side, entries in (("INFLOWS", r.inflows), ("OUTFLOWS", r.outflows)):
        print(f"    {side}:")
        if not entries:
            print("      (none)")
        for e in entries:
            print(f"      {e.system}.{e.operation}: {e.total_delta:+.6f} "
                  f"over {e.count} effective writes "
                  f"(mean {e.mean_delta:+.6f})")
    print(f"    NET: {r.net:+.6f}")
    return r


def classify(view, sample_every=10):
    report = RegimeClassifier(view, sample_every=sample_every).classify()
    print(f"  regime: {report.type.value} (confidence {report.confidence:.2f})")
    if report.extinction_tick is not None:
        print(f"  extinction tick: {report.extinction_tick}")
    if report.equilibrium_population is not None:
        print(f"  equilibrium population: {report.equilibrium_population:.1f}")
    print(f"  soil trajectory: {report.soil_trajectory}")
    print("  death causes: "
          + ", ".join(f"{c} {s:.1%}" for c, s in report.death_causes))
    return report


def main() -> int:
    # ------------------------------------------------------------------
    hr("L2 — regime classification of the three archives")
    with JournalView(IMMUNE) as v:
        print("immune 0.3.0:")
        classify(v)
    with JournalView(FERTILE) as v:
        print("fertile_migration 0.3.3i:")
        classify(v)
    with JournalView(COMPOST) as v:
        print("compost 0.3.3g:")
        rep = classify(v)

    # ------------------------------------------------------------------
    hr("L1 — soil budgets: the one-line difference")
    with JournalView(IMMUNE) as v:
        show_budget(v, "region:4", "soil_fertility",
                    label="immune 0.3.0, region:4, full run:")
    with JournalView(COMPOST) as v:
        show_budget(v, "region:4", "soil_fertility", 2000, 4999,
                    label="compost G, region:4, equilibrium window "
                          "t2000..4999:")
        show_budget(v, "region:4", "soil_fertility", 0, 4999,
                    label="compost G, region:4, full run:")

    # ------------------------------------------------------------------
    hr("L3 — comparator: immune vs compost (region:4 soil)")
    with JournalView(IMMUNE) as va, JournalView(COMPOST) as vb:
        cmp = CausalComparator(va, vb, "immune", "compost")
        diff = cmp.compare_field("region:4", "soil_fertility")
        print(f"  inflows only in compost: {diff.missing_inflows}")
        print(f"  outflows only in immune: {diff.missing_outflows}")
        print(f"  net delta: {diff.budget_deltas['soil_fertility']:+.6f}")
        print(f"  loop diff: {diff.causal_loop_diff}")

    # ------------------------------------------------------------------
    hr("Q1 — why is region:4 alive and region:1 dead in the compost world?")
    with JournalView(COMPOST) as v:
        series = build_series(v, sample_every=25,
                              total_agents=int(v.meta("agents")))
        print("  final populations:", dict(sorted(
            series.final_region_population.items())))
        # true final-inhabitation tick of region:1 (last write with pop > 0)
        rows = v.query(
            "SELECT MAX(t.tick) AS last_tick "
            "FROM transitions t, json_each(t.payload,'$.writes') w "
            "WHERE t.status='COMMITTED' "
            "AND json_extract(w.value,'$[0]')='region:1' "
            "AND json_extract(w.value,'$[1]')='population' "
            "AND json_extract(w.value,'$[3]') > 0")
        print(f"  region:1 last inhabited at tick: {rows[0]['last_tick']}")
        # final soil of the dead vs the alive region
        for reg in ("region:1", "region:4"):
            rows = v.query(
                "SELECT json_extract(w.value,'$[3]') AS s "
                "FROM transitions t, json_each(t.payload,'$.writes') w "
                "WHERE t.status='COMMITTED' "
                "AND json_extract(w.value,'$[0]')=? "
                "AND json_extract(w.value,'$[1]')='soil_fertility' "
                "ORDER BY t.id DESC LIMIT 1", (reg,))
            print(f"  {reg} final soil: {rows[0]['s']:.4f}")
        show_budget(v, "region:1", "soil_fertility",
                    label="  region:1 soil budget (no composters after "
                          "extinction):")
        show_budget(v, "region:4", "soil_fertility",
                    label="  region:4 soil budget (composters present):")

    # ------------------------------------------------------------------
    hr("Q3 — why does disease not kill the compost world?")
    with JournalView(COMPOST) as v:
        for lo in range(0, 5000, 1000):
            infect = v.query(
                "SELECT COUNT(*) n FROM transitions WHERE "
                "operation='disease.infect' AND status='COMMITTED' "
                "AND tick BETWEEN ? AND ?", (lo, lo + 999))[0]["n"]
            deaths = v.query(
                "SELECT COUNT(*) n FROM transitions WHERE "
                "operation='agent.death' AND status='COMMITTED' "
                "AND tick BETWEEN ? AND ?", (lo, lo + 999))[0]["n"]
            recover = v.query(
                "SELECT COUNT(*) n FROM transitions WHERE "
                "operation='disease.recover' AND status='COMMITTED' "
                "AND tick BETWEEN ? AND ?", (lo, lo + 999))[0]["n"]
            print(f"  t{lo:>4}..{lo+999}: infections={infect:<6} "
                  f"recoveries={recover:<6} deaths={deaths}")

    # ------------------------------------------------------------------
    hr("Q5 — informed migration vs blindness: herding statistics")
    for name, path in (("compost (blind)", COMPOST),
                       ("fertile_migration (informed)", FERTILE)):
        with JournalView(path) as v:
            stats = migration_stats(v)
            print(f"  {name}: moves={int(stats['moves'])} "
                  f"movers={int(stats['movers'])} "
                  f"destinations={int(stats['destinations'])} "
                  f"entropy={stats['entropy_bits']:.3f} bits "
                  f"top={stats['top_destination'] or '-'} "
                  f"({stats['top_destination_share']:.1%})")

    # ------------------------------------------------------------------
    hr("L4 — narrative compression of one death in each world")
    for name, path in (("immune 0.3.0", IMMUNE), ("compost G", COMPOST)):
        with JournalView(path) as v:
            row = v.query(
                "SELECT t.id, json_extract(w.value,'$[0]') AS agent "
                "FROM transitions t, json_each(t.payload,'$.writes') w "
                "WHERE t.operation='agent.death' AND t.status='COMMITTED' "
                "AND json_extract(w.value,'$[1]')='alive' "
                "ORDER BY t.id LIMIT 1")
            if not row:
                print(f"  {name}: no deaths")
                continue
            agent = row[0]["agent"]
            print(f"--- {name}: first death ({agent}) ---")
            print(NarrativeCompressor().explain_death(agent, v, depth=8))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
