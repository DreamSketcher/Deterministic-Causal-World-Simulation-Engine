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

    p = sub.add_parser(
        "bio", help="BiographyCard — one life from one archive"
    )
    p.add_argument("--db", required=True, help="path to journal.db")
    p.add_argument("--agent", default="agent:0")
    p.add_argument("--md", action="store_true", help="print the readable card")

    p = sub.add_parser("serve", help="step 5: WebSocket life server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--db-dir", default=".", help="where life-<session>.db live")

    civic_p = sub.add_parser(
        "civic",
        help="v0.7: the civic loop — observe, understand, intervene, verify",
    )
    civic_p.add_argument("--seed", type=int, default=7)
    civic_p.add_argument("--ruleset", default="player_spatial",
                         help="player_spatial (v0.8 cell world) | "
                              "player_civic (v0.7 region world) | "
                              "player_life (v0.6)")
    civic_p.add_argument("--regions", type=int, default=2)
    civic_p.add_argument("--agents", type=int, default=54)
    civic_p.add_argument("--ticks", type=int, default=120)
    civic_p.add_argument("--db", default=None,
                         help="archive path (default: a temp file)")
    civic_p.add_argument("--decree", action="append", default=[],
                         metavar="TICK:KIND:REGION[:PARAM]",
                         help="enact a decree: e.g. 20:amend:region:0:0.25")
    civic_p.add_argument("--fork-at", type=int, default=None,
                         help="world tick at which the counterfactual "
                              "changes the decision")
    civic_p.add_argument("--fork-action", type=int, default=6,
                         help="the decision the counterfactual plays instead")
    civic_p.add_argument("--hypothesis", default=None,
                         metavar="SYSTEM:OPERATION:ENTITY:FIELD",
                         help="a claim to test against the record")
    civic_p.add_argument("--json", action="store_true",
                         help="print the raw report as JSON")

    p = sub.add_parser("play", help="step 5: interactive life client")
    p.add_argument("--url", default="ws://127.0.0.1:8765")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--regions", type=int, default=2)
    p.add_argument("--agents", type=int, default=60)
    p.add_argument("--max-ticks", type=int, default=4000)
    p.add_argument("--world", default="demo",
                   help="world identifier: existing <db_dir>/<name>.db → next "
                        "life by the succession rule, absent → new world")
    p.add_argument("--script", default=None,
                   help="comma-separated action indices, no REPL (demo/tests)")
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


def _cmd_bio(args: argparse.Namespace) -> int:
    from causal_world.observer.biography import build_biography

    card = build_biography(args.db, args.agent)
    if args.md:
        print(card.to_markdown())
        return 0
    m = card.meta
    print(f"Biography of {m.agent} — seed={m.seed} ruleset={m.ruleset_version}")
    print(f"  ticks {m.birth_tick}..{m.final_tick} "
          f"({m.committed} committed, {m.rejected} rejected)")
    if card.death is not None:
        d = card.death
        die = f" | die roll {d.die[1]:.6f} < {d.die[2]:.6f}" if d.die else ""
        print(f"  died T{d.tick} via {d.operation}{die}")
    else:
        print("  alive at end of archive")
    print(f"  decisions: {sum(g.count for g in card.decisions)} "
          f"in {len(card.decisions)} run(s)")
    print(f"  fingerprint: {card.fingerprint()}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from causal_world.server.ws import serve

    serve(host=args.host, port=args.port, db_dir=args.db_dir)
    return 0


def _cmd_play(args: argparse.Namespace) -> int:
    from causal_world.server.client import LifeClient
    from causal_world.systems.player import ACTION_NAMES

    names = {v: int(k) for k, v in ACTION_NAMES.items()}
    client = LifeClient(args.url)

    def _hello() -> dict:
        return client.hello_new(
            world=args.world, seed=args.seed, regions=args.regions,
            agents=args.agents, max_ticks=args.max_ticks,
        )

    welcome = _hello()
    if welcome.get("type") != "welcome":
        print(f"server refused: {welcome}")
        return 1
    sid = welcome["session_id"]
    life = welcome.get("life") or {}
    print(f"session {sid} | world {args.world} | life {life.get('n')} "
          f"({life.get('agent')}, {life.get('succession')}) | alive: "
          f"{welcome['alive']} | actions: {', '.join(names)}")

    def show(f: dict) -> None:
        y = f["you"]
        print(f"  t{f['tick']:>3} {'' if f['applied'] else 'REJECTED '}"
              f"hunger {float(y['hunger']):.3f} health {float(y['health']):.3f} "
              f"region {y['region']} alive {f['alive']}")

    if args.script is not None:  # non-interactive demo drive
        for seq, a in enumerate((int(x) for x in args.script.split(",")), 1):
            f = client.decide(seq, a)
            if f.get("type") == "error":
                print(f"  seq {seq}: error {f['code']}: {f['msg']}")
                continue
            show(f)
            ev = f.get("finished")
            if not f["alive"]:
                if ev:
                    au = ev.get("autopsy") or {}
                    print(f"  finished: {ev.get('reason')} "
                          f"@T{ev.get('death_tick')} | {au.get('label', '—')} | "
                          f"bio {str(ev.get('bio_fingerprint'))[:16]}…")
                print("  next life: run play --world "
                      f"{args.world} again (heir per the succession rule)")
                break
    else:
        seq = welcome["last_seq"]
        while True:
            try:
                line = input("action> ").strip().lower()
            except EOFError:
                break
            if not line:
                continue
            if line in ("quit", "exit"):
                break
            if line == "new-life":
                welcome = _hello()
                if welcome.get("type") != "welcome":
                    print(f"  refused: {welcome.get('code')}: {welcome.get('msg')}")
                    break
                life = welcome.get("life") or {}
                seq = welcome["last_seq"]
                print(f"  life {life.get('n')}: {life.get('agent')} "
                      f"({life.get('succession')}) from t{welcome['tick']}")
                continue
            if line == "bio":
                print(client.bio()["md"])
                continue
            if line in ("autopsy", "close"):
                print(json.dumps(client.autopsy() if line == "autopsy"
                                 else client.close(), indent=2, sort_keys=True))
                continue
            act = names.get(line, None)
            if act is None:
                try:
                    act = int(line)  # raw ints (incl. out-of-range) go to the world
                except ValueError:
                    print(f"unknown: {line} (names: {', '.join(names)}, or bio/autopsy/close)")
                    continue
            seq += 1
            f = client.decide(seq, act)
            if f.get("type") == "error":
                print(f"  error {f['code']}: {f['msg']}")
                seq -= 1
                continue
            show(f)
            if not f["alive"]:
                print("  the life ended — 'autopsy', 'bio', 'close' still work")
    print(json.dumps(client.bio(), indent=2, sort_keys=True))
    print(json.dumps(client.close(), indent=2, sort_keys=True))
    client.terminate()
    return 0


def _cmd_civic(args: argparse.Namespace) -> int:
    """The v0.7 loop: observe -> understand -> intervene -> verify."""
    import tempfile
    from pathlib import Path

    from causal_world.game import (
        GameWorld,
        chronicle,
        intervene_and_verify,
        observe,
        understand,
    )
    from causal_world.observer.hypothesis import Hypothesis
    from causal_world.systems.directive import (
        DIRECTIVE_ALL_NAMES,
        Directive,
    )

    kinds = {name: code for code, name in DIRECTIVE_ALL_NAMES.items()}
    tmpdir = None
    if args.db:
        db_path = args.db
    else:
        tmpdir = tempfile.mkdtemp(prefix="civic-")
        db_path = str(Path(tmpdir) / "world.db")

    world = GameWorld(
        seed=args.seed, ruleset=args.ruleset, regions=args.regions,
        agents=args.agents, db_path=db_path,
    )
    # A list, not a dict keyed by tick: two orders for one tick must
    # reach the channel and get an explicit answer (accepted / queued /
    # rejected), never silently overwrite each other in the CLI (v0.9).
    decrees = []
    for spec in args.decree:
        # TICK:KIND:TARGET[:PARAM] — the target may itself contain colons
        # ("cell:1:0"), so it is parsed from the middle: the first field
        # is the tick, the last is the parameter, the kind is the second.
        parts = spec.split(":")
        if len(parts) < 3:
            print(f"error: bad --decree {spec!r} "
                  f"(expected TICK:KIND:TARGET[:PARAM])", file=sys.stderr)
            return 2
        tick, kind = int(parts[0]), parts[1]
        param = float(parts[-1]) if len(parts) > 3 else 0.25
        target = ":".join(parts[2:-1]) if len(parts) > 3 else parts[2]
        if kind not in kinds:
            print(f"error: unknown decree kind {kind!r} "
                  f"(have {', '.join(sorted(kinds))})", file=sys.stderr)
            return 2
        decrees.append((tick, Directive(kinds[kind], target, param)))

    for tick, directive in sorted(decrees, key=lambda x: x[0]):
        answer = world.decree(tick, directive.kind, directive.region,
                              directive.param)
        print(f"decree {directive.name} -> {directive.region} "
              f"(param {directive.param}): {answer.message}")

    for tick in range(args.ticks):
        world.act(6)  # idle: the personal card is the v0.6 one
    world.close()

    report = {"db": db_path}
    report["observation"] = observe(db_path)

    if args.hypothesis:
        # The entity may itself contain a colon ("region:0"), so the
        # claim is split from the LEFT: system, operation, then the rest
        # is "<entity>:<field>".
        head, _, tail = args.hypothesis.partition(":")
        system, _, rest = tail.partition(":")
        entity, _, field_name = rest.rpartition(":")
        if not (head and system and entity and field_name):
            print("error: --hypothesis expects SYSTEM:OPERATION:ENTITY:FIELD",
                  file=sys.stderr)
            return 2
        report["hypothesis"] = understand(
            db_path,
            Hypothesis(text=args.hypothesis, system=head, operation=system,
                       entity=entity, field=field_name),
        ).to_dict()

    if args.fork_at is not None:
        result = intervene_and_verify(
            db_path, fork_at=args.fork_at, action=args.fork_action,
            fork_db=str(Path(db_path).with_name(Path(db_path).stem + ".fork.db")),
        )
        report["counterfactual"] = {
            "diverged_at_tick": result.diverged_at_tick,
            "diverged_transition": result.diverged_transition,
            "base_alive": result.base_alive,
            "fork_alive": result.fork_alive,
            "soil_diffs": result.soil_diffs,
            "budget_diffs": result.budget_diffs,
            "loop_diff": result.loop_diff,
        }

    report["chronicle"] = chronicle(db_path)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0

    obs = report["observation"]
    print(f"world: {db_path}  (seed {obs['seed']}, ruleset {obs['ruleset']}, "
          f"ticks {obs['ticks'][0]}..{obs['ticks'][1]})")
    print(f"regime: {obs['regime']['type']}  soil trajectory: "
          f"{obs['regime']['soil_trajectory']}  dominant death: "
          f"{obs['regime']['dominant_death_cause']}")
    print(f"population: {obs['final_region_population']}")
    print(f"soil:       {obs['final_region_soil']}")
    if obs.get("cells"):
        print()
        print("cells:")
        for cell in obs["cells"]:
            law = cell.get("law") or {}
            print(f"  {cell['id']:<12} pop {cell['population']:>3}  "
                  f"soil {cell['soil_fertility']:.3f}  "
                  f"food {cell['food_stock']:7.1f}  "
                  f"law: отвод {law.get('labor_diversion', 0):.2f}, "
                  f"полив {law.get('water_aid', 0):.2f}, "
                  f"ясли {law.get('nursery', 0):.2f}")
    if obs.get("situations"):
        print()
        print("situations (the world's own reading of itself):")
        for s in obs["situations"]:
            print(f"  [{s['severity']:.2f}] {s['kind']:<12} {s['message']}")
    print()
    print("budgets (region:0):")
    for field, rep in obs["budgets"].items():
        print(f"  {field}: net {rep['net']:+.6f}")
        for e in rep["inflows"]:
            print(f"    + {e['system']}.{e['operation']:<24} "
                  f"{e['total_delta']:+.6f} x{e['count']}")
        for e in rep["outflows"]:
            print(f"    - {e['system']}.{e['operation']:<24} "
                  f"{e['total_delta']:+.6f} x{e['count']}")
    if "hypothesis" in report:
        h = report["hypothesis"]
        print()
        print(f"hypothesis [{h['hypothesis']['text']}]: {h['verdict']}")
        print(f"  {h['reason']}")
        if h["supporting"]:
            print(f"  supporting transitions: {h['supporting'][:10]}")
    if "counterfactual" in report:
        c = report["counterfactual"]
        print()
        print(f"counterfactual: diverged at tick {c['diverged_at_tick']} "
              f"(T{c['diverged_transition']})")
        print(f"  alive base/fork: {c['base_alive']} / {c['fork_alive']}")
        for region, delta in c["soil_diffs"].items():
            print(f"  soil {region}: {delta:+.6f}")
        if c["loop_diff"]:
            print(f"  loop: {c['loop_diff']}")
    print()
    print(report["chronicle"]["markdown"])
    return 0


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
    if args.command == "bio":
        return _cmd_bio(args)
    if args.command == "serve":
        return _cmd_serve(args)
    if args.command == "play":
        return _cmd_play(args)
    if args.command == "civic":
        return _cmd_civic(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
