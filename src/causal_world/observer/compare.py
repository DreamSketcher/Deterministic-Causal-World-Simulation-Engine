"""L3 — CausalComparator: why does regime A differ from regime B?

Compares two recorded runs of the SAME world seed at the level of causal
budgets. The answer is mechanical, not narrative: which inflows/outflows
exist in one run but not the other, and how the net balances differ.

The v0.4 proposal's headline example — immune (0.3.0) vs compost (G) —
reduces to exactly one missing line in the budget: the compost inflow.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from causal_world.kernel.transition import TransitionStatus
from causal_world.observer.budget import CausalBudget, CausalBudgetReport


@dataclass
class RegimeDiff:
    regime_a: str
    regime_b: str
    entity: str
    field_name: str
    missing_inflows: list[str] = field(default_factory=list)   # in B, not A
    missing_outflows: list[str] = field(default_factory=list)  # in A, not B
    budget_deltas: dict[str, float] = field(default_factory=dict)
    causal_loop_diff: str = ""


class CausalComparator:
    """Compares two runs via their causal budgets."""

    def __init__(self, journal_a, journal_b,
                 name_a: str = "A", name_b: str = "B") -> None:
        self.budget_a = CausalBudget(journal_a)
        self.budget_b = CausalBudget(journal_b)
        self.name_a = name_a
        self.name_b = name_b

    def compare_field(self, entity: str, field_name: str,
                      tick_end: float = math.inf) -> RegimeDiff:
        ba = self.budget_a.analyze(entity, field_name, 0, tick_end)
        bb = self.budget_b.analyze(entity, field_name, 0, tick_end)

        def keys(report: CausalBudgetReport) -> set[str]:
            return {f"{e.system}.{e.operation}"
                    for e in report.inflows + report.outflows}

        def inflow_keys(report: CausalBudgetReport) -> set[str]:
            return {f"{e.system}.{e.operation}" for e in report.inflows}

        def outflow_keys(report: CausalBudgetReport) -> set[str]:
            return {f"{e.system}.{e.operation}" for e in report.outflows}

        diff = RegimeDiff(
            regime_a=self.name_a, regime_b=self.name_b,
            entity=entity, field_name=field_name,
            missing_inflows=sorted(inflow_keys(bb) - inflow_keys(ba)),
            missing_outflows=sorted(outflow_keys(ba) - outflow_keys(bb)),
            budget_deltas={field_name: bb.net - ba.net},
        )
        diff.causal_loop_diff = self._describe_loop_diff(ba, bb)
        return diff

    def compare_soil(self, region: str) -> RegimeDiff:
        return self.compare_field(region, "soil_fertility")

    def compare_entity(self, entity: str) -> dict[str, RegimeDiff]:
        """Field-by-field diff of every numeric field either run touched."""
        fields = sorted(
            set(self.budget_a.fields_of(entity))
            | set(self.budget_b.fields_of(entity))
        )
        return {f: self.compare_field(entity, f) for f in fields}

    # ------------------------------------------------------------------
    def _describe_loop_diff(self, ba: CausalBudgetReport,
                            bb: CausalBudgetReport) -> str:
        lines = []
        if bb.inflows and not ba.inflows:
            lines.append(
                f"regime {self.name_b} has an inflow "
                f"({bb.dominant_inflow()}) that {self.name_a} lacks: "
                f"the loop closes."
            )
        elif bb.inflows and ba.inflows:
            only_b = {f"{e.system}.{e.operation}" for e in bb.inflows} - {
                f"{e.system}.{e.operation}" for e in ba.inflows}
            if only_b:
                lines.append(
                    f"regime {self.name_b} has extra inflow(s): "
                    f"{sorted(only_b)}."
                )
        if abs(bb.net) < 0.01 and ba.net < -0.1:
            lines.append(
                f"in {self.name_b} the field is in balance "
                f"(net={bb.net:+.3f}); in {self.name_a} it declines "
                f"monotonically (net={ba.net:+.3f})."
            )
        return " ".join(lines) if lines else "no structural loop difference."


# ----------------------------------------------------------------------
# migration behaviour: how dispersed are agent moves?
# ----------------------------------------------------------------------

def migration_stats(journal) -> dict[str, float]:
    """Destination distribution of committed migrations.

    Returns counts, destinations used, and Shannon entropy (bits) of the
    destination choice. A world where everyone herds to one region has
    entropy ~0; blind diffusion across N regions approaches log2(N).
    """
    dests: Counter[str] = Counter()
    movers: set[str] = set()
    query = getattr(journal, "query", None)
    if callable(query):
        import json

        rows = query(
            "SELECT payload FROM transitions "
            "WHERE operation='agent.migrate' AND status='COMMITTED'"
        )
        for row in rows:
            payload = json.loads(row["payload"])
            for w in payload["writes"]:
                if w[0].startswith("agent:") and w[1] == "region" \
                        and w[2] is not None and w[2] != w[3]:
                    dests[w[3]] += 1
                    movers.add(w[0])
    else:
        for t in journal:
            if t.status is not TransitionStatus.COMMITTED:
                continue
            if t.operation != "agent.migrate":
                continue
            for w in t.writes:
                if w.entity.startswith("agent:") and w.field == "region" \
                        and w.old is not None and w.old != w.new:
                    dests[w.new] += 1
                    movers.add(w.entity)
    total = sum(dests.values())
    entropy = 0.0
    if total:
        for n in dests.values():
            p = n / total
            entropy -= p * math.log2(p)
    return {
        "moves": float(total),
        "movers": float(len(movers)),
        "destinations": float(len(dests)),
        "entropy_bits": entropy,
        "top_destination": dests.most_common(1)[0][0] if dests else "",
        "top_destination_share": (
            dests.most_common(1)[0][1] / total if dests else 0.0),
    }
