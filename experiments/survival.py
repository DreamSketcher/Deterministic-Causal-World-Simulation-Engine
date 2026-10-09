"""Causal survival experiment (v0.2).

Scale the frozen v0.1 kernel — NOT the world model: no new systems, no new
laws — and compare two kinds of explanation:

    statistical regularity   (correlations over the population)
        VS
    individual causality     (mechanical death traces per agent)

Every agent tries to stay alive under the MVP behaviour laws (eat,
metabolize, flee famine according to risk_tolerance). Per agent the
experiment derives, ENTIRELY from the persisted journal:

    agent_id, birth_tick, death_tick, lifespan, death_transition
    initial attributes, migrations, infections,
    exact per-tick food access and social density (from recorded reads)

Then it reports:

* lifespan distribution + percentile table;
* Pearson/Spearman correlations of observables vs lifespan;
* for every dead agent: causal trace of the death transition, classified
  into mechanisms (acute infection / epidemic disease / starvation);
* side-by-side: does a correlation's sign hold INSIDE each causal
  mechanism group, or does one observable hide different mechanisms?

Run:

    python3 experiments/survival.py --seed 7 --regions 10 --agents 1000 \
        --ticks 10000 --db runs/survival_seed7.db \
        --report experiments/reports/survival_seed7.md

Re-analyze an existing archive without re-running the simulation:

    python3 experiments/survival.py --analyze --ticks 10000 \
        --db runs/survival_seed7.db --report out.md

Everything is deterministic: same seed -> same world -> same report.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from causal_world import create_world  # noqa: E402
from causal_world.causal.trace import (  # noqa: E402
    TraceNode,
    format_trace,
    trace_back,
)
from causal_world.simulation.archive import SqliteArchive  # noqa: E402

STARVATION_THRESHOLD = 0.75


@dataclass
class AgentSurvivalRecord:
    agent: str
    birth_tick: int = 0
    death_tick: int | None = None
    death_transition: int | None = None
    lifespan: int = 0
    initial_health: float = 0.0
    initial_immunity: float = 0.0
    initial_risk: float = 0.0
    initial_region: str = ""
    migrations: int = 0
    infections: int = 0
    avg_food_access: float = 0.0
    avg_density: float = 0.0
    alive_at_end: bool = True
    mechanism: str = ""


# ----------------------------------------------------------------------
# Record collection — derived post hoc from the journal alone
# ----------------------------------------------------------------------

def collect_records(journal, total_ticks: int) -> list[AgentSurvivalRecord]:
    """Build per-agent survival records purely from recorded transitions.

    Initial attributes come from genesis writes; life aggregates from
    committed operation transitions; food access / density come from the
    recorded READS of agent.metabolism (exact per-tick values, not samples).
    """
    records: dict[str, AgentSurvivalRecord] = {}
    food_sum: dict[str, float] = {}
    density_sum: dict[str, float] = {}
    samples: dict[str, int] = {}

    for t in journal.iter_operations({"genesis.agent"}):
        agent = t.writes[0].entity
        fields = {w.field: w.new for w in t.writes}
        records[agent] = AgentSurvivalRecord(
            agent=agent,
            initial_health=float(fields["health"]),
            initial_immunity=float(fields["immunity"]),
            initial_risk=float(fields["risk_tolerance"]),
            initial_region=str(fields["region"]),
        )

    for t in journal.iter_operations({"agent.migrate"}):
        for w in t.writes:
            if w.field == "region" and w.entity in records:
                records[w.entity].migrations += 1

    for t in journal.iter_operations({"disease.infect"}):
        agent = t.writes[0].entity
        if agent in records:
            records[agent].infections += 1
            for w in t.writes:  # lethal infections write alive -> false
                if w.field == "alive" and w.old is True and w.new is False:
                    rec = records[agent]
                    if rec.death_tick is None:
                        rec.death_tick = t.tick
                        rec.death_transition = t.id

    for t in journal.iter_operations({"agent.death"}):
        agent = t.writes[0].entity
        if agent in records:
            rec = records[agent]
            if rec.death_tick is None:
                rec.death_tick = t.tick
                rec.death_transition = t.id

    # Food access / density: exact per-tick values from the recorded reads
    # of agent.metabolism. SQL-side aggregation keeps this O(1) in RAM and
    # fast even for millions of metabolism transitions.
    if hasattr(journal, "query"):
        rows = journal.query(
            """
            SELECT agent,
                   AVG(food / pop) AS avg_food,
                   AVG(pop)        AS avg_density,
                   COUNT(*)        AS n
            FROM (
                SELECT t.id AS tid,
                       json_extract(t.payload, '$.writes[0][0]') AS agent,
                       MAX(CASE WHEN json_extract(re.value, '$[1]') = 'food_stock'
                                THEN json_extract(re.value, '$[2]') END) AS food,
                       MAX(CASE WHEN json_extract(re.value, '$[1]') = 'population'
                                THEN MAX(json_extract(re.value, '$[2]'), 1) END) AS pop
                FROM transitions AS t,
                     json_each(json_extract(t.payload, '$.reads')) AS re
                WHERE t.operation = 'agent.metabolism'
                  AND t.status = 'COMMITTED'
                GROUP BY t.id
            )
            GROUP BY agent
            """
        )
        for row in rows:
            agent = row["agent"]
            if agent in records:
                food_sum[agent] = float(row["avg_food"]) * int(row["n"])
                density_sum[agent] = float(row["avg_density"]) * int(row["n"])
                samples[agent] = int(row["n"])
    else:  # in-memory journals: plain python path
        for t in journal.iter_operations({"agent.metabolism"}):
            agent = t.writes[0].entity
            if agent not in records:
                continue
            food = population = None
            for r in t.reads:
                if r.field == "food_stock":
                    food = float(r.value)
                elif r.field == "population":
                    population = max(int(r.value), 1)
            if food is not None and population is not None:
                food_sum[agent] = food_sum.get(agent, 0.0) + food / population
                density_sum[agent] = density_sum.get(agent, 0.0) + float(population)
                samples[agent] = samples.get(agent, 0) + 1

    out: list[AgentSurvivalRecord] = []
    for agent in sorted(records):
        rec = records[agent]
        n = samples.get(agent, 0)
        if n:
            rec.avg_food_access = food_sum[agent] / n
            rec.avg_density = density_sum[agent] / n
        rec.alive_at_end = rec.death_tick is None
        rec.lifespan = rec.death_tick if rec.death_tick is not None else total_ticks
        out.append(rec)
    return out


# ----------------------------------------------------------------------
# Pure-python statistics
# ----------------------------------------------------------------------

def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if vx == 0 or vy == 0:
        return float("nan")
    return cov / (vx * vy)


def _ranks(values: list[float]) -> list[float]:
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and values[indexed[j + 1]] == values[indexed[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    return pearson(_ranks(xs), _ranks(ys))


# ----------------------------------------------------------------------
# Causal classification of deaths
# ----------------------------------------------------------------------

class DeathClassifier:
    """Backward-DAG reachability over the DECEASED'S OWN causal chain.

    Two mechanical per-death properties:

    * disease-reach:  some ``disease.infect`` transition is an ancestor
      reached through the agent's own fields;
    * starvation-reach: some ancestor transition reads THIS agent's
      hunger >= threshold.

    Restricting the walk to reads of the agent's own entity is complete
    for both questions — an agent's fields are only ever written by
    transitions reading that same agent — and it keeps each classification
    narrow and unambiguous: "starvation" means the deceased was starving,
    not that someone upstream in the epidemic network was. The causal
    graph is acyclic, so the depth-bounded DFS is exact.
    """

    def __init__(self, archive) -> None:
        self._archive = archive
        self._node_cache: dict[int, list] = {}

    def _node(self, tid: int) -> list:
        """Parsed read summary: [(field, entity, value, source), ...]."""
        cached = self._node_cache.get(tid)
        if cached is not None:
            return cached
        import json

        rows = self._archive.query(
            "SELECT payload FROM transitions WHERE id=?", (tid,)
        )
        if rows:
            payload = json.loads(rows[0]["payload"])
            summary = [
                (r[1], r[0], r[2], r[3]) for r in payload["reads"]
            ]
        else:
            summary = []
        self._node_cache[tid] = summary
        return summary

    def operation_of(self, tid: int) -> str:
        rows = self._archive.query(
            "SELECT operation FROM transitions WHERE id=?", (tid,)
        )
        return rows[0]["operation"] if rows else ""

    def classify(self, rec: AgentSurvivalRecord, depth: int) -> str:
        agent = rec.agent
        tid = rec.death_transition
        acute = self.operation_of(tid) == "disease.infect"

        disease = acute
        starvation = False
        stack: list[tuple[int, int]] = [(tid, 0)]
        seen = {tid}
        while stack and not (disease and starvation):
            current, d = stack.pop()
            if not disease and self.operation_of(current) == "disease.infect":
                disease = True
            for field, entity, value, source in self._node(current):
                if entity != agent:
                    continue  # follow only the deceased's own chain
                if (
                    field == "hunger"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and value >= STARVATION_THRESHOLD
                ):
                    starvation = True
                if source is not None and d < depth and source not in seen:
                    seen.add(source)
                    stack.append((source, d + 1))
        if acute:
            return "acute_infection"
        if disease and starvation:
            return "disease+starvation"
        if disease:
            return "disease"
        if starvation:
            return "starvation"
        return "other"


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def build_report(
    seed: int | None,
    regions: int,
    agents: int,
    ticks: int,
    records: list[AgentSurvivalRecord],
    archive,
    elapsed: float,
    db_path: str,
    trace_depth: int = 10,
    ruleset_version: str = "0.1.0",
    ruleset_name: str = "default",
    description: str | None = None,
) -> str:
    dead = [r for r in records if not r.alive_at_end]
    alive = [r for r in records if r.alive_at_end]
    lines: list[str] = []
    add = lines.append

    add(f"# Causal survival experiment" + (f" — seed {seed}" if seed is not None else ""))
    add("")
    if ruleset_version == "0.1.0":
        add("Frozen **CAUSAL KERNEL v0.1**, ruleset **0.1.0** — no new systems,")
        add("no new laws. Scale, statistics and mechanical death traces only.")
    else:
        add(f"Kernel **v0.1 (frozen)**, ruleset **{ruleset_version}** — the laws")
        add("differ from the baseline by proposal only; the kernel, the purposes")
        add("and the addressable draw stream are unchanged.")
        if description:
            add("")
            add(f"> {description}")
    add("")
    add("## Run")
    add("")
    add("| parameter | value |")
    add("|---|---|")
    add(f"| seed | {seed} |")
    add(f"| ruleset | {ruleset_version} |")
    add(f"| regions | {regions} |")
    add(f"| agents | {agents} |")
    add(f"| ticks | {ticks} |")
    add(f"| wall time | {elapsed:.0f}s |")
    add(f"| archive | `{db_path}` |")
    add(f"| survivors | {len(alive)} / {agents} |")
    add(f"| deaths | {len(dead)} |")
    if dead:
        last_death = max(r.death_tick for r in dead)
        add(f"| last death | tick {last_death} |")
    add("")

    lifespans = [r.lifespan for r in records]
    add("## Lifespan distribution" +
        (" (all agents died: no censoring)" if not alive else " (survivors censored at run end)"))
    add("")
    add("| pct | ticks |")
    add("|---|---|")
    for p in (0, 10, 25, 50, 75, 90, 100):
        add(f"| p{p} | {percentile(lifespans, p):.0f} |")
    add(f"\nmean lifespan: **{mean(lifespans):.0f}** ticks")
    add("")

    add("## Statistical regularity: correlations with lifespan")
    add("")
    add("| observable | pearson | spearman |")
    add("|---|---|---|")
    observables = [
        ("initial_health", [r.initial_health for r in records]),
        ("initial_immunity", [r.initial_immunity for r in records]),
        ("risk_tolerance", [r.initial_risk for r in records]),
        ("migration_count", [float(r.migrations) for r in records]),
        ("infection_count", [float(r.infections) for r in records]),
        ("avg_food_access", [r.avg_food_access for r in records]),
        ("avg_social_density", [r.avg_density for r in records]),
    ]
    for name, values in observables:
        add(
            f"| {name} | {pearson(values, lifespans):+.3f} "
            f"| {spearman(values, lifespans):+.3f} |"
        )
    add("")

    # ---- causal classification -------------------------------------
    classifier = DeathClassifier(archive)
    for rec in dead:
        rec.mechanism = classifier.classify(rec, depth=trace_depth)

    counts: dict[str, int] = {}
    for rec in dead:
        counts[rec.mechanism] = counts.get(rec.mechanism, 0) + 1
    add("## Individual causality: death mechanisms (from traces)")
    add("")
    add("| mechanism | deaths | share |")
    add("|---|---|---|")
    for mech in sorted(counts, key=lambda m: -counts[m]):
        add(f"| {mech} | {counts[mech]} | {counts[mech] / max(len(dead), 1):.1%} |")
    add("")

    add("> **Interpretation caveat.** `migration_count`, `infection_count` and")
    add("> the sampled food/density aggregates are *time-at-risk* variables:")
    add("> agents that die early simply have fewer ticks in which to migrate")
    add("> or meet pathogens. A positive correlation of such a variable with")
    add("> lifespan is therefore expected even when the variable is harmful.")
    add("> The group tables below exist precisely to confront those numbers")
    add("> with per-death causal mechanisms.")
    add("")

    # ---- statistical vs causal --------------------------------------
    add("## Statistical regularity vs individual causality")
    add("")
    mechs_sorted = sorted(counts)

    def group_table(title: str, groups: list[tuple[str, list[AgentSurvivalRecord]]]):
        add(f"### {title}")
        add("")
        add("| group | n | mean lifespan | " + " | ".join(mechs_sorted) + " |")
        add("|---|---|---|" + "---|" * len(mechs_sorted))
        for label, members in groups:
            if not members:
                continue
            ls = [m.lifespan for m in members]
            mech_counts = {m: 0 for m in mechs_sorted}
            for m in members:
                if not m.alive_at_end:
                    mech_counts[m.mechanism] += 1
            row = " | ".join(str(mech_counts[m]) for m in mechs_sorted)
            add(f"| {label} | {len(members)} | {mean(ls):.0f} | {row} |")
        add("")

    migrants = [r for r in records if r.migrations > 0]
    stayers = [r for r in records if r.migrations == 0]
    group_table("Migration — same observable, different mechanisms?",
                [("stayers (0 migrations)", stayers),
                 ("migrants (>=1 migration)", migrants)])

    risks = sorted(records, key=lambda r: r.initial_risk)
    quartiles = []
    for i, label in enumerate(
        ("risk Q1 (lowest)", "risk Q2", "risk Q3", "risk Q4 (highest)")
    ):
        quartiles.append(
            (label, risks[i * len(risks) // 4:(i + 1) * len(risks) // 4])
        )
    group_table("Risk tolerance quartiles", quartiles)

    # ---- example traces ----------------------------------------------
    add("## Example mechanical explanations")
    add("")
    examples: list[tuple[str, AgentSurvivalRecord]] = []
    for wanted in ("starvation", "disease", "acute_infection", "disease+starvation"):
        for rec in dead:
            if rec.mechanism == wanted:
                examples.append((wanted, rec))
                break
    for wanted, rec in examples[:2]:
        add(
            f"### {rec.agent} — {wanted} "
            f"(died tick {rec.death_tick}, T{rec.death_transition})"
        )
        add("")
        add("```")
        add(format_trace(trace_back(archive, rec.death_transition, 3), depth=3,
                         max_inputs=8, max_parents=4))
        add("```")
        add("")

    add("## Reproduction")
    add("")
    ruleset_flag = "" if ruleset_name == "default" else f" --ruleset {ruleset_name}"
    add("```bash")
    if seed is not None:
        add(f"python3 experiments/survival.py --seed {seed} --regions {regions} "
            f"--agents {agents} --ticks {ticks}{ruleset_flag} --db {db_path} --report <path>")
    else:
        add(f"python3 experiments/survival.py --analyze --ticks {ticks} "
            f"--db {db_path} --report <path>")
    add("```")
    add("")
    add(f"Same seed + kernel v0.1.0 + ruleset {ruleset_version} → bit-identical "
        "world, identical traces, identical report.")
    return "\n".join(lines)


# ----------------------------------------------------------------------

def analyze_existing(args) -> int:
    t0 = time.time()
    archive = SqliteArchive(args.db)

    def meta(key: str) -> str | None:
        try:
            return archive.get_meta(key)
        except Exception:
            return None  # archive predates the meta table

    seed_text = meta("seed")
    seed = int(seed_text) if seed_text is not None else None
    regions_text = meta("regions")
    agents_text = meta("agents")
    if regions_text is None or agents_text is None:
        # Scale is derivable from the archive itself (genesis transitions).
        agent_set = set()
        region_set = set()
        for t in archive.iter_operations({"genesis.agent", "genesis.region"}):
            entity = t.writes[0].entity
            (agent_set if entity.startswith("agent:") else region_set).add(entity)
        regions_used, agents_used = len(region_set), len(agent_set)
    else:
        regions_used, agents_used = int(regions_text), int(agents_text)

    records = collect_records(archive, args.ticks)
    ruleset_version = meta("ruleset_version") or "0.1.0"
    ruleset_name = meta("ruleset_name") or ("default" if ruleset_version == "0.1.0" else "immune")
    report = build_report(
        seed, regions_used, agents_used, args.ticks, records, archive,
        time.time() - t0, args.db, trace_depth=args.trace_depth,
        ruleset_version=ruleset_version, ruleset_name=ruleset_name,
        description=meta("ruleset_description"),
    )
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(report)
    archive.close()
    print(f"done in {time.time() - t0:.0f}s; report: {args.report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Causal survival experiment")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--regions", type=int, default=10)
    parser.add_argument("--agents", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=10000)
    parser.add_argument("--db", type=str, required=True)
    parser.add_argument("--report", type=str, required=True)
    parser.add_argument("--trace-depth", type=int, default=10)
    parser.add_argument("--ruleset", type=str, default="default",
                        help="world rules: default | immune")
    parser.add_argument("--analyze", action="store_true",
                        help="re-analyze an existing archive; do not simulate")
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    if args.analyze:
        return analyze_existing(args)

    if os.path.exists(args.db):
        os.remove(args.db)
    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)

    from causal_world.world.rules import get_ruleset

    rules = get_ruleset(args.ruleset)
    t0 = time.time()
    sim = create_world(
        seed=args.seed,
        regions=args.regions,
        agents=args.agents,
        ruleset=rules,
        persist=args.db,
    )
    if getattr(rules, "default_systems", None) is not None:
        print(f"ruleset {rules.ruleset_version}: systems = "
              f"{', '.join(s.name for s in sim.systems)}", flush=True)
    # World identity beyond the version string travels with the archive.
    sim.journal.set_meta("ruleset_name", args.ruleset)
    if getattr(rules, "description", None):
        sim.journal.set_meta("ruleset_description", rules.description)
    for tick in range(1, args.ticks + 1):
        sim.step()
        if tick % 500 == 0:
            alive = sum(
                1 for a in sim.state.entities_with_prefix("agent:")
                if sim.state.get(a, "alive")
            )
            print(f"tick {tick}/{args.ticks} alive={alive} "
                  f"elapsed={time.time() - t0:.0f}s", flush=True)
    sim_time = time.time() - t0
    print(f"simulation done in {sim_time:.0f}s; analyzing…", flush=True)

    records = collect_records(sim.journal, args.ticks)
    seed_used = args.seed
    regions_used = args.regions
    agents_used = args.agents
    report = build_report(
        seed_used, regions_used, agents_used, args.ticks, records, sim.journal,
        time.time() - t0, args.db, trace_depth=args.trace_depth,
        ruleset_version=rules.ruleset_version, ruleset_name=args.ruleset,
        description=getattr(rules, "description", None),
    )
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(report)
    sim.journal.close()
    print(f"done in {time.time() - t0:.0f}s; report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
