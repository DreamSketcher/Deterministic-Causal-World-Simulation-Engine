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
from causal_world.player import DecisionChannel, attach_player_channel
from causal_world.server import continuity
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
    def decide(self, seq: int, action: int) -> dict:
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
            self.channel.deliver(action)
            self.decisions[seq] = action
            self.sim.step()
            self.sim.journal.commit()  # ← the acceptance point
            frame = self._render(seq)
            self.frames[seq] = frame
            self.last_seq = seq
            self._advance()
            return frame

    def _render(self, seq: int) -> dict:
        st = self.sim.state
        action = self.decisions[seq]
        applied = 0 <= action < N_ACTIONS  # engine rule (systems/player.py)
        total, committed, rejected = self.sim.journal.counts()
        return {
            "type": "frame",
            "seq": seq,
            "tick": st.tick - 1,  # the step this decision just drove
            "applied": applied,
            "reject": None if applied else "out_of_range",
            "alive": bool(st.get(self.controlled, "alive")),
            "you": {
                f: st.get(self.controlled, f)
                for f in ("hunger", "health", "region", "last_action")
            },
            "journal": {
                "total": total,
                "committed": committed,
                "rejected": rejected,
                "hash": self.sim.journal.hash(),
            },
        }

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
