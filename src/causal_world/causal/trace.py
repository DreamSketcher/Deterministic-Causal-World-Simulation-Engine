"""Backward causal trace reconstruction.

``trace_back`` walks the data-dependency chain:

    Transition -> its StateReads -> each read's source_transition -> ...

Random draws are exposed as first-class causal inputs of a transition
(state dependencies + random realization, spec §21). Nothing here relies
on hand-written cause lists — the chain is mechanically reconstructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from causal_world.causal.index import CausalIndex
from causal_world.kernel.transition import (
    RandomDraw,
    StateChange,
    StateRead,
    Transition,
)


@dataclass(frozen=True)
class TraceNode:
    transition_id: int
    tick: int
    system: str
    operation: str
    inputs: tuple[StateRead, ...]
    draws: tuple[RandomDraw, ...]
    writes: tuple[StateChange, ...]
    parents: tuple["TraceNode", ...]


def trace_back(
    index: CausalIndex,
    transition_id: int,
    depth: int = 8,
    _memo: dict[tuple[int, int], TraceNode] | None = None,
) -> TraceNode:
    """Reconstruct the backward dependency tree of a transition.

    ``depth`` bounds how many generations of source transitions are
    expanded. Memoized on (transition, remaining depth), so the traversal
    is linear in the reachable subgraph.
    """
    memo = _memo if _memo is not None else {}
    key = (transition_id, depth)
    if key in memo:
        return memo[key]

    t = index.get(transition_id)
    parents: list[TraceNode] = []
    if depth > 0:
        seen: set[int] = set()
        sources = sorted(
            r.source_transition
            for r in t.reads
            if r.source_transition is not None
        )
        for source in sources:
            if source in seen or not index.has(source):
                continue
            seen.add(source)
            parents.append(trace_back(index, source, depth - 1, memo))

    node = TraceNode(
        transition_id=transition_id,
        tick=t.tick,
        system=t.system,
        operation=t.operation,
        inputs=tuple(t.reads),
        draws=tuple(t.random_draws),
        writes=tuple(t.writes),
        parents=tuple(parents),
    )
    memo[key] = node
    return node


def trace_record(node: TraceNode) -> list[Any]:
    """Canonical serializable record of a trace tree (for equality tests)."""
    return [
        node.transition_id,
        node.tick,
        node.system,
        node.operation,
        sorted(
            [r.entity, r.field, r.source_transition] for r in node.inputs
        ),
        sorted([d.purpose, d.entity, d.index] for d in node.draws),
        [trace_record(p) for p in node.parents],
    ]


def collect_ancestors(node: TraceNode) -> set[int]:
    """All transition ids reachable backward from this node."""
    found = {node.transition_id}
    for parent in node.parents:
        found |= collect_ancestors(parent)
    return found


# ----------------------------------------------------------------------
# Human-readable rendering (used by CLI and observers; read-only)
# ----------------------------------------------------------------------

def fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(round(value, 6)) if abs(value) < 1e12 else repr(value)
    if value is None:
        return "none"
    return str(value)


def format_transition(t: Transition) -> str:
    lines = [f"T{t.id} {t.system}.{t.operation}  [{t.status.value}] tick={t.tick}"]
    if t.reject_reason:
        lines.append(f"REJECT reason = {t.reject_reason}")
    if t.reads:
        lines.append("")
        lines.append("READ")
        for r in sorted(t.reads, key=lambda r: (r.entity, r.field)):
            source = f"T{r.source_transition}" if r.source_transition is not None else "initial"
            lines.append(f"  {r.entity}.{r.field} = {fmt(r.value)} ← {source}")
    if t.random_draws:
        lines.append("")
        lines.append("RANDOM")
        for d in t.random_draws:
            block = [f"  {d.purpose}@{d.entity}#{d.index} = {fmt(d.value)}"]
            if d.threshold is not None:
                block.append(f"  threshold = {fmt(d.threshold)}")
            block.append(f"  outcome = {fmt(d.outcome)}")
            lines.extend(block)
    if t.writes:
        lines.append("")
        lines.append("WRITE")
        for w in sorted(t.writes, key=lambda w: (w.entity, w.field)):
            lines.append(f"  {w.entity}.{w.field}: {fmt(w.old)} → {fmt(w.new)}")
    return "\n".join(lines)


def format_trace(
    node: TraceNode,
    depth: int | None = None,
    indent: int = 0,
    max_inputs: int | None = None,
) -> str:
    """Render the dependency tree in the spirit of spec §21.

    ``max_inputs`` caps the printed inputs of each node (bulk transitions
    such as censuses can have hundreds of reads); the cap never affects the
    underlying trace object.
    """
    pad = "  " * indent
    lines = [f"{pad}T{node.transition_id} {node.system}.{node.operation} (tick {node.tick})"]
    if node.inputs:
        lines.append(f"{pad}Inputs:")
        ordered = sorted(node.inputs, key=lambda r: (r.entity, r.field))
        shown = ordered if max_inputs is None else ordered[:max_inputs]
        for r in shown:
            source = f"T{r.source_transition}" if r.source_transition is not None else "initial"
            lines.append(f"{pad}  {r.entity}.{r.field} = {fmt(r.value)} ← {source}")
        if max_inputs is not None and len(ordered) > max_inputs:
            lines.append(f"{pad}  … {len(ordered) - max_inputs} more input(s)")
    if node.draws:
        lines.append(f"{pad}Random:")
        for d in node.draws:
            extra = f" threshold={fmt(d.threshold)}" if d.threshold is not None else ""
            lines.append(f"{pad}  {d.purpose}@{d.entity} = {fmt(d.value)}{extra}")
    if node.writes:
        lines.append(f"{pad}Writes:")
        for w in sorted(node.writes, key=lambda w: (w.entity, w.field)):
            lines.append(f"{pad}  {w.entity}.{w.field}: {fmt(w.old)} → {fmt(w.new)}")
    if depth is None or depth > 0:
        next_depth = None if depth is None else depth - 1
        for parent in node.parents:
            lines.append(format_trace(parent, next_depth, indent + 1, max_inputs))
    elif node.parents:
        lines.append(f"{pad}  … {len(node.parents)} more parent(s) beyond depth")
    return "\n".join(lines)
