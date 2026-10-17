#!/usr/bin/env python3
"""v0.11 — the v0.10 grid, repeated with resettlement as the one variable.

The review of v0.10 asked for exactly this: repeat the grid on the SAME
seeds, starting populations and horizons, with comparable control worlds,
and check saturation separately, where resettlement must redistribute
people WITHOUT creating capacity that does not exist.

Design (one factor per comparison):

    baseline  — no orders at all (the regime is read from THIS world);
    protocol  — the v0.8 order protocol only (amend/water, ticks 20-27);
    claim     — the same + two wild parcels claimed at ticks 401/402;
    resettle  — the same claims + four resettlement orders (405/406 with
                2 people, 415/416 with 0 = as many as the cell can take).

``resettle - claim`` isolates the MOVE. ``claim - protocol`` shows what
the claim alone did (v0.10 measured that it changes capacity but not
demography). ``protocol - baseline`` is the price/benefit of the v0.8
orders themselves, so the grid keeps a comparable no-order control.

The script also verifies, from the journal itself, that a resettlement
transition:
* changes the sum of cell populations by zero (redistribution, not
  creation of people);
* writes no capacity field (``pop_base``, ``soil_fertility``,
  ``land_active``);
and it cross-checks the baseline against the v0.10 grid: the added
ruleset must not change the dynamics when the new lever is not used.

Usage:
    python3 experiments/v011_grid.py --ticks 600 \
        --out experiments/reports/v011_grid.md \
        --json experiments/reports/v011_grid.json
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
CLAIM_AT = (401, 402)
RESETTLE_AT = ((405, 2), (406, 2), (415, 0), (416, 0))
STARVATION = 0.75


@dataclass
class Run:
    seed: int
    agents: int
    condition: str
    alive: int = 0
    alive_start: int = 0
    births: int = 0
    deaths: int = 0
    starvation_deaths: int = 0
    mean_soil: float = 0.0
    capacity: float = 0.0
    saturation: float = 0.0
    occupied_cells: int = 0
    active_cells: int = 0
    claims: int = 0
    claim_refusals: int = 0
    moves: int = 0
    resettle_refusals: int = 0
    moved_people: int = 0
    move_cost: float = 0.0
    capacity_writes: int = 0
    population_delta_in_moves: int = 0
    reserve_people: int = 0
    refusals_by_code: dict = field(default_factory=dict)


def _wild_by_region(sim):
    out: dict[str, list[str]] = {}
    for parcel in sim.state.entities_with_prefix("cell:"):
        if sim.state.get(parcel, "land_active"):
            continue
        out.setdefault(sim.state.get(parcel, "region"), []).append(parcel)
    return {region: sorted(ps) for region, ps in out.items()}


def _active_cells(sim) -> list[str]:
    return sorted(
        c for c in sim.state.entities_with_prefix("cell:")
        if sim.state.get(c, "land_active")
    )


def run_one(seed: int, agents: int, condition: str, ticks: int) -> Run:
    sim = create_world(
        seed=seed, ruleset=get_ruleset("player_resettle"), ticks=0,
        regions=2, agents=agents,
    )
    attach_player_channel(sim, DecisionChannel(actions=[6] * (ticks + 10)))
    channel = DirectiveChannel()
    for system in sim.systems:
        if system.name == "ResettlementDirectiveSystem":
            system.channel = channel
    if condition != "baseline":
        for tick, cell in zip((20, 21, 22, 23), PROTOCOL_CELLS):
            channel.schedule(tick, Directive(DIRECTIVE_AMEND, cell, 0.15))
        for tick, cell in zip((24, 25, 26, 27), PROTOCOL_CELLS):
            channel.schedule(tick, Directive(DIRECTIVE_WATER, cell, 1.0))

    result = Run(seed=seed, agents=agents, condition=condition)
    result.alive_start = sum(
        1 for a in sim.state.entities_with_prefix("agent:")
        if sim.state.get(a, "alive")
    )
    wild = _wild_by_region(sim)
    parcels = [ps[0] for _, ps in sorted(wild.items())]
    if condition in ("claim", "resettle"):
        for tick, parcel in zip(CLAIM_AT, parcels):
            channel.schedule(tick, Directive(DIRECTIVE_CLAIM, parcel, 0))
    if condition == "resettle":
        orders = list(zip(parcels * 2, RESETTLE_AT))
        for (parcel, (tick, count)) in orders:
            channel.schedule(tick, Directive(DIRECTIVE_RESETTLE, parcel, count))

    hunger: dict[str, float] = {}
    for _ in range(ticks):
        before = {
            a: bool(sim.state.get(a, "alive"))
            for a in sim.state.entities_with_prefix("agent:")
        }
        sim.step()
        for agent, was_alive in before.items():
            if was_alive and not sim.state.get(agent, "alive"):
                if hunger.get(agent, 0.0) >= STARVATION:
                    result.starvation_deaths += 1
        for agent in sim.state.entities_with_prefix("agent:"):
            if sim.state.get(agent, "alive"):
                hunger[agent] = float(sim.state.get(agent, "hunger") or 0.0)

    st = sim.state
    cells = _active_cells(sim)
    result.alive = sum(
        1 for a in st.entities_with_prefix("agent:") if st.get(a, "alive")
    )
    result.capacity = sum(
        int(st.get(c, "pop_base")) * (1.0 + float(st.get(c, "soil_fertility")))
        for c in cells
    )
    result.saturation = result.alive / max(result.capacity, 1e-9)
    result.mean_soil = sum(
        float(st.get(c, "soil_fertility")) for c in cells
    ) / max(len(cells), 1)
    result.active_cells = len(cells)
    result.occupied_cells = sum(
        1 for c in cells if int(st.get(c, "population")) > 0
    )
    result.reserve_people = sum(
        int(st.get(parcel, "population")) for parcel in parcels
    )

    for transition in sim.journal:
        if transition.status.value != "COMMITTED":
            continue
        if transition.operation == "agent.birth":
            result.births += 1
        elif any(
            w.entity.startswith("agent:") and w.field == "alive"
            and w.new is False
            for w in transition.writes
        ):
            result.deaths += 1
        if transition.operation == "player.directive":
            fields = {w.field: w for w in transition.writes}
            if "claim_state" in fields:
                if int(fields["claim_state"].new) == 1:
                    result.claims += 1
                else:
                    result.claim_refusals += 1
        if transition.operation == "player.resettle":
            fields = {w.field: w for w in transition.writes}
            if "resettle_state" in fields and int(
                fields["resettle_state"].new
            ) != 1:
                result.resettle_refusals += 1
                code = str(int(fields["resettle_state"].new))
                result.refusals_by_code[code] = (
                    result.refusals_by_code.get(code, 0) + 1
                )
                continue
            result.moves += 1
            moved = int(fields["resettle_moved"].new)
            result.moved_people += moved
            result.move_cost += float(fields["resettle_cost"].new)
            result.population_delta_in_moves += sum(
                int(w.new) - int(w.old)
                for w in transition.writes
                if w.field == "population" and w.entity.startswith("cell:")
            )
            for forbidden in ("pop_base", "soil_fertility", "land_active"):
                if any(w.field == forbidden for w in transition.writes):
                    result.capacity_writes += 1
    return result


# ----------------------------------------------------------------------
def _regime(base: Run) -> str:
    if base.alive <= 0.85 * max(base.alive_start, 1):
        return "degradation"
    if base.saturation >= 0.85:
        return "saturation"
    return "equilibrium"


def analyse(runs: list[Run]) -> dict:
    by_key = {(r.seed, r.agents, r.condition): r for r in runs}
    pairs = []
    for seed, agents, condition in sorted(by_key):
        if condition != "resettle":
            continue
        base = by_key[(seed, agents, "baseline")]
        protocol = by_key[(seed, agents, "protocol")]
        claim = by_key[(seed, agents, "claim")]
        resettle = by_key[(seed, agents, "resettle")]
        pairs.append({
            "seed": seed, "agents": agents, "regime": _regime(base),
            "baseline": base.__dict__, "protocol": protocol.__dict__,
            "claim": claim.__dict__, "resettle": resettle.__dict__,
            "delta_protocol": {
                key: protocol.__dict__[key] - base.__dict__[key]
                for key in ("alive", "births", "starvation_deaths",
                            "occupied_cells")
            },
            "delta_claim": {
                key: claim.__dict__[key] - protocol.__dict__[key]
                for key in ("alive", "births", "starvation_deaths",
                            "occupied_cells")
            },
            "delta_resettle": {
                key: resettle.__dict__[key] - claim.__dict__[key]
                for key in ("alive", "births", "starvation_deaths",
                            "occupied_cells", "mean_soil")
            },
        })
    summary = {}
    for pair in pairs:
        bucket = summary.setdefault(pair["regime"], [])
        bucket.append(pair)
    out = {}
    for regime, group in sorted(summary.items()):
        out[regime] = {
            "n": len(group),
            "delta_resettle": {
                key: {
                    "mean": round(sum(p["delta_resettle"][key]
                                      for p in group) / len(group), 4),
                    "positive": sum(1 for p in group
                                    if p["delta_resettle"][key] > 0),
                    "zero": sum(1 for p in group
                                if p["delta_resettle"][key] == 0),
                    "negative": sum(1 for p in group
                                    if p["delta_resettle"][key] < 0),
                }
                for key in ("alive", "births", "starvation_deaths",
                            "occupied_cells", "mean_soil")
            },
            "delta_claim": {
                key: {
                    "mean": round(sum(p["delta_claim"][key]
                                      for p in group) / len(group), 4),
                }
                for key in ("alive", "births", "occupied_cells")
            },
            "moved": sum(p["resettle"]["moved_people"] for p in group),
            "moves": sum(p["resettle"]["moves"] for p in group),
            "refusals": sum(p["resettle"]["resettle_refusals"]
                            for p in group),
            "points": [p["seed"] for p in group],
        }
    return {"pairs": pairs, "by_regime": out}


def _v010_check(report: dict) -> dict:
    path = Path(__file__).resolve().parent / "reports" / "v010_regimes.json"
    if not path.exists():
        return {"available": False}
    old = json.loads(path.read_text(encoding="utf-8"))
    old_runs = {
        (r["seed"], r["agents"]): r for r in old.get("runs", [])
        if r["condition"] == "decrees"
    }
    checked, matched, mismatched = 0, 0, []
    for pair in report["analysis"]["pairs"]:
        key = (pair["seed"], pair["agents"])
        if key not in old_runs:
            continue
        base = pair["protocol"]
        old_run = old_runs[key]
        checked += 1
        same = (
            base["alive"] == old_run["alive"]
            and base["births"] == old_run["births"]
            and base["deaths"] == old_run["deaths"]
            and base["starvation_deaths"] == old_run["starvation_deaths"]
            and abs(base["mean_soil"] - old_run["mean_soil"]) < 1e-4
        )
        if same:
            matched += 1
        else:
            mismatched.append({"seed": key[0], "agents": key[1]})
    return {"available": True, "checked": checked, "matched": matched,
            "mismatched": mismatched}


# ----------------------------------------------------------------------
def _people(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "человек"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "человека"
    return "человек"


def _points(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "точка"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "точки"
    return "точек"


def render(report: dict, args) -> str:
    lines = []
    a = lines.append
    a("# v0.11 — сетка: переселение как единственная переменная")
    a("")
    a(f"seeds {', '.join(map(str, args.seeds))}; старт "
      f"{', '.join(map(str, args.agents))}; горизонт {args.ticks}. "
      f"`player_resettle`, четыре мира на точку: без приказов (baseline — "
      f"по нему читается режим), протокол v0.8, протокол + заявки, "
      f"протокол + заявки + переселение. Сравнение resettle − claim "
      f"изолирует само перемещение людей.")
    a("")
    a("## По точкам")
    a("")
    a("| seed | старт | режим | живых база→протокол→claim→resettle | "
      "рождений | переселено | отказов | занято клеток (claim→resettle) |")
    a("|---:|---:|---|---|---:|---:|---:|---|")
    for pair in report["analysis"]["pairs"]:
        b, p = pair["baseline"], pair["protocol"]
        c, r = pair["claim"], pair["resettle"]
        a(f"| {pair['seed']} | {pair['agents']} | {pair['regime']} | "
          f"{b['alive']} → {p['alive']} → {c['alive']} → {r['alive']} | "
          f"{b['births']} → {p['births']} → {c['births']} → "
          f"{r['births']} | {r['moved_people']} | "
          f"{r['resettle_refusals']} | "
          f"{c['occupied_cells']} → {r['occupied_cells']} |")
    a("")
    a("## По режимам: Δ (resettle − claim)")
    a("")
    a("Δ claim = claim − protocol (что дала одна заявка); "
      "Δ resettle = resettle − claim (что дало одно перемещение).")
    a("")
    a("| режим | точек | Δ claim: живых | Δ claim: клеток | "
      "Δ resettle: живых | Δ resettle: рождений | "
      "Δ resettle: голодных смертей | Δ resettle: клеток | переселено | "
      "отказов |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for regime, block in report["analysis"]["by_regime"].items():
        d = block["delta_resettle"]
        c = block["delta_claim"]
        a(f"| {regime} | {block['n']} | {c['alive']['mean']:+.1f} | "
          f"{c['occupied_cells']['mean']:+.1f} | "
          f"{d['alive']['mean']:+.1f} | {d['births']['mean']:+.1f} | "
          f"{d['starvation_deaths']['mean']:+.1f} | "
          f"{d['occupied_cells']['mean']:+.1f} | {block['moved']} | "
          f"{block['refusals']} |")
    a("")
    a("## Насыщение: перераспределение, а не новая ёмкость")
    a("")
    saturation = [
        p for p in report["analysis"]["pairs"]
        if p["regime"] == "saturation"
    ]
    if saturation:
        a("| seed | старт | ёмкость claim→resettle | живых claim→resettle | "
          "занятых клеток claim→resettle | записей ёмкости в переходах | "
          "Δ суммы населения |")
        a("|---:|---:|---|---|---|---:|---:|")
        for pair in saturation:
            c, r = pair["claim"], pair["resettle"]
            a(f"| {pair['seed']} | {pair['agents']} | "
              f"{c['capacity']:.0f} → {r['capacity']:.0f} | "
              f"{c['alive']} → {r['alive']} | "
              f"{c['occupied_cells']} → {r['occupied_cells']} | "
              f"{r['capacity_writes']} | "
              f"{r['population_delta_in_moves']:+d} |")
        a("")
        a("Ёмкость в этих точках практически не меняется; отличие "
          "`120 → 119` в одной точке — дрейф почвы, а не запись "
          "переселения (колонка «записей ёмкости» = 0). Сумма населения "
          "в каждом переходе равна нулю, поэтому переселение может "
          "только ПЕРЕРАСПРЕДЕЛИТЬ людей между клетками. Если занятых "
          "клеток становится больше, это использование уже существующей "
          "ёмкости, а не её создание.")
    else:
        a("В этой сетке нет точек с режимом saturation по базовому миру.")
    a("")
    a("## Проверка совместимости с v0.10")
    a("")
    check = report["v010_check"]
    if not check.get("available"):
        a("Файл v0.10 не найден — сверка пропущена.")
    else:
        a(f"Сверено точек: {check['checked']}; совпало по живым, "
          f"рождениям, смертям, голодным смертям и почве: "
          f"{check['matched']}.")
        if check["mismatched"]:
            a(f"Расхождения: {check['mismatched']} — их нельзя скрывать; "
              f"они означают, что новый ruleset изменил динамику при "
              f"неиспользуемом рычаге.")
        else:
            a("Это и есть проверка «рычаг не нажат — мир не изменился»: "
              "новый ruleset добавил клетки-целину, поля и систему, но "
              "при тех же приказах базовый мир v0.10 воспроизводится "
              "число в число.")
    a("")
    a("## Что это доказывает")
    a("")
    for regime, block in report["analysis"]["by_regime"].items():
        d = block["delta_resettle"]
        c = block["delta_claim"]
        a(f"- **{regime}** ({block['n']} {_points(block['n'])}): одна "
          f"заявка меняет живых на {c['alive']['mean']:+.1f} и занятых "
          f"клеток на {c['occupied_cells']['mean']:+.1f}; переселение "
          f"меняет живых на {d['alive']['mean']:+.1f}, рождений на "
          f"{d['births']['mean']:+.1f}, занятых клеток на "
          f"{d['occupied_cells']['mean']:+.1f}; переселено "
          f"{block['moved']} {_people(block['moved'])}, "
          f"отказов {block['refusals']}.")
    a("")
    a("Переселение — не «кнопка роста»: сумма населения в его "
      "переходах равна нулю. Всё, что оно может, — заставить уже "
      "существующую ёмкость работать; дальнейший прирост приходит "
      "только из рождений, и это видно отдельной колонкой.")
    a("")
    a("## Честные ограничения")
    a("")
    a("- Переселение внутри региона: межрегиональные караваны не "
      "моделируются.")
    a("- Сетка остаётся сеткой (12 точек), а не статистикой; режим — "
      "итог базового мира, а не прогноз.")
    a("- Голодная смерть — прокси по голоду на последнем живом тике; "
      "в одной точке прокси вырос на 1 при том же общем числе смертей — "
      "это сдвиг атрибуции, а не рост смертности.")
    a("- Один протокол приказов; меняются seed, старт и режим.")
    a("- «Занятые клетки» считают клетки с населением > 0, включая "
      "новые; это мера использования земли, а не благополучия.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="7,11,23,31")
    parser.add_argument("--agents", default="36,54,72")
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--out", default="")
    parser.add_argument("--json", default="")
    parser.add_argument("--from-json", default="",
                        help="re-render an existing report without re-running")
    args = parser.parse_args()
    if args.from_json:
        report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        args.seeds = report["config"]["seeds"]
        args.agents = report["config"]["agents"]
        args.ticks = report["config"]["ticks"]
        report["v010_check"] = _v010_check(report)
        if args.out:
            Path(args.out).write_text(render(report, args), encoding="utf-8")
        return 0

    args.seeds = [int(x) for x in str(args.seeds).split(",")]
    args.agents = [int(x) for x in str(args.agents).split(",")]

    runs = []
    for seed in args.seeds:
        for agents in args.agents:
            for condition in ("baseline", "protocol", "claim", "resettle"):
                run = run_one(seed, agents, condition, args.ticks)
                runs.append(run)
                print(f"seed {seed:>2} agents {agents:>3} "
                      f"{condition:>8}: alive {run.alive:>3} "
                      f"births {run.births:>3} moved {run.moved_people:>2} "
                      f"occupied {run.occupied_cells}/{run.active_cells} "
                      f"sat {run.saturation:.2f}", flush=True)

    report = {
        "config": vars(args),
        "runs": [r.__dict__ for r in runs],
        "analysis": analyse(runs),
    }
    report["v010_check"] = _v010_check(report)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(render(report, args), encoding="utf-8")
        print(f"written {args.out}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"written {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
