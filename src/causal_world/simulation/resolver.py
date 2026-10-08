"""Resolver: validation + deterministic conflict resolution.

The resolver never mutates computed ``new`` values (spec §15). A conflict
on (entity, field) is settled by REJECTING losers — never by rewriting the
winning transition into something it is not.

Conflict rule (explicit and deterministic, spec §14):

    1. higher transition priority wins;
    2. tie -> higher system priority wins;
    3. tie -> lower transition id wins.

Python dict/set iteration order is never consulted: every collection is
walked in sorted order (spec §30).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition, TransitionStatus
from causal_world.kernel.validation import WorldRuleValidator


@dataclass
class Resolution:
    committed: list[Transition] = field(default_factory=list)
    rejected: list[Transition] = field(default_factory=list)


class Resolver:
    def __init__(
        self,
        rules: WorldRuleValidator,
        system_priorities: dict[str, int] | None = None,
    ) -> None:
        self.rules = rules
        self.system_priorities = dict(system_priorities or {})

    # ------------------------------------------------------------------
    def resolve(
        self,
        snapshot: Snapshot,
        transitions: list[Transition],
        allow_creation: bool = False,
    ) -> Resolution:
        result = Resolution()

        # Phase 1: full validation of each transition, independently.
        validated: list[Transition] = []
        for t in transitions:
            errors = self._validate(t, snapshot, allow_creation)
            if errors:
                t.status = TransitionStatus.REJECTED
                t.reject_reason = "; ".join(errors)
                result.rejected.append(t)
            else:
                t.status = TransitionStatus.VALIDATED
                validated.append(t)

        # Phase 2: deterministic conflict resolution among VALIDATED writes.
        # A transition is atomic: once it loses ANY field conflict it is
        # rejected wholesale and all of its other writes are withdrawn too.
        writers: dict[tuple[str, str], list[Transition]] = {}
        for t in validated:
            for w in t.writes:
                writers.setdefault((w.entity, w.field), []).append(t)

        eliminated: set[int] = set()
        for key in sorted(writers):
            contenders = [
                t for t in writers[key] if (t.id or 0) not in eliminated
            ]
            if len(contenders) <= 1:
                continue
            winner = self._winner(contenders)
            for loser in contenders:
                if loser is winner:
                    continue
                loser.status = TransitionStatus.REJECTED
                loser.reject_reason = (
                    f"conflict:{key[0]}.{key[1]}:lost_to:T{winner.id}"
                )
                eliminated.add(loser.id or 0)
                result.rejected.append(loser)

        committed = [t for t in validated if (t.id or 0) not in eliminated]
        result.committed = sorted(committed, key=lambda t: t.id or 0)
        result.rejected.sort(key=lambda t: (t.id is None, t.id if t.id is not None else 0))
        return result

    # ------------------------------------------------------------------
    def _winner(self, contenders: list[Transition]) -> Transition:
        def key(t: Transition) -> tuple[int, int, int]:
            tid = t.id if t.id is not None else 1 << 62
            return (t.priority, self.system_priorities.get(t.system, 0), -tid)

        return max(contenders, key=key)

    # ------------------------------------------------------------------
    def _validate(
        self, t: Transition, snapshot: Snapshot, allow_creation: bool
    ) -> list[str]:
        errors: list[str] = []

        # 13.1 tick consistency
        if t.tick != snapshot.tick:
            errors.append(
                f"tick_mismatch:transition={t.tick}:snapshot={snapshot.tick}"
            )

        if not t.writes:
            errors.append("no_writes")

        seen: set[tuple[str, str]] = set()
        for w in t.writes:
            key = (w.entity, w.field)
            if key in seen:
                errors.append(f"duplicate_write:{w.entity}.{w.field}")
            seen.add(key)

            # 13.2 old-value consistency
            if snapshot.has(w.entity, w.field):
                current = snapshot.get(w.entity, w.field)
                if current != w.old:
                    errors.append(
                        f"old_value_mismatch:{w.entity}.{w.field}:"
                        f"snapshot={current!r}:write.old={w.old!r}"
                    )
            else:
                if w.old is not None:
                    errors.append(
                        f"old_value_mismatch:{w.entity}.{w.field}:field_absent"
                    )
                elif not allow_creation:
                    errors.append(f"field_not_found:{w.entity}.{w.field}")

            # 13.3 type validity (when the ruleset declares a schema)
            expected = self.rules.field_type(w.field)
            if expected is None:
                errors.append(f"unknown_field:{w.entity}.{w.field}")
            elif type(w.new) is not expected:
                errors.append(
                    f"type_mismatch:{w.entity}.{w.field}:"
                    f"expected={expected.__name__}:got={type(w.new).__name__}"
                )

        # 13.4 world invariants (ruleset-provided, not hardcoded in kernel)
        for message in self.rules.validate_transition(t, snapshot):
            errors.append(f"rule:{message}")

        return errors
