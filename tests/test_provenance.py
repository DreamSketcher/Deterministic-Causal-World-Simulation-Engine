"""Provenance: reads carry snapshot provenance; same-tick isolation
(spec §5, §6, tests #4 and #5)."""

from __future__ import annotations

from causal_world.kernel.transition import StateRead, TransitionStatus
from causal_world.systems.base import System

from helpers import RulesForTest, make_sim


class SoilWriter(System):
    """Writes soil 0.6 -> 0.7 on the first tick."""

    name = "SoilWriter"

    def compute(self, snapshot, rng, context):
        b = context.builder("soil.write")
        soil = b.read("region:0", "soil")
        if soil < 0.7:
            b.write("region:0", "soil", 0.7)
            return [b.build()]
        return []


class SoilReader(System):
    name = "SoilReader"
    reads: list[StateRead] = []

    def compute(self, snapshot, rng, context):
        b = context.builder("soil.read.probe")
        b.read("region:0", "soil")
        SoilReader.reads.append(b.build().reads[0])
        return []


def test_read_source_is_the_writing_transition_spec39():
    SoilReader.reads = []
    rules = RulesForTest({"soil": float})
    sim = make_sim(
        rules,
        [SoilWriter(), SoilReader()],
        seed=0,
        genesis_fields={("region:0", "soil"): 0.6},
    )
    genesis_tid = sim.state.get_source("region:0", "soil")

    sim.step()  # SoilWriter commits 0.6 -> 0.7
    soil_writer_tid = sim.state.get_source("region:0", "soil")
    assert soil_writer_tid != genesis_tid

    sim.step()  # SoilReader now reads soil = 0.7
    last_read = SoilReader.reads[-1]
    assert last_read.value == 0.7
    assert last_read.source_transition == soil_writer_tid


class WorkersWriter(System):
    name = "WorkersWriter"

    def compute(self, snapshot, rng, context):
        b = context.builder("workers.write")
        current = b.read("region:0", "workers")
        if current == 10:
            b.write("region:0", "workers", 50)
            return [b.build()]
        return []


class WorkersReader(System):
    name = "WorkersReader"
    reads: list[StateRead] = []

    def compute(self, snapshot, rng, context):
        b = context.builder("workers.read.probe")
        b.read("region:0", "workers")
        WorkersReader.reads.append(b.build().reads[0])
        return []


def test_same_tick_provenance_spec40():
    """A and B share one snapshot: B must read workers = 10 and its source
    must be the PRE-snapshot writer (genesis), not A's same-tick write."""
    WorkersReader.reads = []
    rules = RulesForTest({"workers": int})
    sim = make_sim(
        rules,
        [WorkersWriter(), WorkersReader()],
        seed=0,
        genesis_fields={("region:0", "workers"): 10},
    )
    genesis_tid = sim.state.get_source("region:0", "workers")

    sim.step()

    read = WorkersReader.reads[-1]
    assert read.value == 10, "same-tick writes must be invisible"
    assert read.source_transition == genesis_tid, (
        "source must point to the pre-snapshot writer, not the same-tick one"
    )

    # After the tick, the new value is live and provenance moved to A.
    assert sim.state.get("region:0", "workers") == 50
    writer_tid = sim.state.get_source("region:0", "workers")
    assert writer_tid != genesis_tid
    assert sim.journal.by_id(writer_tid).system == "WorkersWriter"


def test_snapshot_get_source_matches_reads():
    SoilReader.reads = []
    rules = RulesForTest({"soil": float})
    sim = make_sim(
        rules,
        [SoilReader()],
        seed=0,
        genesis_fields={("region:0", "soil"): 0.6},
    )
    snap = sim.snapshot()
    sim.step()
    read = SoilReader.reads[-1]
    assert read.source_transition == snap.get_source("region:0", "soil")


def test_rejected_transitions_are_never_provenance_sources():
    from causal_world import create_world

    sim = create_world(seed=4, ticks=40)
    rejected_ids = {t.id for t in sim.journal.rejected()}
    assert rejected_ids, "this world must produce some rejected transitions"
    for t in sim.journal.committed():
        for r in t.reads:
            assert r.source_transition not in rejected_ids

    # Every live provenance source is a committed transition.
    for source in set(sim.state.provenance.values()):
        assert source is not None
        assert sim.journal.by_id(source).status is TransitionStatus.COMMITTED


def test_genesis_fields_have_provenance():
    from causal_world import create_world

    sim = create_world(seed=1)
    for (entity, field), source in sim.state.provenance.items():
        assert source is not None, f"{entity}.{field} lacks provenance"
        assert sim.journal.by_id(source).operation.startswith("genesis.")
