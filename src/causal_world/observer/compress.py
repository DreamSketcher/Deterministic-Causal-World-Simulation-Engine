"""L4 — NarrativeCompressor: causal trace -> compact human text.

This is the OPTIONAL, swappable layer. By default it uses deterministic
templates (no LLM, so nothing about the simulation's truth depends on
a model). An LLM can be plugged in as ``llm`` — any object exposing
``compress(structured) -> str`` — and it is used ONLY to rephrase the
already-built structured trace. The LLM never sees raw state, never
writes, and is never a dependency of the kernel or of layers L1-L3
(spec §47, invariant: no LLM in the simulation truth).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from causal_world.kernel.transition import TransitionStatus


@dataclass
class TraceStep:
    tick: int
    transition_id: int
    system: str
    operation: str
    reads: dict[str, object] = field(default_factory=dict)
    writes: dict[str, str] = field(default_factory=dict)
    random: dict[str, str] = field(default_factory=dict)


class NarrativeCompressor:
    """Compresses a backward causal trace into a readable line."""

    def __init__(self, llm=None) -> None:
        self.llm = llm

    # ------------------------------------------------------------------
    def explain_death(self, agent_id: str, journal, depth: int = 15) -> str:
        death = self._find_death(agent_id, journal)
        if death is None:
            return f"Agent {agent_id} is alive."
        trace = self._trace_back(agent_id, death, journal, depth)
        structured = self._structure(trace, agent_id)
        if self.llm is not None:
            return self.llm.compress(structured)
        return self._template_compress(structured)

    # ------------------------------------------------------------------
    def _find_death(self, agent_id: str, journal):
        query = getattr(journal, "query", None)
        if callable(query):
            rows = query(
                "SELECT id FROM transitions WHERE operation='agent.death' "
                "AND status='COMMITTED' ORDER BY id"
            )
            for row in rows:
                t = journal.by_id(row["id"])
                if any(w.entity == agent_id for w in t.writes):
                    return t
            return None
        for t in journal:
            if (t.status is TransitionStatus.COMMITTED
                    and t.operation == "agent.death"
                    and any(w.entity == agent_id for w in t.writes)):
                return t
        return None

    def _trace_back(self, agent_id: str, transition, journal, depth: int):
        """Backward walk along the agent's own read-provenance chain."""
        trace = [transition]
        seen = {transition.id}
        current = transition
        for _ in range(depth):
            source_id = None
            for r in current.reads:
                if r.entity == agent_id and r.source_transition is not None:
                    source_id = r.source_transition
                    break
            if source_id is None or source_id in seen:
                break
            if not journal.has(source_id):
                break
            seen.add(source_id)
            current = journal.by_id(source_id)
            trace.append(current)
        return trace

    def _structure(self, trace, agent_id: str) -> list[TraceStep]:
        steps = []
        for t in reversed(trace):
            reads = {}
            for r in t.reads:
                if r.entity == agent_id and len(reads) < 4:
                    reads[r.field] = r.value
            writes = {}
            for w in t.writes:
                if w.entity == agent_id:
                    writes[w.field] = f"{w.old}->{w.new}"
            random = {}
            for d in t.random_draws:
                val = d.value if isinstance(d.value, (int, float)) else 0.0
                if d.threshold is None:
                    random[d.purpose] = f"{val:.3f}"
                else:
                    op = "<" if d.outcome else ">="
                    random[d.purpose] = f"{val:.3f} {op} {d.threshold:.3f}"
            steps.append(TraceStep(
                tick=t.tick, transition_id=t.id, system=t.system,
                operation=t.operation, reads=reads, writes=writes,
                random=random,
            ))
        return steps

    def _template_compress(self, steps: list[TraceStep]) -> str:
        lines = []
        for s in steps:
            rand = ""
            if s.random:
                first = next(iter(s.random.items()))
                rand = f" [{first[0]} {first[1]}]"
            write_str = ", ".join(f"{k}:{v}" for k, v in s.writes.items())
            read_str = ", ".join(f"{k}={v}" for k, v in s.reads.items())
            core = f"t{s.tick} {s.system}.{s.operation}"
            if write_str:
                core += f" -> {write_str}"
            if read_str:
                core += f" (reads {read_str})"
            core += rand
            lines.append(core)
        return "\n".join(lines)
