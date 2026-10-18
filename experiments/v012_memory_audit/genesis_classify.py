"""Classify the genesis transitions of the 100k-scale world by origin.

Builds the same world as the v0.12 checkpoint runner (seed 7,
``player_resettle``, 2 regions) at several agent counts, in memory, and
counts the genesis transitions by operation, entity kind and the number of
writes. The aim is to explain the constant offset (+16) on top of 7 per
living agent, not to change anything.

usage: python genesis_classify.py AGENTS [AGENTS ...]
"""
from __future__ import annotations

import collections
import json
import sys

from causal_world.simulation.engine import create_world
from causal_world.systems.resettle import *  # noqa: F401,F403 (ruleset import side effects)
from causal_world.world.rules import get_ruleset


def classify(agents: int) -> dict:
    sim = create_world(seed=7, ruleset=get_ruleset("player_resettle"),
                       ticks=0, regions=2, agents=agents, persist=None)
    by_op: collections.Counter = collections.Counter()
    by_kind: collections.Counter = collections.Counter()
    writes_by_kind: collections.Counter = collections.Counter()
    samples: dict[str, list[str]] = collections.defaultdict(list)
    total = 0
    for t in sim.journal:
        total += 1
        kind = (t.writes[0].entity.split(":")[0] if t.writes else "none")
        by_op[t.operation] += 1
        by_kind[(t.operation, kind)] += 1
        writes_by_kind[(t.operation, kind)] += len(t.writes)
        if len(samples[t.operation]) < 3:
            samples[t.operation].append(
                f"T{t.id} {t.writes[0].entity if t.writes else '-'} "
                f"fields={[w.field for w in t.writes][:12]}")
    return {
        "agents": agents,
        "transitions": total,
        "by_operation": dict(by_op),
        "by_operation_kind": {f"{op}|{k}": v for (op, k), v in sorted(by_kind.items())},
        "writes_by_operation_kind": {f"{op}|{k}": v for (op, k), v in sorted(writes_by_kind.items())},
        "samples": dict(samples),
    }


if __name__ == "__main__":
    out = [classify(int(a)) for a in sys.argv[1:]]
    print(json.dumps(out, ensure_ascii=False, indent=1))
