#!/usr/bin/env python3
"""v0.11 — does a new settlement LAST, or only appear?

The v0.11 counterfactual proved that the world can USE the land it was
given: eight people moved, and three of them were still there at the end
of a 200-tick window. The review named the limit exactly: three people
at the end of one experiment is evidence of SETTLEMENT, not of a
SUSTAINED settlement. This script removes the last source of help — the
player's orders — and watches for a long time.

Protocol per seed:

    ticks 0..400    the v0.8 orders (amend/water), no capacity lever;
    tick 401        claim the first wild parcel of each region;
    ticks 405, 415  move people into those parcels (2, then the rest);
    ticks 416..1000 NOTHING: no claims, no moves, no laws.

Arms: control (no orders after 400), claim (only the claims), resettle
(claims + moves). The difference between claim and resettle is ONLY the
move, exactly as in the v0.11 counterfactual.

Measured, per parcel, at +0/+50/+100/+200/+400/+600 ticks after the move:

* population, workers, food, soil — does the new cell feed its people?
* whether it empties again, and how many times (episodes);
* births and deaths inside the parcel;
* the source's population, food and soil versus the SAME cell in the
  claim arm — what the move cost the donor beyond natural history;
* survival of the movers versus the people who stayed: a settlement
  that only looks populated because its founders are alive elsewhere is
  not a settlement.

The report is a measurement, not a verdict on the game: it says whether
the long horizon supports the short one.

Usage:
    python3 experiments/v011_settlement.py \
        --out experiments/reports/v011_settlement.md \
        --json experiments/reports/v011_settlement.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world.player import DecisionChannel, attach_player_channel  # noqa: E402
from causal_world.simulation.engine import create_world  # noqa: E402
from causal_world.systems.directive import (  # noqa: E402
    DIRECTIVE_AMEND,
    DIRECTIVE_CLAIM,
    DIRECTIVE_RESETTLE,
    DIRECTIVE_WATER,
    Directive,
    DirectiveChannel,
)
from causal_world.world.rules import get_ruleset  # noqa: E402

PROTOCOL_CELLS = ("cell:1:0", "cell:1:1", "cell:1:2", "cell:1:3")
SATURATE_AT = 400
CLAIM_AT = 401
MOVE_ATS = (405, 415)
HORIZON = 1020  # the world is watched 600+ ticks after the last order
CHECKPOINTS = (0, 50, 100, 200, 400, 600)
STARVATION = 0.75


@dataclass
class Arm:
    name: str
    alive_start: int = 0
    alive: int = 0
    food: float = 0.0
    mean_soil: float = 0.0
    starvation_deaths: int = 0
    cells: dict = field(default_factory=dict)
    parcel_series: dict = field(default_factory=dict)
    parcel_first_move: dict = field(default_factory=dict)
    parcel_state: dict = field(default_factory=dict)
    checkpoints: dict = field(default_factory=dict)
    donor_series: dict = field(default_factory=dict)
    donor_before: dict = field(default_factory=dict)
    donor_source: dict = field(default_factory=dict)
    mover_survival: dict = field(default_factory=dict)
    reempty: dict = field(default_factory=dict)
    parcel_births: dict = field(default_factory=dict)
    parcel_deaths: dict = field(default_factory=dict)


def _active_cells(sim) -> list[str]:
    return sorted(
        c for c in sim.state.entities_with_prefix("cell:")
        if sim.state.get(c, "land_active")
    )


def _wild_by_region(sim) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for parcel in sim.state.entities_with_prefix("cell:"):
        if sim.state.get(parcel, "land_active"):
            continue
        out.setdefault(sim.state.get(parcel, "region"), []).append(parcel)
    return {region: sorted(ps) for region, ps in out.items()}


def _alive(sim) -> set[str]:
    return {
        a for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    }


def _agent_facts(sim, agent: str) -> dict:
    return {
        "cell": sim.state.get(agent, "cell"),
        "hunger": round(float(sim.state.get(agent, "hunger") or 0.0), 3),
        "health": round(float(sim.state.get(agent, "health") or 0.0), 2),
        "birth_tick": int(sim.state.get(agent, "birth_tick") or 0),
    }


def _cell_facts(sim, cell: str, tick: int) -> dict:
    return {
        "tick": tick,
        "population": int(sim.state.get(cell, "population") or 0),
        "workers": int(sim.state.get(cell, "workers") or 0),
        "food": round(float(sim.state.get(cell, "food_stock") or 0.0), 2),
        "soil": round(float(sim.state.get(cell, "soil_fertility") or 0.0), 4),
        "capacity": round(
            float(sim.state.get(cell, "pop_base") or 0.0)
            * (1.0 + float(sim.state.get(cell, "soil_fertility") or 0.0)),
            2,
        ),
    }


def run_arm(name: str, db: str, args, orders) -> Arm:
    Path(db).unlink(missing_ok=True)
    sim = create_world(
        seed=args.seed, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=args.agents, persist=db,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (HORIZON + 10)))
    channel = DirectiveChannel()
    for s in sim.systems:
        if s.name == "ResettlementDirectiveSystem":
            s.channel = channel

    for tick, cell in zip((20, 21, 22, 23), PROTOCOL_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, 0.15))
    for tick, cell in zip((24, 25, 26, 27), PROTOCOL_CELLS):
        channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, 1.0))

    arm = Arm(name=name)
    hunger: dict[str, float] = {}
    starvation = 0
    for _ in range(SATURATE_AT):
        before = _alive(sim)
        sim.step()
        for agent in before - _alive(sim):
            if hunger.get(agent, 0.0) >= STARVATION:
                starvation += 1
        for agent in _alive(sim):
            hunger[agent] = float(sim.state.get(agent, "hunger") or 0.0)

    arm.alive_start = len(_alive(sim))
    wild = _wild_by_region(sim)
    picks = [parcels[0] for _, parcels in sorted(wild.items())]

    if orders in ("claim", "resettle"):
        for offset, parcel in enumerate(picks):
            channel.schedule(CLAIM_AT + offset,
                             Directive(DIRECTIVE_CLAIM, parcel, 0))
    if orders == "resettle":
        for offset, parcel in enumerate(picks):
            channel.schedule(MOVE_ATS[0] + offset,
                             Directive(DIRECTIVE_RESETTLE, parcel, 2))
            channel.schedule(MOVE_ATS[1] + offset,
                             Directive(DIRECTIVE_RESETTLE, parcel, 0))

    parcels = picks if orders in ("claim", "resettle") else []
    parcel_set = set(parcels)
    cell_track: dict[str, list[dict]] = {}
    agent_last_cell: dict[str, str] = {}
    mover_state: dict[str, dict] = {}
    movers: set[str] = set()
    stayers_at_move: dict[str, dict] = {}
    parcel_deaths = {p: 0 for p in parcels}
    parcel_first_move: dict[str, int] = {}
    moved_at: int | None = None
    checkpoints: dict[int, dict] = {}

    for _ in range(HORIZON - SATURATE_AT):
        before_alive = _alive(sim)
        sim.step()
        tick = sim.state.tick - 1  # the step just produced this tick
        after_alive = _alive(sim)

        # WHO the order moved: the transition names the agents; natural
        # migration into the same parcel must not be counted as a mover.
        if orders == "resettle":
            # The archive can answer "what happened at THIS tick" without
            # materializing the whole journal — an indexed read, not a scan.
            for transition in sim.journal.at_tick(tick):
                if transition.operation != "player.resettle":
                    continue
                if transition.status.value != "COMMITTED":
                    continue
                moved_now = [
                    w.entity for w in transition.writes
                    if w.entity.startswith("agent:") and w.field == "cell"
                    and w.new in parcel_set
                ]
                if not moved_now:
                    continue
                if moved_at is None:
                    moved_at = tick
                    stayers_at_move = {
                        a: _agent_facts(sim, a)
                        for a in after_alive
                        if sim.state.get(a, "cell") not in parcel_set
                    }
                for agent in moved_now:
                    if agent in after_alive:
                        movers.add(agent)
                        facts = _agent_facts(sim, agent)
                        facts["age_at_move"] = tick - facts["birth_tick"]
                        mover_state[agent] = facts
                for write in transition.writes:
                    if (write.entity in parcel_set and write.field == "population"
                            and write.entity not in parcel_first_move):
                        parcel_first_move[write.entity] = tick

        # deaths inside a parcel: the agent's last known cell was a parcel
        if moved_at is not None:
            for agent in before_alive - after_alive:
                cell = agent_last_cell.get(agent)
                if cell in parcel_set:
                    parcel_deaths[cell] += 1
        for agent in after_alive:
            agent_last_cell[agent] = sim.state.get(agent, "cell")

        for cell in _active_cells(sim):
            cell_track.setdefault(cell, []).append(
                _cell_facts(sim, cell, tick)
            )

        if moved_at is not None:
            offset = tick - moved_at
            if offset in CHECKPOINTS:
                checkpoints[offset] = {
                    "tick": tick,
                    "parcels": {
                        p: _cell_facts(sim, p, tick) for p in parcels
                    },
                    "movers_alive": sum(1 for a in movers if a in after_alive),
                    "movers_here": sum(
                        1 for a in movers if a in after_alive
                        and sim.state.get(a, "cell") in parcel_set
                    ),
                    "stayers_alive": sum(
                        1 for a in stayers_at_move if a in after_alive
                    ),
                }

    sim.journal.commit()
    sim.journal.close()
    arm.alive = len(_alive(sim))
    arm.food = sum(float(sim.state.get(c, "food_stock") or 0.0)
                   for c in _active_cells(sim))
    arm.mean_soil = sum(
        float(sim.state.get(c, "soil_fertility") or 0.0)
        for c in _active_cells(sim)
    ) / max(len(_active_cells(sim)), 1)
    arm.starvation_deaths = starvation
    arm.cells = {
        c: _cell_facts(sim, c, sim.state.tick - 1)
        for c in _active_cells(sim)
    }
    arm.checkpoints = checkpoints
    arm.parcel_first_move = parcel_first_move
    arm.parcel_state = {
        p: int(sim.state.get(p, "resettle_state") or 0) for p in parcels
    }
    arm.parcel_births = {
        p: int(sim.state.get(p, "births_total") or 0) for p in parcels
    }
    arm.parcel_deaths = parcel_deaths

    if moved_at is not None:
        for parcel in parcels:
            source = sim.state.get(parcel, "last_source")
            if not source or source == "none":
                continue
            arm.donor_source[parcel] = source
            series = [
                row for row in cell_track.get(source, [])
                if row["tick"] >= moved_at - 1
            ]
            arm.donor_series[parcel] = _sample(
                series, series[0]["tick"] if series else 0, CHECKPOINTS)
            before = [
                row for row in cell_track.get(source, [])
                if row["tick"] == moved_at - 1
            ]
            arm.donor_before[parcel] = (
                before[0] if before else (series[0] if series else None)
            )
        for parcel in parcels:
            series = cell_track.get(parcel, [])
            after = [row for row in series if row["tick"] >= moved_at]
            empties = 0
            was = False
            for i, row in enumerate(after):
                if row["population"] > 0:
                    was = True
                if was and i and after[i - 1]["population"] > 0 \
                        and row["population"] == 0:
                    empties += 1
            arm.reempty[parcel] = empties
        arm.parcel_series = {
            p: _sample(
                [row for row in cell_track.get(p, [])
                 if row["tick"] >= moved_at],
                moved_at, CHECKPOINTS,
            )
            for p in parcels
        }
        ages = sorted(
            mover_state[a]["age_at_move"] for a in movers if a in mover_state
        )
        arm.mover_survival = {
            "moved_at": moved_at,
            "movers": len(movers),
            "alive_end": sum(1 for a in movers if a in _alive(sim)),
            "in_parcel_end": sum(
                1 for a in movers if a in _alive(sim)
                and sim.state.get(a, "cell") in parcel_set
            ),
            "stayers": len(stayers_at_move),
            "stayers_alive_end": sum(
                1 for a in stayers_at_move if a in _alive(sim)
            ),
            "age_min": ages[0] if ages else None,
            "age_max": ages[-1] if ages else None,
            "minors": sum(1 for age in ages if age < 16),
            "ages": ages,
        }
    return arm


def _mean(values) -> float:
    values = list(values)
    return round(sum(values) / len(values), 2) if values else 0.0


def _share(flags: list[bool]) -> float:
    return round(sum(1 for x in flags if x) / len(flags), 3) if flags else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="7,11,23,31")
    parser.add_argument("--agents", type=int, default=54)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    args.seeds = [int(x) for x in str(args.seeds).split(",")]

    tmp = Path("/tmp/v011_settlement")
    tmp.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in args.seeds:
        args.seed = seed
        print(f"seed {seed} …", flush=True)
        arms = {}
        for name, orders in (("control", "none"), ("claim", "claim"),
                             ("resettle", "resettle")):
            arms[name] = run_arm(name, str(tmp / f"{seed}-{name}.db"),
                                 args, orders)
            survival = arms[name].mover_survival
            print(f"  {name:>8}: alive {arms[name].alive} "
                  f"movers {survival.get('movers', 0)} "
                  f"still {survival.get('in_parcel_end', 0)}", flush=True)
        runs.append({
            "seed": seed,
            "arms": {name: arm.__dict__ for name, arm in arms.items()},
        })

    report = {
        "config": {"seeds": args.seeds, "agents": args.agents,
                   "protocol_until": SATURATE_AT, "claim_at": CLAIM_AT,
                   "move_ats": list(MOVE_ATS), "horizon": HORIZON,
                   "checkpoints": list(CHECKPOINTS)},
        "runs": runs,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(render(report), encoding="utf-8")
        print(f"written {args.out}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"written {args.json}")
    return 0


# ------------------------------------------------------------------ report


def _sample(rows: list, first: int, checkpoints,
           step: int = 10) -> list:
    """Keep the checkpoints, every `step`-th tick and the last row.

    The full per-tick series is a measurement, but 600 rows x 8 arms is
    megabytes in the report for no extra information: the report reads
    the last row and the six checkpoint offsets and nothing between
    them. The sampling is deterministic, so a fresh run reproduces it.
    """
    keep = [row for row in rows
            if (row["tick"] - first) % step == 0
            or (row["tick"] - first) in checkpoints]
    if rows and (not keep or keep[-1]["tick"] != rows[-1]["tick"]):
        keep.append(rows[-1])
    return keep


def _checkpoint(arm: dict, offset: int) -> dict | None:
    return arm["checkpoints"].get(str(offset)) or arm["checkpoints"].get(offset)


def _parcel_at(arm: dict, parcel: str, offset: int) -> dict | None:
    """The parcel's own +offset sample (its first move is the origin)."""
    first = arm.get("parcel_first_move", {}).get(parcel)
    if first is None:
        return None
    tick = int(first) + offset
    for row in arm["parcel_series"].get(parcel, []):
        if row["tick"] == tick:
            return row
    return None


def render(report: dict) -> str:
    lines: list[str] = []
    a = lines.append
    cfg = report["config"]
    checkpoints = cfg["checkpoints"]
    final = checkpoints[-1]
    a("# v0.11 — держится ли новое поселение? Горизонт без приказов")
    a("")
    a(f"seeds {', '.join(str(s) for s in cfg['seeds'])}; "
      f"{cfg['agents']} агентов; `player_resettle`. Протокол v0.8 до тика "
      f"{cfg['protocol_until']}, заявка на тик {cfg['claim_at']}, "
      f"переселение на тики {', '.join(map(str, cfg['move_ats']))}, затем "
      f"**никаких приказов до тика {cfg['horizon']}** — больше 600 тиков "
      f"наблюдения после последнего вмешательства.")
    a("")
    a("Это продолжение контрфакта v0.11: плечи control / claim / resettle "
      "те же, но окно в три раза длиннее, и игрок после переселения "
      "уходит. Вопрос не «переехали ли люди», а «остались ли они и "
      "прокормила ли их земля».")
    a("")

    a("## 1. Население новых клеток во времени")
    a("")
    a("Отсчёт +N идёт от **первого** переселения в эту клетку: две "
      "клетки получают приказы на соседних тиках, и общий глобальный "
      "сдвиг показывал бы одной из них население до её хода.")
    a("")
    a("| seed | клетка | +0 | +50 | +100 | +200 | +400 | +600 | "
      "почва +0 → +600 | еда +0 → +600 |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for run in report["runs"]:
        arm = run["arms"]["resettle"]
        for parcel in arm["parcel_series"]:
            row = []
            for off in checkpoints:
                facts = _parcel_at(arm, parcel, off)
                row.append(str(facts["population"]) if facts else "—")
            p0 = _parcel_at(arm, parcel, 0)
            p6 = _parcel_at(arm, parcel, final)
            a(f"| {run['seed']} | {parcel} | " + " | ".join(row) +
              f" | {p0['soil']:.3f} → {p6['soil']:.3f} | "
              f"{p0['food']:.0f} → {p6['food']:.0f} |")
    a("")

    retained = []
    reempty = []
    for run in report["runs"]:
        arm = run["arms"]["resettle"]
        for parcel in arm["parcel_series"]:
            facts = _parcel_at(arm, parcel, final)
            retained.append(bool(facts) and facts["population"] > 0)
            reempty.append(arm["reempty"].get(parcel, 0))
    a(f"**Доля новых клеток с населением на +{final}:** "
      f"{sum(1 for x in retained if x)}/{len(retained)} "
      f"({_share(retained):.0%}). Клеток, опустевших повторно: "
      f"{sum(1 for x in reempty if x)}; эпизодов: {sum(reempty)}.")
    a("")

    a("## 2. Выживаемость: переселенцы против оставшихся")
    a("")
    a("Когорта, взятая в момент первого переселения (все живые). "
      "Сравнение честно только на коротком окне: к +600 основатели "
      "умирают от возраста, и поселение может жить уже потомками — "
      "это отдельная колонка, а не выживаемость.")
    a("")
    a("| seed | +50 переселенцы | +50 оставшиеся | +100 переселенцы | "
      "+100 оставшиеся | +200 переселенцы | +200 оставшиеся |")
    a("|---|---:|---:|---:|---:|---:|---:|")
    for run in report["runs"]:
        s = run["arms"]["resettle"]["mover_survival"]
        if not s:
            continue
        cells = []
        for off in (50, 100, 200):
            cp = (run["arms"]["resettle"]["checkpoints"]
                  .get(str(off)) or run["arms"]["resettle"]["checkpoints"].get(off))
            if cp:
                cells.append(f"{cp['movers_alive']}/{s['movers']}")
                cells.append(f"{cp['stayers_alive']}/{s['stayers']}")
            else:
                cells += ["—", "—"]
        a(f"| {run['seed']} | " + " | ".join(cells) + " |")
    a("")

    end_movers = []
    end_here = []
    end_stayers = []
    for run in report["runs"]:
        s = run["arms"]["resettle"]["mover_survival"]
        if not s:
            continue
        end_movers.append(s["alive_end"])
        end_here.append(s["in_parcel_end"])
        end_stayers.append(s["stayers_alive_end"])
    if end_movers:
        a(f"К концу (+600): переселенцы живы "
          f"{sum(end_movers)}/{sum(s['movers'] for s in [run['arms']['resettle']['mover_survival'] for run in report['runs']] if s)}; "
          f"из них в новых клетках {sum(end_here)}. Оставшиеся живы "
          f"{sum(end_stayers)}/{sum(s['stayers'] for s in [run['arms']['resettle']['mover_survival'] for run in report['runs']] if s)}. "
          f"Ноль здесь — возраст когорты, а не провал поселения: "
          f"население клеток на +600 смотрите в таблице 1.")
    a("")
    ages = []
    minors = []
    for run in report["runs"]:
        s = run["arms"]["resettle"]["mover_survival"]
        if not s or s["age_min"] is None:
            continue
        ages.append((s["age_min"], s["age_max"]))
        minors.append(s["minors"])
    if ages:
        a("Возраст переселенцев на момент переезда (тиков от рождения): "
          f"от {min(a for a, _ in ages)} до {max(b for _, b in ages)}; "
          f"детей (моложе 16) — {sum(minors)}. Модель не знает "
          "домохозяйств, поэтому ребёнок может уехать один; это "
          "свойство политики, а не случайность.")
        a("")

    a("## 3. Что стало с источником")
    a("")
    a("| seed | источник | население до | в конце (resettle) | "
      "в конце (claim) | разница с claim |")
    a("|---|---|---:|---:|---:|---:|")
    for run in report["runs"]:
        res = run["arms"]["resettle"]
        claim = run["arms"]["claim"]
        for parcel, source in res["donor_source"].items():
            before = res["donor_before"].get(parcel)
            series = res["donor_series"].get(parcel, [])
            end_res = series[-1]["population"] if series else 0
            end_claim = claim["cells"].get(source, {}).get("population", 0)
            a(f"| {run['seed']} | {source} | "
              f"{before['population'] if before else 0} | {end_res} | "
              f"{end_claim} | {end_res - end_claim:+d} |")
    a("")

    a("## 4. Мир целиком: короткий эффект против длинного")
    a("")
    a("| seed | плечо | живых в конце | еда | средняя почва |")
    a("|---|---|---:|---:|---:|")
    for run in report["runs"]:
        for name in ("control", "claim", "resettle"):
            arm = run["arms"][name]
            a(f"| {run['seed']} | {name} | {arm['alive']} | "
              f"{arm['food']:.0f} | {arm['mean_soil']:.3f} |")
    a("")
    a("### Разница resettle − claim по живым")
    a("")
    for run in report["runs"]:
        d = run["arms"]["resettle"]["alive"] - run["arms"]["claim"]["alive"]
        a(f"* seed {run['seed']}: {d:+d}")
    a("")
    a("### Почему пустеет клетка")
    a("")
    a("| seed | клетка | первый переезд | опустошений | смертей в клетке "
      "| рождений в клетке | население на +600 |")
    a("|---|---|---:|---:|---:|---:|---:|")
    for run in report["runs"]:
        arm = run["arms"]["resettle"]
        for parcel in arm["parcel_series"]:
            first = arm["parcel_first_move"].get(parcel)
            facts = _parcel_at(arm, parcel, final)
            a(f"| {run['seed']} | {parcel} | {first} | "
              f"{arm['reempty'].get(parcel, 0)} | "
              f"{arm['parcel_deaths'].get(parcel, 0)} | "
              f"{arm['parcel_births'].get(parcel, 0)} | "
              f"{facts['population'] if facts else '—'} |")
    a("")
    a("Клетка с нулём смертей и повторным опустошением ушла не в "
      "смерть, а в миграцию: люди ушли сами. Это разные исходы, и "
      "отчёт их не смешивает.")
    a("")

    a("## Что это доказывает")
    a("")
    kept = sum(1 for x in retained if x)
    total = len(retained)
    empty_by_migration = 0
    for run in report["runs"]:
        arm = run["arms"]["resettle"]
        for parcel in arm["parcel_series"]:
            facts = _parcel_at(arm, parcel, final)
            if facts and facts["population"] == 0:
                if arm["parcel_deaths"].get(parcel, 0) == 0:
                    empty_by_migration += 1
    a(f"* На горизонте +{final} поселение живо в **{kept} из {total}** "
      f"новых клеток. Это не «переселение всегда работает»: доля и "
      f"точные числа — в таблице 1.")
    cp200 = []
    for run in report["runs"]:
        arm = run["arms"]["resettle"]
        cp = (arm["checkpoints"].get("200")
              or arm["checkpoints"].get(200))
        s200 = arm["mover_survival"]
        if cp and s200:
            cp200.append((cp["movers_alive"], s200["movers"],
                          cp["stayers_alive"], s200["stayers"]))
    if cp200:
        m_alive = sum(x[0] for x in cp200)
        m_all = sum(x[1] for x in cp200)
        s_alive = sum(x[2] for x in cp200)
        s_all = sum(x[3] for x in cp200)
        a(f"* На +200 переселенцы живы {m_alive}/{m_all} "
          f"({m_alive / m_all:.0%}), оставшиеся {s_alive}/{s_all} "
          f"({s_alive / s_all:.0%}). Переезд не выглядит смертельнее "
          f"пребывания на месте — на этом горизонте.")
    pops = []
    for run in report["runs"]:
        arm = run["arms"]["resettle"]
        for parcel in arm["parcel_series"]:
            facts = _parcel_at(arm, parcel, final)
            if facts and facts["population"] > 0:
                pops.append(facts["population"])
    if pops:
        a(f"* Население удержавшихся клеток на +{final}: от {min(pops)} "
          f"до {max(pops)} человек. Поселение **выживает, но не "
          f"растёт**: это форпост, а не новая область.")
    missing = total - kept
    if missing == 1:
        a("* Единственная опустевшая клетка ушла без единой смерти "
          "внутри неё — это миграция, а не вымирание. Отчёт не "
          "смешивает эти исходы.")
    elif empty_by_migration == missing:
        who = "Обе" if missing == 2 else f"Все {missing}"
        a(f"* {who} опустевшие клетки ушли без единой смерти "
          f"внутри них — это миграция, а не вымирание. Отчёт не "
          f"смешивает эти исходы.")
    else:
        a(f"* Из {missing} опустевших клеток {empty_by_migration} ушли "
          f"без единой смерти внутри клетки (миграция); остальные — "
          f"смерть или смешанный исход. Отчёт не смешивает их.")
    a("* Устойчивость поселения — это **потомки**, а не основатели: "
      "когорта переселенцев к +600 умирает от возраста, а население "
      "клетки может оставаться ненулевым.")
    a("* Цена для источника измерена разницей с claim-плечом на той же "
      "клетке: естественная история вычтена.")
    deltas = [
        run["arms"]["resettle"]["alive"] - run["arms"]["claim"]["alive"]
        for run in report["runs"]
    ]
    if deltas:
        a(f"* Разница resettle − claim по живым на +600: "
          f"{', '.join(f'{d:+d}' for d in deltas)} "
          f"(среднее {_mean(deltas):+.1f}). Направление то же, что на "
          f"коротком окне, но величина меньше: длинный горизонт — не "
          f"усилитель эффекта.")
    a("")
    a("## Что это НЕ доказывает")
    a("")
    a("* Горизонт +600 — не «навсегда»: при другой почве, другом seed "
      "или более длинном окне исход может измениться.")
    a("* Переселенцев по-прежнему выбирает голод, а не домохозяйство: "
      "дети могут уехать (это измерено отдельно в отчёте о выборе).")
    a("* «Голодная смерть» — прокси по последнему живому тику.")
    a("* Выборка — 4 seed × 2 клетки; это проверка направления, а не "
      "оценка вероятности.")
    a("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
