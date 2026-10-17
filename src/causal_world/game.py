"""v0.7 — the GAME loop, assembled from the pieces the repo already has.

    OBSERVE  ->  UNDERSTAND  ->  INTERVENE  ->  VERIFY

* **OBSERVE** — the recorded run (``player_life``/``player_civic``) is
  read through the observer layer: budgets, regime, series, facts.
* **UNDERSTAND** — the player states a HYPOTHESIS; the engine tests it
  against the record and answers confirmed / refuted / unresolved with
  real transition ids. Nothing here is a narrative.
* **INTERVENE** — the player acts: a civic DECREE (a law for a region)
  and/or a changed personal DECISION. Both are committed transitions.
* **VERIFY** — the counterfactual is re-run in the sandbox and the two
  runs are compared mechanically (budgets, soil, population, divergence
  tick).

This module is the orchestration; it owns no new semantics. Every fact
it prints comes from the observer/query/sandbox layers, and every
verdict from the journal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from causal_world import create_world
from causal_world.observer.biography import build_biography
from causal_world.observer.budget import CausalBudget
from causal_world.observer.hypothesis import (
    Hypothesis,
    HypothesisReport,
    test_hypothesis,
)
from causal_world.observer.journal import JournalView
from causal_world.observer.regime import RegimeClassifier
from causal_world.observer.series import build_series
from causal_world.observer.situation import StateView, situations
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.query.index import QueryIndex
from causal_world.sandbox import Fork, SandboxResult, run_counterfactual
from causal_world.systems.directive import (
    Directive,
    DirectiveChannel,
    DirectiveSystem,
)
from causal_world.world.rules import get_ruleset


@dataclass
class GameWorld:
    """A playable world plus the channels the player drives."""

    seed: int
    ruleset: str = "player_civic"
    regions: int = 2
    agents: int = 60
    ticks: int = 200
    db_path: str | None = None
    sim: object = None
    decisions: DecisionChannel = field(default_factory=DecisionChannel)
    decrees: DirectiveChannel = field(default_factory=DirectiveChannel)

    def __post_init__(self) -> None:
        self.sim = create_world(
            seed=self.seed,
            ruleset=get_ruleset(self.ruleset),
            ticks=0,
            regions=self.regions,
            agents=self.agents,
            persist=self.db_path,
        )
        attach_player_channel(self.sim, self.decisions)
        for system in self.sim.systems:
            if isinstance(system, DirectiveSystem):
                system.channel = self.decrees

    # ------------------------------------------------------------------
    def act(self, action: int) -> None:
        """One personal decision (the v0.6 card)."""
        self.decisions.deliver(action)
        self.sim.step()

    def decree(self, tick: int, kind: int, region: str, param: float = 0.25) -> None:
        """One civic law for a region, effective from ``tick + 1``."""
        self.decrees.schedule(tick, Directive(kind, region, param))

    def run(self, ticks: int | None = None) -> None:
        n = self.ticks if ticks is None else ticks
        for _ in range(n):
            self.sim.step()
        if self.db_path:
            self.sim.journal.commit()

    def close(self) -> None:
        if self.db_path and getattr(self.sim.journal, "_conn", None):
            try:
                self.sim.journal.commit()
            finally:
                self.sim.journal.close()

    # ------------------------------------------------------------------
    def fingerprint(self) -> dict:
        fp = self.sim.fingerprint()
        fp["journal_hash"] = self.sim.journal.hash()
        return fp


def observe(db_path: str, *, agent: str = "agent:0") -> dict:
    """The OBSERVE step: what the recorded world looks like.

    Purely read-only over the archive.
    """
    with JournalView(db_path) as view:
        meta = view.meta_all()
        lo, hi = view.tick_range()
        total, committed, rejected = view.counts()
        series = build_series(
            view, total_agents=_agent_total(view, meta)
        )
        regime = RegimeClassifier(
            view, series=series, total_agents=series.total_agents
        ).classify()
        soil_budget = CausalBudget(view).analyze("region:0", "soil_fertility")
        food_budget = CausalBudget(view).analyze("region:0", "food_stock")
        # v0.8: the cells of the spatial world and the problem feed the
        # world itself produces. Both are read from the same archive.
        state = StateView.from_journal(view)
        cells = []
        for cell in state.entities_with_prefix("cell:"):
            cells.append({
                "id": cell,
                "region": state.get(cell, "region"),
                "population": state.get(cell, "population"),
                "soil_fertility": state.get(cell, "soil_fertility"),
                "food_stock": state.get(cell, "food_stock"),
                "rain_factor": state.get(cell, "rain_factor"),
                "law": {
                    "labor_diversion": state.get(cell, "labor_diversion"),
                    "water_aid": state.get(cell, "water_aid"),
                    "rest_until": state.get(cell, "rest_until"),
                    "nursery": state.get(cell, "nursery"),
                } if state.get(cell, "labor_diversion") is not None else None,
            })
        return {
            "db": db_path,
            "ruleset": meta.get("ruleset_name") or meta.get("ruleset_version"),
            "seed": meta.get("seed"),
            "ticks": [lo, hi],
            "transitions": {
                "total": total, "committed": committed, "rejected": rejected,
            },
            "regime": {
                "type": regime.type.value,
                "confidence": regime.confidence,
                "extinction_tick": regime.extinction_tick,
                "dominant_death_cause": regime.dominant_death_cause,
                "death_causes": list(regime.death_causes),
                "soil_trajectory": regime.soil_trajectory,
            },
            "population_series": series.population,
            "soil_series": [(t, round(v, 6)) for t, v in series.soil],
            "final_region_population": series.final_region_population,
            "final_region_soil": {
                k: round(v, 6) for k, v in series.final_region_soil.items()
            },
            "cells": cells,
            "situations": [a.to_dict() for a in situations(view)],
            "budgets": {
                "region:0.soil_fertility": _budget_dict(soil_budget),
                "region:0.food_stock": _budget_dict(food_budget),
            },
        }


def understand(db_path: str, hypothesis: Hypothesis, *,
               cache_path: str | None = None) -> HypothesisReport:
    """The UNDERSTAND step: test the player's hypothesis against the record."""
    cache = cache_path or (db_path + ".qidx")
    with JournalView(db_path) as view, QueryIndex(view, cache) as idx:
        idx.build()
        return test_hypothesis(idx, hypothesis)


def intervene_and_verify(
    db_path: str,
    *,
    fork: Fork | None = None,
    fork_at: int | None = None,
    action: int = 6,
    decrees: dict[int, Directive] | None = None,
    fork_db: str | None = None,
) -> SandboxResult:
    """The INTERVENE + VERIFY steps, as one counterfactual.

    The base archive is never written to; the counterfactual lands in its
    own file so it can be inspected with the same tools as any run.
    """
    if fork is None:
        if fork_at is None:
            raise ValueError("either fork or fork_at must be given")
        from causal_world.sandbox import fork_at_tick

        return fork_at_tick(
            db_path, fork_at, action,
            fork_db=fork_db or str(Path(db_path).with_name(
                Path(db_path).stem + ".fork.db")),
            directives=decrees,
        )
    return run_counterfactual(
        db_path, fork,
        fork_db=fork_db or str(Path(db_path).with_name(
            Path(db_path).stem + ".fork.db")),
        directives=decrees,
    )


def chronicle(db_path: str, agent: str = "agent:0") -> dict:
    """The final chronicle: the player's life, as the engine recorded it."""
    card = build_biography(db_path, agent)
    return {
        "fingerprint": card.fingerprint(),
        "meta": {
            "agent": card.meta.agent,
            "seed": card.meta.seed,
            "ruleset_version": card.meta.ruleset_version,
            "birth_tick": card.meta.birth_tick,
            "final_tick": card.meta.final_tick,
            "alive_at_end": card.meta.alive_at_end,
            "committed": card.meta.committed,
            "rejected": card.meta.rejected,
        },
        "death": (
            None if card.death is None
            else {
                "tick": card.death.tick,
                "operation": card.death.operation,
                "system": card.death.system,
                "die": card.death.die,
                "writes": [list(w) for w in card.death.writes],
            }
        ),
        "decisions": [
            {
                "action": d.action, "label": d.label, "count": d.count,
                "first_tick": d.first_tick, "last_tick": d.last_tick,
                "applied": d.applied,
            }
            for d in card.decisions
        ],
        "causes": (
            None if card.causes is None
            else {
                "root_tid": card.causes.root_tid,
                "depth_limit": card.causes.depth_limit,
                "truncated": card.causes.truncated,
                "nodes": [
                    {"tid": n.tid, "tick": n.tick, "system": n.system,
                     "operation": n.operation, "depth": n.depth, "kind": n.kind}
                    for n in card.causes.nodes
                ],
            }
        ),
        "conditions": [
            {"field": c.field, "system": c.system, "operation": c.operation,
             "writes": c.writes, "total_delta": c.total_delta}
            for c in card.conditions
        ],
        "legacy": {
            "children": [
                {"child": ch.child, "tick": ch.tick, "generation": ch.generation}
                for ch in card.legacy.children
            ],
            "ruined": [
                {"ruin": r.ruin, "tick": r.tick, "taken": r.taken}
                for r in card.legacy.ruined
            ],
        },
        "markdown": card.to_markdown(),
    }


def _budget_dict(report) -> dict:
    return {
        "net": report.net,
        "inflows": [
            {"system": e.system, "operation": e.operation,
             "total_delta": e.total_delta, "count": e.count}
            for e in report.inflows
        ],
        "outflows": [
            {"system": e.system, "operation": e.operation,
             "total_delta": e.total_delta, "count": e.count}
            for e in report.outflows
        ],
    }


def _agent_total(view: JournalView, meta: dict) -> int:
    """How many agent entities the world has (the dormant pool counts)."""
    rows = view.query(
        "SELECT COUNT(DISTINCT json_extract(value, '$[0]')) AS n "
        "FROM transitions, json_each(transitions.payload, '$.writes') "
        "WHERE json_extract(value, '$[0]') LIKE 'agent:%'"
    )
    return int(rows[0]["n"]) if rows else int(meta.get("agents") or 0)
