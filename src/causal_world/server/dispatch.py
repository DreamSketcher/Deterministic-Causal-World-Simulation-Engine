"""Transport-free protocol dispatcher (v0.13 — extracted from ``ws.py``).

One request in, exactly one reply out. The WebSocket transport (``ws.py``)
and the stdio JSON Lines transport (``jsonl.py``, used by the Godot client)
both call this module, so the protocol has ONE implementation. Nothing here
imports a transport library.

Message types (contract: experiments/proposals/v13_godot_protocol.md):

    hello   {session?} | {world} | {seed, ruleset?, regions?, agents?, ...}
    decide  {seq, action, decree?}
    look    {}                       (read-only: the world now, no step)
    bio     {md?, agent?}
    autopsy {}
    close   {}

Every reply is a dict with a ``type``. Protocol refusals come back as the
``error`` dict of ``ProtocolError``; malformed input is an ``error`` with
code ``malformed``. A refused message never touches the world.
"""

from __future__ import annotations

import json
from typing import Callable

from causal_world.server.session import ProtocolError, Session
from causal_world.server.trace import Tracer


def error_reply(code: str, msg: str, seq=None) -> dict:
    out = {"type": "error", "code": code, "msg": msg}
    if seq is not None:
        out["seq"] = seq
    return out


class Dispatcher:
    """Routes protocol messages to sessions held in ``registry``.

    ``conn`` is the per-connection state: ``{"session": Session | None}``.
    A WebSocket connection, or one stdio process, owns one such dict.
    """

    def __init__(
        self,
        registry: dict,
        db_dir: str = ".",
        log: Callable[[str], None] | None = None,
        trace: bool = False,
    ) -> None:
        self.registry = registry
        self.db_dir = db_dir
        self.log = log
        # the debug trace (server/trace.py): read-only, logs only
        self.tracer = Tracer(log or (lambda _m: None)) if trace else None

    # ------------------------------------------------------------ entry ----
    def handle_raw(self, raw: str | bytes, conn: dict) -> dict:
        """Parse one raw line/frame, then dispatch it."""
        try:
            msg = json.loads(raw)
        except Exception:
            return error_reply("malformed", "invalid json")
        return self.handle(msg, conn)

    def handle(self, msg: object, conn: dict) -> dict:
        if self.tracer is not None:
            self._traced(self.tracer.inbound, msg)
        reply = self._dispatch(msg, conn)
        if self.tracer is not None:
            self._traced(self.tracer.outbound, reply)
        return reply

    def _traced(self, fn, *args) -> None:
        """Run a trace call; a failure is logged and never reaches the protocol."""
        try:
            fn(*args)
        except Exception as e:  # the trace must not break the world or the reply
            if self.log is not None:
                self.log(f"[trace] failed: {type(e).__name__}: {e}")

    def _dispatch(self, msg: object, conn: dict) -> dict:
        if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
            return error_reply("malformed", "expected object with 'type'")
        kind = msg["type"]
        try:
            if kind == "hello":
                return self._hello(msg, conn)
            session = conn.get("session")
            if session is None:
                return error_reply("not_awaiting", "send hello first")
            if kind == "decide":
                return self._decide(msg, conn, session)
            if kind == "look":
                return session.look()
            if kind == "bio":
                return session.bio(md=bool(msg.get("md")), agent=msg.get("agent"))
            if kind == "autopsy":
                return session.autopsy()
            if kind == "close":
                reply = session.close()
                self._release_if_finalized(session)
                return reply
            return error_reply("unknown_type", kind)
        except ProtocolError as e:
            return e.to_dict()

    # --------------------------------------------------------- handlers ----
    def _hello(self, msg: dict, conn: dict) -> dict:
        sid = msg.get("session")
        if sid is not None:
            session = self.registry.get(str(sid))
            if session is None:
                return error_reply("unknown_session", str(sid))
        elif msg.get("world") is not None:
            session = self._open_world(msg)
        else:
            session = self._create(msg)
        conn["session"] = session
        reply = session.welcome()
        if self.tracer is not None:
            self._traced(self.tracer.journal_summary, session)
        self._release_if_finalized(session)
        return reply

    def _decide(self, msg: dict, conn: dict, session: Session) -> dict:
        seq, act = msg.get("seq"), msg.get("action")
        if (
            not isinstance(seq, int)
            or isinstance(seq, bool)
            or seq < 1
            or not isinstance(act, int)
            or isinstance(act, bool)
        ):
            return error_reply(
                "malformed",
                "decide needs int seq>=1, int action",
                seq if isinstance(seq, int) else None,
            )
        decree = msg.get("decree")
        if decree is not None and not isinstance(decree, dict):
            return error_reply("malformed", "decree must be an object")
        records_before = session.sim.journal.counts()[0]
        reply = session.decide(seq, act, decree=decree)
        if self.tracer is not None:
            self._traced(self.tracer.step, session, reply, records_before)
        fin = session.take_finished_event()
        if fin is not None:
            # strict request/response: the life verdict rides as a FIELD of
            # the last frame — one reply per request (step 6)
            reply["finished"] = fin
        self._release_if_finalized(session)
        return reply

    def _open_world(self, msg: dict) -> Session:
        """``hello {world}``: no file -> new world (life 1); file present ->
        next life by the succession rule. The world name is a strict
        identifier, never a path (§9/Q4)."""
        from pathlib import Path

        from causal_world.server import continuity

        name = msg.get("world")
        if not continuity.world_name_ok(name):
            raise ProtocolError(
                "malformed",
                "world name must match ^[a-z0-9][a-z0-9_-]{0,31}$ "
                "(identifier, not a path)",
            )
        path = Path(self.db_dir) / f"{name}.db"
        holder = self.registry.get("busy:" + str(path))
        if (
            holder is not None
            and str(holder) in self.registry
            and self.registry[str(holder)].state != "finalized"
        ):
            raise ProtocolError(
                "world_busy",
                f"world '{name}' has an active session — resume+close it "
                "to release, or wait",
                None,
                {"session": str(holder), "world": str(name)},
            )
        if path.exists():
            s = Session.takeover(str(path))
        else:
            s = self._create(msg, db_path=str(path))
        self.registry["busy:" + str(path)] = s.session_id
        self.registry[s.session_id] = s
        if self.log:
            self.log(f"session {s.session_id} life {s.life_n} on {s.db_path}")
        return s

    def _create(self, msg: dict, db_path: str | None = None) -> Session:
        cfg = {}
        for key in ("seed", "ruleset", "regions", "agents", "max_ticks",
                    "tail_ticks", "controlled"):
            if msg.get(key) is not None:
                cfg[key] = msg[key]
        if "seed" not in cfg:
            raise ProtocolError("malformed", "new session needs a seed")
        s = Session(db_dir=self.db_dir, db_path=db_path, **cfg)
        self.registry[s.session_id] = s
        if self.log:
            self.log(f"session {s.session_id} on {s.db_path}")
        return s

    def _release_if_finalized(self, session: Session | None) -> None:
        if session is not None and session.state == "finalized":
            key = "busy:" + str(session.db_path)
            if self.registry.get(key) == session.session_id:
                self.registry.pop(key, None)
