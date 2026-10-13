"""WebSocket glue for the game session (contract §5) — the ONLY module that
imports websockets (optional extra: ``pip install causal-world[server]``).

The transport adds no semantics: it parses a message, routes it to the
session, serializes the reply. Every malformed input is an ``error`` frame
on a live connection; only ``close`` or process death ends a session, and
death/finalize never evict it from the registry (reconnect and results
survive both).
"""

from __future__ import annotations

import json
from typing import Callable

from causal_world.server.session import ProtocolError, Session

_ENCODERS: dict = {"ensure_ascii": False, "separators": (",", ":"), "sort_keys": True}


def _dumps(obj) -> str:
    return json.dumps(obj, **_ENCODERS)


def _error(code: str, msg: str, seq=None) -> str:
    out = {"type": "error", "code": code, "msg": msg}
    if seq is not None:
        out["seq"] = seq
    return _dumps(out)


def make_handler(
    registry: dict, db_dir: str = ".", log: Callable[[str], None] | None = None
) -> Callable:
    """Build the per-connection handler bound to a session registry.

    Exposed separately from ``serve`` so tests can mount it on their own
    server object (port negotiation, lifecycle) — the handler is the whole
    protocol implementation.
    """

    def handle(conn, *args) -> None:  # (*args: websockets passes request)
        session: Session | None = None
        for raw in conn:
            try:
                msg = json.loads(raw)
            except Exception:
                conn.send(_error("malformed", "invalid json"))
                continue
            if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
                conn.send(_error("malformed", "expected object with 'type'"))
                continue
            kind = msg["type"]
            try:
                if kind == "hello":
                    sid = msg.get("session")
                    if sid is not None:
                        session = registry.get(str(sid))
                        if session is None:
                            conn.send(_error("unknown_session", str(sid)))
                            continue
                    elif msg.get("world") is not None:
                        session = _open_world(msg, registry, db_dir)
                    else:
                        session = _create(msg, registry, db_dir)
                    conn.send(_dumps(session.welcome()))
                    _release_if_finalized(registry, session)
                    continue
                if session is None:
                    conn.send(_error("not_awaiting", "send hello first"))
                    continue
                if kind == "decide":
                    seq, act = msg.get("seq"), msg.get("action")
                    if (
                        not isinstance(seq, int)
                        or isinstance(seq, bool)
                        or seq < 1
                        or not isinstance(act, int)
                        or isinstance(act, bool)
                    ):
                        conn.send(
                            _error("malformed", "decide needs int seq>=1, int action",
                                   seq if isinstance(seq, int) else None)
                        )
                        continue
                    reply = session.decide(seq, act)
                    fin = session.take_finished_event()
                    if fin is not None:
                        # strict request/response: the life verdict rides as
                        # a FIELD of the last frame — one reply per request,
                        # no unsolicited-message race with close (step 6)
                        reply["finished"] = fin
                    conn.send(_dumps(reply))
                    _release_if_finalized(registry, session)
                elif kind == "bio":
                    conn.send(
                        _dumps(session.bio(md=bool(msg.get("md")), agent=msg.get("agent")))
                    )
                elif kind == "autopsy":
                    conn.send(_dumps(session.autopsy()))
                elif kind == "close":
                    conn.send(_dumps(session.close()))
                    _release_if_finalized(registry, session)
                else:
                    conn.send(_error("unknown_type", kind))
            except ProtocolError as e:
                conn.send(_dumps(e.to_dict()))
            except (ConnectionError, OSError):
                return  # client vanished: session survives in the registry
        # stream ended (clean or not): the session stays resumable (§4)

    def _open_world(msg: dict, registry: dict, db_dir: str) -> Session:
        """Step 6: `hello {world}` alone decides — no file → new world
        (life 1); file present → next life by the succession rule. The
        world name is a strict identifier, never a path (§9/Q4)."""
        from pathlib import Path

        from causal_world.server import continuity

        name = msg.get("world")
        if not continuity.world_name_ok(name):
            raise ProtocolError(
                "malformed",
                "world name must match ^[a-z0-9][a-z0-9_-]{{0,31}}$ "
                "(identifier, not a path)".replace("{{", "{").replace("}}", "}"),
            )
        path = Path(db_dir) / f"{name}.db"
        holder = registry.get("busy:" + str(path))
        if (
            holder is not None
            and str(holder) in registry
            and registry[str(holder)].state != "finalized"
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
            s = _create(msg, registry, db_dir, db_path=str(path))
        registry["busy:" + str(path)] = s.session_id
        registry[s.session_id] = s
        if log:
            log(f"session {s.session_id} life {s.life_n} on {s.db_path}")
        return s

    def _release_if_finalized(registry: dict, session: Session | None) -> None:
        if session is not None and session.state == "finalized":
            key = "busy:" + str(session.db_path)
            if registry.get(key) == session.session_id:
                registry.pop(key, None)

    def _create(msg: dict, registry: dict, db_dir: str,
                db_path: str | None = None) -> Session:
        cfg = {}
        for key in ("seed", "ruleset", "regions", "agents", "max_ticks",
                    "tail_ticks", "controlled"):
            if msg.get(key) is not None:
                cfg[key] = msg[key]
        if "seed" not in cfg:
            raise ProtocolError("malformed", "new session needs a seed")
        s = Session(db_dir=db_dir, db_path=db_path, **cfg)
        registry[s.session_id] = s
        if log:
            log(f"session {s.session_id} on {s.db_path}")
        return s

    return handle


def serve(host: str = "0.0.0.0", port: int = 8765, db_dir: str = ".") -> None:
    try:
        from websockets.sync.server import serve as ws_serve
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "the server extra is not installed: pip install 'causal-world[server]'"
        ) from e
    registry: dict = {}
    handler = make_handler(registry, db_dir, log=print)
    with ws_serve(handler, host, port) as srv:
        print(f"life server ws://{host}:{port} (archive-first; sessions: {db_dir})")
        srv.serve_forever()
