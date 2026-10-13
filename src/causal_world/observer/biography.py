"""BiographyCard v1: the causal ledger of one life, rendered as data.

v0.6 step 4. The card is a *pure function of the archive*: it issues a fixed
budget of six index queries (no new CausalQuery API) and assembles the
sections agreed in ``experiments/proposals/v06_step4_consult_pack_biographycard.md``:

* **meta** — run identity (seed, ruleset versions, tick range) plus the
  rejected-transition count: the world's «no»s are part of the biography;
* **death** — the last transition that wrote ``alive=False`` (with its die,
  if any: a threshold on the killing draw quantifies «how much was chance»);
* **causes** — the backward trace from the death node, trimmed to the
  agent's ORBIT (every entity any of their transitions touched). Trace
  semantics are last-writer chains: this section is «necessary causes», not
  «conditions» — conditions are the next section on purpose (the two must
  not be conflated, and a card that showed only one could not tell
  «what killed him» from «what wore him down»);
* **conditions** — per-field ``delta_profile`` (hunger, health): inflow and
  outflow of the two streams that decide a life, grouped by
  (system, operation) — «heal gave +40 across 4 uses vs −180 of erosion»
  comes straight from the write ledger, no narrative generation;
* **decisions** — every recorded player choice (one node per action, U3),
  consecutive identical ones GROUPED with a counter — presentation only, the
  journal keeps every tick (idle was a decision too, and the count says so);
* **legacy** — children whose ``parent_id`` names this agent, and ruins this
  agent drained (derived from the decisions rows, so the query budget stays
  six).

Explicitly deferred (contract §7 of the pack): counterfactual re-simulation,
post-death world section, forward-closure explosion, narrative prose. The
card's job is to prove the journal already answers «why did he die» — if it
does not, that is a finding for v2, not something to hide behind prose.

Deterministic: same archive -> byte-identical card (``fingerprint()`` is a
golden anchor for tests and for the step-5 «same seed + same decision stream
over the wire» check).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field

from causal_world.observer.journal import JournalView
from causal_world.query.index import QueryIndex
from causal_world.query.query import CausalQuery

#: the action card (mirrors systems/player.py; imported lazily to keep the
#: observer free of system dependencies)
_ACTION_NAMES = {
    0: "work",
    1: "migrate",
    2: "explore",
    3: "heal",
    4: "trade",
    5: "rest",
    6: "idle",
}

CAUSE_KINDS = ("choice", "chance", "law")


# --------------------------------------------------------------------- model


@dataclass(frozen=True)
class CardMeta:
    agent: str
    seed: str | None
    ruleset_version: str | None
    rng_version: str | None
    birth_tick: int
    final_tick: int
    transitions: int
    committed: int
    rejected: int
    alive_at_end: bool


@dataclass(frozen=True)
class DeathNode:
    tid: int
    tick: int
    system: str
    operation: str
    #: the killing die, if the death carried one: (purpose, roll, threshold)
    die: tuple[str, float, float] | None
    #: write the resolver recorded on this transition (e.g. health/hunger)
    writes: tuple[tuple[str, str, str, str], ...]  # entity, field, old, new


@dataclass(frozen=True)
class CauseNode:
    tid: int
    tick: int
    system: str
    operation: str
    depth: int
    kind: str  # choice | chance | law


@dataclass(frozen=True)
class CauseChain:
    root_tid: int
    depth_limit: int
    truncated: bool
    nodes: tuple[CauseNode, ...]


@dataclass(frozen=True)
class ConditionRow:
    field: str  # which stream: hunger / health
    system: str
    operation: str
    writes: int
    positive: int
    negative: int
    total_delta: float
    mean_delta: float | None


@dataclass(frozen=True)
class DecisionGroup:
    action: int  # raw card index; -1 for rejected attempts
    label: str
    count: int
    first_tick: int
    last_tick: int
    applied: bool
    #: raw draw values, for rejects (kept verbatim, e.g. 99)
    raw: tuple[int, ...]


@dataclass(frozen=True)
class RuinEvent:
    ruin: str
    tick: int
    taken: float


@dataclass(frozen=True)
class ChildEvent:
    child: str
    tick: int
    generation: int


@dataclass(frozen=True)
class Legacy:
    children: tuple[ChildEvent, ...]
    ruined: tuple[RuinEvent, ...]


@dataclass(frozen=True)
class BiographyCard:
    meta: CardMeta
    death: DeathNode | None
    causes: CauseChain | None
    conditions: tuple[ConditionRow, ...]
    decisions: tuple[DecisionGroup, ...]
    legacy: Legacy

    # ---- derived, no new queries ------------------------------------
    def fingerprint(self) -> str:
        payload = json.dumps(
            dataclasses.asdict(self), sort_keys=True, default=str
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_markdown(self) -> str:
        m = self.meta
        lines = [
            f"# Biography of {m.agent}",
            "",
            f"Run seed {m.seed} | ruleset {m.ruleset_version} | rng {m.rng_version}",
            "",
            f"- lived ticks {m.birth_tick}..{m.final_tick} "
            f"({'alive at end' if m.alive_at_end else 'died'})",
            f"- journal: {m.committed} committed / {m.rejected} rejected "
            f"(every «no» of the world is recorded)",
            f"- card fingerprint: `{self.fingerprint()[:16]}`",
        ]
        if self.death is None:
            lines += ["", "## Death", "", "No death transition recorded in the archive."]
        else:
            d = self.death
            lines += [
                "",
                "## Death",
                "",
                f"- T{d.tick} `{d.operation}` ({d.system}, tid {d.tid})",
            ]
            if d.die is not None:
                purpose, roll, thr = d.die
                lines.append(
                    f"- the die: roll {roll:.4f} < p {thr:.4f} — {purpose}"
                )
            else:
                lines.append("- no die: this death was a law, not a chance")
            for ent, fld, old, new in d.writes:
                lines.append(f"- wrote {ent}.{fld}: {old} -> {new}")
        if self.causes is not None:
            c = self.causes
            lines += [
                "",
                f"## Necessary causes (backward trace, depth<={c.depth_limit}"
                + (", TRUNCATED)" if c.truncated else ")"),
                "",
            ]
            shown = c.nodes[:30]
            for n in shown:
                indent = "  " * min(n.depth, 6)
                lines.append(
                    f"- {indent}T{n.tick} {n.kind}: `{n.operation}`"
                    f" ({n.system}) @depth {n.depth}"
                )
            if len(c.nodes) > len(shown):
                lines.append(
                    f"- … {len(c.nodes) - len(shown)} more causes in the card data "
                    f"(presentation cap only — the trace stays complete)"
                )
        if self.conditions:
            lines += ["", "## Conditions (what fed him, what wore him down)", ""]
            by_field: dict[str, list[ConditionRow]] = {}
            for r in self.conditions:
                by_field.setdefault(r.field, []).append(r)
            for fld, rows in by_field.items():
                lines.append(f"**{fld}**")
                for r in rows:
                    mean = f"{r.mean_delta:+.3f}" if r.mean_delta is not None else "—"
                    lines.append(
                        f"- `{r.operation}` ({r.system}): {r.writes} writes, "
                        f"Δ {r.total_delta:+.2f} (+{r.positive}/−{r.negative}), "
                        f"mean {mean}"
                    )
        lines += ["", "## Decisions (one node per action; idle counted too)", ""]
        if not self.decisions:
            lines.append("- none recorded — a life under pure law and chance")
        for g in self.decisions:
            span = (
                f"T{g.first_tick}"
                if g.first_tick == g.last_tick
                else f"T{g.first_tick}..T{g.last_tick}"
            )
            mark = "" if g.applied else f" [rejected: {','.join(map(str, g.raw))}]"
            x = f" ×{g.count}" if g.count > 1 else ""
            lines.append(f"- **{g.label}**{x} ({span}){mark}")
        lines += ["", "## Legacy", ""]
        if self.legacy.children:
            for ch in self.legacy.children:
                lines.append(
                    f"- child `{ch.child}` born T{ch.tick} (gen {ch.generation})"
                )
        else:
            lines.append("- no recorded descendants")
        if self.legacy.ruined:
            for rv in self.legacy.ruined:
                lines.append(
                    f"- drained `{rv.ruin}` at T{rv.tick} (−{rv.taken:.0f} food)"
                )
        else:
            lines.append("- left the ruins standing")
        return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ queries


def classify(transition) -> str:
    """choice | chance | law from the transition's draws — the card never
    re-implements the Q1 distinction, it reads the type the journal gives."""
    for d in transition.random_draws:
        if d.purpose == "player.decision" and d.threshold is None:
            return "choice"
        if d.threshold is not None:
            return "chance"
    return "law"


def _writes_on(t, entity: str, field_name: str):
    for w in t.writes:
        if w.entity == entity and w.field == field_name:
            return w
    return None


def _die_of(t):
    for d in t.random_draws:
        if d.threshold is not None:
            return (d.purpose, float(d.value), float(d.threshold))
    return None


def build_biography(
    db_path: str,
    agent: str = "agent:0",
    cache_path: str | None = None,
    cause_depth: int = 24,
    max_cause_nodes: int = 4000,
    list_limit: int = 100_000,
) -> BiographyCard:
    """Assemble the card from ONE archive with a SIX-query budget:

    1 death locator, 2 decisions, 3 profile(hunger), 4 profile(health),
    5 cause trace, 6 births-for-parents. Everything else is derived.
    """
    view = JournalView(db_path)
    try:
        with QueryIndex(view, cache_path or (db_path + ".qidx")) as idx:
            idx.build()  # incremental + identity-guarded (StaleIndexError)
            card = _assemble(view, CausalQuery(idx), agent, cause_depth,
                              max_cause_nodes, list_limit)
        return card
    finally:
        view.close()


def _assemble(view, q, agent, cause_depth, max_cause_nodes, list_limit):
    lo_tick, final_tick = view.tick_range()
    total, committed, rejected = view.counts()
    meta_all = view.meta_all()

    # -- 1. death: the last COMMITTED transition writing alive=False ------
    death_t = None
    for t in q.writes_to(agent, "alive").committed_only().list(list_limit):
        w = _writes_on(t, agent, "alive")
        if w is not None and not w.new:
            if death_t is None or (t.tick, t.id or 0) > (death_t.tick, death_t.id or 0):
                death_t = t
    death = None
    if death_t is not None:
        death = DeathNode(
            tid=death_t.id,
            tick=death_t.tick,
            system=death_t.system,
            operation=death_t.operation,
            die=_die_of(death_t),
            writes=tuple(
                (w.entity, w.field, str(w.old), str(w.new)) for w in death_t.writes
            ),
        )
    death_tick = death_t.tick if death_t is not None else final_tick

    # birth window: genesis tick. The controlled agent of the game is always
    # a genesis agent (dormant-pool children are never player-controlled),
    # so no 7th query is spent locating birth_tick; for a pool-born subject
    # (an NPC card) the window simply starts at genesis — a superset, never
    # missing anything, which is the safe direction for an explanation.
    birth_tick = lo_tick

    # -- 2. decisions ------------------------------------------------------
    events: list[dict] = []
    orbit: set[str] = {agent}
    # operation-scoped: genesis also pre-writes last_action=-1 on every
    # agent; only the player system's transitions are decisions
    for t in q.operation("player.act").writes_to(agent, "last_action").committed_only().list(list_limit):
        w = _writes_on(t, agent, "last_action")
        if w is None:
            continue
        raw = None
        for d in t.random_draws:
            if d.purpose == "player.decision":
                raw = int(d.value)
                break
        effects = []
        for e in t.writes:
            orbit.add(e.entity)
            if e.field not in ("alive", "last_action") and e.entity != agent:
                effects.append(e)
        for r in t.reads:
            orbit.add(r.entity)
        events.append(
            {
                "tick": t.tick,
                "action": int(w.new),
                "raw": raw,
                "applied": int(w.new) >= 0,
                "effects": effects,
            }
        )
    events.sort(key=lambda e: e["tick"])

    # ruin drain derived from the player's own writes on agent-adjacent ruins
    ruined: list[RuinEvent] = []
    for e in events:
        for w in e["effects"]:
            if w.entity.startswith("ruin:") and w.field == "resource_food":
                taken = float(w.old or 0.0) - float(w.new or 0.0)
                if taken > 0:
                    ruined.append(RuinEvent(w.entity, e["tick"], taken))

    # group consecutive identical decisions (presentation; the journal stays)
    decisions: list[DecisionGroup] = []
    for e in events:
        label = _ACTION_NAMES.get(e["action"], f"rejected({e['raw']})")
        if (
            decisions
            and decisions[-1].action == e["action"]
            and decisions[-1].label == label  # rejects keep distinct raw values
            and decisions[-1].applied == e["applied"]
            and decisions[-1].last_tick == e["tick"] - 1
        ):
            decisions[-1] = dataclasses.replace(
                decisions[-1],
                count=decisions[-1].count + 1,
                last_tick=e["tick"],
                raw=decisions[-1].raw + (e["raw"] if e["raw"] is not None else (),),
            )
        else:
            decisions.append(
                DecisionGroup(
                    action=e["action"],
                    label=label,
                    count=1,
                    first_tick=e["tick"],
                    last_tick=e["tick"],
                    applied=e["applied"],
                    raw=(e["raw"],) if e["raw"] is not None else (),
                )
            )

    # -- 3+4. conditions ---------------------------------------------------
    conditions: list[ConditionRow] = []
    for fld in ("hunger", "health"):
        for r in q.delta_profile(entity=agent, field_name=fld,
                                 tick_start=0, tick_end=death_tick):
            conditions.append(
                ConditionRow(
                    field=fld,
                    system=r.system,
                    operation=r.operation,
                    writes=r.writes,
                    positive=r.positive,
                    negative=r.negative,
                    total_delta=float(r.total_delta),
                    mean_delta=(None if r.mean_delta is None else float(r.mean_delta)),
                )
            )
    conditions.sort(key=lambda r: (r.field, -abs(r.total_delta)))

    # -- 5. necessary causes: backward trace, trimmed to the orbit --------
    causes = None
    if death_t is not None:
        trace = q.trace(
            death_t.id, "backward", depth=cause_depth, max_nodes=max_cause_nodes
        )
        nodes: list[CauseNode] = []
        for t in trace.nodes:
            touches = any(
                e.entity in orbit for e in list(t.writes) + list(t.reads)
            )
            if not touches and trace.depths.get(t.id, -1) != 0:
                continue  # outside this life's orbit: not part of HIS story
            nodes.append(
                CauseNode(
                    tid=t.id,
                    tick=t.tick,
                    system=t.system,
                    operation=t.operation,
                    depth=trace.depths.get(t.id, -1),
                    kind=classify(t),
                )
            )
        causes = CauseChain(
            root_tid=death_t.id,
            depth_limit=cause_depth,
            truncated=trace.truncated,
            nodes=tuple(nodes),
        )

    # -- 6. legacy: children via parent_id on birth transitions -----------
    children: list[ChildEvent] = []
    for t in q.operation("agent.birth").committed_only().list(list_limit):
        pid = next(
            (w for w in t.writes if w.field == "parent_id" and w.new == agent), None
        )
        if pid is None:
            continue
        gen = next(
            (
                w.new
                for w in t.writes
                if w.entity == pid.entity and w.field == "generation"
            ),
            0,
        )
        children.append(ChildEvent(child=pid.entity, tick=t.tick, generation=int(gen)))
    children.sort(key=lambda c: (c.tick, c.child))

    meta = CardMeta(
        agent=agent,
        seed=meta_all.get("seed"),
        ruleset_version=meta_all.get("ruleset_version"),
        rng_version=meta_all.get("rng_version"),
        birth_tick=birth_tick,
        final_tick=final_tick,
        transitions=total,
        committed=committed,
        rejected=rejected,
        alive_at_end=death_t is None,
    )
    return BiographyCard(
        meta=meta,
        death=death,
        causes=causes,
        conditions=tuple(conditions),
        decisions=tuple(decisions),
        legacy=Legacy(children=tuple(children), ruined=tuple(ruined)),
    )
