"""Debug trace of the core: protocol traffic and the journal of each step.

Enabled with ``--trace`` on the stdio server; ``--trace-detail`` adds one
line per transition. Everything goes to the log callback (stderr); stdout
stays protocol-only. The trace is read-only: it reads the archive through
its own ``mode=ro`` view and never writes, and a failure inside the trace
is logged and never reaches the protocol.

Default output is one summary block per decision (counts by system and
operation, rejections), so a whole life stays inside the editor's Output
panel. Per-transition lines are for ``--trace-detail`` only.

ASCII only: the Godot client reads stderr line by line, so arrows and
ellipses are written as ``->`` and ``...``.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

from causal_world.observer.journal import JournalView

MAX_STEP_LINES = 60  # transitions printed per decision in detail mode
MAX_GROUPS = 8  # operation groups shown in the summary line
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

    def __init__(self, log: Callable[[str], None], detail: bool = False) -> None:
        self.log = log
        self.detail = detail

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
        if session.state == "finalized":
            # the live writer is closed; the archive is the source of truth
            with JournalView(session.db_path) as view:
                total, committed, rejected = view.counts()
            digest = session.final_hash or ""
        else:
            journal = session.sim.journal
            total, committed, rejected = journal.counts()
            digest = journal.hash()
        self.log(
            f"[journal] total={total} committed={committed} rejected={rejected} "
            f"hash={digest[:16]}"
        )

    def step(self, session, reply: dict, records_before: int) -> None:
        """The transitions this decision produced (read-only).

        Ids are sequential, so the records of this step are the ones after
        ``records_before`` (the journal length before the decision). Read
        through the archive, so it works whether or not the writer is still
        open (a death closes it inside the decision).
        """
        tick = reply.get("tick")
        with JournalView(session.db_path) as view:
            mine = list(view.since(records_before))
        committed = sum(1 for t in mine if _status(t) == "COMMITTED")
        rejected = len(mine) - committed
        self.log(
            f"[journal] step tick={tick} transitions={len(mine)} "
            f"committed={committed} rejected={rejected}"
        )
        self._groups(mine)
        if self.detail:
            for t in mine[:MAX_STEP_LINES]:
                self.log(f"[journal]   {describe_transition(t)}")
            if len(mine) > MAX_STEP_LINES:
                self.log(
                    f"[journal]   ... {len(mine) - MAX_STEP_LINES} more at tick {tick}"
                )
        self.journal_summary(session)

    def _groups(self, transitions: list) -> None:
        """One line: ``system/operation`` counts, rejections in brackets."""
        if not transitions:
            return
        count: Counter = Counter()
        rejected: Counter = Counter()
        for t in transitions:
            key = f"{t.system}/{t.operation}"
            count[key] += 1
            if _status(t) != "COMMITTED":
                rejected[key] += 1
        ranked = sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))
        parts = []
        for key, n in ranked[:MAX_GROUPS]:
            bad = f" rejected {rejected[key]}" if rejected[key] else ""
            parts.append(f"{key} x{n}{bad}")
        more = len(ranked) - MAX_GROUPS
        if more > 0:
            parts.append(f"+{more} more kinds")
        self.log("[journal]   by operation: " + "; ".join(parts))


def _status(t) -> str:
    return str(getattr(t.status, "value", t.status))
