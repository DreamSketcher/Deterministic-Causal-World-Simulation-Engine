"""stdio transport: JSON Lines over stdin/stdout (v0.13, the Godot client).

    python -m causal_world.server.jsonl --db-dir DIR

The process is the authoritative Python core of the game. The client starts
it, writes one JSON object per line to stdin and reads one JSON object per
line from stdout. The protocol is the SAME dispatcher as the WebSocket
transport (``causal_world.server.dispatch``); this module only frames lines.

Rules (contract: experiments/proposals/v13_godot_protocol.md):

* stdout carries protocol lines and nothing else; logs go to stderr;
* the first line is ``{"type": "ready", "protocol": ..., ...}``;
* every request gets exactly one reply line; malformed input is an
  ``error`` line and never touches the world;
* a ``hello`` may carry ``"protocol": PROTOCOL``; a different value is
  refused with ``protocol_mismatch`` before anything is created;
* ``shutdown`` replies ``bye`` and exits 0; EOF on stdin exits 0 too.
  EOF does NOT end the life: the journal is committed and closed, the life
  stays open and resumable. Ending a life is the explicit ``close`` message
  (abdicate), exactly as on the WebSocket.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from typing import IO

from causal_world import KERNEL_VERSION
from causal_world.server.dispatch import Dispatcher, error_reply

#: Wire version. Bump only on an incompatible change of a message or field.
PROTOCOL = "causal-world-jsonl/1"

_ENCODE = {"ensure_ascii": True, "separators": (",", ":"), "sort_keys": True}


def _line(obj: dict) -> str:
    return json.dumps(obj, **_ENCODE) + "\n"


def serve_stdio(inp: IO[str], out: IO[str], db_dir: str, trace: bool = False) -> int:
    """Run the request loop until ``shutdown`` or EOF. Returns the exit code."""

    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    registry: dict = {}
    dispatcher = Dispatcher(registry, db_dir, log=log, trace=trace)
    conn: dict = {"session": None}

    def send(obj: dict) -> None:
        out.write(_line(obj))
        out.flush()

    send({
        "type": "ready",
        "protocol": PROTOCOL,
        "kernel_version": KERNEL_VERSION,
        "pid": os.getpid(),
    })

    for raw in inp:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            send(error_reply("malformed", "invalid json"))
            continue
        if isinstance(msg, dict) and msg.get("type") == "shutdown":
            send({"type": "bye", "reason": "shutdown"})
            _release(conn)
            return 0
        if (
            isinstance(msg, dict)
            and msg.get("type") == "hello"
            and msg.get("protocol", PROTOCOL) != PROTOCOL
        ):
            send(error_reply(
                "protocol_mismatch",
                f"client speaks {msg.get('protocol')!r}, server {PROTOCOL!r}",
            ))
            continue
        try:
            reply = dispatcher.handle(msg, conn)
        except Exception as e:  # never let one request kill the game process
            traceback.print_exc(file=sys.stderr)
            reply = error_reply("internal", f"{type(e).__name__}: {e}")
        if isinstance(reply, dict) and reply.get("type") == "welcome":
            reply = dict(reply, protocol=PROTOCOL, kernel_version=KERNEL_VERSION)
        send(reply)

    _release(conn)
    return 0


def _release(conn: dict) -> None:
    """Commit and close the archive without ending the life (see module doc)."""
    session = conn.get("session")
    if session is None or session.state == "finalized":
        return
    journal = session.sim.journal
    try:
        journal.commit()
        journal.close()
    except Exception as e:  # pragma: no cover - the process is ending anyway
        print(f"release failed: {e}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="causal_world.server.jsonl",
        description="Causal World simulation core over JSON Lines (stdio).",
    )
    parser.add_argument("--db-dir", required=True,
                        help="directory for world archives (created if missing)")
    parser.add_argument("--trace", action="store_true",
                        help="log protocol traffic and each step's journal to stderr")
    args = parser.parse_args(argv)
    os.makedirs(args.db_dir, exist_ok=True)
    # The pipes are ASCII-only: the client reads them line by line and a
    # multi-byte character split across reads is not decodable there.
    # JSON is already ASCII (ensure_ascii); log text is escaped.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="ascii", errors="backslashreplace")
    return serve_stdio(sys.stdin, sys.stdout, args.db_dir, trace=args.trace)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
