"""Command-line interface (spec §48).

    python -m causal_world run --seed 42 --ticks 100
    python -m causal_world trace --seed 42 --ticks 100 --transition 902
"""

from __future__ import annotations

import argparse
import json
import sys

from causal_world.causal.trace import format_trace, format_transition, trace_back
from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.statistics import compute_statistics, format_statistics
from causal_world.simulation.engine import create_world
from causal_world.world.rules import get_ruleset


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="causal_world",
        description="Deterministic Causal World Simulation Engine",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_world_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--ticks", type=int, default=100)
        p.add_argument("--regions", type=int, default=2)
        p.add_argument("--agents", type=int, default=10)
        p.add_argument("--ruleset", type=str, default="default",
                       help="world rules: default | immune")
        p.add_argument("--persist", type=str, default=None,
                       help="SQLite archive path for the journal + causal index")

    run_p = sub.add_parser("run", help="run a world and print the summary")
    add_world_args(run_p)
    run_p.add_argument("--stats", action="store_true", help="print statistics block")

    trace_p = sub.add_parser("trace", help="run a world and trace one transition")
    add_world_args(trace_p)
    trace_p.add_argument("--transition", type=int, required=True)
    trace_p.add_argument("--depth", type=int, default=4)

    observe_p = sub.add_parser(
        "observe", help="read-only observer over a recorded archive")
    observe_p.add_argument("--db", type=str, required=True,
                           help="path to a SqliteArchive produced by --persist")
    observe_p.add_argument("--budget", nargs=2, metavar=("ENTITY", "FIELD"),
                           help="print the causal budget of one (entity, field)")
    observe_p.add_argument("--tick-start", type=int, default=0)
    observe_p.add_argument("--tick-end", type=float, default=float("inf"))
    observe_p.add_argument("--classify", action="store_true",
                           help="classify the regime (collapse/equilibrium/...)")
    observe_p.add_argument("--sample-every", type=int, default=1)
    observe_p.add_argument("--explain-death", type=str, metavar="AGENT",
                           help="narrative-compress one agent's death trace")
    observe_p.add_argument("--depth", type=int, default=15)
    observe_p.add_argument("--compare-db", type=str, default=None,
                           help="second archive: diff causal budgets against --db")
    observe_p.add_argument("--compare-entity", type=str, default=None)
    observe_p.add_argument("--compare-field", type=str, default=None)

    query_p = sub.add_parser(
        "query", help="indexed causal queries over a recorded archive")
    query_p.add_argument("--db", type=str, required=True,
                         help="path to a SqliteArchive produced by --persist")
    query_p.add_argument("--cache", type=str, default=None,
                         help="query-index cache path (default: <db>.qidx)")
    qsub = query_p.add_subparsers(dest="qcmd", required=True)

    qsub.add_parser("build", help="build/extend the persistent index")

    def add_filter_args(p):
        p.add_argument("--system", type=str, default=None)
        p.add_argument("--operation", type=str, default=None)
        p.add_argument("--entity", type=str, default=None)
        p.add_argument("--field", type=str, default=None)
        p.add_argument("--ticks", type=int, nargs=2, default=None,
                       metavar=("START", "END"))
        p.add_argument("--committed", action="store_true")
        return p

    add_filter_args(qsub.add_parser("count", help="count matching transitions"))

    p = qsub.add_parser("budget", help="L1-equivalent budget via the index")
    p.add_argument("entity")
    p.add_argument("field")
    p.add_argument("--ticks", type=int, nargs=2, default=None,
                   metavar=("START", "END"))

    p = qsub.add_parser("profile", help="write-level delta drill-down")
    p.add_argument("entity", nargs="?")
    p.add_argument("field")
    p.add_argument("--ticks", type=int, nargs=2, default=None,
                   metavar=("START", "END"))

    p = qsub.add_parser("writers", help="list writes of one (entity, field)")
    p.add_argument("entity")
    p.add_argument("field")
    p.add_argument("--ticks", type=int, nargs=2, default=None,
                   metavar=("START", "END"))
    p.add_argument("--limit", type=int, default=40)

    p = qsub.add_parser("trace", help="backward/forward causal trace")
    p.add_argument("tid", type=int)
    p.add_argument("direction", nargs="?", default="backward",
                   choices=("backward", "forward"))
    p.add_argument("depth", type=int, nargs="?", default=10)

    p = qsub.add_parser("readers", help="what depends on one transition")
    p.add_argument("tid", type=int)
    p.add_argument("depth", type=int, nargs="?", default=1)

    p = add_filter_args(qsub.add_parser(
        "entropy", help="Shannon entropy of a distribution"))
    p.add_argument("--by", type=str, default="system",
                   help="system | operation | write:<field>")
    p.add_argument("--changes", action="store_true",
                   help="for write:<field>: only rows where old != new")

    p = qsub.add_parser("life", help="everything that touched one entity")
    p.add_argument("entity")
    p.add_argument("--limit", type=int, default=50)
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    simulation = create_world(
        seed=args.seed,
        ticks=args.ticks,
        regions=args.regions,
        agents=args.agents,
        ruleset=get_ruleset(args.ruleset),
        persist=args.persist,
    )
    state = simulation.state
    fingerprint = simulation.fingerprint()
    total, _committed, rejected = simulation.journal.counts()

    print(f"World seed:       {args.seed}")
    print(f"Ruleset:          {fingerprint['ruleset_version']}")
    print(f"RNG:              {fingerprint['rng_version']}")
    print()
    print(f"Regions:          {len(state.entities_with_prefix('region:'))}")
    print(f"Agents:           {len(state.entities_with_prefix('agent:'))}")
    print(f"Ticks:            {state.tick}")
    print()
    print(f"Final state:      {fingerprint['final_state_hash'][:16]}…")
    print(f"Transitions:      {total}")
    print(f"Rejected:         {rejected}")
    print()
    print("Fingerprint:")
    print(json.dumps(fingerprint, indent=2))

    if args.stats:
        print()
        print(format_statistics(compute_statistics(simulation)))
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    simulation = create_world(
        seed=args.seed,
        ticks=args.ticks,
        regions=args.regions,
        agents=args.agents,
        ruleset=get_ruleset(args.ruleset),
        persist=args.persist,
    )
    journal = simulation.journal
    if not journal.has(args.transition):
        print(
            f"error: transition T{args.transition} does not exist "
            f"(journal has {len(journal)} transitions)",
            file=sys.stderr,
        )
        return 2
    transition = journal.by_id(args.transition)
    print(format_transition(transition))
    if transition.status is TransitionStatus.COMMITTED:
        print()
        print("CAUSAL TRACE (backward)")
        print(format_trace(trace_back(simulation.index, args.transition, args.depth), args.depth))
    return 0


def _format_budget(report) -> str:
    lines = [
        f"Budget {report.entity}.{report.field} "
        f"[ticks {report.tick_range[0]}..{report.tick_range[1]}]"
    ]
    lines.append("  INFLOWS:")
    if report.inflows:
        for e in report.inflows:
            lines.append(
                f"    {e.system}.{e.operation:<28} "
                f"{e.total_delta:+.6f} over {e.count} writes "
                f"(mean {e.mean_delta:+.6f})")
    else:
        lines.append("    (none)")
    lines.append("  OUTFLOWS:")
    if report.outflows:
        for e in report.outflows:
            lines.append(
                f"    {e.system}.{e.operation:<28} "
                f"{e.total_delta:+.6f} over {e.count} writes "
                f"(mean {e.mean_delta:+.6f})")
    else:
        lines.append("    (none)")
    lines.append(f"  NET: {report.net:+.6f}")
    return "\n".join(lines)


def _cmd_observe(args: argparse.Namespace) -> int:
    from causal_world.observer.budget import CausalBudget
    from causal_world.observer.compress import NarrativeCompressor
    from causal_world.observer.journal import JournalView
    from causal_world.observer.regime import RegimeClassifier

    with JournalView(args.db) as view:
        meta = view.meta_all()
        lo, hi = view.tick_range()
        total, committed, rejected = view.counts()
        print(f"Archive:   {args.db}")
        print(f"ruleset:   {meta.get('ruleset_name')} "
              f"({meta.get('ruleset_version')})  seed {meta.get('seed')}")
        print(f"ticks:     {lo}..{hi}   transitions: {total} "
              f"(committed {committed}, rejected {rejected})")
        print()

        if args.budget:
            entity, field = args.budget
            budget = CausalBudget(view)
            print(_format_budget(budget.analyze(
                entity, field, args.tick_start, args.tick_end)))
            print()

        if args.classify:
            classifier = RegimeClassifier(
                view, sample_every=args.sample_every,
                total_agents=int(meta["agents"]) if "agents" in meta else None)
            report = classifier.classify()
            print(f"Regime:              {report.type.value}")
            print(f"confidence:          {report.confidence:.2f}")
            if report.extinction_tick is not None:
                print(f"extinction tick:     {report.extinction_tick}")
            if report.equilibrium_population is not None:
                print(f"equilibrium pop:     "
                      f"{report.equilibrium_population:.1f}")
            if report.oscillation_period is not None:
                print(f"oscillation period:  {report.oscillation_period}")
            print(f"soil trajectory:     {report.soil_trajectory}")
            print(f"dominant death cause:{report.dominant_death_cause:>2}")
            for cause, share in report.death_causes:
                print(f"    {cause:<22} {share:.1%}")
            print()

        if args.explain_death:
            compressor = NarrativeCompressor()
            print(compressor.explain_death(
                args.explain_death, view, depth=args.depth))
            print()

        if args.compare_db:
            from causal_world.observer.compare import CausalComparator

            with JournalView(args.compare_db) as other:
                name_a = view.meta("ruleset_name") or "A"
                name_b = other.meta("ruleset_name") or "B"
                comparator = CausalComparator(view, other, name_a, name_b)
                entity = args.compare_entity or "region:0"
                field = args.compare_field or "soil_fertility"
                diff = comparator.compare_field(entity, field)
                print(f"Diff {name_a} vs {name_b} — {entity}.{field}")
                print(f"  inflows only in {name_b}: "
                      f"{diff.missing_inflows or '(none)'}")
                print(f"  outflows only in {name_a}: "
                      f"{diff.missing_outflows or '(none)'}")
                print(f"  net delta ({field}): "
                      f"{diff.budget_deltas[field]:+.6f}")
                print(f"  loop: {diff.causal_loop_diff}")
    return 0


def _cmd_query(args: argparse.Namespace) -> int:
    from causal_world.observer.journal import JournalView
    from causal_world.query.index import QueryIndex
    from causal_world.query.query import CausalQuery

    cache = args.cache or (args.db + ".qidx")
    with JournalView(args.db) as view, QueryIndex(view, cache) as idx:
        stats = idx.build()
        if args.qcmd == "build":
            print(f"index cache: {cache}")
            print(f"  transitions: {stats.transitions} "
                  f"(last tid {stats.last_tid})")
            print(f"  idx_writes:  {stats.idx_writes}")
            print(f"  idx_reads:   {stats.idx_reads}")
            print(f"  idx_entity:  {stats.idx_entity}")
            print(f"  built in {stats.build_seconds:.1f}s "
                  f"({'incremental' if stats.incremental else 'full'}), "
                  f"{stats.cache_bytes/1e6:.1f} MB")
            return 0

        q = CausalQuery(idx)

        def apply_filters(query):
            if getattr(args, "system", None):
                query = query.system(args.system)
            if getattr(args, "operation", None):
                query = query.operation(args.operation)
            if getattr(args, "entity", None):
                query = query.entity(args.entity)
            if getattr(args, "field", None):
                query = query.field(args.field)
            if getattr(args, "ticks", None):
                query = query.ticks(*args.ticks)
            if getattr(args, "committed", False):
                query = query.committed_only()
            return query

        if args.qcmd == "count":
            print(apply_filters(q).count())
            return 0

        if args.qcmd == "budget":
            t0, t1 = args.ticks or (0, 2**62)
            report = q.budget(args.entity, args.field, t0, t1)
            print(_format_budget(report))
            return 0

        if args.qcmd == "profile":
            t0, t1 = args.ticks or (0, 2**62)
            rows = q.delta_profile(args.entity, args.field, t0, t1)
            print(f"delta profile: {args.entity or '*'}."
                  f"{args.field} [t{t0}..{t1}]")
            for r in rows:
                print(f"  {r.system}.{r.operation}: {r.writes} writes "
                      f"(+{r.positive}/-{r.negative}/0:{r.zero_or_nonnumeric})"
                      f" total {r.total_delta:+.6f}"
                      + (f" mean {r.mean_delta:+.6f}"
                         if r.mean_delta is not None else "")
                      + (f" range [{r.min_delta:+.6f}, {r.max_delta:+.6f}]"
                         if r.min_delta is not None else ""))
            return 0

        if args.qcmd == "writers":
            t0, t1 = args.ticks or (0, 2**62)
            rows = idx.sql(
                "SELECT w.tick, w.tid, w.delta, w.old, w.new, "
                "t.system, t.operation FROM idx_writes w "
                "JOIN arch.transitions t ON t.id=w.tid "
                "WHERE w.entity=? AND w.field=? AND t.tick BETWEEN ? AND ? "
                "AND t.status='COMMITTED' ORDER BY w.tick, w.tid LIMIT ?",
                (args.entity, args.field, t0, t1, args.limit)).fetchall()
            for r in rows:
                print(f"  t{r['tick']} T{r['tid']} {r['system']}."
                      f"{r['operation']}: {r['old']} -> {r['new']} "
                      f"(delta {r['delta']})")
            return 0

        if args.qcmd == "trace":
            result = q.trace(args.tid, args.direction, args.depth)
            print(f"trace {args.direction} from T{args.tid} "
                  f"(depth {args.depth}): {len(result.nodes)} nodes"
                  + (" [TRUNCATED]" if result.truncated else ""))
            for t in result.nodes:
                print(f"  d{result.depths[t.id]} t{t.tick} T{t.id} "
                      f"{t.system}.{t.operation} ({t.status.value})")
            return 0

        if args.qcmd == "readers":
            dependents = q.caused_by(args.tid, args.depth)
            total = dependents.count()
            print(f"transitions reading (depth<={args.depth}) what "
                  f"T{args.tid} wrote: {total}")
            for t in dependents.list(limit=20):
                print(f"  t{t.tick} T{t.id} {t.system}.{t.operation}")
            return 0

        if args.qcmd == "entropy":
            query = apply_filters(q)
            result = query.entropy(by=args.by,
                                   actual_changes_only=args.changes)
            print(f"entropy by {result.by}: {result.entropy_bits:.4f} bits "
                  f"over {result.total} rows, "
                  f"{len(result.distribution)} distinct values")
            for value, n in result.distribution[:15]:
                print(f"  {value}: {n}")
            return 0

        if args.qcmd == "life":
            for t in q.timeline(args.entity, limit=args.limit):
                writes = ", ".join(f"{w.field}:{w.old}->{w.new}"
                                   for w in t.writes if w.entity == args.entity)
                print(f"  t{t.tick} T{t.id} {t.system}.{t.operation}"
                      + (f"  {writes}" if writes else ""))
            return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "trace":
        return _cmd_trace(args)
    if args.command == "observe":
        return _cmd_observe(args)
    if args.command == "query":
        return _cmd_query(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
