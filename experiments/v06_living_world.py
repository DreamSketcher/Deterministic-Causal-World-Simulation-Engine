"""v0.6 living-world experiment (report data generator).

The pytest suite pins the LAWS (gates, formulas, state-machine transitions,
determinism). This script measures the WORLD: what the heredity/ruin/
senescence laws do to a population over long horizons. It is an experiment,
not a test — ~20 ms/tick at 400 entities means a 3600-tick run takes ~80 s.

Usage:
    python experiments/v06_living_world.py [--seed 7] [--regions 2]
        [--agents 200] [--ticks 3600] [--onset ONSET --max-age MAX]

The three configurations that produced the v0.6 report:

    control      --onset 1000000000 --max-age 1000000000   (senescence inert)
    decision-1   (defaults: onset 250, max 350)            (as approved)
    long-life    --onset 1500 --max-age 2000                (wave deferral)

Metrics:
* population/soil trajectory (sampled) — persistence and the Malthusian
  constraint N_eq = birth_rate_cap / death_pressure;
* births, max generation EVER reached (from the journal — surviving agents
  under-count; births are the lineage);
* birth-time immune_memory by generation from committed agent.birth
  transitions (the STATE snapshot metric is age-confounded: older generations
  accumulate memory longer — only birth-time values are comparable);
* ruin law counts (activate/collapse — oscillation must be ~0);
* a determinism pair (same seed -> identical state + journal hashes).
"""

from __future__ import annotations

import argparse
import collections
import time

from causal_world import create_world
from causal_world.systems.senescence import SenescenceSystem
from causal_world.world.rules import get_ruleset


def sample(w, regions: int) -> tuple[int, float]:
    pop = sum(int(w.state.get(f"region:{r}", "population")) for r in range(regions))
    soil = sum(
        float(w.state.get(f"region:{r}", "soil_fertility")) for r in range(regions)
    ) / max(1, regions)
    return pop, soil


def birth_metrics(w) -> tuple[int, dict[int, list[float]]]:
    """(max generation ever, {generation: [immune_memory at birth]})."""
    maxgen, mem = 0, collections.defaultdict(list)
    for t in w.journal.all():
        if t.operation != "agent.birth":
            continue
        per = collections.defaultdict(dict)
        for c in t.writes:
            per[c.entity][c.field] = c.new
        for fields in per.values():
            g = fields["generation"]
            maxgen = max(maxgen, g)
            mem[g].append(fields["immune_memory"])
    return maxgen, dict(mem)


def run(args, onset: int, max_age: int, label: str) -> None:
    SenescenceSystem.SENESCENCE_ONSET = onset
    SenescenceSystem.MAX_LIFESPAN = max_age
    t0 = time.time()
    w = create_world(
        seed=args.seed, ruleset=get_ruleset("player_life"),
        ticks=0, regions=args.regions, agents=args.agents,
    )
    extinct_at, traj = None, []
    for tick in range(1, args.ticks + 1):
        w.step()
        pop, soil = sample(w, args.regions)
        if pop == 0 and extinct_at is None:
            extinct_at = tick
        if tick % args.sample == 0:
            births = sum(
                1 for x in w.journal.all()
                if x.operation == "agent.birth" and x.tick <= tick
            )
            traj.append(f"t{tick}: N={pop} b={births} soil={soil:.2f}")
    ops = collections.Counter(t.operation for t in w.journal.all())
    maxgen, mem = birth_metrics(w)
    dt = time.time() - t0
    print(f"## {label}  (onset={onset}, max_age={max_age}, {dt:.0f}s)")
    print(f"   extinction first at: {extinct_at or 'never'}")
    print(f"   births={ops.get('agent.birth', 0)} maxgen={maxgen} "
          f"senescent_deaths={ops.get('agent.senescence', 0)} "
          f"other_deaths={ops.get('agent.death', 0)}")
    print(f"   ruins: activate={ops.get('ruin.activate', 0)} "
          f"collapse={ops.get('ruin.collapse', 0)} "
          f"note_alive={ops.get('ruin.note_alive', 0)} "
          f"| explore={ops.get('agent.explore', 0)} "
          f"deplete={ops.get('ruin.deplete', 0)}")
    print("   trajectory: " + " | ".join(traj))
    print("   birth-time immune_memory by generation: "
          + " ".join(f"gen{g}={sum(v)/len(v):.3f} (n={len(v)})"
                     for g, v in sorted(mem.items())))
    print()


def determinism_pair(args) -> None:
    a = create_world(seed=args.seed, ruleset=get_ruleset("player_life"),
                     ticks=args.ticks // 6, regions=args.regions, agents=args.agents)
    b = create_world(seed=args.seed, ruleset=get_ruleset("player_life"),
                     ticks=args.ticks // 6, regions=args.regions, agents=args.agents)
    print("## determinism pair")
    print("   state hashes identical:", a.state.hash() == b.state.hash())
    print("   journal hashes identical:", a.journal.hash() == b.journal.hash())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--regions", type=int, default=2)
    p.add_argument("--agents", type=int, default=200, help="total across regions")
    p.add_argument("--ticks", type=int, default=3600)
    p.add_argument("--sample", type=int, default=300)
    p.add_argument("--onset", type=int, default=None)
    p.add_argument("--max-age", type=int, default=None)
    args = p.parse_args()
    # capture the shipped defaults BEFORE any run mutates them
    spec = (SenescenceSystem.SENESCENCE_ONSET, SenescenceSystem.MAX_LIFESPAN)
    if args.onset is not None:
        run(args, args.onset, args.max_age or args.onset + 100, "custom")
    else:
        run(args, *spec, "decision-1 spec (as approved)")
        run(args, 10**9, 10**9, "control (senescence inert)")
        run(args, 1500, 2000, "long-life")
    determinism_pair(args)


if __name__ == "__main__":
    main()
