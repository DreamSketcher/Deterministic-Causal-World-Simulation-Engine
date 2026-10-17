"""v0.7 — the SANDBOX: counterfactual runs of the same world.

The engine's determinism is not only a correctness property; it is the
gameplay advantage of the researcher role. Given (seed, ruleset, world
size) the world is a pure function of the DECISION STREAM, so a player can
ask counterfactual questions and get exact answers:

    "what if I had gone east at tick 40 instead of resting?"

The sandbox answers that question the only honest way: it re-runs the
world with ONE changed decision and compares the two recorded runs with
the read-only observer layer (``CausalComparator`` + budgets + series).
No narrative, no plausibility — two journals, two budgets, one diff.

Why this is not "just re-running the simulation":

* The BASE run is a recorded archive (it may be a live session's
  archive). The sandbox reads its decision stream back out of the journal
  (``DecisionStreamReader``), so the counterfactual starts from the
  player's ACTUAL history, not from a hand-written script.
* The fork is defined by a ``Fork`` — a set of (tick, action) overrides.
  The rest of the stream is the recorded one, unchanged.
* Both runs are persisted, so the comparison uses the same code path as
  the rest of the repo (``CausalComparator`` over two ``JournalView``s),
  and the verdict is reproducible by re-running the sandbox.

The sandbox is read-only with respect to the base archive: it never
writes to it. The counterfactual run gets its OWN archive.

Scope of the fork: overrides address the decision STREAM INDEX, which
is the index of a live tick of the controlled agent (the stream is
lossless: one entry per live tick, in order). ``fork_at_tick`` maps a
world tick to a stream index using the recorded ``player.act``
transitions, so the player can say "at world tick 40" and get the right
decision slot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from causal_world import create_world
from causal_world.observer.compare import CausalComparator
from causal_world.observer.journal import JournalView
from causal_world.observer.series import build_series
from causal_world.player import (
    DecisionChannel,
    DecisionStreamReader,
    attach_player_channel,
)
from causal_world.systems.directive import Directive, DirectiveChannel
from causal_world.systems.directive import DirectiveSystem
from causal_world.world.rules import get_ruleset


@dataclass(frozen=True)
class Fork:
    """One changed decision: at STREAM INDEX ``index``, play ``action``.

    ``index`` is the position in the decision stream (one entry per live
    tick of the controlled agent), NOT a world tick — see
    :func:`fork_at_tick` for the world-tick spelling.
    """

    index: int
    action: int

    def apply(self, stream: list[int]) -> list[int]:
        out = list(stream)
        if 0 <= self.index < len(out):
            out[self.index] = self.action
        return out


@dataclass(frozen=True)
class SandboxResult:
    """The outcome of a counterfactual comparison."""

    base_db: str
    fork_db: str
    diverged_at_tick: int | None
    diverged_transition: int | None
    base_alive: int
    fork_alive: int
    base_population: list[tuple[int, int]]
    fork_population: list[tuple[int, int]]
    base_soil: list[tuple[int, float]]
    fork_soil: list[tuple[int, float]]
    soil_diffs: dict[str, float] = field(default_factory=dict)
    budget_diffs: dict[str, dict[str, float]] = field(default_factory=dict)
    loop_diff: str = ""

    @property
    def diverged(self) -> bool:
        return self.diverged_at_tick is not None


def read_decision_stream(db_path: str) -> list[int]:
    """The decision stream of a recorded run, read back from the journal.

    This is the v0.6 lossless-replay property applied to an ARCHIVE:
    every live tick of the controlled agent left one ``player.act``
    transition carrying its ``player.decision`` draw, so the stream can
    be reconstructed without any side information.
    """
    with JournalView(db_path) as view:
        return DecisionStreamReader.actions_from(view)


def read_decree_ledger(db_path: str) -> dict[int, Directive]:
    """The civic decree ledger of a recorded run, read back from the journal.

    The second input channel of the v0.7 world. It MUST be recoverable
    from the archive alone, for the same reason the decision stream is:
    a counterfactual whose BASE is not the recorded world is not a
    counterfactual at all, it is a different experiment.

    Each decree is recoverable because the engine recorded everything
    needed: the KIND in the ``player.directive`` draw, the TARGET in the
    draw's entity, and the MAGNITUDE in the write itself (the parameter
    is the delta the write applied to the law parameter).
    """
    from causal_world.systems.directive import (
        DIRECTIVE_AMEND,
        DIRECTIVE_REST,
        DIRECTIVE_WATER,
    )

    ledger: dict[int, Directive] = {}
    with JournalView(db_path) as view:
        for t in view:
            if t.operation != "player.directive" or t.status.value != "COMMITTED":
                continue
            if not t.random_draws:
                continue
            kind = int(t.random_draws[0].value)
            region = t.random_draws[0].entity
            param = 0.0
            for w in t.writes:
                if w.entity != region:
                    continue
                if kind == DIRECTIVE_AMEND and w.field == "labor_diversion":
                    param = float(w.new) - float(w.old)
                elif kind == DIRECTIVE_WATER and w.field == "water_aid":
                    param = float(w.new) - float(w.old)
                elif kind == DIRECTIVE_REST and w.field == "rest_until":
                    param = float(int(w.new) - t.tick)
            ledger[t.tick] = Directive(kind, region, param)
    return ledger


def stream_index_of_tick(db_path: str, tick: int) -> int | None:
    """Map a WORLD tick to the decision-stream index played at that tick.

    Returns None when the controlled agent was dead at that tick (no
    decision was taken, so the stream has no entry for it).
    """
    with JournalView(db_path) as view:
        index = 0
        for t in view:
            if t.operation != "player.act":
                continue
            if t.tick == tick:
                return index
            index += 1
    return None


def _run(
    db_path: str,
    seed: int,
    ruleset: str,
    regions: int,
    agents: int,
    actions: list[int],
    directives: dict[int, Directive] | None = None,
) -> None:
    """Run one world to completion and persist it to ``db_path``."""
    sim = create_world(
        seed=seed,
        ruleset=get_ruleset(ruleset),
        ticks=0,
        regions=regions,
        agents=agents,
        persist=db_path,
    )
    attach_player_channel(sim, DecisionChannel(actions=list(actions)))
    if directives:
        channel = DirectiveChannel(directives)
        for system in sim.systems:
            if isinstance(system, DirectiveSystem):
                system.channel = channel
    # run until the stream is exhausted (the player is dead or idle)
    for _ in range(max(len(actions), 1)):
        sim.step()
    sim.journal.commit()
    sim.journal.close()


def run_counterfactual(
    base_db: str,
    fork: Fork,
    *,
    fork_db: str,
    directives: dict[int, Directive] | None = None,
) -> SandboxResult:
    """Re-run the recorded world with ONE changed decision and compare.

    ``base_db`` is never written to. The counterfactual is persisted to
    ``fork_db`` so it can be inspected with the same tools as any other
    run (bio, observe, query).
    """
    with JournalView(base_db) as view:
        meta = view.meta_all()
        base_stream = DecisionStreamReader.actions_from(view)

    # The BASE of a counterfactual is the recorded world, decree ledger
    # included: a fork must change ONE factor (the decision), not two.
    # Without this the comparison would attribute the difference to the
    # wrong cause — the very sin the whole repo is built against.
    base_ledger = read_decree_ledger(base_db)
    variant_ledger = {**base_ledger, **(directives or {})}

    seed = int(meta["seed"])
    ruleset = meta.get("ruleset_name") or _ruleset_of(meta["ruleset_version"])
    regions = int(meta["regions"])
    agents = int(meta["agents"])

    forked_stream = fork.apply(base_stream)
    _run(
        fork_db,
        seed,
        ruleset,
        regions,
        agents,
        forked_stream,
        directives=variant_ledger,
    )

    with JournalView(base_db) as a_view, JournalView(fork_db) as b_view:
        comparator = CausalComparator(a_view, b_view, "base", "fork")
        # The number of agent ENTITIES, not the requested agent count: the
        # v0.6 game ruleset pre-allocates a dormant pool, so ``meta[agents]``
        # undercounts the population the series must subtract deaths from.
        base_total = _agent_count(a_view)
        fork_total = _agent_count(b_view)
        base_series = build_series(a_view, total_agents=base_total)
        fork_series = build_series(b_view, total_agents=fork_total)

        diverged_at, diverged_tid = _first_divergence(a_view, b_view)

        soil_diffs = {}
        budget_diffs = {}
        loop_diff = ""
        for region in _regions_of(a_view):
            base_soil = base_series.final_region_soil.get(region)
            fork_soil = fork_series.final_region_soil.get(region)
            if base_soil is not None and fork_soil is not None:
                soil_diffs[region] = fork_soil - base_soil
            diff = comparator.compare_field(region, "soil_fertility")
            budget_diffs[region] = dict(diff.budget_deltas)
            if not loop_diff:
                loop_diff = diff.causal_loop_diff

        return SandboxResult(
            base_db=base_db,
            fork_db=fork_db,
            diverged_at_tick=diverged_at,
            diverged_transition=diverged_tid,
            base_alive=_alive_count(base_series),
            fork_alive=_alive_count(fork_series),
            base_population=base_series.population,
            fork_population=fork_series.population,
            base_soil=base_series.soil,
            fork_soil=fork_series.soil,
            soil_diffs=soil_diffs,
            budget_diffs=budget_diffs,
            loop_diff=loop_diff,
        )


def fork_at_tick(
    base_db: str,
    tick: int,
    action: int,
    *,
    fork_db: str,
    directives: dict[int, Directive] | None = None,
) -> SandboxResult:
    """Counterfactual that changes the decision taken at a WORLD tick."""
    index = stream_index_of_tick(base_db, tick)
    if index is None:
        raise ValueError(
            f"no decision was taken at world tick {tick} "
            f"(the controlled agent was dead or the tick is out of range)"
        )
    return run_counterfactual(
        base_db, Fork(index, action), fork_db=fork_db, directives=directives
    )


def _alive_count(series) -> int:
    """Living agents at the head of a run, from the derived series."""
    return series.population[-1][1] if series.population else 0


def _agent_count(view: JournalView) -> int:
    """How many agent entities the world actually has (genesis included)."""
    rows = view.query(
        "SELECT COUNT(DISTINCT json_extract(value, '$[0]')) AS n "
        "FROM transitions, json_each(transitions.payload, '$.writes') "
        "WHERE json_extract(value, '$[0]') LIKE 'agent:%'"
    )
    return int(rows[0]["n"]) if rows else 0


def _regions_of(view: JournalView) -> list[str]:
    """Every region that appears in a recorded run, sorted."""
    rows = view.query(
        "SELECT DISTINCT json_extract(value, '$[0]') AS e "
        "FROM transitions, json_each(transitions.payload, '$.writes') "
        "WHERE json_extract(value, '$[0]') LIKE 'region:%'"
    )
    return sorted(str(r["e"]) for r in rows)


def _first_divergence(a_view: JournalView, b_view: JournalView):
    """The first tick at which the two runs differ, and its transition id.

    Compares the two journals transition by transition (id order). Since
    both runs share the same prefix, the first DIFFERENT record is the
    fork point — the exact tick at which the changed decision changed
    the world.
    """
    a_iter = iter(a_view)
    b_iter = iter(b_view)
    while True:
        a = next(a_iter, None)
        b = next(b_iter, None)
        if a is None or b is None:
            return None, None
        if a.id != b.id or a.tick != b.tick or a.operation != b.operation:
            return min(a.tick, b.tick), min(a.id, b.id) if a.id else None
        if a.writes != b.writes or a.random_draws != b.random_draws:
            return a.tick, a.id


def _ruleset_of(version: str) -> str:
    from causal_world.world.rules import RULESETS

    for name, cls in RULESETS.items():
        if cls.ruleset_version == version:
            return name
    raise KeyError(f"no known ruleset for version {version!r}")


def default_fork_path(base_db: str) -> str:
    """A sibling path for the counterfactual archive."""
    p = Path(base_db)
    return str(p.with_name(p.stem + ".fork.db"))
