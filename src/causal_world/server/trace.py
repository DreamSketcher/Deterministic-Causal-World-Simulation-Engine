"""Debug trace of the core: protocol traffic and the journal of each step.

Enabled with ``--trace`` on the stdio server. Everything goes to the log
callback (stderr); stdout stays protocol-only. The trace is read-only: it
reads the journal and never writes to it, and a failure inside the trace
is logged and never reaches the protocol.

ASCII only: the Godot client reads stderr line by line, so arrows and
ellipses are written as ``->`` and ``...``.
"""

from __future__ import annotations

from typing import Callable

MAX_STEP_LINES = 60  # transitions printed per decision; the rest is counted
MAX_WRITES = 6  # field changes printed per transition
MAX_DRAWS = 3  # random draws printed per transition
VALUE_CHARS = 24  # width of a value in a field change


def _short(value: object, width: int = VALUE_CHARS) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= width else text[: width - 3] + "..."


def describe_transition(t) -> str:
    """One line for one transition: id, tick, system/operation, status, changes."""
    status = getattr(t.status, "value", t.status)
    head = f"T{t.id} t{t.tick} {t.system}/{t.operation} {status}"
    if t.reject_reason:
        head += f" reject={t.reject_reason}"
    parts = [head, f"reads={len(t.reads)}"]
    if t.writes:
        shown = [
            f"{w.entity}.{w.field} {_short(w.old)}->{_short(w.new)}"
            for w in t.writes[:MAX_WRITES]
        ]
        more = len(t.writes) - MAX_WRITES
        if more > 0:
            shown.append(f"+{more} more")
        parts.append("writes=[" + ", ".join(shown) + "]")
    if t.random_draws:
        purposes = [d.purpose for d in t.random_draws[:MAX_DRAWS]]
        parts.append("draws=[" + ", ".join(purposes) + "]")
    return " ".join(parts)


class Tracer:
    """Writes the protocol traffic and the per-step journal to ``log``."""

    def __init__(self, log: Callable[[str], None]) -> None:
        self.log = log

    def inbound(self, msg: object) -> None:
        if not isinstance(msg, dict):
            self.log("[proto] << (not an object)")
            return
        kind = msg.get("type")
        extra = ""
        if kind == "decide":
            extra = f" seq={msg.get('seq')} action={msg.get('action')}"
        self.log(f"[proto] << {kind}{extra}")

    def outbound(self, reply: dict) -> None:
        kind = reply.get("type")
        if kind == "frame":
            detail = (
                f"seq={reply.get('seq')} tick={reply.get('tick')} "
                f"applied={reply.get('applied')} alive={reply.get('alive')}"
            )
        elif kind == "error":
            detail = f"code={reply.get('code')} msg={_short(str(reply.get('msg')), 80)}"
        elif kind == "view":
            detail = f"tick={reply.get('tick')} alive={reply.get('alive')}"
        else:
            detail = ""
        self.log(f"[proto] >> {kind} {detail}".rstrip())

    def journal_summary(self, session) -> None:
        journal = session.sim.journal
        total, committed, rejected = journal.counts()
        self.log(
            f"[journal] total={total} committed={committed} rejected={rejected} "
            f"hash={journal.hash()[:16]}"
        )

    def step(self, session, reply: dict, records_before: int) -> None:
        """The transitions this decision produced (read-only).

        Ids are sequential, so the records of this step are the ones after
        ``records_before`` (the journal length before the decision). Genesis
        records share the tick and are not part of the step.
        """
        journal = session.sim.journal
        tick = reply.get("tick")
        at = journal.at_tick(tick) if isinstance(tick, int) else []
        mine = [t for t in at if t.id is not None and t.id > records_before]
        self.log(f"[journal] step tick={tick} transitions={len(mine)}")
        for t in mine[:MAX_STEP_LINES]:
            self.log(f"[journal]   {describe_transition(t)}")
        if len(mine) > MAX_STEP_LINES:
            self.log(f"[journal]   ... {len(mine) - MAX_STEP_LINES} more at tick {tick}")
        self.journal_summary(session)
