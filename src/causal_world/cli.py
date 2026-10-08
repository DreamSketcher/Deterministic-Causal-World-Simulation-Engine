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
        p.add_argument("--persist", type=str, default=None,
                       help="SQLite archive path for the journal + causal index")

    run_p = sub.add_parser("run", help="run a world and print the summary")
    add_world_args(run_p)
    run_p.add_argument("--stats", action="store_true", help="print statistics block")

    trace_p = sub.add_parser("trace", help="run a world and trace one transition")
    add_world_args(trace_p)
    trace_p.add_argument("--transition", type=int, required=True)
    trace_p.add_argument("--depth", type=int, default=4)
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    simulation = create_world(
        seed=args.seed,
        ticks=args.ticks,
        regions=args.regions,
        agents=args.agents,
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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "trace":
        return _cmd_trace(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
