"""Lean archive regeneration for the v0.5 demo (persist only, no report).

    python3 experiments/_regen_archive.py --seed 7 --regions 10 \
        --agents 1000 --ticks 10000 --ruleset immune --db runs/v05_immune.db
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world import create_world  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--regions", type=int, default=10)
    ap.add_argument("--agents", type=int, default=1000)
    ap.add_argument("--ticks", type=int, default=10000)
    ap.add_argument("--ruleset", type=str, default="immune")
    ap.add_argument("--db", type=str, required=True)
    args = ap.parse_args()

    if os.path.exists(args.db):
        os.remove(args.db)
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    rules = get_ruleset(args.ruleset)
    t0 = time.time()
    sim = create_world(seed=args.seed, regions=args.regions,
                       agents=args.agents, ruleset=rules, persist=args.db)
    sim.journal.set_meta("ruleset_name", args.ruleset)
    if getattr(rules, "description", None):
        sim.journal.set_meta("ruleset_description", rules.description)
    for tick in range(1, args.ticks + 1):
        sim.step()
        if tick % 1000 == 0:
            alive = sum(1 for a in sim.state.entities_with_prefix("agent:")
                        if sim.state.get(a, "alive"))
            print(f"tick {tick}/{args.ticks} alive={alive} "
                  f"elapsed={time.time()-t0:.0f}s", flush=True)
    sim.journal.close()
    print(f"done in {time.time()-t0:.0f}s -> {args.db}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
