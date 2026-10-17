"""v0.7 — civic directives: the player acts on the WORLD, not only on
themselves.

Until v0.6 the player drove ONE agent through a seven-card personal action
list (work / migrate / explore / heal / trade / rest / idle). That is a
survival game: the world is the backdrop, the avatar is the subject. The
v0.7 direction is the opposite — the WORLD is the object, and the player is
steward, researcher and law-maker at once.

A **directive** is the player's law-making act. It is not a mode switch and
not a UI-only annotation: it is a normal, committed transition that writes
law parameters of ONE region, so it lands in the journal with provenance
like everything else and can be read back by the observer and query layers.

Design constraints this module obeys (they are the repo's, not inventions):

* **One coherent snapshot per tick (I4/I5).** Every system of tick T reads
  the SAME snapshot. A directive enacted at tick T is therefore visible to
  the law systems from tick T+1 — the moment of entry into force is
  ``T+1`` and it is DERIVED, not configured. The journal records the
  enactment tick, so the version of the law at any tick is reconstructible.
* **No state pokes.** A directive never writes a value directly to the
  live state; it proposes a transition, and the resolver decides
  (I1/I3). Conflicting writers are rejected by the documented rule.
* **One writer per field.** The directive system owns the law-parameter
  fields; the agriculture system READS them. They never both write.
* **Scope + version + effective date.** A directive names a region (scope),
  is enacted at a tick (version) and enters force at T+1 (effective date).
  The resulting law of a region at tick t is therefore
  ``base ruleset version + that region's directive ledger up to t-1`` —
  fully reconstructible, hence comparable across runs.

Three directive kinds, each a lever the lab has already measured
(``experiments/reports/v031_diagnosis.md``):

* ``AMEND``  — divert part of the region's labour to making compost:
  soil recovery rises, harvest falls. Long-horizon, structural.
* ``WATER``  — irrigation: effective rainfall rises, but the soil is mined
  faster (salinity). Short-horizon food, long-horizon debt.
* ``REST``   — fallow: the region stops being harvested until a tick, the
  soil heals, and its people eat the stores meanwhile. Save the land, risk
  the people — with no inter-region trade in v0.6 there is no way to feed
  them from elsewhere.

The parameters are written as fields, not as flags, so the player can dial
a law up and down over time; each dial is a separate enacted directive and
therefore a separate entry of the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass

from causal_world.kernel.random import RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.transition import Transition
from causal_world.systems.base import System, clamp

#: Directive kinds (the enacted law change).
DIRECTIVE_AMEND = 0   # labour -> compost
DIRECTIVE_WATER = 1   # irrigation (yield up, soil mined faster)
DIRECTIVE_REST = 2    # fallow until a tick (harvest stops, soil heals)
DIRECTIVE_NURSERY = 3  # v0.8: the nursery policy (conception + child health)

#: The v0.7 card: the three levers a REGION knows.
DIRECTIVE_NAMES = {
    DIRECTIVE_AMEND: "amend",
    DIRECTIVE_WATER: "water",
    DIRECTIVE_REST: "rest",
}
#: The v0.8 card: the same three plus the nursery (a CELL knows four).
DIRECTIVE_ALL_NAMES = {
    **DIRECTIVE_NAMES,
    DIRECTIVE_NURSERY: "nursery",
}
N_DIRECTIVES = len(DIRECTIVE_NAMES)

#: Cap on the amendment share of a region's labour (0..1).
AMEND_CAP = 0.75
#: Cap on irrigation intensity (0..1).
WATER_CAP = 1.0
#: Default fallow length when the directive carries no explicit length.
#: Chosen against the MEASURED horizon of a v0.6 life: the world decays
#: after ~250 ticks (senescence outruns births — see the v0.7 design
#: doc §7), so a lever that only pays off across generations is never
#: paid off at all. A 40-tick rest is a decision inside one life.
REST_DEFAULT = 40
#: Hard cap on a fallow order (a player may not rest a region forever).
REST_MAX = 200

#: Upper bound of a single dial step (guards against absurd orders).
MAX_STEP = 0.75


@dataclass(frozen=True)
class Directive:
    """One enacted law change: kind, target region, magnitude."""

    kind: int
    region: str
    param: float = 0.25

    def __post_init__(self) -> None:
        if self.kind not in DIRECTIVE_ALL_NAMES:
            raise ValueError(f"unknown directive kind {self.kind!r}")

    @property
    def name(self) -> str:
        return DIRECTIVE_ALL_NAMES[self.kind]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name,
                "region": self.region, "param": self.param}


class DirectiveChannel:
    """Tick-indexed directives for one world.

    A directive is scheduled for a TICK, not queued: the system asks for
    the directive of the tick it is computing, so absence of a directive at
    a tick is unambiguous (no transition is written). That makes the
    ledger losslessly readable back from the journal — the same discipline
    the v0.6 decision stream follows.
    """

    def __init__(self, directives: dict[int, Directive] | None = None) -> None:
        self._by_tick: dict[int, Directive] = dict(directives or {})

    def schedule(self, tick: int, directive: Directive) -> None:
        self._by_tick[int(tick)] = directive

    def at(self, tick: int) -> Directive | None:
        return self._by_tick.get(int(tick))

    def __len__(self) -> int:
        return len(self._by_tick)

    def scheduled_ticks(self) -> list[int]:
        return sorted(self._by_tick)


class DirectiveSystem(System):
    """Enacts the player's directives as ordinary committed transitions.

    Priority 45 — the same tier as the player's personal action system:
    a decree is as authoritative as a decision, and it never competes for
    a field with the world-law systems (they only READ what this writes).
    """

    name = "DirectiveSystem"
    priority = 45

    #: The operation name recorded in the journal.
    OPERATION = "player.directive"

    #: Which levers this system can enact, and what it can decree upon.
    #: The v0.7 system works on regions; the v0.8 spatial system works on
    #: cells and knows one lever more (the nursery).
    KIND_NAMES = DIRECTIVE_NAMES
    TARGET_PREFIX = "region:"

    @classmethod
    def kinds(cls) -> dict:
        """The card of this world's decrees (what the client may offer)."""
        return dict(cls.KIND_NAMES)

    def __init__(self, channel: DirectiveChannel | None = None) -> None:
        # No-arg construction by the engine registry: a world without a
        # channel is a world without a steward (the laws simply run).
        self.channel = channel

    def compute(
        self, snapshot: Snapshot, rng: RandomSource, context
    ) -> list[Transition]:
        if self.channel is None:
            return []
        directive = self.channel.at(snapshot.tick)
        if directive is None:
            return []  # no decree this tick -> no transition, no ledger entry
        if directive.kind not in self.KIND_NAMES:
            return []  # a lever this world does not have
        region = directive.region
        if region not in context.entities(self.TARGET_PREFIX):
            return []  # a target that does not exist is simply not enacted

        b = context.builder(self.OPERATION)
        # The recorded draw carries the KIND; the PARAMETER lives in the
        # written field (old -> new), so the journal alone reproduces the
        # law: no hidden state, no second channel of truth.
        b.draw("player.directive", region, index=0, value=float(directive.kind))

        if directive.kind == DIRECTIVE_AMEND:
            old = float(b.read(region, "labor_diversion"))
            new = clamp(old + float(directive.param), 0.0, AMEND_CAP)
            b.write(region, "labor_diversion", new)
        elif directive.kind == DIRECTIVE_WATER:
            old = float(b.read(region, "water_aid"))
            new = clamp(old + float(directive.param), 0.0, WATER_CAP)
            b.write(region, "water_aid", new)
        else:  # DIRECTIVE_REST
            old = int(b.read(region, "rest_until"))
            if directive.param <= 0:
                # A rest order with a non-positive length CANCELS the
                # fallow: the decree that ends it is a decree too.
                b.write(region, "rest_until", 0)
            else:
                length = max(1, min(int(directive.param), REST_MAX))
                b.write(region, "rest_until", max(old, snapshot.tick + length))
        return [b.build()]
