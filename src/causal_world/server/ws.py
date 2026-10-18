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

from causal_world.server.dispatch import Dispatcher, error_reply

_ENCODERS: dict = {"ensure_ascii": False, "separators": (",", ":"), "sort_keys": True}


def _dumps(obj) -> str:
    return json.dumps(obj, **_ENCODERS)


def _error(code: str, msg: str, seq=None) -> str:
    return _dumps(error_reply(code, msg, seq))


def make_handler(
    registry: dict, db_dir: str = ".", log: Callable[[str], None] | None = None
) -> Callable:
    """Build the per-connection handler bound to a session registry.

    The protocol itself lives in ``causal_world.server.dispatch`` (shared
    with the stdio transport of the Godot client); this function only moves
    frames on the socket. Exposed separately from ``serve`` so tests can
    mount it on their own server object.
    """
    dispatcher = Dispatcher(registry, db_dir, log=log)

    def handle(conn, *args) -> None:  # (*args: websockets passes request)
        state: dict = {"session": None}
        for raw in conn:
            reply = dispatcher.handle_raw(raw, state)
            try:
                conn.send(_dumps(reply))
            except (ConnectionError, OSError):
                return  # client vanished: session survives in the registry
        # stream ended (clean or not): the session stays resumable (§4)

    return handle


def serve(host: str = "0.0.0.0", port: int = 8765, db_dir: str = ".",
          web: bool = True) -> None:
    """The life server.

    With ``web=True`` (the default) ONE port serves three things: the
    static client (the living map + the analytical mode), the WebSocket
    session protocol at ``/ws``, and the read-only ``/analyze``
    endpoint. The browser and the protocol therefore talk about the same
    live world.
    """
    try:
        from websockets.sync.server import serve as ws_serve
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "the server extra is not installed: pip install 'causal-world[server]'"
        ) from e
    registry: dict = {}
    handler = make_handler(registry, db_dir, log=print)

    process_request = None
    if web:
        from causal_world.server.web import make_analyze_handler, static_response

        def _current_db() -> str | None:
            """The archive of the most recent live session (if any)."""
            for value in reversed(list(registry.values())):
                session = value
                if hasattr(session, "db_path") and getattr(session, "state", "") != "finalized":
                    return session.db_path
            for value in reversed(list(registry.values())):
                if hasattr(value, "db_path"):
                    return value.db_path
            return None

        analyze_handler = make_analyze_handler(_current_db)

        def _process_request(conn, request):
            """Serve the static client; let ``/ws`` through to the protocol."""
            path = request.path.split("?")[0]
            if path == "/ws":
                return None
            if path == "/analyze":
                from urllib.parse import parse_qs, urlparse

                query = parse_qs(urlparse(request.path).query)
                status, ctype, body = analyze_handler(query)
                from websockets.http11 import Headers, Response

                return Response(status, "OK", Headers(
                    [("Content-Type", ctype), ("Content-Length", str(len(body)))]
                ), body)
            status, ctype, body = static_response(path)
            from websockets.http11 import Headers, Response

            return Response(status, "OK", Headers(
                [("Content-Type", ctype), ("Content-Length", str(len(body)))]
            ), body)

        process_request = _process_request

    with ws_serve(handler, host, port, process_request=process_request) as srv:
        print(f"life server ws://{host}:{port} (archive-first; sessions: {db_dir})")
        if web:
            print(f"  client:   http://{host}:{port}/  (map + analytical mode)")
        srv.serve_forever()
