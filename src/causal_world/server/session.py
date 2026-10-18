"""Game session: the authoritative loop behind the step-5/6 protocols.

Contract: v06_step5_protocol_contract.md (§1-§5) and the continuity
amendments of v06_step6_continuity_contract.md §9. The five ratified rules,
in code:

1. execution order — ``decide`` runs validate → deliver → step → commit →
   frame; the decision is ACCEPTED at ``journal.commit()`` (§1).
2. idempotency — ``client_seq`` gates delivery: re-delivery of an applied
   seq replays the stored frame and never re-steps; same seq, different
   action, is ``conflict``; a gap is ``seq_gap`` with resync info (§2).
3. server authority — the client sends actions, never state; world config
   is read once at creation (or from the archive meta on takeover) (§3).
4. lifecycle — death ends the LIFE: the session flushes, registers the life
   row (end/to_tick/decisions + final_state_hash) and finalizes the writer
   itself (Q2 — a finalized writer releases the world for the next life),
   but the session object REMAINS for results: bio/autopsy build from the
   archive (JournalView) live and after finalize; close is idempotent.
   Agent death ≠ world extinction: the world may simply have no heir left
   (no_heir, terminal — see continuity.py).
5. transport-invariance — nothing here imports websockets.

Continuity: a Session is either a fresh world (registers life 1 in the
identity meta) or a TAKEOVER: the archive alone replays every previous
life's stream with its pointer schedule (verified — TakeoverError before
any write), the heir is chosen by the deterministic rule, and the new life
registers itself. No journal-format change; ids/ticks continue by
construction.

The channel is fed EXACTLY one action per live tick by ``decide`` — the
session blocks on the client (transport), never the channel on a timeout
(Q1: a disconnect is not an in-world action, so no idle fallback is ever
reachable in a WS session).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from causal_world import create_world
from causal_world.observer.biography import build_biography
from causal_world.observer.deaths import DeathClassifier
from causal_world.observer.journal import JournalView
from causal_world.observer.slice import CellSlice, WorldIndex
from causal_world.observer.goal import goals as goal_verdicts
from causal_world.observer.situation import (
    FieldHistory,
    StateView,
    growth_limit,
    resettle_opportunities,
    situations,
)
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.server import continuity
from causal_world.systems.directive import (
    Directive,
    DirectiveChannel,
    DirectiveSystem,
    ScheduleResult,
)
from causal_world.systems.player import ACTION_NAMES, N_ACTIONS
from causal_world.world.rules import get_ruleset


@dataclass
class ProtocolError(Exception):
    """A rejected message — the world was not touched (all raises in
    ``decide`` precede delivery, or follow an already-committed step)."""

    code: str
    msg: str
    seq: int | None = None
    extra: dict | None = None

    def to_dict(self) -> dict:
        out = {"type": "error", "code": self.code, "msg": self.msg}
        if self.seq is not None:
            out["seq"] = self.seq
        if self.extra:
            out.update(self.extra)
        return out


class Session:
    #: states: "awaiting" (a decision may be delivered) → "finalized"
    #: (life ended — death, tick_limit or close — writer flushed and closed,
    #: results read from the file; decide refused)
    def __init__(
        self,
        seed: int,
        *,
        ruleset: str = "player_life",
        regions: int = 2,
        agents: int = 60,
        db_path: str | None = None,
        db_dir: str = ".",
        max_ticks: int = 4000,
        tail_ticks: int = 0,
        controlled: str = "agent:0",
        session_id: str | None = None,
    ) -> None:
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.config = {
            "seed": int(seed),
            "ruleset": str(ruleset),
            "regions": int(regions),
            "agents": int(agents),
            "max_ticks": int(max_ticks),
            "tail_ticks": int(tail_ticks),
            "controlled": str(controlled),
        }
        self.db_path = (
            str(db_path)
            if db_path is not None
            else str(Path(db_dir) / f"life-{self.session_id}.db")
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.sim = create_world(
            seed=self.config["seed"],
            ruleset=get_ruleset(self.config["ruleset"]),
            ticks=0,
            regions=self.config["regions"],
            agents=self.config["agents"],
            persist=self.db_path,
        )
        # non-blocking channel: the SESSION waits on the client, the channel
        # is never empty at step() time (one delivery per one step)
        self.channel = DecisionChannel()
        attach_player_channel(self.sim, self.channel, self.config["controlled"])
        self.controlled = self.config["controlled"]
        # The civic layer (v0.7): if the world runs the directive system,
        # the player may also enact laws. A world without it simply has
        # no decree channel — the ruleset, not the transport, decides.
        self.decrees = DirectiveChannel()
        self._last_decree: ScheduleResult | None = None
        # The live memory of the situation layer (v0.9): the fields the
        # goal layer needs to say WHEN a problem began and what it cost.
        # It is a READ-ONLY projection: nothing here is ever written back
        # into the world.
        self._history = FieldHistory()
        for system in self.sim.systems:
            if isinstance(system, DirectiveSystem):
                system.channel = self.decrees

        self.decisions: dict[int, int] = {}
        self.frames: dict[int, dict] = {}
        self.last_seq = 0
        self.state = "awaiting"
        # step 6: a world REGISTERS its lives in the identity meta — one
        # JSON row per life; the journal format is untouched, and the
        # replayed stream is verified against the rows, never replaced by
        # hidden session state (Check A).
        self.life_n = 1
        self.succession = "genesis"
        self._from = self.sim.state.tick
        self._write_life(end=None, to_tick=None)
        self.death_tick: int | None = None
        self.finish_reason: str | None = None
        self.final_hash: str | None = None
        self._finished_payload: dict | None = None
        self._lock = threading.RLock()
        # v0.12/2b: one index for the frame path. It is built ONCE (one
        # pass at session start) and then advanced by the committed
        # writes of each tick; a frame reads a cell slice from it instead
        # of materialising every (entity, field) pair in the world.
        self._index: WorldIndex | None = WorldIndex.from_state(
            self.sim.state, journal=self.sim.journal
        )
        self._indexed_tick: int = self.sim.state.tick - 1

    # ------------------------------------------------------------- takeover
    @classmethod
    def takeover(cls, db_path: str, *, max_ticks: int = 4000,
                 tail_ticks: int = 0, session_id: str | None = None) -> "Session":
        """Open the NEXT life on an existing world archive.

        Reproduction first (read-only replay verified against the archive),
        heir selection second (pure function of the reproduced head),
        registration last — a refused takeover never writes: no heir means
        no new archive, no pool refill, no restart (§9, terminal).
        """
        try:
            sim, archive, lives = continuity.replay_head(db_path)
        except continuity.TakeoverError as e:
            raise ProtocolError(e.code, e.msg, None, dict(e.extra)) from e
        prev = lives[-1]
        heir = continuity.choose_heir(prev["agent"], continuity.agents_map(sim.state))
        if heir is None:
            archive.close()  # nothing was written; the file stays as it was
            alive = sum(
                1
                for a in sim.state.entities_with_prefix("agent:")
                if sim.state.get(a, "alive")
            )
            raise ProtocolError(
                "no_heir",
                "the world has no living descendant and no living agent: "
                "the dynasty is terminal — results remain readable",
                None,
                {"alive_agents": alive, "world": str(db_path)},
            )
        agent, succession = heir
        self = cls.__new__(cls)
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.config = {
            "seed": int(archive.get_meta("seed") or 0),
            "ruleset": continuity.ruleset_name_for_version(
                archive.get_meta("ruleset_version") or ""
            ),
            "regions": int(archive.get_meta("regions") or 0),
            "agents": int(archive.get_meta("agents") or 0),
            "max_ticks": int(max_ticks),
            "tail_ticks": int(tail_ticks),
            "controlled": agent,
        }
        self.db_path = str(db_path)
        self.sim = sim  # journal/index already handed over by replay_head
        self.channel = DecisionChannel()
        attach_player_channel(sim, self.channel, agent)
        # A takeover gets its own (empty) order channel and its own live
        # history: the laws of the previous life stay in the archive, and
        # the new life's goal feed starts at the moment it takes over.
        self.decrees = DirectiveChannel()
        self._last_decree = None
        self._history = FieldHistory()
        for system in sim.systems:
            if isinstance(system, DirectiveSystem):
                system.channel = self.decrees
        self.controlled = agent
        self.life_n = prev["n"] + 1
        self.succession = succession
        self._from = sim.state.tick
        self.decisions, self.frames = {}, {}
        self.last_seq = 0
        self.state = "awaiting"
        self.death_tick, self.finish_reason = None, None
        self.final_hash, self._finished_payload = None, None
        self._lock = threading.RLock()
        self._index = WorldIndex.from_state(
            self.sim.state, journal=self.sim.journal
        )
        self._indexed_tick = self.sim.state.tick - 1
        self._write_life(end=None, to_tick=None)
        archive.commit()
        if sim.state.tick >= max_ticks:
            self._finish("tick_limit")
        return self

    # ---------------------------------------------------------- life rows
    def _write_life(self, end, to_tick) -> None:
        key, value = continuity.life_record(
            self.life_n, self.controlled, self._from, self.succession,
            end=end, to_tick=to_tick, decisions=self.last_seq,
            session=self.session_id,
        )
        self.sim.journal.set_meta(key, value)

    # ------------------------------------------------------------- views ---
    def _decree_card(self) -> dict:
        """The levers this world offers (empty without a civic layer).

        The card comes from the world's own directive system, so a v0.7
        world offers three levers and a v0.8 spatial world four — the
        client never has to know the difference.
        """
        for system in self.sim.systems:
            if isinstance(system, DirectiveSystem):
                return system.kinds()
        return {}

    def welcome(self) -> dict:
        return {
            "type": "welcome",
            "session_id": self.session_id,
            "tick": self.sim.state.tick,
            "alive": self._alive(),
            "last_seq": self.last_seq,
            "state": self.state,
            "config": dict(self.config),  # server authority: echoed, not set
            "db_path": self.db_path,
            "action_card": dict(ACTION_NAMES),
            # The civic card (v0.7/v0.8): empty for a world without the
            # civic layer, so the client knows the difference between "no
            # laws exist" and "laws exist but none offered".
            "decree_card": self._decree_card(),
            "life": {
                "n": self.life_n,
                "agent": self.controlled,
                "succession": self.succession,
            },
        }

    def take_finished_event(self) -> dict | None:
        """One-shot; carries the life verdict (§9: finished must be
        informative without a live writer — death auto-finalizes)."""
        out, self._finished_payload = self._finished_payload, None
        return out

    # ------------------------------------------------------------ decide ---
    def decide(self, seq: int, action: int,
               decree: dict | None = None) -> dict:
        """Apply one decision (and optionally one decree) and step the world.

        The decree is scheduled for the tick AFTER this one: a decree
        enacted in the same tick as a step would be read by the law
        systems from the very same snapshot, and the moment a law enters
        force must stay derived (one coherent snapshot per tick), not
        depend on message ordering inside a tick.
        """
        with self._lock:
            if self.state == "finalized":
                raise ProtocolError("finalized", "life is over and finalized", seq)
            prior = self.decisions.get(seq)
            if prior is not None:  # already applied: replay, never re-step
                if prior == action:
                    return self.frames[seq]
                raise ProtocolError(
                    "conflict", f"seq {seq} applied with action {prior}", seq
                )
            if seq != self.last_seq + 1:
                raise ProtocolError(
                    "seq_gap",
                    f"expected seq {self.last_seq + 1}",
                    seq,
                    {"resync": {"last_seq": self.last_seq}},
                )
            # — from here the step happens; §1 order —
            # The decree is validated BEFORE the decision is delivered: a
            # refused decree must not consume the seq (the client's next
            # message would otherwise be answered as a replay of a
            # decision that never happened).
            if decree is not None:
                self._last_decree = self._schedule_decree(decree)
            self.channel.deliver(action)
            self.decisions[seq] = action
            self.sim.step()
            self.sim.journal.commit()  # ← the acceptance point
            self._sample_history()
            frame = self._render(seq)
            # The answer rides ONE frame: the frame that carries the
            # decision which gave the order. Replays keep it (the frame
            # is stored); later frames do not repeat a stale banner.
            self._last_decree = None
            self.frames[seq] = frame
            self.last_seq = seq
            self._advance()
            return frame

    def _schedule_decree(self, decree: dict) -> ScheduleResult:
        """Schedule a civic decree for the next tick (validated first).

        A world without the civic layer refuses the decree instead of
        silently dropping it — a law the player thinks they enacted but
        which never happened is exactly the kind of lie this repo
        refuses to tell.

        The TARGET of a decree is whatever the world's law works on: a
        region in the v0.7 world, a cell in the v0.8 spatial world. The
        target must exist — a decree addressed to nothing is refused,
        not silently ignored.

        The RESULT is explicit (v0.9): accepted / queued / rejected. An
        order is never lost silently — the client is told which of the
        three happened, and the journal records the tick the order was
        actually enacted at.
        """
        directive_system = next(
            (s for s in self.sim.systems if isinstance(s, DirectiveSystem)), None
        )
        if directive_system is None:
            raise ProtocolError(
                "no_civic_layer",
                "this world runs no directive system: the chosen ruleset "
                "has no civic layer, so decrees cannot be enacted",
                None,
                {"ruleset": self.config["ruleset"]},
            )
        kind = decree.get("kind")
        target = decree.get("target") or decree.get("region")
        param = float(decree.get("param", 0.25))
        if not isinstance(kind, int) or kind not in directive_system.KIND_NAMES:
            raise ProtocolError(
                "malformed",
                f"decree kind must be one of {sorted(directive_system.KIND_NAMES)}",
                None,
            )
        if not isinstance(target, str) or not target:
            raise ProtocolError("malformed", "decree target must be an entity id",
                                None)
        if target not in self._decree_targets(directive_system):
            raise ProtocolError(
                "unknown_target",
                f"no such decree target in this world: {target!r}",
                None,
                {
                    "target_prefix": directive_system.TARGET_PREFIX,
                    "rule": "the target must exist in the world",
                },
            )
        return self.decrees.schedule(
            self.sim.state.tick + 1, Directive(kind, target, param)
        )

    def _decree_targets(self, directive_system) -> set:
        """The entities this world's law can be written upon."""
        return set(
            self.sim.state.entities_with_prefix(directive_system.TARGET_PREFIX)
        )

    def _orders_view(self) -> dict:
        """The order ledger: the orders waiting and the ones on the calendar.

        The tick of an order is the tick it will be ENACTED at; for a
        queued order the tick is the one it was asked for, and the real
        tick is in the journal (``player.directive``).
        """
        pending = [
            {"requested_tick": tick, "kind": d.kind, "name": d.name,
             "target": d.region, "param": d.param}
            for tick, d in self.decrees.pending()
        ]
        return {
            "pending": pending,
            "scheduled": [
                {"tick": tick, "kind": d.kind, "name": d.name,
                 "target": d.region, "param": d.param}
                for tick, d in sorted(self.decrees.scheduled().items())
                if tick >= self.sim.state.tick
            ],
        }

    def look(self) -> dict:
        """The world as it is NOW, without a decision (v0.13, read-only).

        The same status block a frame carries (``_status``), but no step is
        taken and nothing is written: the client draws the map before the
        first decision and after the life has ended. ``tick`` is the last
        completed step (-1 before the first one), as in a frame.
        """
        view = self._frame_view()
        out = {"type": "view", "tick": self.sim.state.tick - 1}
        out.update(self._status(view))
        return out

    def _status(self, view: CellSlice) -> dict:
        """The part of a reply that describes the world (frame and view)."""
        st = self.sim.state
        total, committed, rejected = self.sim.journal.counts()
        return {
            "alive": bool(st.get(self.controlled, "alive")),
            "you": {
                f: st.get(self.controlled, f)
                for f in ("hunger", "health", "region", "last_action")
            },
            # The world view (contract §1.5: "the world section of the
            # frame is read from sim.state, view-only"). It is a READ of
            # the live state — never a write — and it is what lets a
            # client draw the living map without a second protocol.
            "world": self._world_view(view),
            # The order ledger, as the client sees it (v0.9): what
            # happened to the order of this message, and what is still
            # waiting for a free tick. Nothing here is hidden state —
            # the journal is the truth about what was ENACTED.
            "orders": self._orders_view(),
            "journal": {
                "total": total,
                "committed": committed,
                "rejected": rejected,
                "hash": self.sim.journal.hash(),
            },
        }

    def _render(self, seq: int) -> dict:
        st = self.sim.state
        # ONE slice feeds the map, the situations, the goal cards and the
        # resettlement card of this frame: they cannot disagree, and none
        # of them builds a full view of the world.
        view = self._frame_view()
        action = self.decisions[seq]
        applied = 0 <= action < N_ACTIONS  # engine rule (systems/player.py)
        out = {
            "type": "frame",
            "seq": seq,
            "tick": st.tick - 1,  # the step this decision just drove
            "applied": applied,
            "reject": None if applied else "out_of_range",
        }
        out.update(self._status(view))
        # the civic order that rode this decision (v0.9), if any
        out["decree"] = (
            self._last_decree.to_dict() if self._last_decree else None
        )
        return out

    def _frame_view(self) -> CellSlice:
        """The slice this frame is drawn from — read-only, index-backed.

        The index is advanced by every finished tick exactly once, so a
        tail epilogue that steps several times does not leave it behind.
        """
        state = self.sim.state
        if self._index is None:
            self._index = WorldIndex.from_state(
                state, journal=self.sim.journal
            )
            self._indexed_tick = state.tick - 1
        last = state.tick - 1
        while self._indexed_tick < last:
            self._indexed_tick += 1
            self._index.advance(self.sim.journal, self._indexed_tick)
        return CellSlice.from_state(
            state, self._index, tick_of=self._tick_of
        )

    def _world_view(self, view) -> dict:
        """The world as the client may see it (view-only).

        Reads the frame's ``CellSlice`` — the same object the situations,
        goals and the resettlement card are computed from. No history, no
        writes, and no full ``StateView``: a frame pays for the cells it
        draws, not for every entity in the world (v0.12/2b). The
        civic law parameters are included when the world runs the civic
        layer, so the map can show WHICH law a region (or a cell) lives
        under. The v0.8 spatial world adds the CELLS: the map is a grid
        of cells, each with its own soil, food, people and law.

        The SITUATIONS (the computed problem feed of v0.8) come with the
        frame: they are derived from the same state and cite the
        transition ids they rest on.
        """
        st = self.sim.state
        regions = []
        for region in view.entities_with_prefix("region:"):
            row = {
                "id": region,
                "population": view.get(region, "population"),
                "workers": view.get(region, "workers"),
                "soil_fertility": view.get(region, "soil_fertility"),
                "food_stock": view.get(region, "food_stock"),
                "temperature": view.get(region, "temperature"),
                "rainfall": view.get(region, "rainfall"),
                "disease_load": view.get(region, "disease_load"),
            }
            if view.has(region, "labor_diversion"):
                row["law"] = {
                    "labor_diversion": view.get(region, "labor_diversion"),
                    "water_aid": view.get(region, "water_aid"),
                    "rest_until": view.get(region, "rest_until"),
                    "resting": int(view.get(region, "rest_until") or 0) > st.tick,
                }
            regions.append(row)

        cells = []
        for cell in view.entities_with_prefix("cell:"):
            row = {
                "id": cell,
                "region": view.get(cell, "region"),
                "x": view.get(cell, "cell_x"),
                "y": view.get(cell, "cell_y"),
                "population": view.get(cell, "population"),
                "workers": view.get(cell, "workers"),
                "soil_fertility": view.get(cell, "soil_fertility"),
                "food_stock": view.get(cell, "food_stock"),
                "rain_factor": view.get(cell, "rain_factor"),
                # v0.10: wild land is drawn as land waiting, not as a
                # dead cell; the limit says what blocks growth (if
                # anything) so the player does not have to guess.
                "land_active": (
                    view.get(cell, "land_active")
                    if view.has(cell, "land_active") else 1
                ),
                "capacity": (
                    float(view.get(cell, "pop_base") or 0)
                    * (1.0 + float(view.get(cell, "soil_fertility") or 0))
                ),
                "claim_state": (
                    view.get(cell, "claim_state")
                    if view.has(cell, "claim_state") else 0
                ),
                "terraces": (
                    view.get(cell, "terraces")
                    if view.has(cell, "terraces") else 0
                ),
                # v0.11: what the resettlement orders did to this cell.
                # Absent fields read as zero, so older worlds draw the
                # same map and never invent a resettlement.
                "resettled_in": (
                    view.get(cell, "resettled_in")
                    if view.has(cell, "resettled_in") else 0
                ),
                "resettled_out": (
                    view.get(cell, "resettled_out")
                    if view.has(cell, "resettled_out") else 0
                ),
                "resettle_state": (
                    view.get(cell, "resettle_state")
                    if view.has(cell, "resettle_state") else 0
                ),
                "last_source": (
                    view.get(cell, "last_source")
                    if view.has(cell, "last_source") else None
                ),
            }
            if row["land_active"]:
                row["limit"] = growth_limit(
                    view, cell, int(st.tick)
                )["limit"]
            if view.has(cell, "labor_diversion"):
                row["law"] = {
                    "labor_diversion": view.get(cell, "labor_diversion"),
                    "water_aid": view.get(cell, "water_aid"),
                    "rest_until": view.get(cell, "rest_until"),
                    "nursery": view.get(cell, "nursery"),
                    "resting": int(view.get(cell, "rest_until") or 0) > st.tick,
                }
            cells.append(row)

        # the counters come from the index: a scan over all agents would
        # make the frame O(world) again
        alive = getattr(view, "alive_agents", None)
        if alive is None:
            alive = sum(
                1 for a in view.entities_with_prefix("agent:")
                if view.get(a, "alive")
            )
        total_agents = getattr(view, "total_agents", None)
        if total_agents is None:
            total_agents = len(view.entities_with_prefix("agent:"))
        _, alerts = self._situation_alerts(view)
        return {
            "tick": st.tick,
            "regions": regions,
            "cells": cells,
            "alive_agents": alive,
            "total_agents": total_agents,
            "situations": [a.to_dict() for a in alerts],
            "goals": self._goals(alerts, view),
            # v0.11: the destinations a resettlement order could use,
            # read with the SAME arithmetic the system will apply.
            "resettle": self._resettle_view(view),
        }

    def _resettle_view(self, view: StateView) -> list[dict]:
        """The resettlement card: room, habitability, donor and price.

        Empty for worlds without the resettlement system, so a v0.10
        client sees no card rather than a card of zeros.
        """
        for system in self.sim.systems:
            if system.name != "ResettlementDirectiveSystem":
                continue
            return resettle_opportunities(
                view,
                int(self.sim.state.tick),
                soil_min=system.RESETTLE_SOIL_MIN,
                food_pc_min=system.RESETTLE_FOOD_PC_MIN,
                cost_base=system.RESETTLE_FOOD_BASE,
                cost_per_step=system.RESETTLE_FOOD_PER_STEP,
                max_per_order=system.RESETTLE_MAX_PER_ORDER,
            )
        return []

    def _sample_history(self) -> None:
        """Remember the few fields the goal layer reads — one sample a tick.

        Appending the CURRENT values (instead of re-reading the journal)
        keeps the live path O(cells) per tick and makes it read exactly
        what the world was at that tick: the same snapshot the frame is
        drawn from.
        """
        st = self.sim.state
        tick = st.tick - 1  # the step that just ran (state.tick is next)
        # advance the index here and reuse the same slice in the frame:
        # the sample and the picture of a tick must describe one world
        view = self._frame_view()
        scopes = (view.cells or view.regions)
        for scope in scopes:
            for field_name in ("population", "food_stock", "soil_fertility",
                               "births_total"):
                if st.has(scope, field_name):
                    self._history.add(scope, field_name, tick,
                                      st.get(scope, field_name))

    def _situation_alerts(self, view=None):
        """The current alerts as objects (shared by the feed and the goals).

        The caller passes the frame's slice; a caller without one (the
        analysis endpoint) gets a slice built on demand — never a full
        StateView, which would put the whole world back on the frame path.
        """
        try:
            if view is None:
                view = self._frame_view()
            return view, situations(
                view,
                current_tick=self.sim.state.tick,
                history=self._history,
            )
        except Exception:
            return None, []

    def _situations(self) -> list:
        """The problem feed of the world (v0.8), computed from the state.

        Read-only and cheap: the values come from the live state and
        their provenance (the transition that last wrote them) from the
        state's own index. The history-based readings (how long a cell
        has been empty) are served by the analysis endpoint, where a full
        pass over the journal is affordable.
        """
        try:
            _, alerts = self._situation_alerts()
            return [a.to_dict() for a in alerts]
        except Exception:
            return []  # a failed feed never breaks the frame

    def _goals(self, alerts, view=None) -> list:
        """Goal verdicts of the live world (v0.9) — read-only."""
        try:
            if view is None:
                view = self._frame_view()
            return [
                v.to_dict()
                for v in goal_verdicts(
                    self._history, view, alerts,
                    tick=self.sim.state.tick - 1,
                )
            ]
        except Exception:
            return []

    def _tick_of(self, tid: int | None) -> int | None:
        if tid is None:
            return None
        try:
            return self.sim.journal.by_id(tid).tick
        except Exception:
            return None

    def _alive(self) -> bool:
        return bool(self.sim.state.get(self.controlled, "alive"))

    def _advance(self) -> None:
        if self._alive():
            if self.sim.state.tick >= self.config["max_ticks"]:
                self._finish("tick_limit")
            return
        if self.death_tick is None:
            self.death_tick = self.sim.state.tick - 1
        for _ in range(self.config["tail_ticks"]):  # optional epilogue
            if self.sim.state.tick >= self.config["max_ticks"]:
                break
            self.sim.step()
            self.sim.journal.commit()
        self._finish("death")

    def _finish(self, reason: str) -> None:
        self.finish_reason = reason
        payload = {
            "type": "finished",
            "reason": reason,
            "death_tick": self.death_tick,
            "life": {
                "n": self.life_n,
                "agent": self.controlled,
                "succession": self.succession,
            },
        }
        if reason == "death":  # one card build per life end (P3 profiling)
            try:
                card = build_biography(self.db_path, self.controlled)
                payload["bio_fingerprint"] = card.fingerprint()
                if card.death is not None:
                    with self._journal_view() as view:
                        payload["autopsy"] = {
                            "operation": card.death.operation,
                            "label": DeathClassifier(view).classify(
                                self.controlled, card.death.tid
                            ),
                        }
            except Exception as e:  # a refused autopsy never loses the frame
                payload["autopsy_error"] = str(e)
        self._finished_payload = payload
        self.close()  # Q2 ratified: the life finalizes its own writer

    # ------------------------------------------------- results from disk ---
    def _journal_view(self) -> JournalView:
        # same read path while live (writer committed every step, WAL lets
        # ro readers in) and after finalize — one code path, archive-first
        return JournalView(self.db_path)

    def bio(self, md: bool = False, agent: str | None = None) -> dict:
        agent = agent or self.controlled
        card = build_biography(self.db_path, agent)
        out = {
            "type": "biography",
            "agent": agent,
            "fingerprint": card.fingerprint(),
            "life": {"n": self.life_n, "succession": self.succession}
            if agent == self.controlled else None,
            "meta": {
                "birth_tick": card.meta.birth_tick,
                "final_tick": card.meta.final_tick,
                "committed": card.meta.committed,
                "rejected": card.meta.rejected,
                "alive_at_end": card.meta.alive_at_end,
            },
            "death": (
                None
                if card.death is None
                else {"tick": card.death.tick, "operation": card.death.operation}
            ),
            "decisions": {
                "runs": len(card.decisions),
                "total": sum(g.count for g in card.decisions),
            },
        }
        if md:
            out["md"] = card.to_markdown()
        return out

    def autopsy(self) -> dict:
        if self.state == "awaiting" and self._alive():
            raise ProtocolError("alive", "the agent is alive: nothing to autopsy")
        card = build_biography(self.db_path, self.controlled)
        death = card.death
        if death is None:  # ended while alive (tick_limit / abdicate)
            return {"type": "autopsy", "alive": True, "death_tick": None,
                    "life_end": self.finish_reason,
                    "bio_fingerprint": card.fingerprint()}
        with self._journal_view() as view:
            label = DeathClassifier(view).classify(self.controlled, death.tid)
        return {
            "type": "autopsy",
            "alive": False,
            "death_tick": death.tick,
            "operation": death.operation,
            "system": death.system,
            "die": (
                None if death.die is None
                else {"purpose": death.die[0], "roll": death.die[1],
                      "threshold": death.die[2]}
            ),
            "label": label,
            "causes": (
                None if card.causes is None
                else {"nodes": len(card.causes.nodes),
                      "depth_limit": card.causes.depth_limit,
                      "truncated": card.causes.truncated}
            ),
            "bio_fingerprint": card.fingerprint(),
        }

    def close(self) -> dict:
        with self._lock:
            if self.state == "finalized":
                return self._closed_payload(note="already finalized")
            self._write_life(end=self.finish_reason or "abdicate",
                             to_tick=self.sim.state.tick)
            self.sim.journal.set_meta(
                continuity.FINAL_STATE_KEY, self.sim.state.hash()
            )
            self.sim.journal.commit()
            self.final_hash = self.sim.journal.hash()
            self.sim.journal.close()
            self.state = "finalized"
            return self._closed_payload()

    def _closed_payload(self, note: str | None = None) -> dict:
        out = {
            "type": "closed",
            "session_id": self.session_id,
            "hash": self.final_hash,
            "reason": self.finish_reason or "abdicate",
            "db_path": self.db_path,
            "life": {"n": self.life_n, "agent": self.controlled,
                     "succession": self.succession},
        }
        if note:
            out["note"] = note
        return out
