"""Game session: the authoritative loop behind the step-5 protocol.

Contract: experiments/proposals/v06_step5_protocol_contract.md. The five
ratified rules, in code:

1. execution order — ``decide`` runs validate → deliver → step → commit →
   frame; the decision is ACCEPTED at ``journal.commit()`` (§1).
2. idempotency — ``client_seq`` gates delivery: re-delivery of an applied
   seq replays the stored frame and never re-steps; same seq, different
   action, is ``conflict``; a gap is ``seq_gap`` with resync info (§2).
3. server authority — the client sends actions, never state; world config
   is read once at creation and reported back in ``welcome`` (§3).
4. lifecycle — death pauses decision intake but NOT access: bio/autopsy
   build from the archive (JournalView, read-only) while the writer is
   live (every step commits) and identically after ``close()``; close is
   idempotent; only the process dying destroys the session (§4).
5. transport-invariance — nothing here imports websockets; the WS layer
   adds no semantics, and the acceptance test proves hash + fingerprint
   equality against a local run.

The channel is fed EXACTLY one action per live tick by ``decide`` — the
session blocks on the client (transport), never the channel on a timeout
(Q1: a disconnect is not an in-world action, so no idle fallback is ever
reachable in a WS session).

Autopsy reads death facts from the archive and classifies through
``DeathClassifier`` (the v0.2+ algorithm, Q3 filter unchanged).
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
    #: states: "awaiting" (a decision may be delivered) → "finished"
    #: (life over: bio/autopsy open, decide refused) → "finalized"
    #: (writer closed: results read from the file alone)
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
        self.death_tick: int | None = None
        self.finish_reason: str | None = None
        self.final_hash: str | None = None
        self._finished_event_pending = False
        self._card = None  # cached BiographyCard, keyed by last_seq at build
        self._card_at_seq: int | None = None
        self._lock = threading.RLock()

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
        }

    def take_finished_event(self) -> dict | None:
        """One-shot: the transport sends `finished` right after the last
        frame and never repeats it (a reconnect sees state in welcome)."""
        if self._finished_event_pending:
            self._finished_event_pending = False
            return {
                "type": "finished",
                "reason": self.finish_reason,
                "death_tick": self.death_tick,
            }
        return None

    # ------------------------------------------------------------ decide ---
    def decide(self, seq: int, action: int) -> dict:
        with self._lock:
            if self.state == "finalized":
                raise ProtocolError("finalized", "session is finalized", seq)
            if self.state == "finished":
                raise ProtocolError(
                    "dead", "life is over — bio/autopsy remain open", seq
                )
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
        self.state = "finished"
        self.finish_reason = reason
        self._finished_event_pending = True

    # ------------------------------------------------- results from disk ---
    def _journal_view(self) -> JournalView:
        # same read path while live (writer committed every step, WAL lets
        # ro readers in) and after finalize — one code path, archive-first
        return JournalView(self.db_path)

    def bio(self, md: bool = False, agent: str | None = None) -> dict:
        agent = agent or self.controlled
        card = build_biography(self.db_path, agent)
        self._card, self._card_at_seq = card, self.last_seq
        out = {
            "type": "biography",
            "agent": agent,
            "fingerprint": card.fingerprint(),
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
        if death is None:  # finished by tick_limit while alive
            return {"type": "autopsy", "alive": True, "death_tick": None,
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
                return {"type": "closed", "session_id": self.session_id,
                        "hash": self.final_hash, "note": "already finalized"}
            self.sim.journal.commit()
            self.final_hash = self.sim.journal.hash()
            self.sim.journal.close()
            self.state = "finalized"
            return {"type": "closed", "session_id": self.session_id,
                    "hash": self.final_hash,
                    "reason": self.finish_reason, "db_path": self.db_path}
