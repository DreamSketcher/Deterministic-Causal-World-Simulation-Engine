#!/usr/bin/env python3
"""v0.6 P2 — demographic baseline BEFORE any calibration (contract:
experiments/proposals/v06_p2_demography_contract.md).

Zero rules changes: this measures what the CURRENT rules do, so that
acceptance criteria can be ratified against reality, not hope.

Panel A  player_life worlds, no player (rules' own demographic character):
         12 seeds, 4 regions x 50 agent slots, cap 1500 ticks.
         population curve, births, deaths by system (cause), first birth,
         extinction / pool-exhaustion ticks, fingerprints.
Panel B  the same worlds through a live Session: life chain per seed
         (cap 12 lives x 150 decisions); outcomes classified SEPARATELY:
         player_death (per life) vs heir_break vs extinction vs tick_limit.
Panel C  research worlds (frozen default ruleset), same seeds/shape — the
         control the calibration must never touch.

Run:  python3 experiments/p2_demography_baseline.py [TMPDIR]
Writes: experiments/p2_demography_baseline.json
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

from causal_world import create_world
from causal_world.observer.journal import JournalView
from causal_world.server.session import ProtocolError, Session
from causal_world.world.rules import get_ruleset

TMP = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/p2")
TMP.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(12))
TICK_CAP = 1500
REGIONS, SLOTS = 4, 50
LIFE_CAP, DECIDE_CAP = 12, 150

DATA: dict = {"protocol": {
    "seeds": SEEDS, "regions": REGIONS, "slots": SLOTS,
    "tick_cap": TICK_CAP, "life_cap": LIFE_CAP, "decide_cap": DECIDE_CAP,
    "rules_changes": "NONE — baseline before calibration",
}}


def world_panel(ruleset: str | None, seed: int) -> dict:
    kwargs = dict(seed=seed, ticks=0, regions=REGIONS, agents=SLOTS)
    if ruleset is not None:
        kwargs["ruleset"] = get_ruleset(ruleset)
    sim = create_world(**kwargs)
    # roster = genesis agents AND the pre-allocated dormant pool (ids beyond
    # the genesis count); enumerate from state, never assume numbering
    agent_ids = [e for e in sim.state.entities() if e.startswith("agent:")]
    curve, free_curve, pop0 = [], [], None
    first_birth = None
    extinction_tick = None
    pool_exhausted_tick = None
    dormant_at_extinction = None
    for tick in range(TICK_CAP):
        alive = 0
        free = 0
        for a in agent_ids:
            if sim.state.get(a, "alive"):
                alive += 1
            elif sim.state.get(a, "region") == "none":
                free += 1
        if pop0 is None:
            pop0 = alive
        if extinction_tick is None and alive == 0:
            extinction_tick = tick
            dormant_at_extinction = free
        if (pool_exhausted_tick is None and tick > 0 and free == 0
                and alive > 0):
            pool_exhausted_tick = tick
        if tick % 10 == 0:
            curve.append(alive)
            free_curve.append(free)
        sim.step()
    births, deaths, causes = 0, 0, {}
    for t in sim.journal:
        if t.status.value != "COMMITTED":
            continue
        for w in t.writes:
            if w.entity.startswith("agent:"):
                if w.field == "region" and w.old == "none" and w.new != "none":
                    births += 1
                    if first_birth is None:
                        first_birth = t.tick
                elif w.field == "alive" and w.old and not w.new:
                    deaths += 1
                    causes[t.system] = causes.get(t.system, 0) + 1
    alive_final = sum(1 for a in agent_ids if sim.state.get(a, "alive"))
    return {
        "seed": seed, "roster_total": len(agent_ids), "pop_start": pop0,
        "pop_final": alive_final,
        "dormant_at_extinction": dormant_at_extinction,
        "pop_min": min(curve), "pop_median": statistics.median(curve),
        "first_birth_tick": first_birth, "births_total": births,
        "deaths_total": deaths, "death_causes_by_system": causes,
        "extinction_tick": extinction_tick,
        "pool_exhausted_tick": pool_exhausted_tick,
        "curve_sample10": curve, "free_curve_sample10": free_curve,
        "state_hash16": sim.state.hash()[:16],
        "journal_hash16": sim.journal.hash()[:16],
    }


def script_actions(n: int, source: int) -> list[int]:
    rng = random.Random(source)
    return [
        2 if (r := rng.random()) < 0.25 else 1 if r < 0.4 else 0 if r < 0.7 else 6
        for _ in range(n)
    ]


def session_panel(seed: int) -> dict:
    db = str(TMP / f"p2b_{seed}.db")
    for suffix in ("", "-wal", "-shm"):
        p = Path(db + suffix)
        p.unlink(missing_ok=True)
    script = script_actions(2000, source=1000 + seed)
    s = Session(seed=seed, regions=REGIONS, agents=SLOTS,
                max_ticks=TICK_CAP, db_path=db)
    lives, si, stop = [], 0, None
    outcome = "world_alive_at_cap"  # battery stopped, world did not
    while True:
        seq = 0
        while s.state == "awaiting" and seq < DECIDE_CAP and si + seq < len(script):
            s.decide(seq + 1, script[si + seq])
            seq += 1
        if s.state == "awaiting":
            s.close()
        lives.append({
            "n": len(lives) + 1, "agent": s.controlled,
            "succession": s.succession, "end": s.finish_reason,
            "from_tick": s._from, "to_tick": s.sim.state.tick,
            "decisions": seq,
        })
        if len(lives) >= LIFE_CAP or si + seq >= len(script) - 5:
            break
        si += seq
        try:
            s = Session.takeover(db, max_ticks=TICK_CAP)
        except ProtocolError as e:
            stop = {"code": e.code, "extra": e.extra}
            if e.code == "no_heir":
                extra = e.extra or {}
                alive = int(extra.get("alive_agents", 0))
                outcome = "extinction" if alive == 0 else "heir_break"
            break
    with JournalView(db) as v:
        reached = v.tick_range()[1]
    player_deaths = sum(1 for l in lives if l["end"] == "death")
    lengths = [l["to_tick"] - l["from_tick"] for l in lives]
    return {
        "seed": seed, "lives": len(lives), "player_deaths": player_deaths,
        "life_lengths": lengths, "reached_ticks": reached,
        "outcome": outcome, "stop": stop,
        "world_extinct_at_end": stop is not None
        and stop.get("extra", {}).get("alive_agents", None) == 0,
    }


def spread(vals: list) -> dict:
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return {"n": 0}
    q = statistics.quantiles(vals, n=4) if len(vals) >= 4 else None
    return {
        "n": len(vals), "min": vals[0], "median": statistics.median(vals),
        "max": vals[-1],
        "q1": round(q[0], 2) if q else None,
        "q3": round(q[2], 2) if q else None,
    }


def main():
    print("Panel A: player_life worlds, no player …", flush=True)
    DATA["panel_A"] = [world_panel("player_life", sd) for sd in SEEDS]
    print("Panel B: player_life worlds with live session …", flush=True)
    DATA["panel_B"] = [session_panel(sd) for sd in SEEDS]
    print("Panel C: research worlds (frozen control) …", flush=True)
    DATA["panel_C"] = [world_panel(None, sd) for sd in SEEDS]
    for key in ("panel_A", "panel_C"):
        rows = DATA[key]
        DATA[key + "_stats"] = {
            "pop_final": spread([r["pop_final"] for r in rows]),
            "pop_min": spread([r["pop_min"] for r in rows]),
            "first_birth_tick": spread([r["first_birth_tick"] for r in rows]),
            "births_total": spread([r["births_total"] for r in rows]),
            "deaths_total": spread([r["deaths_total"] for r in rows]),
            "extinct_seeds": sum(1 for r in rows if r["extinction_tick"] is not None),
            "extinction_tick": spread([r["extinction_tick"] for r in rows]),
            "pool_exhausted_seeds": sum(
                1 for r in rows if r["pool_exhausted_tick"] is not None),
            "pool_exhausted_tick": spread([r["pool_exhausted_tick"] for r in rows]),
        }
    rows = DATA["panel_B"]
    DATA["panel_B_stats"] = {
        "lives_per_world": spread([r["lives"] for r in rows]),
        "life_length": spread([x for r in rows for x in r["life_lengths"]]),
        "outcomes": {o: sum(1 for r in rows if r["outcome"] == o)
                     for o in ("tick_limit", "heir_break", "extinction")},
        "player_deaths_total": sum(r["player_deaths"] for r in rows),
    }
    out = Path(__file__).parent / "p2_demography_baseline.json"
    out.write_text(json.dumps(DATA, indent=1, sort_keys=True))
    print(f"written: {out}", flush=True)


if __name__ == "__main__":
    main()
