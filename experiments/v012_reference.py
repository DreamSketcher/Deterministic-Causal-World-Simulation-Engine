#!/usr/bin/env python3
"""v0.12, stage 2c — the reference run, written down before the change.

The 2c invariants are only meaningful against a run recorded BEFORE any
representation change. This script writes that reference:

* seed 7, ``player_resettle``, 2 regions, 54 agents, 40 ticks;
* the state hash and the journal hash after EVERY tick, not only at the
  end (a representation change can agree at the finish and drift inside);
* the number of recorded transitions per tick.

The file it writes (``tests/golden/v012_reference.json``) is the gate:
``tests/test_v012_equivalence.py`` re-runs the same world and requires
every value to match. A change that alters one tick's state is a change
of the law, not of the representation, and must bump the ruleset version
instead of editing this file.

Usage:
    python3 experiments/v012_reference.py
    python3 experiments/v012_reference.py --check   # compare, do not write
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world import create_world  # noqa: E402
from causal_world.world.rules import get_ruleset  # noqa: E402

CONFIG = {
    "seed": 7,
    "ruleset": "player_resettle",
    "regions": 2,
    "agents": 54,
    "ticks": 40,
}


def run_reference(config: dict | None = None) -> dict:
    cfg = dict(config or CONFIG)
    sim = create_world(
        seed=cfg["seed"], ruleset=get_ruleset(cfg["ruleset"]), ticks=0,
        regions=cfg["regions"], agents=cfg["agents"],
    )
    ticks = [{
        "tick": sim.state.tick,
        "state_hash": sim.state.hash(),
        "journal_hash": sim.journal.hash(),
        "transitions": len(sim.journal),
    }]
    for _ in range(cfg["ticks"]):
        sim.step()
        ticks.append({
            "tick": sim.state.tick,
            "state_hash": sim.state.hash(),
            "journal_hash": sim.journal.hash(),
            "transitions": len(sim.journal),
        })
    total, committed, rejected = sim.journal.counts()
    return {
        "config": cfg,
        "ticks": ticks,
        "final": {
            "state_hash": sim.state.hash(),
            "journal_hash": sim.journal.hash(),
            "transitions_total": total,
            "committed": committed,
            "rejected": rejected,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tests/golden/v012_reference.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    report = run_reference()
    path = Path(args.out)
    if args.check:
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != report:
            print("REFERENCE DRIFT: the run no longer matches the golden file")
            for i, (old, new) in enumerate(zip(current["ticks"], report["ticks"])):
                if old != new:
                    print(f"  first difference at tick {old['tick']}:")
                    print(f"    before {old}")
                    print(f"    after  {new}")
                    break
            return 1
        print(f"reference matches {path} ({len(report['ticks'])} ticks)")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"written {path}: {len(report['ticks'])} ticks, "
          f"{report['final']['transitions_total']} transitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
