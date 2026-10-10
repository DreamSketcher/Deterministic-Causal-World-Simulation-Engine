"""Simulation engine: the Snapshot -> Plan -> Resolve -> Commit -> Index loop.

The engine is the ONLY place where the WorldState is mutated, and it does
so exclusively inside ``_commit`` (spec §16), through committed
transitions, with provenance updated simultaneously with the values.

Transition ids are assigned from the CANONICALLY SORTED set of proposals
of a tick (content-based key), never from system execution order. This
keeps the physics independent of the order in which systems are listed
(spec §19, §45) while still giving conflict tie-breaks a deterministic id.
"""

from __future__ import annotations

from causal_world.causal.index import CausalIndex
from causal_world.kernel.errors import GenesisError
from causal_world.kernel.random import PurposeRegistry, RandomSource
from causal_world.kernel.snapshot import Snapshot
from causal_world.kernel.state import WorldState
from causal_world.kernel.transition import (
    Transition,
    TransitionStatus,
    proposal_sort_key,
)
from causal_world.kernel.validation import WorldRuleValidator
from causal_world.simulation.journal import Journal
from causal_world.simulation.resolver import Resolver
from causal_world.systems.base import System, SystemContext


class Simulation:
    def __init__(
        self,
        world_seed: int,
        systems: list[System],
        rules: WorldRuleValidator,
        rng: RandomSource,
        journal: Journal | None = None,
        index: CausalIndex | None = None,
    ) -> None:
        self.world_seed = int(world_seed)
        self.systems = list(systems)
        self.rules = rules
        self.rng = rng
        self.state = WorldState(tick=0)
        # Pluggable stores: in-memory by default; a SqliteArchive can serve
        # as BOTH journal and index for long runs (identical semantics and
        # identical journal hashes).
        self.journal = journal if journal is not None else Journal()
        self.index = index if index is not None else CausalIndex()
        self.resolver = Resolver(
            rules, {system.name: system.priority for system in self.systems}
        )
        self._next_id = 1
        self.initial_state_hash: str | None = None

    # ------------------------------------------------------------------
    # Genesis
    # ------------------------------------------------------------------
    def initialize(self, genesis_transitions: list[Transition]) -> None:
        """Commit the initial conditions as genesis transitions.

        Initial state also flows through the transition machinery so every
        value has provenance from the very beginning.
        """
        self._assign_ids(genesis_transitions)
        snapshot = Snapshot.from_state(self.state)
        resolution = self.resolver.resolve(
            snapshot, genesis_transitions, allow_creation=True
        )
        for t in resolution.rejected:
            raise GenesisError(f"genesis transition T{t.id} rejected: {t.reject_reason}")
        for t in resolution.committed:
            self._commit(t)
        for t in sorted(genesis_transitions, key=lambda t: t.id or 0):
            self.journal.record(t)
            self.index.add(t)
        self.initial_state_hash = self.state.hash()

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------
    def step(self) -> None:
        # SNAPSHOT — one immutable view shared by every system (I4, I5).
        snapshot = Snapshot.from_state(self.state)

        # PLAN — systems propose transitions; they never see each other's
        # current-tick writes and never touch the live state.
        proposals: list[Transition] = []
        for system in self.systems:
            context = SystemContext(system, snapshot, self.rng)
            produced = system.compute(snapshot, self.rng, context) or []
            proposals.extend(produced)

        # Canonical ids (independent of system execution order).
        self._assign_ids(proposals)

        # RESOLVE — validation + deterministic conflict resolution.
        resolution = self.resolver.resolve(snapshot, proposals)

        # COMMIT — the only place WorldState changes (I1).
        for t in resolution.committed:
            self._commit(t)

        # INDEX — journal + causal indexes; rejected transitions included.
        for t in sorted(proposals, key=lambda t: t.id or 0):
            self.journal.record(t)
            self.index.add(t)

        with self.state.unsealed():
            self.state.tick += 1

    def run(self, ticks: int) -> None:
        for _ in range(int(ticks)):
            self.step()

    # ------------------------------------------------------------------
    def _assign_ids(self, proposals: list[Transition]) -> None:
        for t in sorted(proposals, key=proposal_sort_key):
            t.id = self._next_id
            self._next_id += 1

    def _commit(self, t: Transition) -> None:
        with self.state.unsealed():
            for w in sorted(t.writes, key=lambda w: (w.entity, w.field)):
                self.state.set(w.entity, w.field, w.new, t.id)
        t.status = TransitionStatus.COMMITTED

    # ------------------------------------------------------------------
    # Read-only conveniences
    # ------------------------------------------------------------------
    def snapshot(self) -> Snapshot:
        return Snapshot.from_state(self.state)

    def fingerprint(self) -> dict:
        from causal_world import KERNEL_VERSION

        return {
            "seed": self.world_seed,
            "kernel_version": KERNEL_VERSION,
            "ruleset_version": self.rules.ruleset_version,
            "rng_version": self.rules.rng_version,
            "ticks": self.state.tick,
            "initial_state_hash": self.initial_state_hash,
            "final_state_hash": self.state.hash(),
        }


def create_world(
    seed: int,
    system_order: list[str] | None = None,
    ruleset: WorldRuleValidator | None = None,
    ticks: int = 0,
    regions: int = 2,
    agents: int = 10,
    persist: str | None = None,
) -> Simulation:
    """Build a fully deterministic world: seed + ruleset + initial state.

    ``persist``: path of a SQLite archive; when given, the journal and the
    causal index live on disk (for long/large runs) instead of in RAM.
    Scaling ``regions``/``agents`` never changes an existing entity's
    genesis attributes (addressable RNG, invariant I8).
    """
    from causal_world.systems.agents import AgentSystem
    from causal_world.systems.agriculture import AgricultureSystem
    from causal_world.systems.climate import ClimateSystem
    from causal_world.systems.diagnostic import (
        IronHealthAgentSystem,
        IronHealthDiseaseSystem,
        NoHungerDiseaseSystem,
        NoHungerErosionAgentSystem,
        StableSoilAgricultureSystem,
    )
    from causal_world.systems.disease import DiseaseSystem
    from causal_world.systems.food import (
        FallowAgricultureSystem,
        RotationAgricultureSystem,
        StorageAgricultureSystem,
    )
    from causal_world.systems.immune_disease import ImmuneDiseaseSystem
    from causal_world.world.generator import generate_genesis
    from causal_world.world.rules import DefaultWorldRules

    registry: dict[str, type[System]] = {
        "ClimateSystem": ClimateSystem,
        "AgricultureSystem": AgricultureSystem,
        "DiseaseSystem": DiseaseSystem,
        "ImmuneDiseaseSystem": ImmuneDiseaseSystem,
        "IronHealthDiseaseSystem": IronHealthDiseaseSystem,
        "IronHealthAgentSystem": IronHealthAgentSystem,
        "StableSoilAgricultureSystem": StableSoilAgricultureSystem,
        "NoHungerDiseaseSystem": NoHungerDiseaseSystem,
        "NoHungerErosionAgentSystem": NoHungerErosionAgentSystem,
        "FallowAgricultureSystem": FallowAgricultureSystem,
        "StorageAgricultureSystem": StorageAgricultureSystem,
        "RotationAgricultureSystem": RotationAgricultureSystem,
        "AgentSystem": AgentSystem,
    }
    default_order = [
        "ClimateSystem",
        "AgricultureSystem",
        "DiseaseSystem",
        "AgentSystem",
    ]
    # A ruleset may declare its own system roster (duck-typed); the kernel
    # does not know about it otherwise.
    names = system_order or getattr(ruleset, "default_systems", None) or default_order
    unknown = [n for n in names if n not in registry]
    if unknown:
        raise KeyError(f"unknown systems: {unknown}")

    rules = ruleset or DefaultWorldRules()
    purposes = PurposeRegistry()
    for purpose in sorted(rules.purposes):
        purposes.declare(purpose, rules.purposes[purpose])
    rng = RandomSource(seed, rules.rng_version, purposes)

    journal: Journal | None = None
    index: CausalIndex | None = None
    if persist is not None:
        from causal_world.simulation.archive import SqliteArchive

        archive = SqliteArchive(persist)
        journal = archive
        index = archive  # one SQLite file serves both roles
        # World identity travels with the archive.
        archive.set_meta("seed", seed)
        archive.set_meta("regions", regions)
        archive.set_meta("agents", agents)
        archive.set_meta("ruleset_version", rules.ruleset_version)
        archive.set_meta("rng_version", rules.rng_version)

    systems = [registry[name]() for name in names]
    simulation = Simulation(seed, systems, rules, rng, journal=journal, index=index)
    simulation.initialize(
        generate_genesis(rng, region_count=regions, agent_count=agents, rules=rules)
    )
    if ticks:
        simulation.run(ticks)
    return simulation
